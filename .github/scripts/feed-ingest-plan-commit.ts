/** How do exact completed planner files append to main without changing the checkout? */
import { mkdtemp, realpath, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { isAbsolute, join, relative, resolve } from "node:path";
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
    if (result.code !== 0) throw new Error(`commit: git ${args[0]} failed; completed artifacts retained`);
    return result.stdout;
  }
  try {
    const writes = [];
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
