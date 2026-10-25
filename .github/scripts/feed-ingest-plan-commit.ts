/** How do exact completed planner files append to main without changing the checkout? */
import { mkdtemp, realpath, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isAbsolute, join, relative, resolve } from "node:path";
import { createHash } from "node:crypto";
import { RAW_DAY_INDEX_VERSION, RawDayIndexSchema } from "../../packages/common-contracts/src/index";
import { DateStampSchema } from "../../packages/common-contracts/src/index";

export type PreparedPlannerState = Readonly<{
  status: "written" | "not_written";
  reason: string;
  files: readonly Readonly<{ path: string; bytes: Uint8Array }>[];
}>;
function utcSecond(value: string): string {
  const milliseconds = Date.parse(value);
  if (!value.endsWith("Z") || !Number.isFinite(milliseconds)) throw new Error("commit: fresh-base clock must return a UTC instant");
  return new Date(milliseconds).toISOString().replace(/\.\d{3}Z$/, "Z");
}

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
  repository: string; stateRoot: string; paths: readonly string[]; message: string; retry: unknown; now: string;
  clock?: () => string;
  prepare_fresh_base?: (input: Readonly<{
    base: string; now: string; read_file: (path: string) => Promise<Uint8Array | undefined>;
  }>) => Promise<PreparedPlannerState>;
}>): Promise<{
  status: "landed" | "already-on-main" | "no-changes"; commit: string | null; files: number;
  derived_state: Readonly<{ status: "not_requested" } | Pick<PreparedPlannerState, "status" | "reason">>;
  derived_state_files: readonly string[]; raw_index_files: readonly string[];
  committed_files: readonly Readonly<{ path: string; git_blob: string }>[];
}> {
  const retry = readRetry(input.retry);
  if (new Set(input.paths).size !== input.paths.length) throw new Error("commit: duplicate output paths");
  if (input.paths.length === 0 && input.prepare_fresh_base === undefined) {
    return { status: "no-changes", commit: null, files: 0, derived_state: { status: "not_requested" },
      derived_state_files: [], raw_index_files: [], committed_files: [] };
  }
  DateStampSchema.parse(input.now.slice(0, 10));
  if (!Number.isFinite(Date.parse(input.now)) || !input.now.endsWith("Z")) {
    throw new Error("commit: now must be a captured UTC instant");
  }
  const stateRoot = await realpath(input.stateRoot);
  const directory = await mkdtemp(join(tmpdir(), "planner-index-"));
  const deadline = performance.now() + retry.deadline * 1000;
  const env = {
    ...process.env, GIT_INDEX_FILE: join(directory, "index"), GIT_LITERAL_PATHSPECS: "1",
    GIT_AUTHOR_NAME: "miztiik", GIT_AUTHOR_EMAIL: "miztiik@users.noreply.github.com",
    GIT_COMMITTER_NAME: "miztiik", GIT_COMMITTER_EMAIL: "miztiik@users.noreply.github.com",
  };
  async function git(args: string[]) {
    const remaining = Math.floor(deadline - performance.now());
    if (remaining <= 0) throw new Error("commit: retry deadline exhausted; completed artifacts retained");
    const child = Bun.spawn(["git", ...args], {
      cwd: input.repository, env, stdout: "pipe", stderr: "pipe", timeout: remaining,
    });
    const [stdout, stderr, code] = await Promise.all([
      new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
    ]);
    return { stdout: stdout.trim(), stderr, code };
  }
  async function required(args: string[]) {
    const result = await git(args);
    if (result.code !== 0) {
      const diagnostic = [result.stderr, result.stdout].map(value => value.trim()).filter(Boolean).join("; ");
      throw new Error(`commit: git ${args[0]} exited ${result.code}${diagnostic === "" ? "" : `: ${diagnostic}`}; completed artifacts retained`);
    }
    return result.stdout;
  }
  async function readBaseFile(base: string, path: string): Promise<Uint8Array | undefined> {
    const entry = await required(["ls-tree", base, "--", path]);
    if (entry === "") return undefined;
    if (!/^100644 blob [a-f0-9]+\t/.test(entry)) throw new Error(`commit: named base input is not a file at ${path}`);
    const remaining = Math.floor(deadline - performance.now());
    if (remaining <= 0) throw new Error("commit: retry deadline exhausted; completed artifacts retained");
    const child = Bun.spawn(["git", "show", `${base}:${path}`], {
      cwd: input.repository, env, stdout: "pipe", stderr: "pipe", timeout: remaining,
    });
    const [stdout, stderr, code] = await Promise.all([
      new Response(child.stdout).arrayBuffer(), new Response(child.stderr).text(), child.exited,
    ]);
    if (code !== 0) throw new Error(`commit: cannot read named base input ${path}: ${stderr}`);
    return new Uint8Array(stdout);
  }
  try {
    const writes: { path: string; blob: string }[] = [];
    for (const path of input.paths) {
      if (!/^raw\/(?:[a-z0-9-]+\/)+\d{4}\/\d{2}\/\d{2}\/[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.parquet$/.test(path)) {
        throw new Error("commit: expected an exact raw UUID Parquet output path");
      }
      const file = await realpath(resolve(stateRoot, ...path.split("/")));
      const local = relative(stateRoot, file);
      if (isAbsolute(local) || local === ".." || local.startsWith(`..\\`) || local.startsWith("../")) {
        throw new Error("commit: output escapes state root");
      }
      const blob = await required(["hash-object", "-w", "--no-filters", file]);
      writes.push({ path: `state/${path}`, blob });
    }
    let failures = 0;
    while (performance.now() < deadline) {
      await required(["fetch", "--no-tags", "origin", "refs/heads/main"]);
      const base = await required(["rev-parse", "FETCH_HEAD"]);
      const baseNow = input.prepare_fresh_base === undefined ? input.now
        : utcSecond(input.clock?.() ?? new Date(Date.now()).toISOString());
      const effectiveNow = Date.parse(baseNow) < Date.parse(utcSecond(input.now)) ? utcSecond(input.now) : baseNow;
      const prepared = input.prepare_fresh_base === undefined ? { status: "not_written" as const, reason: "not_requested", files: [] }
        : await input.prepare_fresh_base({ base, now: effectiveNow, read_file: path => readBaseFile(base, path) });
      if ((prepared.status === "written") !== (prepared.files.length > 0)) {
        throw new Error("commit: prepared state status differs from its exact file set");
      }
      const iterationWrites = [...writes];
      const indexWrites: { path: string; blob: string }[] = [];
      for (const file of prepared.files) {
        if (!/^raw\/(?:[a-z0-9-]+\/)+\d{4}\/\d{2}\/\d{2}\/[0-9a-f]{8}-[0-9a-f]{4}-8[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.parquet$/.test(file.path)) {
          throw new Error("commit: prepared output must be an exact raw UUID Parquet path");
        }
        const preparedPath = join(directory, `${createHash("sha256").update(file.path).digest("hex")}.parquet`);
        await writeFile(preparedPath, file.bytes);
        iterationWrites.push({ path: `state/${file.path}`, blob: await required(["hash-object", "-w", "--no-filters", preparedPath]) });
      }
      if (new Set(iterationWrites.map(write => write.path)).size !== iterationWrites.length) {
        throw new Error("commit: prepared output repeats an immutable path");
      }
      const groups = new Map<string, { ledger: string; date: string; names: string[] }>();
      for (const write of iterationWrites) {
        const parts = write.path.split("/");
        const dateParts = parts.slice(-4, -1);
        const date = dateParts.join("-");
        const prefix = parts.slice(2, -4);
        if (prefix.length === 0 || !/^\d{4}\/\d{2}\/\d{2}$/.test(dateParts.join("/"))) {
          throw new Error("commit: raw output path lacks its registered UTC partition");
        }
        const ledger = prefix.at(-1)!;
        const indexPath = `state/raw/${prefix.join("/")}/${dateParts.join("/")}/index.json`;
        const group = groups.get(indexPath) ?? { ledger, date, names: [] };
        if (group.ledger !== ledger || group.date !== date) throw new Error("commit: raw index group identity differs");
        group.names.push(parts.at(-1)!);
        groups.set(indexPath, group);
      }
      await required(["read-tree", base]);
      let changed = false;
      for (const write of iterationWrites) {
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
      for (const [indexPath, group] of groups) {
        const listed = await required(["ls-tree", base, "--", indexPath]);
        let existing: { files: string[] } = { files: [] };
        let existingBytes: Map<string, number> | null = null;
        if (listed !== "") {
          if (!/^100644 blob [a-f0-9]+\t/.test(listed)) throw new Error(`commit: raw index is not a file at ${indexPath}`);
          const text = await required(["show", `${base}:${indexPath}`]);
          const parsed = RawDayIndexSchema.parse(JSON.parse(text));
          if (parsed.ledger !== group.ledger || parsed.date !== group.date) {
            throw new Error(`commit: raw index identity differs at ${indexPath}`);
          }
          existing = { files: [...parsed.files] };
          if (parsed.bytes !== null) {
            existingBytes = new Map(parsed.files.map((name, index) => [name, parsed.bytes![index]!]));
          }
        }
        const names = [...new Set([...existing.files, ...group.names])].sort();
        let bytes: number[] | null = existingBytes === null && listed !== "" ? null : [];
        if (bytes !== null) for (const name of names) {
          const priorSize = existingBytes?.get(name);
          if (priorSize !== undefined) {
            bytes.push(priorSize);
            continue;
          }
          const write = iterationWrites.find(item => item.path.endsWith(`/${name}`));
          if (write === undefined) throw new Error(`commit: raw index has no byte source for ${name}`);
          const size = Number(await required(["cat-file", "-s", write.blob]));
          if (!Number.isSafeInteger(size) || size < 0) throw new Error(`commit: invalid raw file size for ${name}`);
          bytes.push(size);
        }
        const index = RawDayIndexSchema.parse({
          version: RAW_DAY_INDEX_VERSION, ledger: group.ledger, date: group.date,
          files: names, content_sha256: createHash("sha256").update(names.join("\n"), "utf8").digest("hex"),
          bytes, listed_at: effectiveNow,
        });
        const indexFile = join(directory, `${createHash("sha256").update(indexPath).digest("hex")}.json`);
        await writeFile(indexFile, JSON.stringify(index));
        const blob = await required(["hash-object", "-w", "--no-filters", indexFile]);
        const prior = await required(["ls-tree", base, "--", indexPath]);
        if (prior === `100644 blob ${blob}\t${indexPath}`) continue;
        await required(["update-index", "--add", "--cacheinfo", `100644,${blob},${indexPath}`]);
        indexWrites.push({ path: indexPath, blob });
        changed = true;
      }
      const derivedState = input.prepare_fresh_base === undefined
        ? { status: "not_requested" as const } : { status: prepared.status, reason: prepared.reason };
      const derivedStateFiles = prepared.files.map(file => file.path);
      const rawIndexFiles = [...groups.keys()].map(path => path.slice("state/".length));
      const committedFiles = [...iterationWrites, ...indexWrites].map(write => ({
        path: write.path.slice("state/".length), git_blob: write.blob,
      }));
      if (!changed) return { status: "already-on-main", commit: base, files: iterationWrites.length,
        derived_state: derivedState, derived_state_files: derivedStateFiles, raw_index_files: rawIndexFiles,
        committed_files: committedFiles };
      const tree = await required(["write-tree"]);
      const commit = await required(["commit-tree", tree, "-p", base, "-m", input.message]);
      const pushed = await git(["push", "--no-thin", "origin", `${commit}:refs/heads/main`]);
      if (pushed.code === 0) return { status: "landed", commit, files: iterationWrites.length,
        derived_state: derivedState, derived_state_files: derivedStateFiles, raw_index_files: rawIndexFiles,
        committed_files: committedFiles };
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
