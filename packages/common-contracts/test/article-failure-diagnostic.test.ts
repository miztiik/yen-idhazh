/** Does the terminal subtype preserve native diagnostics without widening their safe projection? */
import { expect, test } from "bun:test";
import {
  ARTICLE_FAILURE_DIAGNOSTIC_VERSION, ArticleFailureDiagnosticSchema, ArticleFailureDiagnosticDataSchema,
  articleDiagnosticContentType, createCandidateId, createCloudEvent, createRootContext,
  FEED_INGEST_EVENT_VERSION, HarvestDiagnosticsSchema,
} from "../src/index";

async function diagnostic() {
  const fixture = await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/article-terminal-failures.json", import.meta.url,
  )).json();
  return ArticleFailureDiagnosticSchema.parse(createCloudEvent({
    source: "/fixtures/common-contracts", type: "planner.progress", context: createRootContext(),
    data: {
      version: FEED_INGEST_EVENT_VERSION, run_id: "2026-11-05-700", operation: "quality", phase: "failed",
      details: {
        attempt: 3, feed_id: "recorded-news", candidate_id: createCandidateId(), url_key: "a".repeat(64),
        stage: "harvest-feeds", reason_code: "EXTRACT_FAILED",
        diagnostics: HarvestDiagnosticsSchema.parse(fixture.quality_diagnostic),
      },
    },
    parseData: value => ArticleFailureDiagnosticDataSchema.parse(value),
  }));
}

test("the current subtype retains all native quality fields, nulls, measured zero, warnings and versions", async () => {
  const event = await diagnostic();
  const fixture = await Bun.file(new URL(
    "../../../tests/fixtures/feed-ingest-plan/article-terminal-failures.json", import.meta.url,
  )).json();
  expect(event.data.details.diagnostics).toEqual(HarvestDiagnosticsSchema.parse(fixture.quality_diagnostic));
  expect(event.data.details.diagnostics).toMatchObject({
    fetch_ms: null, extract_ms: 0, pacing_time_ms: 0,
    response_evidence: { decoded_bytes: 0, declared_content_length: null },
    quality: { source_word_count: 45, token_count: null, truncated: null, contaminated: null },
  });
  expect(ArticleFailureDiagnosticSchema.parse(JSON.parse(JSON.stringify(event)))).toEqual(event);
  expect(ArticleFailureDiagnosticSchema.meta()).toMatchObject({
    version: ARTICLE_FAILURE_DIAGNOSTIC_VERSION, readCompatibility: "current_only; diagnostic readers and writers change together",
    changelog: [{ version: ARTICLE_FAILURE_DIAGNOSTIC_VERSION }],
  });
  expect(event.data.version).toBe(FEED_INGEST_EVENT_VERSION);
  expect(event.data).not.toHaveProperty("schema_version");
  for (const field of Object.keys(HarvestDiagnosticsSchema.shape)) {
    const partial: Record<string, unknown> = { ...event.data.details.diagnostics };
    delete partial[field];
    expect(ArticleFailureDiagnosticSchema.safeParse({ ...event, data: { ...event.data, details: {
      ...event.data.details, diagnostics: partial,
    } } }).success).toBe(false);
  }
});

test("unknown quality remains null and only a post-parse missing title can use the missing-fields reason", async () => {
  const event = await diagnostic();
  const missing = { ...event, data: { ...event.data, operation: "parse", details: {
    ...event.data.details, reason_code: "MISSING_REQUIRED_FIELDS",
    diagnostics: HarvestDiagnosticsSchema.parse({
      extraction_failure: "missing-title", stopped_stage: "extract", detail: "missing-title", failure_code: "no_title",
    }),
  } } };
  expect(ArticleFailureDiagnosticSchema.parse(missing).data.details.diagnostics.quality).toBeNull();
  for (const change of [
    { reason_code: "FEED_EMPTY" }, { stage: "screen-article-candidates" },
    { candidate_id: null }, { candidate_id: "a".repeat(64) }, { candidate_id: createCandidateId().toUpperCase() },
    { attempt: 0 }, { url_key: "address" },
    { diagnostics: HarvestDiagnosticsSchema.parse({}) },
  ]) {
    expect(ArticleFailureDiagnosticSchema.safeParse({
      ...missing, data: { ...missing.data, details: { ...missing.data.details, ...change } },
    }).success).toBe(false);
  }
  expect(ArticleFailureDiagnosticSchema.safeParse({ ...event, type: "other.progress" }).success).toBe(false);
  expect(ArticleFailureDiagnosticSchema.safeParse({
    ...event, data: { ...event.data, version: "2026-11-04" },
  }).success).toBe(false);
  expect(ArticleFailureDiagnosticSchema.safeParse({
    ...event, data: { ...event.data, operation: "fetch" },
  }).success).toBe(false);
  expect(ArticleFailureDiagnosticSchema.safeParse({
    ...event, data: { ...event.data, operation: "parse" },
  }).success).toBe(false);
});

test("the subtype keeps the native quality cross-field and body-limit rules", async () => {
  const event = await diagnostic();
  const base = event.data.details.diagnostics;
  for (const change of [
    { source_word_count: 44 }, { corroborated_word_count: 0, contaminated: false },
    { contaminated: true }, { truncated: true }, { truncated_at_tokens: 256 },
    { failure_code: "contaminated" }, { failure_code: null }, { truncation_cap_tokens: 255 },
  ]) {
    expect(ArticleFailureDiagnosticSchema.safeParse({ ...event, data: { ...event.data, details: {
      ...event.data.details, diagnostics: { ...base, quality: { ...base.quality, ...change } },
    } } }).success).toBe(false);
  }
  const cutoff = { ...event, data: { ...event.data, operation: "fetch", details: {
    ...event.data.details, reason_code: "FETCH_FAILED", diagnostics: HarvestDiagnosticsSchema.parse({
      fetch_failure: "body-too-large", stopped_stage: "fetch", detail: "body-too-large",
      body_limit: { configured_limit_bytes: 1024, observed_at_least_bytes: 1050 },
    }),
  } } };
  expect(ArticleFailureDiagnosticSchema.safeParse(cutoff).success).toBe(true);
  expect(ArticleFailureDiagnosticSchema.safeParse({ ...cutoff, data: { ...cutoff.data, details: {
    ...cutoff.data.details, diagnostics: { ...cutoff.data.details.diagnostics, fetch_failure: "network" },
  } } }).success).toBe(false);
});

test("strict projection refuses hidden content, header values, exception text and oversized strings", async () => {
  const event = await diagnostic();
  const base = event.data.details.diagnostics;
  for (const change of [
    { article_text: "PRIVATE_BODY" }, { html: "PRIVATE_HTML" }, { title: "PRIVATE_TITLE" },
    { url: "https://news.example/private?signature=PRIVATE_SECRET" },
    { error_code: "Error: PRIVATE_EXCEPTION" }, { stack: "PRIVATE_EXCEPTION" },
    { response_evidence: { ...base.response_evidence, selected_headers: { server: "PRIVATE_HEADER" } } },
    { response_evidence: { ...base.response_evidence, content_type: "text/html; private=PRIVATE_HEADER" } },
    { quality: { ...base.quality, extractor_version: "v".repeat(513) } },
    { quality: { ...base.quality, sanitizer_version: "https://private.example/secret" } },
  ]) {
    expect(ArticleFailureDiagnosticSchema.safeParse({ ...event, data: { ...event.data, details: {
      ...event.data.details, diagnostics: { ...base, ...change },
    } } }).success).toBe(false);
  }
  expect(ArticleFailureDiagnosticSchema.safeParse({ ...event, data: { ...event.data, details: {
    ...event.data.details, publisher_id: null,
  } } }).success).toBe(false);
  expect(articleDiagnosticContentType("text/html; private=PRIVATE_HEADER")).toBe("text/html");
  expect(articleDiagnosticContentType("application/x.recorded~v1; charset=utf-8")).toBe("application/x.recorded~v1");
  expect(articleDiagnosticContentType("PRIVATE_HEADER")).toBeNull();
  expect(articleDiagnosticContentType(null)).toBeNull();
});
