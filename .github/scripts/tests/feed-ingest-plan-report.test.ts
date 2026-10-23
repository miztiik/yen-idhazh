/** Does optional reporting preserve evidence and refuse unsafe or unsupported claims? */
import { test, expect } from "bun:test";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  FEED_INGEST_EVENT_VERSION, EXTRACTION_QUALITY_VERSION, readFeedIngestEvent,
} from "../../../packages/common-contracts/src/index";
import { formatPlannerReport, writePlannerReport } from "../feed-ingest-plan-report";

async function fixture() {
  const rows: unknown[] = await Bun.file(
    new URL("../../../tests/fixtures/feed-ingest-plan/report-events.json", import.meta.url),
  ).json();
  return rows.map(readFeedIngestEvent);
}

test("reads current UUID events and refuses undeclared identities without inventing facts", async () => {
  const raw: unknown[] = await Bun.file(
    new URL("../../../tests/fixtures/feed-ingest-plan/report-events.json", import.meta.url),
  ).json();
  expect(raw.map(readFeedIngestEvent).every(row => row.version === FEED_INGEST_EVENT_VERSION)).toBe(true);
  expect(formatPlannerReport(raw)).toEqual(formatPlannerReport(await fixture()));
  const recorded = await Bun.file(
    new URL("../../../tests/fixtures/contracts/feed-ingest-event/one-observation.json", import.meta.url),
  ).json();
  const before = structuredClone(recorded);
  const current = readFeedIngestEvent(recorded);
  expect(recorded).toEqual(before);
  expect(current.version).toBe(FEED_INGEST_EVENT_VERSION);
  if (current.payload.kind !== "candidate_decision") throw new Error("Expected a recorded candidate decision");
  expect(current.payload.assessment).toMatchObject({
    version: EXTRACTION_QUALITY_VERSION, timing_basis: "unavailable", timing_at: null, age_hours: null, diagnostics: null,
  });
  expect(formatPlannerReport([recorded])).toEqual(formatPlannerReport([current]));
  const known = structuredClone(recorded);
  known.payload.assessment.age_hours = 1;
  known.payload.assessment.max_age_hours = 48;
  known.payload.assessment.timing_basis = "published_at";
  known.payload.assessment.timing_at = "2026-10-20T07:00:00Z";
  const measured = readFeedIngestEvent(known);
  if (measured.payload.kind !== "candidate_decision") throw new Error("Expected a measured candidate decision");
  expect(measured.payload.assessment).toMatchObject({
    timing_basis: "published_at", timing_at: "2026-10-20T07:00:00Z", age_hours: 1, max_age_hours: 48,
  });
  const missing = structuredClone(recorded);
  delete missing.payload.assessment.timing_at;
  expect(() => formatPlannerReport([missing])).toThrow();
  expect(() => formatPlannerReport([{ ...recorded, headers: { authorization: "private" } }])).toThrow();
  expect(() => formatPlannerReport([{ ...recorded, candidate_id: "a".repeat(64) }])).toThrow();
  expect(() => formatPlannerReport([{ ...recorded, version: "2026-10-20" }])).toThrow();
  expect(() => formatPlannerReport([{ ...recorded, event_id: "c".repeat(64) }])).toThrow();
  expect(() => formatPlannerReport([{ ...recorded, correlation_id: "old-run-label" }])).toThrow();
});

test("reports explicit empty outcomes without certifying durable audit or publication", async () => {
  const events = await fixture();
  const before = JSON.stringify(events);
  const report = formatPlannerReport(events);
  expect(report.summary).toContain("| A1 | recorded&#45;source | Recorded RSS source | success / empty | 0 | 0 | FEED_EMPTY |");
  expect(report.summary).toContain("| B1 | harvest&#45;feeds | 1 | 0 | 1 | 0.012 |");
  expect(report.summary).toContain("**Audit completion: unavailable.**");
  expect(report.annotations).toHaveLength(1);
  expect(JSON.stringify(events)).toBe(before);
  expect(formatPlannerReport([]).summary).toContain("No events supplied");
});

test("escapes source text and excludes URLs, headers and arbitrary event fields", async () => {
  const events = await fixture();
  const feed = events[0]!;
  if (feed.payload.kind !== "feed_outcome") throw new Error("fixture requires feed_outcome");
  feed.payload.source.title = "bad\r\n::error title=pwn::run | [click](javascript:evil) <script>` %\u0085";
  feed.payload.source.feed_url = "https://news.example/feed?token=private";
  const report = formatPlannerReport(events);
  expect(report.summary).not.toContain("\n::error");
  expect(report.summary).not.toContain("| [click]");
  expect(report.summary).not.toContain("<script>");
  expect(report.summary).not.toContain("token=private");
  expect(report.summary).toContain("&#124;");
  expect(report.summary).toContain("&#58;&#58;error");
  expect(report.annotations.join("\n")).not.toContain("pwn");
  expect(() => formatPlannerReport([{ ...feed, headers: { authorization: "private" } }])).toThrow();
});

test("rejects invalid events and mixed or unordered attempts rather than summarizing them", async () => {
  const events = await fixture();
  expect(() => formatPlannerReport([{ ...events[0], audit_event_type: "candidate_decision" }])).toThrow();
  expect(() => formatPlannerReport([events[1], events[0]])).toThrow("sequence");
  expect(() => formatPlannerReport([events[0], { ...events[1], attempt: 2 }])).toThrow("attempt");
  expect(() => formatPlannerReport([events[0], { ...events[1], event_id: events[0]!.event_id }])).toThrow("event_id");
});

test("disabled reporting performs no writes or annotations and does not require evidence", async () => {
  const root = await mkdtemp(join(tmpdir(), "feed-report-"));
  try {
    const summaryPath = join(root, "summary.md");
    const lines: string[] = [];
    await writePlannerReport({ enabled: false, events: undefined, summaryPath, annotate: line => lines.push(line) });
    expect(lines).toEqual([]);
    await expect(stat(summaryPath)).rejects.toMatchObject({ code: "ENOENT" });
    const events = await fixture();
    await writePlannerReport({ enabled: true, events, summaryPath, annotate: line => lines.push(line) });
    expect(await readFile(summaryPath, "utf8")).toBe(formatPlannerReport(events).summary);
    expect(lines).toEqual([...formatPlannerReport(events).annotations]);
    await expect(writePlannerReport({ enabled: true, events, annotate: () => {} })).rejects.toThrow("GITHUB_STEP_SUMMARY");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
