/** Do real planning and document operations depend only on their required health evidence? */
import { expect, test } from "bun:test";
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import { z } from "zod";
import { FeedHealthStateRowContract, FeedHealthStateRowSchema } from "@idhazh/common-contracts";
import { preparePlanningHealth, healthHistoryInput } from "../src/api/prepare-planning-health";
import { prepareFeedHealthState, prepareRequestReport } from "../src/api/feed-health-state-operation";
import { currentExecutionState } from "../src/api/document-state";
import { createPlanApp } from "../src/api/server";
import { endpointKey, readFeedHistory } from "../src/read-ledger-history/read-feed-history";
import { readRequestHistory } from "../src/read-ledger-history/read-request-history";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { runFeedPlan } from "../src/run-feed-plan";
import { healthFieldFixture, rewriteHealthFields } from "./health-field-fixtures";
import { recordedPlan } from "./plan-recordings";
import { commitFixtureFiles, writeRows } from "./partition-fixtures";
import { fixtureGit } from "./publication-recordings";

const schema = z.object(FeedHealthStateRowSchema.shape);
const changedColumns = schema.omit({
  permission: true, reliability: true, articles_selected: true, article_requests: true,
}).extend({
  status: z.string(),
  rejection_counts: z.array(z.object(FeedHealthStateRowSchema.shape.rejection_counts.element.shape).omit({ stage: true })),
});
async function recording() {
  const setup = await recordedPlan();
  try {
    const seed = await healthFieldFixture(setup.inputs.outputRoot);
    const row = FeedHealthStateRowSchema.parse({
      ...seed.row, feed_id: setup.inputs.harvest.sources[0]!.id,
      endpoint_key: endpointKey(setup.inputs.harvest.sources[0]!.url),
    });
    const file = seed.written.files[0]!.path;
    const path = join(setup.inputs.outputRoot, file);
    await rewriteHealthFields(path, [row], schema);
    setup.inputs.settings.inputs.feed_health_days = [
      { day: row.date, raw_files: [`state/${file}`] },
      ...["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24"]
        .map(day => ({ day, raw_files: [] })),
    ];
    setup.inputs.harvest.config.feedback.lifecycle_window_days = 1;
    setup.inputs.clock_config.collect.reliability_window_days = 1;
    setup.runtime.clock = () => new Date("2026-10-26T12:00:00Z");
    setup.runtime.observation_clock = setup.runtime.clock;
    return { ...setup, row, path };
  } catch (error) { await setup.close(); throw error; }
}

test("changed unrelated columns and row dates preserve real planning evidence and isolate missing request fields", async () => {
  const setup = await recording();
  try {
    const now = setup.runtime.clock!().toISOString();
    const baseline = await preparePlanningHealth(setup.inputs, now);
    const expected = baseline.sources.get(setup.row.feed_id)!;
    expect(expected).toMatchObject({
      lifecycle: "eligible", article_pass_rate: 0.75,
      reliability: { productive: 1, attempted: 1, complete: true, production_factor: 1 },
    });
    for (const stamp of ["2026-10-25", "2027-01-01"]) {
      await rewriteHealthFields(setup.path, [changedColumns.parse({ ...setup.row, status: "unrelated" })], changedColumns, { stamp });
      const restored = await preparePlanningHealth(setup.inputs, now);
      expect(restored.sources.get(setup.row.feed_id)).toEqual(expected);
      const summary = await prepareFeedHealthState(setup.inputs, now);
      expect(summary.sources.get(setup.row.feed_id)).toEqual(expected);
      expect(summary.request_report.feeds[0]).toMatchObject({
        counts_complete: false, feed_requests: null, article_requests: null, robots_requests: null,
      });
      const requests = await readRequestHistory(healthHistoryInput(setup.inputs, now));
      expect(requests.partial_rows[0]).toMatchObject({ feed_requests: 2, robots_requests: 0 });
      expect(requests.partial_rows[0]).not.toHaveProperty("article_requests");
    }
  } finally { await setup.close(); }
});

test("unknown or invalid admission and read fields never turn partial evidence into complete scores", async () => {
  const setup = await recording();
  try {
    const now = setup.runtime.clock!().toISOString();
    const second = { ...setup.row, run_id: "2026-10-25-5678", article_candidates: 0 };
    await rewriteHealthFields(setup.path, [setup.row, { ...second, article_candidates: null }], schema);
    let history = await preparePlanningHealth(setup.inputs, now);
    expect(history.sources.get(setup.row.feed_id)).toMatchObject({
      lifecycle: "eligible", article_pass_rate: null,
      reliability: { productive: 2, attempted: 2, complete: true },
    });
    await rewriteHealthFields(setup.path, [setup.row, { ...second, items: -1 }], schema);
    history = await preparePlanningHealth(setup.inputs, now);
    expect(history.sources.get(setup.row.feed_id)).toMatchObject({
      lifecycle: "unknown", strikes: null, rested_runs: null,
      reliability: { productive: 1, attempted: 1, complete: false },
    });
    await rewriteHealthFields(setup.path, [setup.row, {
      ...second, endpoint_key: "2".repeat(64), article_candidates: -1,
    }], schema);
    history = await preparePlanningHealth(setup.inputs, now);
    expect(history.sources.get(setup.row.feed_id)?.article_pass_rate).toBe(0.75);
    setup.inputs.settings.inputs.feed_health_input_gap = true;
    history = await preparePlanningHealth(setup.inputs, now);
    expect(history.sources.get(setup.row.feed_id)).toMatchObject({
      article_pass_rate: null, reliability: { complete: false },
    });
    setup.inputs.settings.inputs.feed_health_input_gap = false;
    await rewriteHealthFields(setup.path, [schema.omit({ attempt: true }).parse(setup.row)],
      schema.omit({ attempt: true }));
    history = await preparePlanningHealth(setup.inputs, now);
    expect(history.sources.get(setup.row.feed_id)).toMatchObject({
      lifecycle: "unknown", reliability: null, article_pass_rate: null,
    });
  } finally { await setup.close(); }
});

test("field-based captures retain attempts, exclude current work before replacement and refuse conflicting full facts", async () => {
  const setup = await recording();
  try {
    const failed = { ...setup.row, attempt: 2, checked_at: "2026-10-25T11:00:00Z",
      outcome: "permanent", items: 0, article_requests: 6 };
    await rewriteHealthFields(setup.path, [setup.row, setup.row, failed], schema);
    const input = {
      ...healthHistoryInput(setup.inputs, setup.runtime.clock!().toISOString()),
      own_rows: [setup.row],
    };
    const planning = await readFeedHistory(input);
    expect(planning.uses.feed_reliability.rows).toHaveLength(2);
    expect(planning.sources.get(setup.row.feed_id)?.reliability).toMatchObject({ productive: 1, attempted: 1 });
    const requests = await readRequestHistory(input);
    expect(requests.request_report.feeds[0]).toMatchObject({ article_requests: 10, counts_complete: true });
    const replaced = await readFeedHistory({
      ...input, exclude_execution: { run_id: setup.row.run_id, attempt: 2 },
      current_rows: [{ ...setup.row, attempt: 2, article_requests: 9 }],
    });
    expect(replaced.uses.request_totals.rows.map(row => row.article_requests).sort()).toEqual([4, 9]);
    await expect(readFeedHistory({ ...input, own_rows: [{ ...setup.row, permission: "denied" }] }))
      .rejects.toThrow("Conflicting copies");
    await rewriteHealthFields(setup.path, [setup.row, failed, { ...failed, permission: "denied" }], schema);
    const excluded = await readFeedHistory({
      ...input, exclude_execution: { run_id: setup.row.run_id, attempt: 2 },
      current_rows: [{ ...setup.row, attempt: 2, article_requests: 9 }],
    });
    expect(excluded.uses.request_totals.rows.map(row => row.article_requests).sort()).toEqual([4, 9]);
  } finally { await setup.close(); }
});

test("report-only conflicts cannot block combined or standalone fetch and parse or discard actual requests", async () => {
  const setup = await recording();
  const standalone = await recording();
  const prefix = "/api/2026-10-20";
  const json = (body: unknown) => ({
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  });
  let app: ReturnType<typeof createPlanApp> | undefined;
  try {
    for (const fixture of [setup, standalone]) {
      fixture.inputs.settings.inputs.feed_health_days = fixture.inputs.settings.inputs.feed_health_days
        .filter(day => day.day === fixture.row.date);
      await rewriteHealthFields(fixture.path, [changedColumns.parse({ ...fixture.row, status: "unrelated" })],
        changedColumns, { stamp: "2027-01-01" });
      const reportOnlyDay = "2026-10-20";
      const poison = FeedHealthStateRowSchema.parse({
        ...fixture.row, date: reportOnlyDay, run_id: `${reportOnlyDay}-900`,
        checked_at: `${reportOnlyDay}T10:00:00Z`,
      });
      const written = await writeRows(fixture.inputs.outputRoot, "feed-health-state", reportOnlyDay,
        FeedHealthStateRowContract, [poison]);
      await rewriteHealthFields(join(fixture.inputs.outputRoot, written.files[0]!.path),
        [poison, { ...poison, permission: "denied" }], schema);
      const paths = [fixture.path, ...written.files.map(file => join(fixture.inputs.outputRoot, file.path))];
      await commitFixtureFiles(fixture.directory, paths);
      const revision = await fixtureGit(fixture.directory, ["rev-parse", "--verify", "HEAD"]);
      fixture.inputs.settings.inputs.feed_health_days[0]!.raw_revision = revision;
      // Planning inventory deliberately does not include this report-only day.
      await expect(prepareRequestReport(fixture.inputs, fixture.runtime.clock!().toISOString()))
        .rejects.toMatchObject({ errors: expect.arrayContaining([
          expect.objectContaining({ message: expect.stringContaining("Conflicting copies") }),
        ]) });
    }
    const combined = await runFeedPlan({}, setup.inputs, setup.runtime);
    expect(combined.row.api_timings).toEqual(expect.arrayContaining([
      expect.objectContaining({ operation: "feed-health-before-fetch", status: "completed" }),
      expect.objectContaining({ operation: "fetch", status: "completed" }),
      expect.objectContaining({ operation: "parse", status: "completed" }),
    ]));
    const healthFiles = combined.files.feed_health_state!.files;
    const actual = (await readPlannerParquet(join(setup.inputs.outputRoot, healthFiles[0]!.path),
      "feed-health-state", FeedHealthStateRowContract)).rows[0]!;
    expect(actual.feed_requests).toBeGreaterThan(0);
    expect(actual.article_requests).toBeGreaterThan(0);
    expect(actual.feed_requests! + actual.article_requests! + actual.robots_requests!).toBe(setup.transport.requests.length);

    app = createPlanApp(standalone.inputs, standalone.runtime);
    const requestId = randomUUID();
    const correlation = randomUUID();
    const fetched = await app.request(`${prefix}/fetch`, json({
      request_id: requestId, correlation_id: correlation, feed_id: standalone.row.feed_id, fetch_item_type: "feed",
    }));
    expect(fetched.status).toBe(200);
    const document = await fetched.json();
    const parsed = await app.request(`${prefix}/parse`, json({
      request_id: randomUUID(), fetch_request_id: requestId, article_id: document.article_id, correlation_id: correlation,
    }));
    expect(parsed.status).toBe(200);
    expect((await parsed.json()).parsed_count).toBeGreaterThan(0);
    const state = await currentExecutionState(standalone.inputs, document.run_id);
    expect(state?.kind).toBe("document");
    if (state?.kind !== "document") throw new Error("Expected current document work");
    expect(state.history.sources.get(standalone.row.feed_id)).toMatchObject({
      lifecycle: "eligible", article_pass_rate: 0.75, reliability: { complete: true },
    });
    const work = state.work.rows()[0]!;
    expect(work.feed_requests! + work.article_requests! + work.robots_requests!).toBe(standalone.transport.requests.length);
    expect(work.feed_reads).toBe(1);
  } finally { app?.close(); await Promise.all([setup.close(), standalone.close()]); }
}, 120_000);
