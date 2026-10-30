/** Does optional reporting preserve body-free observations without inventing saved output? */
import { test, expect } from "bun:test";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { FeedIngestConfigSchema, readFeedIngestEvent } from "../../../packages/common-contracts/src/index";
import { prepareProgressEvent } from "../src/logging/structured-logger";
import { writePlannerReport } from "../scripts/feed-ingest-plan-report";
import { formatHostFingerprintSummary } from "../scripts/feed-ingest-plan-host-summary";
import { formatPolicyTable, formatWorkflowPolicy } from "../scripts/feed-ingest-plan-policy-report";
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
  expect(events.every(event => event.version === "2026-10-30T22:25")).toBe(true);
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
    expect(rendered).toContain(`<td>Logical processors</td><td>${host.row.cpu_logical_processors}</td>`);
    expect(rendered).toContain(`<td>Allowed processors</td><td>${host.row.cpu_allowed_processors}</td>`);
    expect(rendered).not.toContain("Live planner process");
  } finally { await f.cleanup(); }
  const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
  const policy = formatWorkflowPolicy({ config: {
    ...config, curate_articles: {
      ...config.curate_articles, article_quality_buckets: config.curate_articles.article_quality_buckets.map(rule =>
        ({ ...rule, ladder_hours: [6, 12] })),
    },
  },
    request: { article_limit: 10, shards: 4, partition_strategy: "bin-pack" },
    history: settings.collect, parser_concurrency: 4 }, true);
  expect(policy.notice).toContain("article limit: 10 (workflow override); article assignments: 4; strategy: bin-pack");
  for (const rule of config.curate_articles.article_quality_buckets) {
    expect(policy.rows.find(([name]) => name === `Tier ${rule.tier} age steps (hours)`))
      .toEqual([`Tier ${rule.tier} age steps (hours)`, "6 / 12", "configuration"]);
  }
  expect(policy.rows.find(([name]) => name === "Article limit")).toEqual(["Article limit", "10", "workflow override"]);
  expect(policy.rows.find(([name]) => name === "Policy config version")?.[1]).toBe(config.version);
  expect(policy.rows.find(([name]) => name === "Feed-status history (represented UTC days)")?.[1])
    .toBe(String(config.feedback.lifecycle_window_days));
  expect(policy.rows.find(([name]) => name === "Reliability history (represented UTC days)")?.[1])
    .toBe(String(settings.collect.reliability_window_days));
  expect(policy.rows.find(([name]) => name === "Request history (closed UTC days)")?.[1])
    .toBe(String(config.feedback.request_report_closed_days));
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

test("policy cells preserve effective JSON values and override sources without inventing enablement", async () => {
  const config = FeedIngestConfigSchema.parse(await Bun.file(
    new URL("../../../config/feed-ingest-plan.json", import.meta.url),
  ).json());
  const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
  const input = {
    config: { ...config, harvest: { ...config.harvest, concurrency: 7, fetch_timeout_ms: 4321 },
      curate_articles: { ...config.curate_articles, source_authority_weight: 1.25, source_reliability_penalty_enabled: false } },
    request: { article_limit: 17, shards: 3, partition_strategy: "round-robin" },
    history: { ...settings.collect, availability_strikes_before_rest: 4, reliability_floor: 0.3 },
    parser_concurrency: 2,
  };
  const before = structuredClone(input);
  const policy = formatWorkflowPolicy(input, false);
  const cells = Object.fromEntries(policy.rows.map(([label, value, source]) => [label, { value, source }]));
  expect(cells).toMatchObject({
    "Policy config version": { value: config.version },
    "Article limit": { value: "17", source: "workflow override" },
    "Article assignments": { value: "3", source: "workflow override" },
    "Assignment strategy": { value: "round-robin", source: "workflow override" },
    "Fetch concurrency": { value: "7", source: "configuration" },
    "Fetch timeout (ms)": { value: "4321" },
    "Parser workers": { value: "2" },
    "Authority coefficient": { value: "1.25" },
    "Article-pass adjustment enabled": { value: "false" },
    "Failing checks before rest": { value: "4" },
    "Rested runs before retry": { value: "4" },
    "Reliability floor (fraction)": { value: "0.3" },
  });
  expect(cells).not.toHaveProperty("Selection");
  expect(policy.notice).toContain("selection started: false");
  expect(formatWorkflowPolicy({ ...input, request: {} }, false).rows.find(([name]) => name === "Article limit"))
    .toEqual(["Article limit", String(config.curate_articles.article_limit), "configuration"]);
  const html = Bun.markdown.html(formatPolicyTable(input, false).summary);
  expect(html).toContain("<td>0.3</td>");
  expect(html).toContain("<td>false</td>");
  expect(html).toContain("<td>round-robin</td>");
  expect(html).toContain("<td>1.25</td>");
  expect(html).not.toContain("<th>Source</th>");
  expect(html).not.toContain("<td>workflow override</td>");
  expect(html).toContain("Workflow overrides: Article limit, Article assignments, Assignment strategy.");
  expect(input).toEqual(before);
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
