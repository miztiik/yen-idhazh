/** Does optional reporting preserve body-free observations without inventing saved output? */
import { test, expect } from "bun:test";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { FeedIngestConfigSchema, readFeedIngestEvent } from "../../../packages/common-contracts/src/index";
import { prepareProgressEvent } from "../src/logging/structured-logger";
import { writePlannerReport } from "../scripts/feed-ingest-plan-report";
import { formatHostFingerprintSummary } from "../scripts/feed-ingest-plan-host-summary";
import { formatWorkflowPolicy } from "../scripts/feed-ingest-plan-policy-report";
import { formatWorkflowAnnotation } from "../scripts/feed-ingest-plan-report-format";
import { renderPlannerProgressMarkdown } from "../src/reporting";
import { fixture as hostFixture } from "../../host-fingerprints/test/fixture";
import { captureLocalFingerprint } from "../../host-fingerprints/src/api/local-fingerprint";

async function fixture() {
  const rows: unknown[] = await Bun.file(
    new URL("../../../tests/fixtures/feed-ingest-plan/report-events.json", import.meta.url),
  ).json();
  return rows.map(readFeedIngestEvent);
}

test("reads current sparse progress and refuses hidden article or audit payloads", async () => {
  const events = await fixture();
  const before = structuredClone(events);
  expect(renderPlannerProgressMarkdown(events)).toEqual(renderPlannerProgressMarkdown(before));
  expect(events.every(event => event.version === "2026-10-29T08:00")).toBe(true);
  for (const changed of [
    { ...events[0], headers: { authorization: "private" } },
    { ...events[0], article_text: "Private article body" },
    { ...events[0], payload: { kind: "candidate_decision" } },
    { ...events[0], event_id: "a".repeat(64) },
    { ...events[0], correlation_id: "old-run-label" },
    { ...events[0], version: "2026-10-20" },
  ]) expect(() => renderPlannerProgressMarkdown([changed])).toThrow();
  expect(events).toEqual(before);
});

test("absent progress stays unavailable and zero counts do not certify publication", async () => {
  const events = await fixture();
  const before = JSON.stringify(events);
  const report = renderPlannerProgressMarkdown(events);
  expect(report.markdown).toContain("Progress does not prove saved output or publication.");
  expect(report.notices).toEqual([]);
  expect(JSON.stringify(events)).toBe(before);
  const empty = renderPlannerProgressMarkdown([]);
  expect(empty.markdown).toContain("No progress was supplied. The result is unavailable.");
  expect(empty.notices).toEqual([]);
  const zero = renderPlannerProgressMarkdown([{ ...events[0], phase: "completed", details: { output_count: 0, duration_ms: 0 } }]);
  expect(zero.markdown).toContain("duration&#95;ms");
  expect(zero.markdown).toContain("output&#95;count");
  expect(zero.markdown).toContain("&#58;0");
  expect(zero.markdown).not.toContain("publication completed");
  const unavailable = formatHostFingerprintSummary(undefined);
  expect(unavailable.notice).toContain("Host fingerprint unavailable");
  expect(unavailable.notice).not.toContain("0.00");
  const config = FeedIngestConfigSchema.parse(await Bun.file(
    new URL("../../../config/feed-ingest-plan.json", import.meta.url),
  ).json());
  const f = await hostFixture();
  try {
    const host = await captureLocalFingerprint(f.apiInput, { ...f.config, listen_port: 0 }, f.settings, {
      outputRoot: join(f.directory, "state"), inspection: f.inspection,
    });
    if (host.status !== "written") throw new Error("A report fixture requires completed host Parquet");
    const summary = formatHostFingerprintSummary({
      host_request: f.apiInput, host: { ...host, status: "recorded" },
    });
    expect(summary.notice).toContain("Host fingerprint recorded:");
    expect(summary.summary).toContain("Total machine RAM capacity");
    expect(summary.summary).not.toContain("CPU quota");
    expect(summary.summary).not.toContain("Fingerprint file");
    expect(summary.summary).not.toContain("Hardware fingerprint");
    const rendered = Bun.markdown.html(summary.summary);
    expect((rendered.match(/<table>/g) ?? [])).toHaveLength(1);
    expect(rendered).toContain("Measurement time (UTC)");
    expect(rendered).not.toContain("Live planner process");
  } finally { await f.cleanup(); }
  const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
  const policy = formatWorkflowPolicy({ config: {
    ...config, curate_articles: {
      ...config.curate_articles, article_quality_buckets: config.curate_articles.article_quality_buckets.map(rule =>
        ({ ...rule, ladder_hours: [6, 12] })),
    },
  },
    request: { freshness_hours: 2, article_limit: 10, shards: 4, partition_strategy: "bin-pack" },
    history: settings.collect, parser_concurrency: 4 }, true);
  expect(policy.notice).toContain("10 articles; 4 workers; bin-pack");
  expect(policy.rows.find(([name]) => name === "Article age windows")?.[1]).toBe(
    `${config.curate_articles.article_quality_buckets.map(rule => `Article-quality bucket ${rule.tier}: 2 hours`).join("; ")} (workflow override)`,
  );
  expect(policy.rows.find(([name]) => name === "Article limit")?.[1]).toBe("10 articles (workflow override)");
  expect(formatWorkflowPolicy(undefined, false).notice).toContain("defaults do not prove");
});

test("escapes command data and refuses URLs or arbitrary progress fields", async () => {
  const events = await fixture();
  const report = renderPlannerProgressMarkdown([{ ...events[0], phase: "failed",
    details: { failure_code: "NETWORK\r\n::error title=pwn::run | <script>` %" } }]);
  expect(report.notices).toHaveLength(1);
  const annotation = formatWorkflowAnnotation(report.notices[0]!);
  expect(annotation).not.toContain("\n");
  expect(annotation).not.toContain("\r");
  expect(annotation).toContain("%0A");
  expect(annotation).toContain("%25");
  const unsafe = prepareProgressEvent({ ...events[0], details: { feed_url: "https://news.example/feed?token=private" } });
  expect(unsafe.details._compliance).toMatchObject({ status: "NON_COMPLIANT" });
  expect(JSON.stringify(unsafe)).not.toContain("news.example");
  expect(() => renderPlannerProgressMarkdown([{ ...events[0], url: "https://news.example/private" }])).toThrow();
});

test("publisher keeps flexible details and records missing or unsafe details without leaking values", async () => {
  const events = await fixture();
  const compliant = prepareProgressEvent({
    ...events[0],
    details: { feed_id: "recorded-news", publisher_id: null, extension: { enabled: true } },
  }, ["feed_id", "publisher_id"]);
  expect(compliant.details).toEqual({ feed_id: "recorded-news", publisher_id: null, extension: { enabled: true } });

  const nonCompliant = prepareProgressEvent({
    ...events[0],
    details: { feed_id: "recorded-news", article_text: "Private article body", _compliance: { status: "COMPLIANT" } },
  }, ["feed_id", "publisher_id"]);
  expect(nonCompliant.details._compliance).toMatchObject({
    status: "NON_COMPLIANT",
    violations: [
      { code: "unsafe_detail_key", path: "details" },
      { code: "reserved_publisher_field", path: "details" },
      { code: "required_detail_missing", path: "details.publisher_id" },
    ],
  });
  expect(JSON.stringify(nonCompliant)).not.toContain("Private article body");
  expect(renderPlannerProgressMarkdown([nonCompliant]).markdown).toContain("NON_COMPLIANT");

  const malformed = prepareProgressEvent({ ...events[0], details: "not-an-object" }, ["feed_id"]);
  expect(malformed.details._compliance).toMatchObject({
    status: "NON_COMPLIANT",
    violations: [
      { code: "details_must_be_object", path: "details" },
      { code: "required_detail_missing", path: "details.feed_id" },
    ],
  });
});

test("refuses mixed executions but permits concurrent stage ordering without fabricated sequence fields", async () => {
  const events = await fixture();
  expect(() => renderPlannerProgressMarkdown([events[0], { ...events[1], run_id: "2026-10-21-999" }])).toThrow("more than one run");
  expect(() => renderPlannerProgressMarkdown([events[0], { ...events[1], correlation_id: "040345df-230e-4bf9-8efc-d0d823fcde3b" }])).toThrow("more than one run");
  expect(() => renderPlannerProgressMarkdown([{ ...events[0], sequence: 1 }])).toThrow();
  expect(() => renderPlannerProgressMarkdown([events[1], events[0]])).not.toThrow();
});

test("disabled reporting reads no evidence and enabled reporting requires an explicit output path", async () => {
  const root = await mkdtemp(join(tmpdir(), "feed-report-"));
  try {
    const config = FeedIngestConfigSchema.parse(await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json());
    const summary = join(root, "summary.md");
    const lines: string[] = [];
    await writePlannerReport({
      config: { ...config, workflow_reporting: { ...config.workflow_reporting, enabled: false } },
      summary_path: summary, annotate: line => lines.push(line),
      get events(): never { throw new Error("Disabled reporting must not inspect progress"); },
      get evidence(): never { throw new Error("Disabled reporting must not inspect execution evidence"); },
    });
    expect(lines).toEqual([]);
    await expect(stat(summary)).rejects.toMatchObject({ code: "ENOENT" });
    const events = await fixture();
    const report = renderPlannerProgressMarkdown(events);
    const enabled = { ...config, workflow_reporting: { ...config.workflow_reporting, enabled: true } };
    await writePlannerReport({ config: enabled, events, summary_path: summary, annotate: line => lines.push(line) });
    expect(await readFile(summary, "utf8")).toBe(report.markdown);
    expect(lines).toEqual(report.notices.map(formatWorkflowAnnotation));
    await expect(writePlannerReport({ config: enabled, events, annotate: () => {} })).rejects.toThrow("summary output path");
  } finally { await rm(root, { recursive: true, force: true }); }
});
