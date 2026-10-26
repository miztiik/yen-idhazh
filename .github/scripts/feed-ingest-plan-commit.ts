/** How do exact completed planner files append to main without changing the checkout? */
import { mkdtemp, readFile, realpath, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isAbsolute, join, relative, resolve } from "node:path";
import { createHash } from "node:crypto";
import { RawDayIndexSchema, RAW_DAY_INDEX_VERSION, PlannerLedgerNameSchema } from "../../packages/common-contracts/src/index";
import { plannerContracts } from "./feed-ingest-plan-verification";
import { readPlannerParquet } from "../../services/feed-ingest-plan/src/read-ledger-history/read-planner-parquet";
import type { LedgerRowContract } from "../../packages/ledger-file-writer/src/index";
function readRetry(input: unknown) {
  if (typeof input !== "object" || input === null || !("deadline_seconds" in input)
    || typeof input.deadline_seconds !== "object" || input.deadline_seconds === null) {
    throw new Error("push retry requires deadline_seconds.default");
  }
  function positive(value: unknown, name: string): number {
    if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) throw new Error(`push retry requires positive ${name}`);
    return value;
  }
  const deadline = positive("default" in input.deadline_seconds ? input.deadline_seconds.default : undefined, "deadline_seconds.default");
  const base = positive("base_step_seconds" in input ? input.base_step_seconds : undefined, "base_step_seconds");
  const ceiling = positive("ceiling_seconds" in input ? input.ceiling_seconds : undefined, "ceiling_seconds");
  const after = positive("ceiling_after" in input ? input.ceiling_after : undefined, "ceiling_after");
  if (!Number.isInteger(after) || base > ceiling) throw new Error("push retry has invalid backoff bounds");
  return { deadline, base, ceiling, after };
}

export async function commitPlannerFiles(input: Readonly<{
  repository: string; stateRoot: string; paths: readonly string[]; message: string; retry: unknown;
}>): Promise<{ status: "landed" | "already-on-main" | "no-changes"; commit: string | null; files: number }> {
  const retry = readRetry(input.retry);
  if (new Set(input.paths).size !== input.paths.length) throw new Error("commit: duplicate output paths");
  if (input.paths.length === 0) return { status: "no-changes", commit: null, files: 0 };
  const stateRoot = await realpath(input.stateRoot);
  const directory = await mkdtemp(join(tmpdir(), "planner-index-"));
  const deadline = performance.now() + retry.deadline * 1000;
  const env = {
    ...process.env, GIT_INDEX_FILE: join(directory, "index"), GIT_LITERAL_PATHSPECS: "1",
    GIT_AUTHOR_NAME: "miztiik", GIT_AUTHOR_EMAIL: "miztiik@users.noreply.github.com",
    GIT_COMMITTER_NAME: "miztiik", GIT_COMMITTER_EMAIL: "miztiik@users.noreply.github.com",
  };
  async function git(args: string[], bytes?: Uint8Array) {
    const remaining = Math.floor(deadline - performance.now());
    if (remaining <= 0) throw new Error("commit: retry deadline exhausted; completed artifacts retained");
    const child = Bun.spawn(["git", ...args], {
      cwd: input.repository, env, stdout: "pipe", stderr: "pipe", timeout: remaining,
      stdin: bytes === undefined ? "ignore" : "pipe",
    });
    if (bytes !== undefined) {
      if (child.stdin == null) throw new Error("commit: Git input pipe is unavailable");
      child.stdin.write(bytes);
      child.stdin.end();
    }
    const [stdout, stderr, code] = await Promise.all([
      new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
    ]);
    return { stdout: stdout.trim(), stderr, code };
  }
  async function required(args: string[], bytes?: Uint8Array) {
    const result = await git(args, bytes);
    if (result.code !== 0) throw new Error(`commit: git ${args[0]} failed; completed artifacts retained`);
    return result.stdout;
  }
  try {
    const writes = [];
    for (const path of input.paths) {
      if (!/^raw\/feed-ingest-plan\/(discovered-articles|selected-articles|feed-health-state|plan-runs)\/\d{4}\/\d{2}\/\d{2}\/[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.parquet$/.test(path)) {
        throw new Error("commit: expected one exact current planner raw UUID Parquet path");
      }
      const file = await realpath(resolve(stateRoot, ...path.split("/")));
      const local = relative(stateRoot, file);
      if (isAbsolute(local) || local === ".." || local.startsWith(`..\\`) || local.startsWith("../")) {
        throw new Error("commit: output escapes state root");
      }
      const pieces = path.split("/");
      const ledger = PlannerLedgerNameSchema.parse(pieces[2]);
      const contract: LedgerRowContract<object> = plannerContracts[ledger];
      const checked = await readPlannerParquet(file, ledger, contract);
      const bytes = await readFile(file);
      if (createHash("sha256").update(bytes).digest("hex") !== checked.file_sha256) throw new Error("commit: validated output changed before hashing");
      const blob = await required(["hash-object", "-w", "--stdin"], bytes);
      writes.push({ path: `state/${path}`, blob, bytes: bytes.byteLength });
    }
    let failures = 0;
    while (performance.now() < deadline) {
      await required(["fetch", "--no-tags", "origin", "refs/heads/main"]);
      const base = await required(["rev-parse", "FETCH_HEAD"]);
      await required(["read-tree", base]);
      let changed = false;
      for (const write of writes) {
        const held = await required(["ls-tree", base, "--", write.path]);
        if (held !== "") {
          if (held !== `100644 blob ${write.blob}\t${write.path}`) {
            throw new Error(`commit: immutable output collision at ${write.path}; artifacts retained`);
          }
        } else {
          changed = true;
          await required(["update-index", "--add", "--cacheinfo", `100644,${write.blob},${write.path}`]);
        }
      }

      const dayFolders = [...new Set(writes.map(write => write.path.slice(0, write.path.lastIndexOf("/"))))];
      for (const directory of dayFolders) {
        const members = new Map<string, number>();
        if (await required(["ls-tree", base, "--", directory]) !== "") {
          const listing = await required(["ls-tree", "-l", `${base}:${directory}`]);
          for (const line of listing.split("\n").filter(Boolean)) {
            const match = /^100644 blob [0-9a-f]{40}\s+(\d+)\t(.+)$/.exec(line);
            if (match === null) throw new Error("commit: raw day contains a non-file entry");
            if (match[2] === "index.json") continue;
            if (!/^[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.parquet$/.test(match[2]!)) {
              throw new Error("commit: raw day contains an undeclared member");
            }
            members.set(match[2]!, Number(match[1]));
          }
        }
        for (const write of writes.filter(write => write.path.startsWith(`${directory}/`))) {
          members.set(write.path.slice(directory.length + 1), write.bytes);
        }
        const names = [...members.keys()].sort();
        const parts = directory.split("/");
        const day = parts.slice(-3).join("-");
        const index = RawDayIndexSchema.parse({
          version: RAW_DAY_INDEX_VERSION, ledger: parts[3], date: day,
          files: names, bytes: names.map(name => members.get(name)!),
          content_sha256: createHash("sha256").update(names.join("\n")).digest("hex"),
          listed_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
        });
        const indexPath = `${directory}/index.json`;
        const existing = await required(["ls-tree", base, "--", indexPath]);
        if (existing !== "") {
          const previous = RawDayIndexSchema.parse(JSON.parse(await required(["show", `${base}:${indexPath}`])));
          if (previous.ledger !== index.ledger || previous.date !== day) throw new Error("commit: raw index identity differs");
          if (JSON.stringify(previous.files) === JSON.stringify(index.files)
            && JSON.stringify(previous.bytes) === JSON.stringify(index.bytes)
            && previous.content_sha256 === index.content_sha256) continue;
        }
        const blob = await required(["hash-object", "-w", "--stdin"], new TextEncoder().encode(`${JSON.stringify(index)}\n`));
        await required(["update-index", "--add", "--cacheinfo", `100644,${blob},${indexPath}`]);
        changed = true;
      }
      if (!changed) return { status: "already-on-main", commit: base, files: writes.length };
      const tree = await required(["write-tree"]);
      const commit = await required(["commit-tree", tree, "-p", base, "-m", input.message]);
      const pushed = await git(["push", "--no-thin", "origin", `${commit}:refs/heads/main`]);
      if (pushed.code === 0) return { status: "landed", commit, files: writes.length };
      failures++;
      console.error(JSON.stringify({ event: "PLANNER_COMMIT_RETRY", failed_pushes: failures }));
      const backoff = Math.min(retry.base * 2 ** Math.min(failures - 1, retry.after), retry.ceiling) * 1000;
      await Bun.sleep(Math.min(backoff, Math.max(0, deadline - performance.now())));
    }
    throw new Error("commit: retry deadline exhausted; completed artifacts retained");
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

if (import.meta.main) {
  const { RUNNER_TEMP, CURRENT_RUN_FILES } = process.env;
  if (!RUNNER_TEMP || !CURRENT_RUN_FILES) throw new Error("Commit requires exact planner output paths");
  const paths: unknown = JSON.parse(CURRENT_RUN_FILES);
  if (!Array.isArray(paths) || paths.some(path => typeof path !== "string")) throw new Error("Commit output list is invalid");
  const root = join(RUNNER_TEMP, "feed-ingest-plan");
  try {
    const result = await commitPlannerFiles({
      repository: process.cwd(), stateRoot: join(root, "state"), paths,
      message: "Record feed planner outcomes", retry: await Bun.file("config/push-retry.json").json(),
    });
    await writeFile(join(root, "commit-result.json"), JSON.stringify(result));
    console.log(JSON.stringify(result));
  } catch (error) {
    const result = { status: "failed", commit: null, files: paths.length };
    await writeFile(join(root, "commit-result.json"), JSON.stringify(result));
    console.error(JSON.stringify({ event: "planner_metadata_commit_failed", ...result,
      code: error instanceof Error ? error.name : "UnknownError",
      reason: error instanceof Error ? error.message.replaceAll(root, "feed-ingest-plan")
        .replaceAll(process.cwd(), ".").replaceAll("\\", "/") : "Unknown commit failure" }));
    process.exitCode = 2;
  }
}
