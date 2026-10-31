/** Reuse real saved Parquet calculations and recover only the calculation that is absent. */
import { expect, test } from "bun:test";
import { join } from "node:path";
import { readFile, writeFile } from "node:fs/promises";
import { z } from "zod";
import { randomUUID } from "node:crypto";
import { FeedHealthStateRowContract, FeedHealthStateRowSchema } from "@idhazh/common-contracts";
import type { FeedHealthReliability } from "@idhazh/common-contracts";
import { healthFieldFixture, rewriteHealthFields } from "./health-field-fixtures";
import { recordedPlan } from "./plan-recordings";
import { preparePlanningHealth } from "../src/api/prepare-planning-health";
import { recordFeedHealthState } from "../src/api/feed-health-state-operation";
import { resolveRunContext } from "../src/resolve-run-context";
import { inputEndpointKey } from "../src/read-ledger-history/health-summary";
import { sourceSnapshot } from "../src/harvest-feeds/load-harvest-inputs";
import { createFeedHealthRow } from "../src/health-row";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { writeRows } from "./partition-fixtures";

const schema = z.object(FeedHealthStateRowSchema.shape);
async function recording() {
  const setup = await recordedPlan();
  try {
    const seed = await healthFieldFixture(setup.inputs.outputRoot);
    const row = FeedHealthStateRowSchema.parse({
      ...seed.row, feed_id: setup.inputs.harvest.sources[0]!.id,
      endpoint_key: inputEndpointKey(setup.inputs.harvest.sources[0]!.url),
      reliability: { productive: 4, attempted: 5, success_fraction: 0.8, production_factor: 0.8,
        from_day: seed.row.date, through_day: seed.row.date, complete: true },
    });
    const path = join(setup.inputs.outputRoot, seed.written.files[0]!.path);
    await rewriteHealthFields(path, [row], schema);
    setup.inputs.settings.inputs.feed_health_days = [{ day: row.date, raw_files: [`state/${seed.written.files[0]!.path}`] }];
    setup.inputs.harvest.config.feedback.lifecycle_window_days = 1;
    setup.inputs.clock_config.collect.reliability_window_days = 1;
    setup.runtime.clock = () => new Date("2026-10-26T12:00:00.000Z");
    setup.runtime.observation_clock = setup.runtime.clock;
    return { ...setup, row, path, now: setup.runtime.clock().toISOString() };
  } catch (error) { await setup.close(); throw error; }
}

async function writeCarriedSummary(
  setup: Awaited<ReturnType<typeof recording>>, day: string, run: string,
  reliability: FeedHealthReliability, updatedAt = "2026-10-29T10:00:00.000Z",
) {
  const row = FeedHealthStateRowSchema.parse({
    ...setup.row, date: day, run_id: `${day}-${run}`, checked_at: null,
    check_request_id: null, check_result: null, outcome: null, status: null, items: null,
    availability: "resting", strikes: 5, rest_until: "2026-11-01T10:00:00.000Z",
    first_confirmed_failure_at: "2026-10-29T10:00:00.000Z", availability_updated_at: updatedAt,
    feed_reads: null, productive_reads: null, failed_reads: null, article_candidates: null,
    articles_selected: null, feed_requests: null, article_requests: null, robots_requests: null,
    counts_complete: false, rejection_counts: [], reliability,
  });
  const written = await writeRows(setup.inputs.outputRoot, "feed-health-state", day, FeedHealthStateRowContract, [row]);
  return { day, raw_files: written.files.map(file => `state/${file.path}`) };
}

test("carried reliability reuses the requested saved window even when the availability clock did not change", async () => {
  const setup = await recording();
  try {
    const older = await writeCarriedSummary(setup, "2026-10-30", "9100", {
      productive: 1, attempted: 1, success_fraction: 1, production_factor: 1,
      from_day: "2026-10-29", through_day: "2026-10-30", complete: true,
    });
    const current = await writeCarriedSummary(setup, "2026-10-31", "9101", {
      productive: 0, attempted: 0, success_fraction: null, production_factor: null,
      from_day: "2026-10-30", through_day: "2026-10-31", complete: true,
    });
    setup.inputs.settings.inputs.feed_health_days = [older, current];
    setup.inputs.clock_config.collect.reliability_window_days = 2;
    const read = await preparePlanningHealth(setup.inputs, "2026-10-31T12:00:00.000Z");
    expect(read.sources.get(setup.row.feed_id)).toMatchObject({
      lifecycle: "resting", availability_updated_at: "2026-10-29T10:00:00.000Z",
      reliability: { productive: 0, attempted: 0, success_fraction: null, production_factor: null,
        from_day: "2026-10-30", through_day: "2026-10-31", complete: true },
    });
    const snapshots = [...read.uses.feed_reliability.rows, ...read.uses.feed_reliability.partial_rows];
    expect(snapshots).toHaveLength(2);
    expect(snapshots.every(row => row.checked_at === null && row.check_request_id === null)).toBe(true);
    const carried = await writeCarriedSummary(setup, "2026-11-01", "9102", {
      productive: 0, attempted: 0, success_fraction: null, production_factor: null,
      from_day: "2026-10-30", through_day: "2026-10-31", complete: true,
    });
    setup.inputs.settings.inputs.feed_health_days.push(carried);
    const advanced = await preparePlanningHealth(setup.inputs, "2026-11-01T12:00:00.000Z");
    expect(advanced.sources.get(setup.row.feed_id)?.reliability).toEqual({
      productive: 0, attempted: 0, success_fraction: null, production_factor: null,
      from_day: "2026-10-31", through_day: "2026-11-01", complete: true,
    });
  } finally { await setup.close(); }
});

test("carried reliability keeps same-window clock ambiguity instead of borrowing another question's totals", async () => {
  const setup = await recording();
  try {
    const older = await writeCarriedSummary(setup, "2026-10-30", "9200", {
      productive: 1, attempted: 1, success_fraction: 1, production_factor: 1,
      from_day: "2026-10-29", through_day: "2026-10-30", complete: true,
    });
    const first = await writeCarriedSummary(setup, "2026-10-31", "9201", {
      productive: 0, attempted: 0, success_fraction: null, production_factor: null,
      from_day: "2026-10-30", through_day: "2026-10-31", complete: true,
    }, "2026-10-29T10:00:00Z");
    const overlapping = await writeCarriedSummary(setup, "2026-10-31", "9202", {
      productive: 1, attempted: 1, success_fraction: 1, production_factor: 1,
      from_day: "2026-10-30", through_day: "2026-10-31", complete: true,
    }, "2026-10-29T10:00:00.005Z");
    setup.inputs.settings.inputs.feed_health_days = [older, {
      day: first.day, raw_files: [...first.raw_files, ...overlapping.raw_files],
    }];
    setup.inputs.clock_config.collect.reliability_window_days = 2;
    const read = await preparePlanningHealth(setup.inputs, "2026-10-31T12:00:00.000Z");
    expect(read.sources.get(setup.row.feed_id)?.reliability).toEqual({
      productive: null, attempted: null, success_fraction: null, production_factor: null,
      from_day: "2026-10-30", through_day: "2026-10-31", complete: false,
    });
  } finally { await setup.close(); }
});

test("saved availability and reliability survive missing check and unrelated accounting fields", async () => {
  const setup = await recording();
  try {
    const expected = (await preparePlanningHealth(setup.inputs, setup.now)).sources.get(setup.row.feed_id)!;
    expect(expected.reliability).toMatchObject({ productive: 4, attempted: 5, success_fraction: 0.8, complete: true });
    const variant = schema.omit({ checked_at: true, outcome: true, items: true, article_requests: true });
    await rewriteHealthFields(setup.path, [variant.parse(setup.row)], variant);
    const read = await preparePlanningHealth(setup.inputs, setup.now);
    expect(read.sources.get(setup.row.feed_id)).toEqual(expected);
    expect(read.uses.request_totals.partial_rows[0]).not.toHaveProperty("article_requests");
    expect(read.uses.feed_rest.gaps.some(gap => gap.field === "checked_at")).toBe(true);
  } finally { await setup.close(); }
});

test("a missing reliability calculation recovers read facts without recalculating saved lifecycle", async () => {
  const setup = await recording();
  try {
    const resting = FeedHealthStateRowSchema.parse({
      ...setup.row, availability: "resting", strikes: 5, check_result: "confirmed-http-failure",
      rest_until: "2026-10-27T10:00:00.123Z", first_confirmed_failure_at: "2026-10-25T05:00:00.000Z",
      status: 503, outcome: "transient", items: 0,
    });
    const variant = schema.omit({ reliability: true });
    await rewriteHealthFields(setup.path, [variant.parse(resting)], variant);
    const result = (await preparePlanningHealth(setup.inputs, setup.now)).sources.get(setup.row.feed_id)!;
    expect(result).toMatchObject({ lifecycle: "resting", strikes: 5, rest_until: resting.rest_until,
      availability_updated_at: resting.availability_updated_at, availability_complete: true });
    expect(result.reliability).toMatchObject({ productive: 0, attempted: 1, success_fraction: 0, complete: true });
    const missingLifecycle = schema.omit({ availability_updated_at: true });
    await rewriteHealthFields(setup.path, [missingLifecycle.parse(setup.row)], missingLifecycle);
    const recovered = (await preparePlanningHealth(setup.inputs, setup.now)).sources.get(setup.row.feed_id)!;
    expect(recovered).toMatchObject({ lifecycle: "eligible", strikes: 0, availability_updated_at: setup.row.checked_at,
      availability_complete: true, reliability: { productive: 4, attempted: 5, success_fraction: 0.8 } });
  } finally { await setup.close(); }
});

test("one run retains its captured input while a later independent run reads changed evidence", async () => {
  const setup = await recording();
  try {
    const context = resolveRunContext(setup.inputs.settings, setup.runtime.git_sha, new Date(setup.now), "701");
    const first = await preparePlanningHealth(setup.inputs, setup.now, { context, rows: [] });
    const changed = { ...setup.row, reliability: { ...setup.row.reliability!, productive: 3, success_fraction: 0.6, production_factor: 0.6 } };
    await rewriteHealthFields(setup.path, [changed], schema);
    expect((await preparePlanningHealth(setup.inputs, setup.now, { context, rows: [] })).sources)
      .toEqual(first.sources);
    const next = resolveRunContext(setup.inputs.settings, setup.runtime.git_sha, new Date(setup.now), "702");
    expect((await preparePlanningHealth(setup.inputs, setup.now, { context: next, rows: [] })).sources.get(setup.row.feed_id)?.reliability)
      .toMatchObject({ productive: 3, attempted: 5, success_fraction: 0.6 });
  } finally { await setup.close(); }
});

test("a recovered calculation is reused across API calls after its original facts are no longer needed", async () => {
  const setup = await recording();
  try {
    const variant = schema.omit({ availability_updated_at: true, reliability: true });
    await rewriteHealthFields(setup.path, [variant.parse(setup.row)], variant);
    const now = `${setup.row.date}T12:00:00.000Z`;
    const context = resolveRunContext(setup.inputs.settings, setup.runtime.git_sha, new Date(now), "800");
    const captured = await preparePlanningHealth(setup.inputs, now, { context, rows: [] });
    expect(captured.sources.get(setup.row.feed_id)).toMatchObject({ strikes: 0, reliability: { productive: 1, attempted: 1 } });
    captured.uses.feed_rest.rows.length = 0;
    captured.uses.feed_rest.partial_rows.length = 0;
    captured.uses.feed_reliability.rows.length = 0;
    captured.uses.feed_reliability.partial_rows.length = 0;
    const current = FeedHealthStateRowSchema.parse({
      ...setup.row, run_id: context.run_id, check_request_id: randomUUID(), checked_at: now,
      check_result: "confirmed-http-failure", status: 503, outcome: "transient", items: 0,
    });
    const updated = await preparePlanningHealth(setup.inputs, now, { context, rows: [current] });
    expect(updated.sources.get(setup.row.feed_id)).toMatchObject({
      strikes: 1, availability_complete: true, first_confirmed_failure_at: now,
      reliability: { productive: 1, attempted: 2, success_fraction: 0.5 },
    });
  } finally { await setup.close(); }
});

test("finalized carry-forward Parquet reloads supported calculations without claiming a new check", async () => {
  const setup = await recording();
  try {
    const context = resolveRunContext(setup.inputs.settings, setup.runtime.git_sha, new Date(setup.now), "703");
    const history = await preparePlanningHealth(setup.inputs, setup.now, { context, rows: [] });
    const source = sourceSnapshot(setup.inputs.harvest, setup.inputs.harvest.sources[0]!);
    const carry = createFeedHealthRow(context, source, history.sources.get(source.feed_id), setup.now);
    const written = await recordFeedHealthState([carry], context, setup.inputs);
    const actual = await readPlannerParquet(join(setup.inputs.outputRoot, written.files[0]!.path), "feed-health-state", FeedHealthStateRowContract);
    expect(actual.rows[0]).toMatchObject({
      checked_at: null, check_request_id: null, check_result: null, feed_reads: 0, feed_requests: 0,
      availability_updated_at: setup.row.availability_updated_at, availability_complete: true,
      reliability: setup.row.reliability,
    });
    const fresh = { ...setup.inputs, settings: { ...setup.inputs.settings, inputs: {
      ...setup.inputs.settings.inputs, feed_health_days: [{ day: context.date, raw_files: [`state/${written.files[0]!.path}`] }],
    } } };
    const reloaded = await preparePlanningHealth(fresh, setup.now);
    // The stored measurement still covers its original day, not the carry-forward work day.
    expect(reloaded.sources.get(source.feed_id)?.availability_updated_at).toBe(setup.row.availability_updated_at);
    expect(reloaded.sources.get(source.feed_id)?.reliability).toMatchObject({
      productive: 4, attempted: 5, success_fraction: 0.8, through_day: setup.row.date, complete: false,
    });
    expect(actual.rows[0]!.reliability!.through_day).toBe(setup.row.date);
  } finally { await setup.close(); }
});

test("a refused old format or corrupt sibling preserves usable current decisions without restoring JSON", async () => {
  const setup = await recording();
  try {
    const original = await readFile(setup.path);
    const sibling = await writeRows(setup.inputs.outputRoot, "feed-health-state", setup.row.date,
      FeedHealthStateRowContract, [{ ...setup.row, run_id: `${setup.row.date}-9000` }]);
    const siblingPath = join(setup.inputs.outputRoot, sibling.files[0]!.path);
    await writeFile(siblingPath, new Uint8Array([1, 2, 3]));
    setup.inputs.settings.inputs.feed_health_days[0]!.raw_files!.push(`state/${sibling.files[0]!.path}`);
    let result = await preparePlanningHealth(setup.inputs, setup.now);
    expect(result.sources.get(setup.row.feed_id)).toMatchObject({ lifecycle: "eligible", availability_complete: true });
    expect(result.days[0]!.complete).toBe(false);
    await rewriteHealthFields(setup.path, [setup.row], schema, { stamp: "2026-10-30" });
    result = await preparePlanningHealth(setup.inputs, setup.now);
    expect(result.sources.get(setup.row.feed_id)).toMatchObject({ lifecycle: "unknown", strikes: null,
      availability_complete: false, reliability: { productive: null, attempted: null, complete: false } });
    await writeFile(setup.path, original);
  } finally { await setup.close(); }
});

test("a real known skipped day expires the last measured read without carrying its old perfect fraction", async () => {
  const setup = await recording();
  try {
    const measured = { ...setup.row, reliability: {
      productive: 1, attempted: 1, success_fraction: 1, production_factor: 1,
      from_day: setup.row.date, through_day: setup.row.date, complete: true,
    } };
    await rewriteHealthFields(setup.path, [measured], schema);
    const nextDay = setup.now.slice(0, 10);
    const skipped = FeedHealthStateRowSchema.parse({
      ...measured, run_id: `${nextDay}-901`, date: nextDay,
      check_request_id: null, check_result: null, checked_at: null, outcome: null, items: null,
      feed_reads: 0, productive_reads: 0, failed_reads: 0, article_candidates: 0, articles_selected: 0,
      feed_requests: 0, article_requests: 0, robots_requests: 0, rejection_counts: [],
    });
    const saved = await writeRows(setup.inputs.outputRoot, "feed-health-state", nextDay, FeedHealthStateRowContract, [skipped]);
    setup.inputs.settings.inputs.feed_health_days.push({
      day: nextDay, raw_files: saved.files.map(file => `state/${file.path}`),
    });
    const refreshed = await preparePlanningHealth(setup.inputs, setup.now);
    const calculation = refreshed.sources.get(setup.row.feed_id)!.reliability!;
    expect(calculation).toEqual({
      productive: 0, attempted: 0, success_fraction: null, production_factor: null,
      from_day: nextDay, through_day: nextDay, complete: true,
    });
  } finally { await setup.close(); }
});
