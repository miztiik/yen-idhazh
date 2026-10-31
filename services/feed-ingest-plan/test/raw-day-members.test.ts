/** Prove exact-day Git membership, complete staging and native integrity on real Parquet bytes. */
import { expect, test } from "bun:test";
import { mkdtemp, mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { DiscoveredArticleRowContract, FeedHealthStateRowContract, FeedIngestEventSchema, PlanRunRowContract } from "@idhazh/common-contracts";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { fixtureGit } from "./publication-recordings";
import { registration, writeRows } from "./partition-fixtures";
import { fixedHistoryRevision, listExactRawDayMembers, readNamedGitFile, readNamedGitMember } from "../src/read-ledger-history/raw-day-members";
import { createPlannerHistoryCache, readPlannerDay } from "../src/read-ledger-history/read-planner-history";
import { stageNamedFiles, stagePlannerHistory } from "../scripts/feed-ingest-plan-history";
import { PlannerDayInputSchema } from "../src/config/service-settings";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { createStageLogger } from "../src/logging/structured-logger";
import { randomUUID } from "node:crypto";
import { inputEndpointKey } from "../src/read-ledger-history/health-summary";
import { preparePlanningHealth } from "../src/api/prepare-planning-health";

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
    const capture = createPlannerHistoryCache<ReturnType<typeof PlanRunRowContract.schema.parse>>();
    await readPlannerDay(root, entry, { day, raw_revision: revision }, PlanRunRowContract, capture);
    await rename(join(root, ".git"), join(root, ".git-held"));
    try {
      expect(await readPlannerDay(root, entry, { day, raw_revision: revision }, PlanRunRowContract, capture))
        .toMatchObject({ complete: true, represented: true, rows: complete.rows });
    } finally { await rename(join(root, ".git-held"), join(root, ".git")); }
    await writeFile(join(root, "README.md"), "Another revision, the same native files.\n");
    await fixtureGit(root, ["add", "--", "README.md"]);
    await fixtureGit(root, ["commit", "-m", "Advance generated history revision"]);
    expect((await readPlannerDay(root, entry, {
      day, raw_revision: await fixedHistoryRevision(root),
    }, PlanRunRowContract, capture)).complete).toBe(false);
    const missing = await readPlannerDay(root, entry, { day: "2026-10-19", raw_revision: revision }, PlanRunRowContract);
    expect(missing).toMatchObject({ complete: true, represented: false, rows: [], gaps: [] });
    const incomplete = await readPlannerDay(root, entry, {
      day, raw_revision: revision, raw_files: paths.slice(0, 1),
    }, PlanRunRowContract);
    expect(incomplete.complete).toBe(false);
    expect(incomplete.rows).toEqual([]);
    await expect(listExactRawDayMembers(root, entry, day, "0".repeat(40))).rejects.toThrow("Git");
    const logged: unknown[] = [];
    const correlation_id = randomUUID();
    const log = createStageLogger({ run_id: `${day}-999`, correlation_id }, event => logged.push(event));
    const failed = await readPlannerDay(
      root, entry, { day, raw_revision: "0".repeat(40) }, PlanRunRowContract, undefined, log,
    );
    expect(failed.complete).toBe(false);
    expect(failed.gaps.length).toBeGreaterThan(0);
    expect(FeedIngestEventSchema.parse(logged[0])).toMatchObject({
      run_id: `${day}-999`, correlation_id, operation: "history", phase: "failed",
      details: {
        source: "planner-ledger", failed_check: "named-day-read", reason: expect.any(String),
        ledger: "plan-runs", day, path: expect.any(String),
      },
    });
    await expect(listExactRawDayMembers(root, { ...entry, prefix: [".."] }, day, revision)).rejects.toThrow("registered");
    await expect(listExactRawDayMembers(root, entry, "2026-02-30", revision)).rejects.toThrow("UTC day");
    const original = await readFile(join(root, paths[0]!));
    await writeFile(join(root, paths[0]!), "different bytes at the same UUID");
    expect((await readPlannerDay(root, entry, { day, raw_revision: revision }, PlanRunRowContract)).complete).toBe(false);
    await writeFile(join(root, paths[0]!), original);
    const origin = join(root, "origin.git");
    await fixtureGit(root, ["init", "--bare", "--initial-branch=main", origin]);
    await fixtureGit(root, ["remote", "add", "origin", origin]);
    await fixtureGit(root, ["push", "origin", "HEAD:refs/heads/main"]);
    await fixtureGit(root, ["sparse-checkout", "set", "--no-cone", "/README.md"]);
    await stageNamedFiles(root, paths);
    expect((await readPlannerDay(root, entry, { day, raw_revision: revision, raw_files: paths }, PlanRunRowContract)).rows).toHaveLength(2);
    const inputs = await loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url)));
    inputs.harvest.config.discovered_articles.lookback_days = 0;
    inputs.clock_config.collect.published_window_days = 0;
    await stagePlannerHistory(root, inputs, `${day}T12:00:00Z`);
    const staged = await readPlannerDay(root, registration("discovered-articles"), { day, raw_revision: revision }, DiscoveredArticleRowContract);
    expect(staged).toMatchObject({ complete: true, rows: [discoveryRow] });
    inputs.settings.inputs.discovered_days = [{ day, raw_revision: revision, raw_files: discoveryPaths }];
    await expect(stagePlannerHistory(root, inputs, `${day}T12:00:00Z`)).rejects.toMatchObject({
      errors: expect.arrayContaining([expect.objectContaining({
        message: "Authored raw history revision differs from the captured staging revision",
      })]),
    });
    await rm(join(root, paths[0]!));
    expect((await readPlannerDay(root, entry, { day, raw_revision: revision, raw_files: paths }, PlanRunRowContract)).complete).toBe(false);
  } finally { await rm(root, { recursive: true, force: true }); }
}, 120_000);

test("cached parent absence still rejects uncommitted files and cannot hide a later revision", async () => {
  const root = await mkdtemp(join(tmpdir(), "planner-cached-git-entry-"));
  const path = "config/second.json";
  const cache = new Map<string, Promise<string>>();
  try {
    await fixtureGit(root, ["init", "--initial-branch=main"]);
    await fixtureGit(root, ["commit", "--allow-empty", "-m", "Create generated history"]);
    const revision = await fixedHistoryRevision(root);
    expect(await readNamedGitMember(root, "config/first.json", revision, cache)).toBeUndefined();
    await rename(join(root, ".git"), join(root, ".git-held"));
    try {
      expect(await readNamedGitMember(root, path, revision, cache)).toBeUndefined();
      await mkdir(join(root, "config"));
      await writeFile(join(root, path), "{}\n");
      await expect(readNamedGitMember(root, path, revision, cache)).rejects.toThrow("Uncommitted");
    } finally { await rename(join(root, ".git-held"), join(root, ".git")); }
    await fixtureGit(root, ["add", "--", path]);
    await fixtureGit(root, ["commit", "-m", "Record generated named file"]);
    const latest = await fixedHistoryRevision(root);
    expect(latest).not.toBe(revision);
    expect((await readNamedGitMember(root, path, latest, cache))?.bytes.toString("utf8")).toBe("{}\n");
  } finally { await rm(root, { recursive: true, force: true }); }
});

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

test("a stale sparse checkout captures latest remote health bytes once without a runtime commit", async () => {
  const root = await mkdtemp(join(tmpdir(), "planner-remote-capture-"));
  try {
    const producer = join(root, "producer");
    const consumer = join(root, "consumer");
    const origin = join(root, "origin.git");
    await mkdir(producer);
    await fixtureGit(producer, ["init", "--initial-branch=main"]);
    await writeFile(join(producer, "README.md"), "Generated captured input.\n");
    await fixtureGit(producer, ["add", "--", "README.md"]);
    await fixtureGit(producer, ["commit", "-m", "Create generated capture baseline"]);
    await fixtureGit(root, ["init", "--bare", "--initial-branch=main", origin]);
    await fixtureGit(producer, ["remote", "add", "origin", origin]);
    await fixtureGit(producer, ["push", "origin", "HEAD:refs/heads/main"]);
    await fixtureGit(root, ["clone", "--quiet", origin, consumer]);
    const original = await fixedHistoryRevision(consumer);
    await fixtureGit(consumer, ["sparse-checkout", "set", "--no-cone", "/README.md"]);
    const inputs = await loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url)));
    const day = "2026-10-20";
    const source = inputs.harvest.sources.find(source => source.status === "active")!;
    const seed = plannerRecordings(day).find(record => record.name === "feed-health-state")!.row;
    const row = FeedHealthStateRowContract.schema.parse({
      ...seed, feed_id: source.id, endpoint_key: inputEndpointKey(source.url),
      availability: "resting", strikes: 5, rest_until: "2026-10-21T10:00:00.123Z",
      first_confirmed_failure_at: "2026-10-20T06:00:00Z",
      reliability: { productive: 3, attempted: 5, success_fraction: 0.6, production_factor: 0.6,
        from_day: day, through_day: day, complete: true },
    });
    const saved = await writeRows(join(producer, "state"), "feed-health-state", day, FeedHealthStateRowContract, [row]);
    const paths = saved.files.map(file => `state/${file.path}`);
    await fixtureGit(producer, ["add", "--", ...paths]);
    await fixtureGit(producer, ["commit", "-m", "Record generated current health"]);
    await fixtureGit(producer, ["push", "origin", "HEAD:refs/heads/main"]);
    const latest = await fixedHistoryRevision(producer);
    inputs.harvest.config.discovered_articles.lookback_days = 0;
    inputs.clock_config.collect.published_window_days = 0;
    inputs.clock_config.collect.reliability_window_days = 1;
    inputs.harvest.config.feedback.lifecycle_window_days = 1;
    const staged = await stagePlannerHistory(consumer, inputs, `${day}T12:00:00Z`);
    expect(staged.feed_health_days[0]).toMatchObject({ day, raw_revision: latest, raw_files: paths });
    expect(await readFile(join(consumer, paths[0]!))).toEqual(await readFile(join(producer, paths[0]!)));
    expect(await fixedHistoryRevision(consumer)).toBe(original);
    expect(await fixtureGit(origin, ["--git-dir", origin, "rev-parse", "main"])).toBe(latest);
    const capturedInputs = { ...inputs, root: consumer, settings: { ...inputs.settings, inputs: {
      ...inputs.settings.inputs, ...staged,
    } } };
    expect((await preparePlanningHealth(capturedInputs, `${day}T12:00:00Z`)).sources.get(source.id))
      .toMatchObject({ lifecycle: "resting", strikes: 5, reliability: { productive: 3, attempted: 5, complete: true } });
  } finally { await rm(root, { recursive: true, force: true }); }
}, 120_000);
