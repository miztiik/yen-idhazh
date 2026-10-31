/** Prove saved snapshot ordering, raw/compact overlap and bounded rolling adjustments. */
import { expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { FeedHealthStateRowContract, FeedHealthStateRowSchema } from "@idhazh/common-contracts";
import { readLifecyclePolicy } from "./health-field-fixtures";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { projectFeedHealthFields } from "../src/read-ledger-history/read-feed-health-fields";
import { reuseFeedLifecycle, recoverFeedLifecycle } from "../src/read-ledger-history/feed-lifecycle-history";
import { reuseFeedReliability } from "../src/read-ledger-history/feed-reliability-history";
import { readFeedHealthFieldsDay } from "../src/read-ledger-history/read-feed-health-fields";
import { commitFixtureFiles, compactRows, registration, writeRows } from "./partition-fixtures";
import { fixtureGit } from "./publication-recordings";

function row(day: string, run: number, productive = true) {
  const seed = plannerRecordings(day).find(record => record.name === "feed-health-state")!.row;
  return FeedHealthStateRowSchema.parse({
    ...seed, run_id: `${day}-${run}`, check_request_id: randomUUID(),
    check_result: productive ? "valid-feed" : "confirmed-http-failure",
    outcome: productive ? "ok" : "transient", status: productive ? 200 : 503, items: productive ? 1 : 0,
  });
}

test("independent cumulative snapshots are selected by actual check order, not summed", async () => {
  const settings = await readLifecyclePolicy();
  const earlier = { ...row("2026-10-01", 1, false), strikes: 1,
    checked_at: "2026-10-01T10:00:00.000Z", availability_updated_at: "2026-10-01T10:00:00.000Z" };
  const later = { ...earlier, run_id: "2026-10-01-2", check_request_id: randomUUID(),
    checked_at: "2026-10-01T11:00:00.000Z", availability_updated_at: "2026-10-01T11:00:00.000Z" };
  const gaps: string[] = [];
  expect(reuseFeedLifecycle([later, earlier, later], "2026-10-02T00:00:00Z", settings, reason => gaps.push(reason)))
    .toMatchObject({ strikes: 1, availability_updated_at: later.checked_at, availability_complete: true });
  expect(gaps).toEqual([]);
  const ambiguous = { ...later, strikes: 2 };
  const conflict = reuseFeedLifecycle([later, ambiguous], "2026-10-02T00:00:00Z", settings, reason => gaps.push(reason));
  expect(conflict).toMatchObject({ strikes: null, retired_at: null, availability_complete: false });
  expect(gaps).toContain("availability-order-ambiguous");
  const partial = projectFeedHealthFields(later.date, [{ ...later, failed_recovery_checks: undefined,
    rest_until: "2026-10-03T00:00:00Z", availability: "resting" }]).feed_rest;
  expect(reuseFeedLifecycle(partial.partial_rows, "2026-10-02T00:00:00Z", settings, reason => gaps.push(reason)))
    .toMatchObject({ availability: "resting", rest_until: "2026-10-03T00:00:00Z",
      failed_recovery_checks: null, retired_at: null, availability_complete: false });
});

test("a check present in monthly Parquet and a late raw file is one fact across a month boundary", async () => {
  const root = await mkdtemp(join(tmpdir(), "lifecycle-overlap-"));
  try {
    const latest = { ...row("2026-09-30", 1, false), strikes: 5, availability: "resting" as const,
      rest_until: "2026-10-01T10:00:00.123Z", first_confirmed_failure_at: "2026-09-29T00:00:00Z",
      reliability: { productive: 2, attempted: 3, success_fraction: 0.666, production_factor: 0.666,
        from_day: "2026-09-30", through_day: "2026-09-30", complete: true } };
    const state = join(root, "state");
    const raw = await writeRows(state, "feed-health-state", latest.date, FeedHealthStateRowContract, [latest]);
    await compactRows(state, "feed-health-state", latest.date, FeedHealthStateRowContract, [latest], "monthly", root);
    await commitFixtureFiles(root, raw.files.map(file => `state/${file.path}`));
    const revision = await fixtureGit(root, ["rev-parse", "HEAD"]);
    const capture = await readFeedHealthFieldsDay(root, registration("feed-health-state"), {
      day: latest.date, raw_revision: revision, raw_files: raw.files.map(file => `state/${file.path}`),
    });
    expect(capture.complete).toBe(true);
    expect(capture.uses.feed_rest.rows).toHaveLength(1);
    const lifecycle = reuseFeedLifecycle(capture.uses.feed_rest.rows, "2026-10-01T12:00:00Z",
      await readLifecyclePolicy(), () => { throw new Error("Saved calculation unexpectedly required recovery"); });
    expect(lifecycle).toMatchObject({ availability: "eligible", strikes: 5,
      availability_updated_at: latest.availability_updated_at, rest_until: latest.rest_until });
    expect(reuseFeedReliability({
      rows: capture.uses.feed_reliability.rows, current: [], days: [latest.date], history_days: [latest.date], knownDay: () => true,
      now: "2026-10-01T12:00:00Z", floor: 0.5, window: 1,
      onGap: () => { throw new Error("Saved reliability unexpectedly required recovery"); },
    })).toMatchObject({ productive: 2, attempted: 3, success_fraction: 0.666, complete: true });
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("rolling windows subtract only known leaving work and retain uncertainty when contributions disappear", () => {
  const first = row("2026-10-01", 1);
  const second = { ...row("2026-10-02", 2, false), reliability: {
    productive: 1, attempted: 2, success_fraction: 0.5, production_factor: 0.5,
    from_day: first.date, through_day: "2026-10-02", complete: true,
  } };
  const current = row("2026-10-03", 3);
  const gaps: string[] = [];
  const input = {
    rows: [first, second], current: [current], days: [second.date, current.date], history_days: [first.date, second.date, current.date],
    now: "2026-10-03T12:00:00Z", floor: 0.5, window: 2,
    knownDay: () => true, onGap: (reason: string) => gaps.push(reason),
  };
  expect(reuseFeedReliability(input)).toMatchObject({
    productive: 1, attempted: 2, success_fraction: 0.5, from_day: second.date, through_day: current.date, complete: true,
  });

  expect(gaps).toEqual([]);
  expect(reuseFeedReliability({ ...input, knownDay: day => day !== first.date })).toMatchObject({
    productive: 1, attempted: 2, complete: false, from_day: second.date, through_day: current.date,
  });
  expect(gaps).toContain("reliability-window-contributions-missing");
  expect(reuseFeedReliability({ ...input, current: [], knownDay: day => day !== first.date })).toMatchObject({
    productive: 1, attempted: 2, complete: false, from_day: first.date, through_day: second.date,
  });
});

test("ambiguous check order cannot prove a failure episode and a later real reset restores certainty", async () => {
  const settings = await readLifecyclePolicy();
  const first = row("2026-10-01", 1);
  const failure = { ...row("2026-10-02", 2, false), checked_at: "2026-10-02T10:00:00Z" };
  const reset = { ...row("2026-10-02", 3), checked_at: "2026-10-02T10:00:00.500Z" };
  const gaps: string[] = [];
  const read = (rows: typeof first[]) => recoverFeedLifecycle(rows, "2026-10-04T00:00:00Z", settings, reason => gaps.push(reason));
  expect(read([first, failure, reset])).toMatchObject({
    availability: "unknown", strikes: null, first_confirmed_failure_at: null, retired_at: null, availability_complete: false,
  });
  expect(read([reset, failure, first])).toMatchObject({ strikes: null, availability_complete: false });
  expect(read([first, failure, reset, row("2026-10-03", 4)])).toMatchObject({
    strikes: 0, rest_until: null, retired_at: null, availability_complete: true,
  });
  expect(gaps).toContain("availability-order-ambiguous");
});
