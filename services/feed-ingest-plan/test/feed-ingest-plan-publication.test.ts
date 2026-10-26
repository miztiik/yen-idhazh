/** Do host and planner bytes publish together without host indexes or damage to caller Git state? */
import { expect, test } from "bun:test";
import { copyFile, mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { RawDayIndexSchema, PlanRunRowContract } from "../../../packages/common-contracts/src/index";
import { persistLedger } from "../../../packages/ledger-file-writer/src/index";
import { commitPlannerFiles } from "../scripts/feed-ingest-plan-commit";
import { MetadataCommitResultSchema } from "../scripts/feed-ingest-plan-commit-result";
import { collectWorkflowFiles } from "../scripts/feed-ingest-plan-current-files";
import { prepareWorkflowArtifacts } from "../scripts/feed-ingest-plan-artifacts";
import { verifyMetadataFile } from "../scripts/feed-ingest-plan-metadata";
import { readPlannerDay } from "../src/read-ledger-history/read-planner-history";
import { fixtureGit, publicationRecording } from "./publication-recordings";

async function readOrigin(f: Awaited<ReturnType<typeof publicationRecording>>, args: string[]) {
  return fixtureGit(f.repository, ["--git-dir", f.origin, ...args]);
}
async function invokeCommit(f: Awaited<ReturnType<typeof publicationRecording>>, extra: Record<string, string> = {}) {
  const child = Bun.spawn([process.execPath, fileURLToPath(new URL("../scripts/feed-ingest-plan-commit.ts", import.meta.url))], {
    cwd: f.repository, stdout: "pipe", stderr: "pipe", env: {
      ...Bun.env, RUNNER_TEMP: dirname(f.directory), CURRENT_RUN_FILES: JSON.stringify(f.paths),
      GITHUB_RUN_ID: "700", GITHUB_RUN_ATTEMPT: "1", ...extra,
    },
  });
  const [output, errors, code] = await Promise.all([
    new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
  ]);
  return { output, errors, code };
}

test("real planner and HTTP host files land together, keep four named indexes, and replay without a commit", async () => {
  const f = await publicationRecording();
  try {
    const completed = await collectWorkflowFiles({
      root: f.repository, directory: f.directory, identity: f.commit.identity, registrations: f.commit.registrations,
    });
    expect(completed.failures).toEqual([]);
    expect(completed.paths).toEqual(f.paths);
    expect(new Set(f.plannerPaths.map(path => path.split("/")[2])).size).toBe(4);
    const before = await Promise.all(f.paths.map(path => readFile(join(f.commit.stateRoot, path))));
    const result = await commitPlannerFiles(f.commit);
    expect(result).toMatchObject({ status: "landed", files: f.paths.length, paths: f.paths });
    const tip = await readOrigin(f, ["rev-parse", "main"]);
    expect(result.commit).toBe(tip);
    expect(await readOrigin(f, ["rev-parse", `${tip}^`])).toBe(f.head);
    expect(await fixtureGit(f.repository, ["rev-parse", "HEAD"])).toBe(f.head);
    const changed = (await readOrigin(f, ["diff-tree", "--no-commit-id", "--name-only", "-r", f.head, tip])).split("\n");
    const indexes = [...new Set(f.plannerPaths.map(path => `state/${dirname(path).replaceAll("\\", "/")}/index.json`))];
    expect(indexes).toHaveLength(4);
    expect(changed.sort()).toEqual([...f.paths.map(path => `state/${path}`), ...indexes].sort());
    const hostIndex = `state/${dirname(f.host.response.files[0]!.path).replaceAll("\\", "/")}/index.json`;
    expect(await readOrigin(f, ["ls-tree", tip, "--", hostIndex])).toBe("");
    for (const path of indexes) {
      const index = RawDayIndexSchema.parse(JSON.parse(await readOrigin(f, ["show", `${tip}:${path}`])));
      expect(index.files).toHaveLength(1);
      expect(index.bytes?.[0]).toBeGreaterThan(0);
    }
    await fixtureGit(f.repository, ["fetch", "origin", "main"]);
    const reader = join(dirname(f.directory), "reader");
    await fixtureGit(f.repository, ["clone", "--quiet", f.origin, reader]);
    const loaded = await readPlannerDay(reader, f.commit.registrations["plan-runs"], {
      day: f.summary.date, raw_index: `state/raw/feed-ingest-plan/plan-runs/${f.summary.date.replaceAll("-", "/")}/index.json`,
    }, PlanRunRowContract);
    expect(loaded.complete).toBe(true);
    expect(loaded.rows[0]).toMatchObject({ run_id: f.summary.run_id, attempt: f.summary.attempt });
    const replay = await commitPlannerFiles(f.commit);
    expect(replay.status).toBe("already-on-main");
    expect(replay.commit).toBe(tip);
    expect(await readOrigin(f, ["rev-parse", "main"])).toBe(tip);
    for (const [index, path] of f.paths.entries()) expect(await readFile(join(f.commit.stateRoot, path))).toEqual(before[index]!);
  } finally { await f.close(); }
});

test("private publication preserves sparse patterns, the real index and a supplied foreign index", async () => {
  const f = await publicationRecording();
  try {
    await fixtureGit(f.repository, ["sparse-checkout", "set", "--no-cone", "/README.md", "/config/"]);
    await writeFile(join(f.repository, "README.md"), "Unrelated staged caller work.\n");
    await fixtureGit(f.repository, ["add", "--", "README.md"]);
    const realIndex = join(f.repository, ".git", "index");
    const foreignIndex = join(dirname(f.directory), "foreign-index");
    await copyFile(realIndex, foreignIndex);
    const sparse = join(f.repository, ".git", "info", "sparse-checkout");
    const [indexBefore, foreignBefore, sparseBefore] = await Promise.all([
      readFile(realIndex), readFile(foreignIndex), readFile(sparse),
    ]);
    const result = await invokeCommit(f, { GIT_INDEX_FILE: foreignIndex });
    expect({ code: result.code, errors: result.errors }).toEqual({ code: 0, errors: "" });
    expect(MetadataCommitResultSchema.parse(JSON.parse(result.output)).status).toBe("landed");
    expect(await readFile(realIndex)).toEqual(indexBefore);
    expect(await readFile(foreignIndex)).toEqual(foreignBefore);
    expect(await readFile(sparse)).toEqual(sparseBefore);
    expect(await fixtureGit(f.repository, ["rev-parse", "HEAD"])).toBe(f.head);
    expect(await readOrigin(f, ["show", "main:README.md"])).toBe("Generated publication fixture.");
  } finally { await f.close(); }
});

test("a real rejected push rebuilds only planner day indexes on the new parent without rerunning producers", async () => {
  const f = await publicationRecording();
  try {
    const concurrent = join(dirname(f.directory), "concurrent");
    await fixtureGit(f.repository, ["clone", "--quiet", f.origin, concurrent]);
    const previous = PlanRunRowContract.schema.parse(Object.fromEntries(Object.keys(PlanRunRowContract.schema.shape)
      .map(key => [key, key === "attempt" ? 2 : f.summary[key as keyof typeof f.summary]])));
    const recorded = await persistLedger({
      ledger: "plan-runs", rowContract: PlanRunRowContract, outputRoot: join(concurrent, "state"),
      registryEntry: f.commit.registrations["plan-runs"], ledgerSettings: f.inputs.ledgerSettings,
      period: { tier: "raw", covers: previous.date }, rows: [previous],
    });
    if (recorded.status !== "written") throw new Error("The concurrent native run must persist");
    const priorPath = recorded.files[0]!.path;
    const unrelated = "state/raw/host-fingerprint/2026/10/20/unrelated.txt";
    await mkdir(dirname(join(concurrent, unrelated)), { recursive: true });
    await writeFile(join(concurrent, unrelated), "Do not scan accumulated host directories.\n");
    await fixtureGit(concurrent, ["add", "--", `state/${priorPath}`, unrelated]);
    await fixtureGit(concurrent, ["commit", "-m", "Record concurrent native metadata"]);
    const moved = await fixtureGit(concurrent, ["rev-parse", "HEAD"]);
    await fixtureGit(concurrent, ["push", "origin", "HEAD:refs/heads/prepared-concurrent"]);
    const hook = join(f.repository, ".git", "hooks", "pre-push");
    await writeFile(hook, [
      "#!/bin/sh", "set -eu",
      `if test ! -f '${hook.replaceAll("\\", "/")}.used'; then`,
      `  git --git-dir='${f.origin.replaceAll("\\", "/")}' update-ref refs/heads/main '${moved}' '${f.head}'`,
      `  touch '${hook.replaceAll("\\", "/")}.used'`, "fi", "",
    ].join("\n"), { mode: 0o755 });
    const before = await Promise.all(f.paths.map(path => readFile(join(f.commit.stateRoot, path))));
    const committed = await commitPlannerFiles(f.commit);
    expect(committed.status).toBe("landed");
    expect(await readOrigin(f, ["rev-parse", `${committed.commit}^`])).toBe(moved);
    expect(await stat(`${hook}.used`)).toBeDefined();
    const day = dirname(priorPath).replaceAll("\\", "/");
    const index = RawDayIndexSchema.parse(JSON.parse(await readOrigin(f, ["show", `main:state/${day}/index.json`])));
    expect(index.files).toEqual([priorPath.split("/").at(-1)!, f.plannerPaths.find(path => path.includes("/plan-runs/"))!.split("/").at(-1)!].sort());
    expect(await readOrigin(f, ["show", `main:${unrelated}`])).toContain("Do not scan");
    expect(await readOrigin(f, ["ls-tree", "main", "--", "state/raw/host-fingerprint/2026/10/21/index.json"])).toBe("");
    for (const [index, path] of f.paths.entries()) expect(await readFile(join(f.commit.stateRoot, path))).toEqual(before[index]!);
  } finally { await f.close(); }
});

test("immutable host collisions refuse publication and retain all valid completed files for recovery", async () => {
  const f = await publicationRecording();
  try {
    const other = join(dirname(f.directory), "collision");
    await fixtureGit(f.repository, ["clone", "--quiet", f.origin, other]);
    const target = `state/${f.host.response.files[0]!.path}`;
    await mkdir(dirname(join(other, target)), { recursive: true });
    await writeFile(join(other, target), "Conflicting immutable bytes");
    await fixtureGit(other, ["add", "--", target]);
    await fixtureGit(other, ["commit", "-m", "Create generated immutable collision"]);
    await fixtureGit(other, ["push", "origin", "HEAD:refs/heads/main"]);
    const tip = await readOrigin(f, ["rev-parse", "main"]);
    const result = await invokeCommit(f);
    expect(result.code).toBe(2);
    expect(result.output).toBe("");
    expect(JSON.parse(result.errors).reason).toContain("immutable output collision");
    expect(await readOrigin(f, ["rev-parse", "main"])).toBe(tip);
    const artifacts = await prepareWorkflowArtifacts({ root: f.repository, directory: f.directory, runNumber: "700", attempt: 1 });
    const recovery = join(f.directory, artifacts.metadata_recovery!);
    expect(await Bun.file(join(recovery, "current-run-files.json")).json()).toEqual(f.paths);
    for (const path of f.paths) expect(await readFile(join(recovery, path))).toEqual(await readFile(join(f.commit.stateRoot, path)));
    expect(await Bun.file(join(recovery, "response.json")).exists()).toBe(false);
    expect(await Bun.file(join(recovery, "index.json")).exists()).toBe(false);
  } finally { await f.close(); }
});

test("completed diagnostics may land while real planner persistence remains failed", async () => {
  const f = await publicationRecording(true);
  try {
    expect(f.summary.planning_complete).toBe(false);
    expect(f.summary.status).not.toBe("completed");
    const before = JSON.stringify(f.summary);
    const committed = await commitPlannerFiles(f.commit);
    expect(committed.status).toBe("landed");
    expect(f.summary.planning_complete).toBe(false);
    expect(JSON.stringify(f.summary)).toBe(before);
    expect(await verifyMetadataFile(f.commit.stateRoot, f.host.response.files[0]!.path, f.commit.registrations,
      f.commit.identity)).toMatchObject({ ledger: "host-fingerprint", row_count: 1 });
    await expect(commitPlannerFiles({ ...f.commit, paths: ["raw/item-health/2026/10/21/anything.parquet"] })).rejects.toThrow("exact current");
    const already = await commitPlannerFiles(f.commit);
    expect(already.status).toBe("already-on-main");
  } finally { await f.close(); }
});
