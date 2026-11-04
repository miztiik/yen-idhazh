/** Does optional reporting preserve body-free observations without inventing saved output? */
import { test, expect } from "bun:test";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { FeedIngestConfigSchema, readFeedIngestEvent } from "../../../packages/common-contracts/src/index";
import { prepareProgressEvent } from "../src/logging/structured-logger";
import { resolveWorkflowGuideUrl, writePlannerReport } from "../scripts/feed-ingest-plan-report";
import { formatHostFingerprintSummary } from "../scripts/feed-ingest-plan-host-summary";
import { formatPolicyTable, formatWorkflowPolicy } from "../scripts/feed-ingest-plan-policy-report";
import { formatWorkflowAnnotation } from "../scripts/feed-ingest-plan-report-format";
import { renderPlannerProgressMarkdown } from "../src/reporting";
import { WorkflowHostFingerprintSchema } from "../scripts/feed-ingest-plan-host-fingerprint";
import { renderSelectedEvidence } from "../src/reporting/selected-evidence-markdown";
import { parseHTML } from "linkedom";

async function fixture() {
  const rows: unknown[] = await Bun.file(
    new URL("../../../tests/fixtures/feed-ingest-plan/report-events.json", import.meta.url),
  ).json();
  return rows.map(readFeedIngestEvent);
}

test("selected evidence preserves measured zero and refuses incomplete or foreign saved rows", async () => {
  const row = await Bun.file(new URL(
    "../../../tests/fixtures/ledger-file-writer/feed-ingest-dispatch-row.json", import.meta.url)).json();
  const run = { run_id: row.run_id, attempt: row.attempt, selected_count: 1 };
  const document = parseHTML(Bun.markdown.html(renderSelectedEvidence([row], run))).document;
  const cells = [...document.querySelectorAll("tbody td")].map(cell => cell.textContent);
  expect(cells).toEqual(["J1", "1", row.feed_id, "180", "0", "1", "0", "1.5", "1.25", "First recorded sighting"]);
  const before = structuredClone(row);
  const config = FeedIngestConfigSchema.parse(await Bun.file(
    new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json());
  const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
  const display = formatWorkflowPolicy({
    config: { ...config, workflow_reporting: { ...config.workflow_reporting, score_decimal_places: 0 } },
    request: {}, history: settings.collect, parser_concurrency: 1,
  }, true);
  const rounded = parseHTML(Bun.markdown.html(
    renderSelectedEvidence([row], run, display.score_decimal_places))).document;
  expect([...rounded.querySelectorAll("tbody td")].map(cell => cell.textContent).slice(6, 9)).toEqual(["0", "2", "1"]);
  expect(rounded.querySelector("details")!.textContent).toContain("rounded to 0 decimal places");
  expect(row).toEqual(before);
  expect(document.querySelector("details")!.textContent).not.toContain(row.canonical_url);
  expect(renderSelectedEvidence(undefined, run)).toContain("unavailable");
  expect(renderSelectedEvidence([], { ...run, selected_count: 0 })).toContain("zero articles");
  expect(() => renderSelectedEvidence([], run)).toThrow("complete execution");
  expect(() => renderSelectedEvidence([{ ...row, attempt: row.attempt + 1 }], run)).toThrow("complete execution");
  expect(() => renderSelectedEvidence([{ ...row, substance_word_count: null }], run)).toThrow("substance_word_count");
});

test("links the workflow guide at the recorded GitHub commit without assuming a repository", () => {
  expect(resolveWorkflowGuideUrl({})).toBeUndefined();
  expect(() => resolveWorkflowGuideUrl({ GITHUB_REPOSITORY: "project/repository" })).toThrow("server URL and commit SHA");
  expect(resolveWorkflowGuideUrl({
    GITHUB_REPOSITORY: "project/repository", GITHUB_SERVER_URL: "https://github.example", GITHUB_SHA: "a".repeat(40),
  })).toBe(`https://github.example/project/repository/blob/${"a".repeat(40)}/docs/how-to/run-feed-ingest-plan-test.md`);
});

test("reads current sparse progress and refuses hidden article or audit payloads", async () => {
  const events = await fixture();
  const before = structuredClone(events);
  expect(renderPlannerProgressMarkdown(events)).toEqual(renderPlannerProgressMarkdown(before));
  for (const changed of [
    { ...events[0], headers: { authorization: "private" } },
    { ...events[0], article_text: "Private article body" },
    { ...events[0], payload: { kind: "candidate_decision" } },
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
  const zero = renderPlannerProgressMarkdown([{ ...events[0],
    data: { ...events[0]!.data, phase: "completed", details: { output_count: 0, duration_ms: 0 } } }]);
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
    const evidence = WorkflowHostFingerprintSchema.parse(await Bun.file(new URL(
      "../../../tests/fixtures/feed-ingest-plan/host-report.json", import.meta.url)).json());
    if (evidence.host.status !== "recorded") throw new Error("The host report recording must contain its actual native row");
    const host = evidence.host;
    const summary = formatHostFingerprintSummary(evidence);
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
  const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
  const policy = formatWorkflowPolicy({ config: {
    ...config, curate_articles: {
      ...config.curate_articles, global_age_ceiling_hours: 12,
    },
  },
    request: { article_limit: 10, shards: 4, partition_strategy: "bin-pack" },
    history: settings.collect, parser_concurrency: 4 }, true);
  expect(policy.notice).toContain("article limit: 10 (workflow override); article assignments: 4; strategy: bin-pack");
  expect(policy.rows.find(([name]) => name === "Maximum known age (hours)"))
    .toEqual(["Maximum known age (hours)", "12", "configuration"]);
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
  const report = renderPlannerProgressMarkdown([{ ...events[0], data: { ...events[0]!.data, phase: "failed",
    details: { failure_code: "NETWORK\r\n::error title=pwn::run | <script>` %" } } }]);
  expect(report.notices).toHaveLength(1);
  const annotation = formatWorkflowAnnotation(report.notices[0]!);
  expect(annotation).not.toContain("\n");
  expect(annotation).not.toContain("\r");
  expect(annotation).toContain("%0A");
  expect(annotation).toContain("%25");
  const unsafe = prepareProgressEvent({ ...events[0],
    data: { ...events[0]!.data, details: { feed_url: "https://news.example/feed?token=private" } } });
  expect(unsafe.data.details._compliance).toMatchObject({ status: "NON_COMPLIANT" });
  expect(JSON.stringify(unsafe)).not.toContain("news.example");
  expect(() => renderPlannerProgressMarkdown([{ ...events[0], url: "https://news.example/private" }])).toThrow();
});

test("effective report separates raw admission from active soft scoring without retired controls", async () => {
  const config = FeedIngestConfigSchema.parse(await Bun.file(
    new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json());
  const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
  const input = { config, request: {}, history: settings.collect, parser_concurrency: 2 };
  const policy = formatWorkflowPolicy(input, true);
  const cells = Object.fromEntries(policy.rows.map(([label, value]) => [label, value]));
  expect(cells).toMatchObject({
    "Raw technical minimum (full-body words)": "180",
    "Substance scoring": "Measured once and cached in the base score",
    "Retained-word admission minimum": "None; measured zero stays eligible",
    "Paragraph retention (minimum words OR sentences)": "25 words OR 2 sentences",
    "Retained-word full-credit start (words)": "750",
    "Retained-word full-credit end (words)": "3500",
    "Retained-word taper end (words)": "6000",
    "Length points at full credit": "1",
    "Length points after taper": "0.8",
    "Maximum name/number-density points": "0.3",
    "Name/number signals per sentence for full credit": "1",
    "Maximum headline deduction (points)": "0.25",
    "Maximum known age (hours)": String(config.curate_articles.global_age_ceiling_hours),
    "Unknown age": "Eligible with null timing and zero recency points",
    "Website squared-count penalty coefficient": String(config.curate_articles.diversity.lambda_domain),
    "Feed squared-count penalty coefficient": String(config.curate_articles.diversity.lambda_feed),
    "First-use feed bonus (points)": String(config.curate_articles.diversity.novelty_bonus),
  });
  expect(cells["Retained-word length curve"]).toContain("zero words / zero points");
  expect(policy.notice).toContain("included in the base score");
  for (const retired of ["Per-feed share limit (fraction)", "Exploration share (fraction)", "Publisher exposure weight"]) {
    expect(cells).not.toHaveProperty(retired);
  }
  const changed = structuredClone(input);
  changed.config.triage.min_words = 200;
  Object.assign(changed.config.curate_articles.substance, {
    substantive_paragraph_min_words: 30, substantive_paragraph_min_sentences: 3,
    word_count_ramp_end: 500, word_count_sweet_spot_max: 2000, word_count_plateau_start: 4000,
    length_scores: { full: 2 }, long_form_floor_score: 0.6,
  });
  const rendered = parseHTML(Bun.markdown.html(formatPolicyTable(changed, true).summary)).document;
  const changedCells = Object.fromEntries([...rendered.querySelectorAll("tbody tr")].map(row => {
    const columns = [...row.querySelectorAll("td")].map(cell => cell.textContent);
    return [columns[1], columns[2]];
  }));
  expect(changedCells).toMatchObject({
    "Raw technical minimum (full-body words)": "200",
    "Paragraph retention (minimum words OR sentences)": "30 words OR 3 sentences",
    "Retained-word full-credit start (words)": "500",
    "Retained-word full-credit end (words)": "2000",
    "Retained-word taper end (words)": "4000",
    "Length points at full credit": "2",
    "Length points after taper": "0.6",
  });
  expect(changedCells["Retained-word length curve"]).toContain("4000 words; then constant");
});

test("policy cells preserve effective JSON values and override sources without inventing enablement", async () => {
  const config = FeedIngestConfigSchema.parse(await Bun.file(
    new URL("../../../config/feed-ingest-plan.json", import.meta.url),
  ).json());
  const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
  const input = {
    config: { ...config, availability: { ...config.availability, consecutive_failed_checks_before_rest: 4 },
      harvest: { ...config.harvest, concurrency: 7, fetch_timeout_ms: 4321 },
      curate_articles: { ...config.curate_articles, source_authority_weight: 1.25, source_reliability_penalty_enabled: false } },
    request: { article_limit: 17, shards: 3, partition_strategy: "round-robin", global_age_ceiling_hours: 24 },
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
    "Fetch timeout per HTTP attempt (ms)": { value: "4321" },
    "Parser workers": { value: "2" },
    "Estimated source authority coefficient": { value: "1.25" },
    "Article-pass adjustment enabled": { value: "false" },
    "Availability controls": { value: "Recorded" },
    "Consecutive failed logical checks before rest": { value: "4", source: "configuration" },
    "Reliability floor (fraction)": { value: "0.3" },
    "Maximum known age (hours)": { value: "24", source: "workflow override" },
  });
  expect(cells).not.toHaveProperty("Selection");
  expect(policy.notice).toContain("selection started: false");
  expect(formatWorkflowPolicy({ ...input, request: {} }, false).rows.find(([name]) => name === "Article limit"))
    .toEqual(["Article limit", String(config.curate_articles.article_limit), "configuration"]);
  const documentationUrl = "https://github.example/project/repository/blob/current/docs/how-to/run-feed-ingest-plan-test.md";
  const summary = formatPolicyTable(input, false, documentationUrl).summary;
  const html = Bun.markdown.html(summary);
  const { document } = parseHTML(html);
  const fold = document.querySelector("details")!;
  expect(fold.hasAttribute("open")).toBe(false);
  expect(fold.querySelector("summary")?.textContent).toBe("Effective settings");
  expect(fold.querySelectorAll("table")).toHaveLength(1);
  expect(fold.querySelector("a")?.getAttribute("href")).toBe(documentationUrl);
  expect(html).toContain("<td>0.3</td>");
  expect(html).toContain("<td>false</td>");
  expect(html).toContain("<td>round-robin</td>");
  expect(html).toContain("<td>1.25</td>");
  expect(html).toContain("<th>Source</th>");
  expect(html).toContain("<td>workflow override</td>");
  for (const request of [{}, input.request]) {
    const report = formatPolicyTable({ ...input, request }, false).summary;
    for (const removed of [
      "Workflow overrides:", "Other controls use configuration;",
      "The article limit is a maximum.", "Shares and the reliability floor use the JSON fractions:",
      "Authority multiplies the coefficient", "A valid parsed feed, even empty,",
      "Retirement needs both configured gates", "Source authority estimates expected quality;",
      "bin-pack balances estimated article work;",
    ]) expect(report).not.toContain(removed);
  }
  const bypass = { ...input, config: { ...input.config, partition: { ...input.config.partition, enabled: false } } };
  const bypassPolicy = formatWorkflowPolicy(bypass, false);
  expect(bypassPolicy.rows.find(([name]) => name === "Article assignments"))
    .toEqual(["Article assignments", "0", "ignored workflow override"]);
  expect(bypassPolicy.rows.find(([name]) => name === "Assignment strategy"))
    .toEqual(["Assignment strategy", "bypassed", "ignored workflow override"]);
  const bypassReport = formatPolicyTable(bypass, false).summary;
  expect(bypassReport).not.toContain("Workflow overrides:");
  expect(bypassReport).toContain("Ignored workflow inputs because worker assignment is disabled: Article assignments, Assignment strategy.");
  expect(parseHTML(Bun.markdown.html(bypassReport)).document.querySelector("details")?.textContent)
    .toContain("Ignored workflow inputs because worker assignment is disabled:");
  const missing = parseHTML(Bun.markdown.html(formatPolicyTable(undefined, false).summary)).document;
  expect(missing.querySelector("details")?.textContent).toContain("Policy evidence was not supplied");
  expect(missing.querySelector("td")?.textContent).toBe("G1");
  expect(formatWorkflowPolicy({ ...bypass, request: {} }, false).rows.find(([name]) => name === "Article assignments"))
    .toEqual(["Article assignments", "0", "partition disabled"]);
  expect(input).toEqual(before);
});

test("publisher keeps flexible details and records missing or unsafe details without leaking values", async () => {
  const events = await fixture();
  const compliant = prepareProgressEvent({
    ...events[0],
    data: { ...events[0]!.data, details: { feed_id: "recorded-news", publisher_id: null, extension: { enabled: true } } },
  }, ["feed_id", "publisher_id"]);
  expect(compliant.data.details).toEqual({ feed_id: "recorded-news", publisher_id: null, extension: { enabled: true } });

  const nonCompliant = prepareProgressEvent({
    ...events[0],
    data: { ...events[0]!.data,
      details: { feed_id: "recorded-news", article_text: "Private article body", _compliance: { status: "COMPLIANT" } } },
  }, ["feed_id", "publisher_id"]);
  expect(nonCompliant.data.details._compliance).toMatchObject({
    status: "NON_COMPLIANT",
    violations: [
      { code: "unsafe_detail_key", path: "details" },
      { code: "reserved_publisher_field", path: "details" },
      { code: "required_detail_missing", path: "details.publisher_id" },
    ],
  });
  expect(JSON.stringify(nonCompliant)).not.toContain("Private article body");
  expect(renderPlannerProgressMarkdown([nonCompliant]).markdown).toContain("NON_COMPLIANT");

  const malformed = prepareProgressEvent({ ...events[0], data: { ...events[0]!.data, details: "not-an-object" } }, ["feed_id"]);
  expect(malformed.data.details._compliance).toMatchObject({
    status: "NON_COMPLIANT",
    violations: [
      { code: "details_must_be_object", path: "details" },
      { code: "required_detail_missing", path: "details.feed_id" },
    ],
  });
});

test("refuses mixed runs but permits concurrent stage ordering", async () => {
  const events = await fixture();
  expect(() => renderPlannerProgressMarkdown([events[0],
    { ...events[1], data: { ...events[1]!.data, run_id: "2026-10-21-999" } }])).toThrow("more than one run");
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
