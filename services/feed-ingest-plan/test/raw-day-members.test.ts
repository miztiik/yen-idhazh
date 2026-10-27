/** Prove exact-day Git membership, complete staging and native integrity on real Parquet bytes. */
import { expect, test } from "bun:test";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { DiscoveredArticleRowContract, PlanRunRowContract } from "@idhazh/common-contracts";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { fixtureGit } from "./publication-recordings";
import { registration, writeRows } from "./partition-fixtures";
import { fixedHistoryRevision, listExactRawDayMembers, readNamedGitFile } from "../src/read-ledger-history/raw-day-members";
import { readPlannerDay } from "../src/read-ledger-history/read-planner-history";
import { stageNamedFiles, stagePlannerHistory } from "../scripts/feed-ingest-plan-history";
import { PlannerDayInputSchema } from "../src/config/service-settings";
import { loadPlanInputs } from "../src/load-plan-inputs";

test("one revision proves absent days, every sibling and sparse staging without raw indexes", async () => {
  const root = await mkdtemp(join(tmpdir(), "planner-named-git-day-"));
  const day = "2026-10-20";
  const entry = registration("plan-runs");
  expect(PlannerDayInputSchema.safeParse({ day, raw_index: "old/index.json" }).success).toBe(false);
  expect(PlannerDayInputSchema.safeParse({ day, raw_files: [] }).success).toBe(false);
  try {
    await fixtureGit(root, ["init", "--initial-branch=main"]);
    await writeFile(join(root, "README.md"), "Bounded generated repository.\n");
    const outputs = [];
    for (const attempt of [1, 2]) {
      const row = PlanRunRowContract.schema.parse(plannerRecordings(day, attempt).find(value => value.name === "plan-runs")!.row);
      outputs.push(await writeRows(join(root, "state"), "plan-runs", day, PlanRunRowContract, [row]));
    }
    const paths = outputs.flatMap(output => output.files.map(file => `state/${file.path}`)).sort();
    const discoveryRow = DiscoveredArticleRowContract.schema.parse(plannerRecordings(day)
      .find(value => value.name === "discovered-articles")!.row);
    const discovery = await writeRows(join(root, "state"), "discovered-articles", day, DiscoveredArticleRowContract, [discoveryRow]);
    const discoveryPaths = discovery.files.map(file => `state/${file.path}`);
    const inertIndex = `${dirname(paths[0]!).replaceAll("\\", "/")}/index.json`;
    await writeFile(join(root, inertIndex), "obsolete invalid JSON");
    const emptyIndex = "state/raw/feed-ingest-plan/plan-runs/2026/10/18/index.json";
    await mkdir(dirname(join(root, emptyIndex)), { recursive: true });
    await writeFile(join(root, emptyIndex), "unused");
    await fixtureGit(root, ["add", "--", "README.md", inertIndex, emptyIndex, ...paths, ...discoveryPaths]);
    await fixtureGit(root, ["commit", "-m", "Record two immutable native siblings"]);
    const revision = await fixedHistoryRevision(root);
    expect(await readNamedGitFile(root, "untracked.json", revision)).toBeUndefined();
    await writeFile(join(root, "untracked.json"), "{}");
    await expect(readNamedGitFile(root, "untracked.json", revision)).rejects.toThrow("Uncommitted");
    expect(await listExactRawDayMembers(root, entry, "2026-10-19", revision))
      .toEqual({ present: false, members: [] });
    expect(await listExactRawDayMembers(root, entry, "2026-10-18", revision))
      .toEqual({ present: true, members: [] });
    const members = await listExactRawDayMembers(root, entry, day, revision);
    expect(members.present).toBe(true);
    expect(members.members.map(member => member.path).sort()).toEqual(paths);
    const complete = await readPlannerDay(root, entry, { day, raw_revision: revision }, PlanRunRowContract);
    expect(complete).toMatchObject({ complete: true, represented: true });
    expect(complete.rows.map(row => row.attempt).sort()).toEqual([1, 2]);
    const missing = await readPlannerDay(root, entry, { day: "2026-10-19", raw_revision: revision }, PlanRunRowContract);
    expect(missing).toMatchObject({ complete: true, represented: false, rows: [], gaps: [] });
    const incomplete = await readPlannerDay(root, entry, {
      day, raw_revision: revision, raw_files: paths.slice(0, 1),
    }, PlanRunRowContract);
    expect(incomplete.complete).toBe(false);
    expect(incomplete.rows).toEqual([]);
    await expect(listExactRawDayMembers(root, entry, day, "0".repeat(40))).rejects.toThrow("Git");
    const failed = await readPlannerDay(root, entry, { day, raw_revision: "0".repeat(40) }, PlanRunRowContract);
    expect(failed.complete).toBe(false);
    expect(failed.gaps.length).toBeGreaterThan(0);
    await expect(listExactRawDayMembers(root, { ...entry, prefix: [".."] }, day, revision)).rejects.toThrow("registered");
    await expect(listExactRawDayMembers(root, entry, "2026-02-30", revision)).rejects.toThrow("UTC day");
    const original = await readFile(join(root, paths[0]!));
    await writeFile(join(root, paths[0]!), "different bytes at the same UUID");
    expect((await readPlannerDay(root, entry, { day, raw_revision: revision }, PlanRunRowContract)).complete).toBe(false);
    await writeFile(join(root, paths[0]!), original);
    await fixtureGit(root, ["sparse-checkout", "set", "--no-cone", "/README.md"]);
    await stageNamedFiles(root, paths);
    expect((await readPlannerDay(root, entry, { day, raw_revision: revision, raw_files: paths }, PlanRunRowContract)).rows).toHaveLength(2);
    const inputs = await loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url)));
    inputs.clock_config.collect.seen_window_days = 0;
    inputs.clock_config.collect.published_window_days = 0;
    await stagePlannerHistory(root, inputs, `${day}T12:00:00Z`);
    const staged = await readPlannerDay(root, registration("discovered-articles"), { day, raw_revision: revision }, DiscoveredArticleRowContract);
    expect(staged).toMatchObject({ complete: true, rows: [discoveryRow] });
    await rm(join(root, paths[0]!));
    expect((await readPlannerDay(root, entry, { day, raw_revision: revision, raw_files: paths }, PlanRunRowContract)).complete).toBe(false);
  } finally { await rm(root, { recursive: true, force: true }); }
}, 120_000);

test("an invalid mode or day path is not a verified empty day", async () => {
  const root = await mkdtemp(join(tmpdir(), "planner-invalid-git-day-"));
  try {
    await fixtureGit(root, ["init", "--initial-branch=main"]);
    const day = "state/raw/feed-ingest-plan/plan-runs/2026/10/20";
    await mkdir(dirname(join(root, day)), { recursive: true });
    await writeFile(join(root, day), "not a directory");
    await fixtureGit(root, ["add", "--", day]);
    await fixtureGit(root, ["commit", "-m", "Record invalid generated day"]);
    await expect(listExactRawDayMembers(root, registration("plan-runs"), "2026-10-20", await fixedHistoryRevision(root)))
      .rejects.toThrow("not a directory");
    const blob = await fixtureGit(root, ["hash-object", "-w", "--", day]);
    await fixtureGit(root, ["update-index", "--force-remove", "--", day]);
    const parent = "state/raw/feed-ingest-plan/plan-runs/2026";
    await fixtureGit(root, ["update-index", "--add", "--cacheinfo", `120000,${blob},${parent}`]);
    await fixtureGit(root, ["commit", "-m", "Record non-directory ancestor"]);
    await expect(listExactRawDayMembers(root, registration("plan-runs"), "2026-10-20", await fixedHistoryRevision(root)))
      .rejects.toThrow("parent is not a directory");
  } finally { await rm(root, { recursive: true, force: true }); }
});
