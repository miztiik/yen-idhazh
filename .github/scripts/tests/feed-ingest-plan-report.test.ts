/** Does optional reporting preserve body-free observations without inventing saved output? */
import { test, expect } from "bun:test";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readFeedIngestEvent } from "../../../packages/common-contracts/src/index";
import { formatPlannerReport, writePlannerReport } from "../feed-ingest-plan-report";

async function fixture() {
  const rows: unknown[] = await Bun.file(
    new URL("../../../tests/fixtures/feed-ingest-plan/report-events.json", import.meta.url),
  ).json();
  return rows.map(readFeedIngestEvent);
}

test("reads current sparse progress and refuses hidden article or audit payloads", async () => {
  const events = await fixture();
  const before = structuredClone(events);
  expect(formatPlannerReport(events)).toEqual(formatPlannerReport(before));
  expect(events.every(event => event.version === "2026-10-25")).toBe(true);
  for (const changed of [
    { ...events[0], headers: { authorization: "private" } },
    { ...events[0], article_text: "Private article body" },
    { ...events[0], payload: { kind: "candidate_decision" } },
    { ...events[0], event_id: "a".repeat(64) },
    { ...events[0], correlation_id: "old-run-label" },
    { ...events[0], version: "2026-10-20" },
  ]) expect(() => formatPlannerReport([changed])).toThrow();
  expect(events).toEqual(before);
});

test("absent progress stays unavailable and zero counts do not certify publication", async () => {
  const events = await fixture();
  const before = JSON.stringify(events);
  const report = formatPlannerReport(events);
  expect(report.summary).toContain("Progress does not prove saved output or publication.");
  expect(report.annotations).toEqual([]);
  expect(JSON.stringify(events)).toBe(before);
  const empty = formatPlannerReport([]);
  expect(empty.summary).toContain("No progress was supplied. The result is unavailable.");
  expect(empty.annotations).toEqual([]);
  const zero = formatPlannerReport([{ ...events[0], phase: "completed", output_count: 0, duration_ms: 0 }]);
  expect(zero.summary).toContain("0 milliseconds");
  expect(zero.summary).not.toContain("publication completed");
});

test("escapes command data and refuses URLs or arbitrary progress fields", async () => {
  const events = await fixture();
  const report = formatPlannerReport([{ ...events[0], phase: "failed",
    failure_code: "NETWORK\r\n::error title=pwn::run | <script>` %" }]);
  expect(report.annotations).toHaveLength(1);
  expect(report.annotations[0]).not.toContain("\n");
  expect(report.annotations[0]).not.toContain("\r");
  expect(report.annotations[0]).toContain("%0A");
  expect(report.annotations[0]).toContain("%25");
  expect(() => formatPlannerReport([{ ...events[0], feed_id: "https://news.example/feed?token=private" }])).toThrow();
  expect(() => formatPlannerReport([{ ...events[0], url: "https://news.example/private" }])).toThrow();
});

test("refuses mixed executions but permits concurrent stage ordering without fabricated sequence fields", async () => {
  const events = await fixture();
  expect(() => formatPlannerReport([events[0], { ...events[1], run_id: "2026-10-21-999" }])).toThrow("more than one run");
  expect(() => formatPlannerReport([events[0], { ...events[1], correlation_id: "040345df-230e-4bf9-8efc-d0d823fcde3b" }])).toThrow("more than one run");
  expect(() => formatPlannerReport([{ ...events[0], sequence: 1 }])).toThrow();
  expect(() => formatPlannerReport([events[1], events[0]])).not.toThrow();
});

test("disabled reporting reads no evidence and enabled reporting requires an explicit output path", async () => {
  const root = await mkdtemp(join(tmpdir(), "feed-report-"));
  try {
    const config = await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();
    const summary = join(root, "summary.md");
    const lines: string[] = [];
    await writePlannerReport({
      config: { ...config, workflow_reporting: { ...config.workflow_reporting, enabled: false } },
      summary_path: summary, annotate: line => lines.push(line),
      get events(): never { throw new Error("Disabled reporting must not inspect progress"); },
    });
    expect(lines).toEqual([]);
    await expect(stat(summary)).rejects.toMatchObject({ code: "ENOENT" });
    const events = await fixture();
    const enabled = { ...config, workflow_reporting: { ...config.workflow_reporting, enabled: true } };
    await writePlannerReport({ config: enabled, events, summary_path: summary, annotate: line => lines.push(line) });
    expect(await readFile(summary, "utf8")).toBe(formatPlannerReport(events).summary);
    expect(lines).toEqual([...formatPlannerReport(events).annotations]);
    await expect(writePlannerReport({ config: enabled, events, annotate: () => {} })).rejects.toThrow("summary output path");
  } finally { await rm(root, { recursive: true, force: true }); }
});
