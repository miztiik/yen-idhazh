/** Does attention distinguish current failures from paused coverage and absent evidence? */
import { expect, test } from "bun:test";
import { parseHTML } from "linkedom";
import {
  ArticleFailureDiagnosticDataSchema, ArticleFailureDiagnosticSchema, createCandidateId, createCloudEvent,
  createRootContext, FEED_INGEST_EVENT_VERSION, HarvestDiagnosticsSchema,
  RejectedArticleRowSchema, writeTraceContext,
} from "@idhazh/common-contracts";
import { PLANNER_EVENT_SOURCE } from "../src/declare-event-source";
import { renderFailureEvidence } from "../src/reporting/failure-evidence-markdown";
import { renderPlanMarkdown } from "../src/reporting/plan-markdown";
import { renderSelectionExclusions } from "../src/reporting/selection-exclusions-markdown";
import { readPlannerOutputRecording } from "./planner-output-recordings";

test("counts screening refusals, selection decisions and request failures separately", async () => {
  const { response, health } = await readPlannerOutputRecording();
  const base = health.rows[0]!;
  const failure = { subject: "article", stage: "harvest-feeds", attribution: "feed" } as const;
  const screening = { subject: "article", stage: "screen-article-candidates" } as const;
  const paywall = { ...screening, reason_code: "PAYWALL_OR_BLOCKED" };
  const tooShort = { ...screening, reason_code: "REJECTED_SCREENING_MIN_WORDS" };
  const rows = [{ ...base, feed_id: "failed-feed", rejection_counts: [
    { ...failure, reason_code: "FETCH_FAILED_HTTP", count: 3 },
    { ...failure, reason_code: "EXTRACT_EMPTY", count: 1 },
    { ...paywall, attribution: "feed" as const, count: 2 },
    { ...paywall, attribution: null, count: 2 },
    { ...tooShort, attribution: "feed" as const, count: 7 },
    { ...tooShort, attribution: null, count: 3 },
  ] }, { ...base, feed_id: "failed-feed", rejection_counts: [
    { ...failure, reason_code: "FETCH_FAILED_HTTP", count: 2 },
  ] }];
  const before = structuredClone(rows);
  const report = renderPlanMarkdown({ response: { ...response, health: { ...health, rows } } });
  const { document } = parseHTML(Bun.markdown.html(report.markdown));
  const attention = document.querySelectorAll("table")[1]!.textContent!;
  expect(attention).toContain("5 recorded article failures");
  expect(attention).toContain("No article text extracted");
  expect(attention).not.toContain("minimum word");
  expect(attention).not.toContain("blocked by screening");
  expect(attention).toContain("response status unavailable in report input");
  expect(attention).not.toContain("403");
  expect(document.querySelector("details summary")?.textContent).toBe("Per-feed article results");
  const exclusions = [...document.querySelectorAll("details")]
    .find(node => node.querySelector("summary")?.textContent === "Why articles were not selected")!;
  expect([...exclusions.querySelectorAll("tbody tr")].map(row =>
    [...row.querySelectorAll("td")].slice(2).map(cell => cell.textContent))).toEqual([
    ["Article below minimum word count", "3", "1"],
    ["Article blocked by screening rules", "2", "1"],
  ]);
  expect(exclusions.querySelector("h3")?.textContent).toBe("Technical admission refusals");
  expect([...exclusions.querySelectorAll("li")].map(item => item.textContent)).toEqual([
    "Article below minimum word count: 7 refusals across 1 feed.",
    "Article blocked by screening rules: 2 refusals across 1 feed.",
  ]);
  expect(exclusions.textContent).toContain("do not add them");
  expect(report.notices).toEqual([]);
  expect(rows).toEqual(before);
});

test("technical-only partial evidence does not imply a selection decision", async () => {
  const { health } = await readPlannerOutputRecording();
  const rows = [{ ...health.rows[0]!, articles_selected: null, counts_complete: false, rejection_counts: [{
    subject: "article", stage: "screen-article-candidates", reason_code: "PAYWALL_OR_BLOCKED",
    attribution: "feed", count: 1,
  }] }] satisfies typeof health.rows;
  const before = structuredClone(rows);
  const { document } = parseHTML(Bun.markdown.html(renderSelectionExclusions(rows)));
  expect(document.querySelectorAll("tbody tr")).toHaveLength(0);
  expect(document.querySelector("details")?.textContent).toContain("No routine exclusions were recorded.");
  expect(document.querySelector("li")?.textContent).toBe("Article blocked by screening rules: 1 refusal across 1 feed.");
  expect(rows).toEqual(before);
});

test("paused feeds do not establish new requests or historical causes", async () => {
  const { health } = await readPlannerOutputRecording();
  const base = health.rows[0]!;
  const markdown = renderFailureEvidence([{ ...base, rejection_counts: [], feed_reads: 0,
    checked_at: null, links: [], check_result: null }], {
    eligible_feed_ids: [], feeds: [{
      feed_id: base.feed_id, endpoint_key: base.endpoint_key, availability: "resting",
      strikes: 5, failed_recovery_checks: 2, availability_complete: true,
      availability_updated_at: "2026-10-29T12:00:00Z",
      first_confirmed_failure_at: "2026-10-25T00:00:00Z",
      rest_until: "2026-10-30T12:00:00Z", retired_at: null, retirement_reason: null,
    }],
  }).markdown;
  const text = [...parseHTML(Bun.markdown.html(markdown)).document.querySelectorAll("td")].map(node => node.textContent).join(" ");
  expect(text).toContain("historical cause unavailable");
  expect(text).toContain("not a new HTTP failure");
  expect(text).toContain("Saved state at 2026-10-29T12:00:00Z UTC");
  expect(text).toContain("2026-10-30T12:00:00Z");
  expect(text).not.toContain("403");
});

test("missing evidence is an attention item while proven empty evidence has no empty table", () => {
  expect(renderFailureEvidence(undefined).markdown).toContain("Feed work evidence unavailable");
  const empty = renderFailureEvidence([], { feeds: [], eligible_feed_ids: [] }).markdown;
  expect(empty).toContain("No recorded problems");
  expect(Bun.markdown.html(empty)).not.toContain("<table>");
});

test("full typed detail explains native causes once and missing title never becomes an extra health failure", async () => {
  const { response, health } = await readPlannerOutputRecording();
  const fixture = await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/article-terminal-failures.json", import.meta.url,
  )).json();
  const diagnostic = HarvestDiagnosticsSchema.parse(fixture.quality_diagnostic);
  const base = RejectedArticleRowSchema.array().parse(await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/entry-points/rejected-articles.rows.json", import.meta.url,
  )).json())[0]!;
  const article = RejectedArticleRowSchema.parse({
    ...base, run_id: response.run_id, attempt: response.attempt, candidate_id: createCandidateId(),
    feed_id: health.rows[0]!.feed_id, url_key: "a".repeat(64), stage: "harvest-feeds", reason_code: "EXTRACT_FAILED",
    freshness_cutoff_at: null, http_status: diagnostic.http_status, fetch_failure: diagnostic.fetch_failure,
    error_code: diagnostic.error_code, pacing_time_ms: diagnostic.pacing_time_ms, pacing_settings: diagnostic.pacing_settings,
  });
  const event = ArticleFailureDiagnosticSchema.parse(createCloudEvent({
    source: PLANNER_EVENT_SOURCE, type: "planner.progress", context: { ...createRootContext(), traceId: response.traceId },
    data: {
      version: FEED_INGEST_EVENT_VERSION, run_id: response.run_id, operation: "quality", phase: "failed",
      details: {
        attempt: response.attempt, feed_id: article.feed_id, candidate_id: article.candidate_id, url_key: article.url_key,
        stage: "harvest-feeds", reason_code: article.reason_code, diagnostics: { ...diagnostic,
          quality: { ...diagnostic.quality, extractor_version: "recorded-`<>&-v1" } },
      },
    }, parseData: value => ArticleFailureDiagnosticDataSchema.parse(value),
  }));
  const missing = ArticleFailureDiagnosticSchema.parse({ ...event, id: createCandidateId(), data: {
    ...event.data, operation: "parse", details: {
      ...event.data.details, candidate_id: createCandidateId(), reason_code: "MISSING_REQUIRED_FIELDS",
      diagnostics: HarvestDiagnosticsSchema.parse({ extraction_failure: "missing-title", detail: "missing-title",
        failure_code: "no_title", stopped_stage: "extract" }),
    },
  } });
  const cause = { subject: "article" as const, stage: "harvest-feeds", attribution: "feed" as const };
  const feeds = [{ ...health.rows[0]!, rejection_counts: [
    { ...cause, reason_code: "EXTRACT_FAILED", count: 1 }, { ...cause, reason_code: "MISSING_REQUIRED_FIELDS", count: 1 },
  ] }];
  const before = structuredClone(feeds);
  const evidence = { articles: [article, article], article_diagnostics: [event, event, missing] };
  const report = renderFailureEvidence(feeds, health.availability, undefined, [], evidence);
  const { document } = parseHTML(Bun.markdown.html(report.markdown));
  const rows = [...document.querySelectorAll("tbody tr")].map(node => node.textContent);
  expect(rows.filter(row => row?.includes("too short"))).toHaveLength(1);
  if (diagnostic.quality === null) throw new Error("Detailed quality evidence requires recorded word measurements");
  const qualityRow = rows.find(row => row?.includes("too short"));
  expect(qualityRow).toContain(`${diagnostic.quality.source_word_count} source words measured during extraction`);
  expect(qualityRow).toContain(`${diagnostic.quality.word_count} body words measured during extraction`);
  expect(qualityRow).not.toContain("after the cap");
  expect(rows.filter(row => row?.includes("missing title"))).toHaveLength(1);
  expect(rows.find(row => row?.includes("missing title"))).toContain("not an additional health failure");
  expect(rows.join(" ")).not.toContain("recorded article failure");
  expect(JSON.parse(document.querySelector("details code")!.textContent!)).toEqual([event, missing]);
  expect(feeds).toEqual(before);
  for (const change of [
    { feed_id: "another-feed" }, { url_key: "b".repeat(64) }, { reason_code: "EXTRACT_EMPTY" },
    { http_status: 429 }, { pacing_time_ms: 10 },
    { stage: "screen-article-candidates", reason_code: "REJECTED_SCREENING_MIN_WORDS" },
  ] as const) {
    expect(() => renderFailureEvidence(feeds, health.availability, undefined, [], {
      ...evidence, articles: [{ ...article, ...change }],
    })).toThrow("disagrees with saved rejection");
  }
  for (const foreign of [
    { ...event, data: { ...event.data, run_id: "2026-10-21-999" } },
    { ...event, data: { ...event.data, details: { ...event.data.details, attempt: response.attempt + 1 } } },
    { ...event, ...writeTraceContext(createRootContext()) },
  ]) {
    expect(() => renderPlanMarkdown({ response,
      failures: { article_diagnostics: [ArticleFailureDiagnosticSchema.parse(foreign)] } })).toThrow("another execution");
  }
});
