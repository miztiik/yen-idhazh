/** Are lifecycle, represented reliability and closed-day request spend independent bounded views? */
import { expect, test } from "bun:test";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { FeedHealthStateRowContract, FeedHealthStateRowSchema, SourceSnapshotSchema } from "@idhazh/common-contracts";
import type { FeedHealthStateRow } from "@idhazh/common-contracts";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { closedRequestDays, summarizeHealth } from "../src/read-ledger-history/health-summary";
import { endpointKey, readFeedHistory } from "../src/read-ledger-history/read-feed-history";
import { registration, writeRows } from "./partition-fixtures";

const now = "2026-10-21T12:00:00Z";
function work(day = "2026-10-20", patch: Partial<FeedHealthStateRow> = {}) {
  const seed = plannerRecordings(day).find(record => record.name === "feed-health-state")!;
  return FeedHealthStateRowSchema.parse({
    ...seed.row, feed_id: "recorded-news", endpoint_key: endpointKey("https://news.example/feed.xml"), ...patch,
  });
}
async function input() {
  const loaded = await loadPlanInputs(fileURLToPath(new URL("../../../", import.meta.url)));
  const source = SourceSnapshotSchema.parse({
    source_id: "recorded-news", feed_url: "https://news.example/feed.xml", title: "Recorded feed",
    publisher_id: null, kind: "reporting", tier: 2,
    form: "article", status: "active", weight: 0.8, applied_tier_weight: 0.6,
  });
  return {
    loaded, sources: [source], now, policy: loaded.clock_config.collect, ...loaded.harvest.config.feedback,
  };
}
function summarize(setup: Awaited<ReturnType<typeof input>>, rows: FeedHealthStateRow[],
  patch: Partial<Parameters<typeof summarizeHealth>[0]> = {}) {
  return summarizeHealth({
    ...setup, rows,
    days: closedRequestDays(now, setup.request_report_closed_days).map(day => ({ day, complete: true })), ...patch,
  });
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
  const unavailable = summarize(setup, [], { days: [] });
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
    days: closedRequestDays(now, 7).map(day => ({ day, complete: day !== "2026-10-18" })),
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
    ...setup.sources[0], source_id: testCase.id, feed_url: `${setup.sources[0]!.feed_url}?ordering=${testCase.id}`,
    status: testCase.id === "known-retired" ? "retired" : "active",
  }));
  const rows = recorded.cases.flatMap((testCase, sourceIndex) => recorded.run_suffixes.map((suffix, index) => work(undefined, {
    feed_id: testCase.id, endpoint_key: endpointKey(sources[sourceIndex]!.feed_url),
    run_id: `2026-10-20-${suffix}`, checked_at: `2026-10-20T10:00:00${testCase.times[index]}`,
    outcome: testCase.kinds[index]!, status: testCase.statuses[index]!, items: testCase.kinds[index] === "ok" ? 3 : 0,
  })));
  const forward = summarize(setup, rows, { sources, policy: { ...setup.policy, availability_strikes_before_rest: recorded.threshold } });
  const reverse = summarize(setup, [...rows].reverse(), { sources, policy: { ...setup.policy, availability_strikes_before_rest: recorded.threshold } });
  for (const testCase of recorded.cases) {
    expect(forward.sources.get(testCase.id)!.lifecycle, testCase.id).toBe(testCase.expected);
    expect(reverse.sources.get(testCase.id), testCase.id).toEqual(forward.sources.get(testCase.id)!);
  }
});

test("a changed feed URL inherits neither the old endpoint reliability nor its request spend", async () => {
  const setup = await input();
  const source = { ...setup.sources[0]!, feed_url: "https://news.example/changed.xml" };
  const result = summarize(setup, [work()], { sources: [source] });
  expect(result.sources.get(source.source_id)).toMatchObject({
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
    const written = await writeRows(root, "feed-health-state", "2026-10-20", FeedHealthStateRowContract, [work()]);
    await writeFile(join(root, "outside-unrequested.parquet"), "not a ledger and never an input");
    const request = {
      ...setup, root, concurrency: 2, health: registration("feed-health-state"),
      health_days: [{ day: "2026-10-20", raw_files: written.files.map(file => file.path) }],
    };
    const loaded = await readFeedHistory(request);
    expect(loaded.rows).toEqual([work()]);
    expect(loaded.represented_days).toContain("2026-10-20");
    await expect(readFeedHistory({ ...request, health_days: [...request.health_days, ...request.health_days] })).rejects.toThrow("distinct");
    await expect(readFeedHistory({ ...request, health_days: [{ day: "2026-10-22", raw_files: [] }] })).rejects.toThrow("past UTC days");
    await expect(readFeedHistory({
      ...request, health_days: Array.from({ length: 39 }, () => request.health_days[0]!),
    })).rejects.toThrow("bounds");
  } finally { await rm(root, { recursive: true, force: true }); }
});
