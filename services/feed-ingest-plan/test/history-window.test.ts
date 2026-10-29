/** Are lifecycle, represented reliability and closed-day request spend independent bounded views? */
import { expect, test } from "bun:test";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { FeedHealthStateRowContract, FeedHealthStateRowSchema, SourceSnapshotSchema } from "@idhazh/common-contracts";
import type { FeedHealthStateRow } from "@idhazh/common-contracts";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { settleHealthRows, summarizePlanningHealth } from "../src/read-ledger-history/health-summary";
import { closedRequestDays, summarizeRequestReport } from "../src/read-ledger-history/request-summary";
import { projectFeedHealthFields } from "../src/read-ledger-history/read-feed-health-fields";
import { endpointKey, readFeedHistory as readPlanningHistory } from "../src/read-ledger-history/read-feed-history";
import { readRequestHistory } from "../src/read-ledger-history/read-request-history";
import { commitFixtureFiles, compactRows, registration, writeRows } from "./partition-fixtures";
import { fixtureGit } from "./publication-recordings";
import { defaultDayInput } from "../src/read-ledger-history/named-days";

const now = "2026-10-21T12:00:00Z";
async function readFeedHistory(input: Parameters<typeof readPlanningHistory>[0]) {
  const planning = await readPlanningHistory(input);
  const requests = await readRequestHistory(input);
  return { ...planning, request_report: requests.request_report };
}
function work(day = "2026-10-20", patch: Partial<FeedHealthStateRow> = {}) {
  const seed = plannerRecordings(day).find(record => record.name === "feed-health-state")!;
  return FeedHealthStateRowSchema.parse({
    ...seed.row, feed_id: "recorded-news", endpoint_key: endpointKey("https://news.example/feed.xml"), ...patch,
  });
}
async function input() {
  const loaded = await loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url)));
  const source = SourceSnapshotSchema.parse({
    feed_id: "recorded-news", feed_url: "https://news.example/feed.xml", title: "Recorded feed",
    publisher_id: null, tier: 2,
    status: "active", weight: 0.8, applied_tier_weight: 0.6,
  });
  return {
    loaded, sources: [source], now, policy: loaded.clock_config.collect, ...loaded.harvest.config.feedback,
  };
}
function summarize(setup: Awaited<ReturnType<typeof input>>, rows: FeedHealthStateRow[],
  patch: Partial<Omit<Parameters<typeof summarizePlanningHealth>[0], "uses"> & {
    request_days: { day: string; complete: boolean }[];
  }> = {}) {
  const request = {
    ...setup, rows,
    days: [...new Set(rows.map(row => row.date))].map(day => ({ day, complete: true })),
    request_days: closedRequestDays(now, setup.request_report_closed_days).map(day => ({ day, complete: true })), ...patch,
  };
  const settled = settleHealthRows(rows);
  const projections = [...new Set(settled.map(row => row.date))].map(day =>
    projectFeedHealthFields(day, settled.filter(row => row.date === day)));
  return {
    ...summarizePlanningHealth({ ...request, uses: {
      feed_rest: { rows: projections.flatMap(use => use.feed_rest.rows), gaps: projections.flatMap(use => use.feed_rest.gaps) },
      feed_reliability: { rows: projections.flatMap(use => use.feed_reliability.rows), gaps: projections.flatMap(use => use.feed_reliability.gaps) },
      article_admission: { rows: projections.flatMap(use => use.article_admission.rows), gaps: projections.flatMap(use => use.article_admission.gaps) },
    } }),
    request_report: summarizeRequestReport({ ...request, rows: settled, days: request.request_days }),
  };
}

test("default lifecycle, reliability and closed request windows stay independent at UTC boundaries", async () => {
  const setup = await input();
  expect(setup.lifecycle_window_days).toBe(31);
  expect(setup.policy.reliability_window_days).toBe(30);
  expect(setup.policy.reliability_floor).toBe(0.5);
  expect(setup.request_report_closed_days).toBe(7);
  expect(closedRequestDays("2026-11-01T23:59:59Z", 7)).toEqual([
    "2026-10-25", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31",
  ]);
  expect(closedRequestDays("2024-03-01T00:00:00Z", 2)).toEqual(["2024-02-28", "2024-02-29"]);
  expect(summarize(setup, []).request_report).toMatchObject({
    from_day: "2026-10-14", through_day: "2026-10-20", complete: true,
  });
});

test("closed request spend sums distinct attempts once without adding captured reliability", async () => {
  const setup = await input();
  const first = work(undefined, { article_requests: 3, reliability: {
    productive: 99, attempted: 100, success_fraction: 0.99, production_factor: 0.99,
    from_day: "2026-09-20", through_day: "2026-10-19", complete: true,
  } });
  const second = work(undefined, { attempt: 2, article_requests: 7, outcome: "permanent", status: 404,
    items: 0, productive_reads: 0, failed_reads: 1 });
  const anotherRun = work(undefined, { run_id: "2026-10-20-2", article_requests: 2,
    outcome: "transient", items: 0, productive_reads: 0, failed_reads: 1 });
  const result = summarize(setup, [first, structuredClone(first), second, anotherRun]);
  expect(result.request_report.feeds[0]).toEqual({
    feed_id: "recorded-news", feed_requests: 6, article_requests: 12, robots_requests: 0, counts_complete: true,
  });
  expect(result.sources.get("recorded-news")!.reliability).toMatchObject({
    productive: 1, attempted: 2, success_fraction: 0.5, production_factor: 0.5, complete: false,
  });
});

test("represented-day reliability excludes skips and honors its floor rather than counting calendar gaps", async () => {
  const setup = await input();
  const days = ["2026-01-01", "2026-05-01", "2026-10-20"].map(day => ({ day, complete: true }));
  const rows = [
    work("2026-01-01", { outcome: "permanent", items: 0 }),
    work("2026-05-01", { outcome: "skipped", items: 0, feed_reads: 0 }),
    work("2026-10-20", { outcome: "permanent", items: 0 }),
  ];
  const measured = summarize(setup, rows, { days, lifecycle_window_days: 3, policy: { ...setup.policy, reliability_window_days: 2 } });
  expect(measured.sources.get("recorded-news")!.reliability).toMatchObject({
    attempted: 1, productive: 0, from_day: "2026-05-01", through_day: "2026-10-20",
    success_fraction: 0, production_factor: 0.5, complete: true,
  });
  const substituted = summarize(setup, rows, { days, policy: { ...setup.policy, reliability_window_days: 3, reliability_floor: 0.8 } });
  expect(substituted.sources.get("recorded-news")!.reliability).toMatchObject({
    attempted: 2, productive: 0, from_day: "2026-01-01", production_factor: 0.8, complete: true,
  });
  const denied = summarize(setup, [work(undefined, { outcome: "robots_denied", items: 0, permission: "denied" })]);
  expect(denied.sources.get("recorded-news")!.reliability).toBeNull();
});

test("missing work, nullable counters and partial days never become measured zero or perfect reliability", async () => {
  const setup = await input();
  const unavailable = summarize(setup, [], { days: [], request_days: [] });
  expect(unavailable.sources.get("recorded-news")!.reliability).toBeNull();
  expect(unavailable.sources.get("recorded-news")!.lifecycle).toBe("unknown");
  expect(unavailable.request_report).toMatchObject({ complete: false, feeds: [{
    counts_complete: false, article_requests: null, feed_requests: null, robots_requests: null,
  }] });
  const unknown = summarize(setup, [work(undefined, {
    counts_complete: false, article_requests: null, feed_requests: 0, robots_requests: 0,
    checked_at: null, outcome: null, items: null,
  })]);
  expect(unknown.sources.get("recorded-news")!.reliability).toBeNull();
  expect(unknown.request_report.feeds[0]).toMatchObject({ counts_complete: false, article_requests: null, feed_requests: null });
  const partial = summarize(setup, [work()], {
    request_days: closedRequestDays(now, 7).map(day => ({ day, complete: day !== "2026-10-18" })),
  });
  expect(partial.request_report.complete).toBe(false);
  expect(partial.request_report.feeds[0]!.article_requests).toBeNull();
});

test("precise, legacy and tied timestamps preserve the recorded lifecycle uncertainty", async () => {
  const setup = await input();
  const recorded = await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/health-order-cases.json", import.meta.url,
  )).json() as {
    threshold: number; run_suffixes: [string, string];
    cases: { id: string; times: [string, string]; kinds: [FeedHealthStateRow["outcome"], FeedHealthStateRow["outcome"]];
      statuses: [number | null, number | null]; expected: "eligible" | "resting" | "retired" | "unknown" }[];
  };
  const sources = recorded.cases.map(testCase => SourceSnapshotSchema.parse({
    ...setup.sources[0], feed_id: testCase.id, feed_url: `${setup.sources[0]!.feed_url}?ordering=${testCase.id}`,
    status: testCase.id === "known-retired" ? "retired" : "active",
  }));
  const rows = recorded.cases.flatMap((testCase, sourceIndex) => recorded.run_suffixes.map((suffix, index) => work(undefined, {
    feed_id: testCase.id, endpoint_key: endpointKey(sources[sourceIndex]!.feed_url),
    run_id: `2026-10-20-${suffix}`, checked_at: `2026-10-20T10:00:00${testCase.times[index]}`,
    outcome: testCase.kinds[index]!, status: testCase.statuses[index]!, items: testCase.kinds[index] === "ok" ? 3 : 0,
  })));
  const forward = summarize(setup, rows, {
    sources, lifecycle_window_days: 1,
    policy: { ...setup.policy, availability_strikes_before_rest: recorded.threshold },
  });
  const reverse = summarize(setup, [...rows].reverse(), {
    sources, lifecycle_window_days: 1,
    policy: { ...setup.policy, availability_strikes_before_rest: recorded.threshold },
  });
  for (const testCase of recorded.cases) {
    expect(forward.sources.get(testCase.id)!.lifecycle, testCase.id).toBe(testCase.expected);
    expect(reverse.sources.get(testCase.id), testCase.id).toEqual(forward.sources.get(testCase.id)!);
  }
});

test("incomplete lifecycle history cannot establish a resting feed", async () => {
  const setup = await input();
  const rows = Array.from({ length: setup.policy.availability_strikes_before_rest }, (_, index) =>
    work(undefined, {
      run_id: `2026-10-20-${index + 1}`,
      checked_at: `2026-10-20T06:00:0${index}Z`,
      outcome: "transient",
      items: 0,
    }));
  const days = closedRequestDays(now, setup.lifecycle_window_days).map(day => ({ day, complete: true }));
  const complete = summarize(setup, rows, { days });
  expect(complete.sources.get("recorded-news")!.lifecycle).toBe("resting");
  const partial = summarize(setup, rows, {
    days: days.map(day => day.day === "2026-10-19" ? { ...day, complete: false } : day),
  });
  expect(partial.sources.get("recorded-news")).toMatchObject({
    lifecycle: "unknown", strikes: null, rested_runs: null,
  });
});

test("a changed feed URL inherits neither the old endpoint reliability nor its request spend", async () => {
  const setup = await input();
  const source = { ...setup.sources[0]!, feed_url: "https://news.example/changed.xml" };
  const result = summarize(setup, [work()], { sources: [source] });
  expect(result.sources.get(source.feed_id)).toMatchObject({
    endpoint_key: endpointKey(source.feed_url), lifecycle: "unknown", strikes: null, rested_runs: null, reliability: null,
  });
  expect(result.request_report.feeds[0]).toMatchObject({
    feed_requests: 0, article_requests: 0, robots_requests: 0, counts_complete: true,
  });
});

test("logical productive-read settlement never erases a lower attempt's dispatched work", async () => {
  const setup = await input();
  const first = work(undefined, { outcome: "ok", items: 2, article_requests: 4 });
  const retry = work(undefined, { attempt: 2, outcome: "permanent", status: 410,
    items: 0, productive_reads: 0, failed_reads: 1, article_requests: 6 });
  const result = summarize(setup, [first, retry, first]);
  expect(result.sources.get("recorded-news")!.reliability).toMatchObject({ productive: 1, attempted: 1, success_fraction: 1 });
  expect(result.request_report.feeds[0]!.article_requests).toBe(10);
  expect(() => summarize(setup, [first, { ...first, article_requests: 99 }])).toThrow("Conflicting copies");
});

test("known-empty closed days contribute zero while today's and future work stay out of the spend window", async () => {
  const setup = await input();
  const empty = summarize(setup, []);
  expect(empty.represented_days).toEqual([]);
  expect(empty.request_report.feeds[0]).toMatchObject({
    counts_complete: true, feed_requests: 0, article_requests: 0, robots_requests: 0,
  });
  const result = summarize(setup, [
    work("2026-10-21", { article_requests: 100 }),
    work("2026-10-22", { article_requests: 200 }),
    work("2026-10-13", { article_requests: 300 }),
    work("2026-10-20", { article_requests: 2 }),
  ]);
  expect(result.request_report.feeds[0]!.article_requests).toBe(2);
  expect(result.represented_days).not.toContain("2026-10-22");
});

test("native history reads only named current-family days and rejects unbounded or repeated inventories", async () => {
  const setup = await input();
  const root = await mkdtemp(join(tmpdir(), "planner-health-window-"));
  try {
    const written = await writeRows(join(root, "state"), "feed-health-state", "2026-10-20",
      FeedHealthStateRowContract, [work()]);
    const rawFiles = written.files.map(file => `state/${file.path}`);
    await commitFixtureFiles(root, rawFiles);
    const rawRevision = await fixtureGit(root, ["rev-parse", "--verify", "HEAD"]);
    await writeFile(join(root, "outside-unrequested.parquet"), "not a ledger and never an input");
    const request = {
      ...setup, root, concurrency: 2, health: registration("feed-health-state"),
      health_days: [{ day: "2026-10-20", raw_revision: rawRevision, raw_files: rawFiles }],
    };
    const loaded = await readFeedHistory(request);
    expect(loaded.uses.feed_rest.rows).toEqual([expect.objectContaining({
      run_id: work().run_id, outcome: work().outcome, items: work().items,
    })]);
    expect(loaded.represented_days).toContain("2026-10-20");
    await expect(readFeedHistory({ ...request, health_days: [...request.health_days, ...request.health_days] })).rejects.toThrow("distinct");
    await expect(readFeedHistory({ ...request, health_days: [{ day: "2026-10-22", raw_files: [] }] })).rejects.toThrow("past UTC days");
    await expect(readFeedHistory({
      ...request, health_days: Array.from({ length: 39 }, () => request.health_days[0]!),
    })).rejects.toThrow("bounds");

    const dailyRoot = join(root, "daily-window");
    const dailyState = join(dailyRoot, "state");
    const earlier = work("2026-01-01", {
      outcome: "permanent", items: 0, productive_reads: 0, failed_reads: 1,
    });
    const recent = work("2026-10-20", {
      outcome: "permanent", items: 0, productive_reads: 0, failed_reads: 1, article_requests: 3,
    });
    const dailyInputs = await Promise.all([earlier, recent].map(async row => {
      const raw = await writeRows(dailyState, "feed-health-state", row.date, FeedHealthStateRowContract, [row]);
      return { day: row.date, raw_files: raw.files.map(file => `state/${file.path}`) };
    }));
    await commitFixtureFiles(dailyRoot, dailyInputs.flatMap(input => input.raw_files));
    const dailyRevision = await fixtureGit(dailyRoot, ["rev-parse", "--verify", "HEAD"]);
    const committedDailyInputs = dailyInputs.map(input => ({ ...input, raw_revision: dailyRevision }));
    const daily = await readFeedHistory({
      ...request, root: dailyRoot, health_days: [...committedDailyInputs,
        ...closedRequestDays(now, 7).filter(day => day !== recent.date).map(day => ({
          ...defaultDayInput(registration("feed-health-state").prefix, day),
          raw_revision: dailyRevision, raw_files: [],
        }))], lifecycle_window_days: 2,
      policy: { ...setup.policy, reliability_window_days: 2, availability_strikes_before_rest: 2 },
    });
    expect(daily.represented_days).toEqual([earlier.date, recent.date]);
    expect(daily.days.map(day => day.day)).toEqual(daily.represented_days);
    expect(daily.sources.get("recorded-news")).toMatchObject({
      lifecycle: "resting", strikes: 2,
      reliability: { attempted: 2, productive: 0, from_day: earlier.date, through_day: recent.date, complete: true },
    });
    expect(daily.request_report).toMatchObject({
      complete: true, feeds: [{ article_requests: 3, counts_complete: true }],
    });

    const monthDays = Array.from({ length: 31 }, (_, index) => `2026-10-${String(index + 1).padStart(2, "0")}`);
    const packedRows = [
      work("2026-10-01", { outcome: "permanent", items: 0, productive_reads: 0, failed_reads: 1 }),
      work("2026-10-02", { outcome: "robots_denied", permission: "denied", items: 0, productive_reads: 0, failed_reads: 0 }),
      work("2026-10-03", { outcome: "skipped", items: 0, feed_reads: 0, productive_reads: 0, failed_reads: 0 }),
      work("2026-10-30", { outcome: "permanent", items: 0, productive_reads: 0, failed_reads: 1, article_requests: 3 }),
    ];
    for (const period of ["monthly", "yearly"] as const) {
      const periodRoot = join(root, period);
      const state = join(periodRoot, "state");
      const compact = await compactRows(state, "feed-health-state", "2026-10-30",
        FeedHealthStateRowContract, packedRows, period, periodRoot);
      const old = work("2026-09-30", { outcome: "permanent", items: 0, productive_reads: 0, failed_reads: 1 });
      const oldRaw = await writeRows(state, "feed-health-state", old.date, FeedHealthStateRowContract, [old]);
      const original = packedRows.at(-1)!;
      const late = { ...original, attempt: 2, checked_at: "2026-10-30T16:00:00Z", article_requests: 5 };
      const copies = await Promise.all([original, late].map(row =>
        writeRows(state, "feed-health-state", row.date, FeedHealthStateRowContract, [row])));
      const rawPaths = [...oldRaw.files, ...copies.flatMap(result => result.files)]
        .map(file => `state/${file.path}`);
      await commitFixtureFiles(periodRoot, rawPaths);
      const raw_revision = await fixtureGit(periodRoot, ["rev-parse", "--verify", "HEAD"]);
      const healthDays = [
        { day: old.date, raw_revision, raw_files: oldRaw.files.map(file => `state/${file.path}`) },
        ...monthDays.map(day => ({
          day, raw_revision, raw_files: day !== original.date ? []
            : copies.flatMap(result => result.files.map(file => `state/${file.path}`)),
        })),
      ];
      const periodRequest = { ...request, root: periodRoot, now: "2026-10-31T12:00:00Z", health_days: healthDays,
        policy: { ...setup.policy, availability_strikes_before_rest: 2 } };
      const packed = await readFeedHistory(periodRequest);
      expect(packed.represented_days).toEqual([old.date, ...monthDays]);
      expect(packed.days.every(day => day.complete)).toBe(true);
      expect(packed.uses.feed_rest.rows).toHaveLength(6);
      expect(packed.uses.feed_rest.rows.filter(row => row.date === original.date).map(row => row.attempt).sort()).toEqual([1, 2]);
      expect(packed.sources.get("recorded-news")).toMatchObject({
        lifecycle: "resting", strikes: 2,
        reliability: {
          attempted: 1, productive: 0, from_day: "2026-10-02", through_day: "2026-10-31",
          success_fraction: 0, production_factor: 0.5, complete: true,
        },
      });
      expect(packed.request_report).toMatchObject({
        complete: true, from_day: "2026-10-24", through_day: "2026-10-30",
        feeds: [{ article_requests: 8, counts_complete: true }],
      });
      const beforeMidnight = await readFeedHistory({
        ...periodRequest, now: "2026-10-30T23:59:59Z", health_days: healthDays.filter(day => day.day !== "2026-10-31"),
      });
      expect(beforeMidnight.represented_days).not.toContain("2026-10-31");
      expect(beforeMidnight.sources.get("recorded-news")).toMatchObject({
        strikes: 3, reliability: { attempted: 2, from_day: "2026-10-01", through_day: "2026-10-30", complete: true },
      });
      const compactBytes = await readFile(compact.path!);
      const failureRequest = {
        ...periodRequest,
        health_days: [{
          day: original.date, raw_revision,
          raw_files: copies.flatMap(result => result.files.map(file => `state/${file.path}`)),
        }],
      };
      await writeFile(compact.path!, new Uint8Array([1, 2, 3]));
      const refused = await readFeedHistory(failureRequest);
      expect(refused.sources.get("recorded-news")!.reliability).toMatchObject({ attempted: 1, complete: false });
      expect(refused.request_report).toMatchObject({
        complete: false, feeds: [{ article_requests: null, counts_complete: false }],
      });
      await writeFile(compact.path!, compactBytes);
      await rm(compact.path!);
      const missing = await readFeedHistory(failureRequest);
      expect(missing.sources.get("recorded-news")!.reliability).toMatchObject({ attempted: 1, complete: false });
      expect(missing.request_report).toMatchObject({
        complete: false, feeds: [{ article_requests: null, counts_complete: false }],
      });
    }
  } finally { await rm(root, { recursive: true, force: true }); }
}, 120_000);
