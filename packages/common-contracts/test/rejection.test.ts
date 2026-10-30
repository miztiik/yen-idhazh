/** Which malformed identities, hidden payloads and unknown measurements must readers refuse? */
import { describe, expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { z } from "zod";
import {
  CandidateRejectionRecordSchema, FeedIngestCandidateSchema,
  ArticleContentEvidenceSchema,
  FeedIngestEventSchema, FileEnvelopeSchema, PlannerFileEnvelopeSchema,
  REASON_STAGES, REQUIRED_DETAILS, RejectionDetailsSchema,
  SourceSnapshotSchema, WriterIdentitySchema, deriveCandidateId, deriveUrlKey, validateEnvelopeContainer,
  readFeedIngestEvent, HarvestDiagnosticsSchema, FetchAttemptSchema, OPERATION_VERSION,
  PLANNER_OPERATION_VERSION, RecordedInstantSchema, TimestampSchema,
  FEED_INGEST_CANDIDATE_VERSION, LEGACY_PARSED_FEED_BATCH_VERSION, PARSED_FEED_BATCH_VERSION,
  PLANNER_LEDGER_VERSION, PLAN_RUN_VERSION,
  SELECTED_ARTICLE_VERSION, FEED_HEALTH_STATE_VERSION, ParsedFeedBatchSchema, SelectedFeedBatchSchema, PartitionedFeedBatchSchema,
  PlannerHarvestObservationSchema, PlannerDiscoveredEvidenceSchema, PlannerDiscoveredRowSchema,
  PlannerStageContextSchema, PlannerStageRequestSchema, StageReferenceRequestSchema,
  PartitionArticlesRequestSchema, PlannerWorkEventSchema, DiscoveredArticleRowSchema,
  FetchRequestSchema,
  SelectedArticleRowSchema, SelectedArticlesArtifactSchema, SelectedArtifactArticleSchema,
  selectedArticleMetadata, readSelectedArticlesArtifact, FeedHealthStateRowSchema, PlanRunRowSchema,
  RetainedRejectionReasonSchema, RejectedArticleRowSchema, ArticleFetchEvidenceSchema,
  CANDIDATE_REJECTION_VERSION, REJECTED_ARTICLE_VERSION,
} from "../src/index";
import { plannerStageSchemas, runtimeSchemas, schemas } from "./schema-binding";

const day = "2026-10-20";
const at = `${day}T12:00:00Z`;
const run = `${day}-7`;
const url = "https://example.com/article";
const digest = "a".repeat(64);
const source = SourceSnapshotSchema.parse({
  feed_id: "example", feed_url: "https://example.com/feed", title: "Example",
  tier: 4, status: "active",
  weight: 1, applied_tier_weight: 0.6,
});
function candidate() {
  return FeedIngestCandidateSchema.parse({
    date: day, correlation_id: "correlation", run_id: run,
    candidate_id: deriveCandidateId(run, source.feed_id, 0), entry_ordinal: 0,
    feed_id: source.feed_id, source,
    canonical_url: url, url_key: deriveUrlKey(url), title: "An article", categories: [],
    article_text: "A recorded article.", word_count: 3, author: null,
    published_at: null, fetched_at: at,
  });
}
function rejection() {
  return CandidateRejectionRecordSchema.parse({
    date: day, correlation_id: "correlation", feed_id: source.feed_id,
    feed_url: source.feed_url, subject: "article", candidate_id: candidate().candidate_id,
    url_key: deriveUrlKey(url), canonical_url: url, title: "An article", categories: [],
    stage: "screen-article-candidates", drop_reason: "REJECTED_SCREENING_MIN_WORDS",
    details: { words_found: 3, words_required: 100 }, rejected_at: at,
  });
}
function envelope() {
  return FileEnvelopeSchema.parse({
    row_schema_version: day, tier: "raw", ledger: "host-fingerprint", covers: day,
    written_at_ms: 1792497600000,
    identity: { run_id: run, attempt: 1, job: null, pipeline_name: "feed-ingest-plan",
      task_name: "plan", shard: 0, producer: "feed.plan", git_sha: "b".repeat(40) },
    unit_id: "d416f288-8f69-5015-a192-04503a45771a",
    file_id: "0199ba8e-9920-8000-8000-000000000001", content_sha256: digest,
    writer: "idhazh_typescript.ledger.parquet", writer_version: "1", compression: "zstd",
  });
}
function selection() {
  return SelectedArticleRowSchema.parse({
    run_id: run, attempt: 1, date: day, url_key: deriveUrlKey(url), feed_id: "example",
    publisher_id: null, canonical_url: url, title: "An article", categories: [],
    author: null, published_at: at, published_at_source: "selection", tier: 1, weight: 1, applied_tier_weight: 0.5,
    editorial_rank: 1, estimated_work: 3, worker_assignment: null,
    ratings: {
      base_article_score: 1.5, marginal_score: 1.25, recency_score: 1,
      feed_authority_score: 0.5, adjustments: [
        { term: "feed-reliability", value: null }, { term: "publisher", value: 0 },
        { term: "domain", value: -0.25 },
      ],
    },
    feed_limit: 3, exploration_slot: false, cap_relaxations: [], freshness_cutoff_at: at,
    timing_at: at, timing_basis: "first_seen", age_hours: 0,
  });
}
function sourceRun() {
  return FeedHealthStateRowSchema.parse({
    feed_id: "example", endpoint_key: deriveUrlKey(source.feed_url), checked_at: at,
    permission: "allowed", availability: "eligible", strikes: 0, rested_runs: 0,
    last_failure_code: null, status: 200,
    reliability: { productive: 0, attempted: 0, success_fraction: null, from_day: null,
      through_day: null, production_factor: null, complete: false },
    date: day, feed_reads: 1, productive_reads: 1, failed_reads: 0,
    article_candidates: 1, articles_selected: 1, feed_requests: 1, article_requests: 1,
    robots_requests: 0, counts_complete: true, rejection_counts: [], run_id: run,
    attempt: 1, items: 1, outcome: "ok",
  });
}
function assessment() {
  return PlanRunRowSchema.parse({
    run_id: run, started_at: at, duration_ms: 0, status: "completed", failure_code: null,
    selected_count: 0, strategy: "none", dispatch_count: 0, selected_articles_artifact: null,
    api_timings: [], date: day, attempt: 1, lifecycle_window_days: 31, reliability_floor: 0.5,
    reliability_penalty_enabled: true, evaluated_at: at, request_report_closed_days: 7,
    reliability_window_days: 30, selection_started_at_utc: null,
  });
}
function event() {
  return FeedIngestEventSchema.parse({
    run_id: run, correlation_id: "7cef34e3-dd9f-40ce-9a56-4d01ff5115cc",
    occurred_at: at, operation: "fetch", phase: "completed",
    details: { input_count: 0, output_count: 0, duration_ms: 1 },
  });
}

describe("rejection evidence", () => {
  test("retains article response evidence separately from policy and health outcomes", () => {
    const evidence = {
      http_status: 200, fetch_failure: null, error_code: null,
      robots: "allowed" as const, robots_http_status: 404, robots_failure: "http" as const,
    };
    const transient = CandidateRejectionRecordSchema.parse({
      ...rejection(), version: CANDIDATE_REJECTION_VERSION, candidate_id: null, title: null,
      stage: "harvest-feeds", drop_reason: "EXTRACT_EMPTY", details: evidence,
    });
    expect(transient.details).toMatchObject(evidence);
    const row = {
      run_id: run, attempt: 1, date: day, candidate_id: null, url_key: deriveUrlKey(url),
      feed_id: source.feed_id, stage: "harvest-feeds" as const, reason_code: "EXTRACT_EMPTY",
      freshness_cutoff_at: null, ...evidence,
    };
    expect(RejectedArticleRowSchema.parse(row)).toEqual(row);
    const unobserved = ArticleFetchEvidenceSchema.parse({});
    expect(Object.values(unobserved)).toEqual([null, null, null, null, null, null]);
    expect(RejectedArticleRowSchema.parse({ ...row, ...unobserved })).toMatchObject(unobserved);
    expect(ArticleFetchEvidenceSchema.parse({
      http_status: null, fetch_failure: "robots-unknown", error_code: "ECONNRESET",
      robots: "unknown", robots_http_status: null, robots_failure: "network",
    }).error_code).toBe("ECONNRESET");
    expect(RejectedArticleRowSchema.meta()?.version).toBe(REJECTED_ARTICLE_VERSION);
    expect(CandidateRejectionRecordSchema.meta()?.version).toBe(CANDIDATE_REJECTION_VERSION);
  });

  test("records the configured body limit and only the observed lower bound", () => {
    expect(HarvestDiagnosticsSchema.parse({
      fetch_failure: "body-too-large",
      body_limit: { configured_limit_bytes: 1024, observed_at_least_bytes: 1056 },
    }).body_limit).toEqual({ configured_limit_bytes: 1024, observed_at_least_bytes: 1056 });
    expect(HarvestDiagnosticsSchema.parse({
      fetch_failure: "robots-unknown", robots_failure: "body-too-large",
      body_limit: { configured_limit_bytes: 30, observed_at_least_bytes: 59 },
    }).body_limit).toEqual({ configured_limit_bytes: 30, observed_at_least_bytes: 59 });
    for (const body_limit of [
      { configured_limit_bytes: 1024, observed_at_least_bytes: 1024 },
      { configured_limit_bytes: -1, observed_at_least_bytes: 1056 },
      { configured_limit_bytes: 1024, observed_at_least_bytes: 1056, response_bytes: 2048 },
    ]) {
      expect(HarvestDiagnosticsSchema.safeParse({
        fetch_failure: "body-too-large", body_limit,
      }).success).toBe(false);
    }
    expect(HarvestDiagnosticsSchema.safeParse({
      fetch_failure: "network", body_limit: { configured_limit_bytes: 1024, observed_at_least_bytes: 1056 },
    }).success).toBe(false);
  });

  test("refuses malformed fetch evidence and missing non-harvest candidate identities", () => {
    const base = rejection();
    const row = {
      run_id: run, attempt: 1, date: day, candidate_id: digest, url_key: digest,
      feed_id: "example", stage: "curate-article-portfolio",
      reason_code: "REJECTED_GLOBAL_CAPACITY_REACHED", freshness_cutoff_at: null,
    };
    for (const invalid of [
      { http_status: 99 }, { http_status: 600 }, { http_status: "503" },
      { robots_http_status: 600 }, { robots_http_status: 0 },
      { fetch_failure: "connection-refused" }, { robots_failure: "not-observed" },
      { error_code: "network_error" }, { error_code: "A".repeat(65) },
      { robots: "permitted" },
    ]) {
      expect(CandidateRejectionRecordSchema.safeParse({ ...base, details: invalid }).success).toBe(false);
      expect(RejectedArticleRowSchema.safeParse({ ...row, ...invalid }).success).toBe(false);
    }
    expect(CandidateRejectionRecordSchema.safeParse({ ...base, candidate_id: null }).success).toBe(false);
    expect(CandidateRejectionRecordSchema.safeParse({
      ...base, version: "2026-10-28",
    }).success).toBe(false);
    expect(RejectedArticleRowSchema.safeParse({ ...row, candidate_id: null }).success).toBe(false);
    expect(RejectedArticleRowSchema.safeParse({
      ...row, stage: "harvest-feeds", reason_code: "FEED_EMPTY",
    }).success).toBe(false);
    expect(RejectedArticleRowSchema.safeParse({
      ...row, candidate_id: null, url_key: null, stage: "harvest-feeds", reason_code: "FETCH_FAILED",
    }).success).toBe(false);
  });

  test("preserves missing article fields without fabricating feed identities", () => {
    const base = rejection();
    expect(base.details.timeout_ms).toBeNull();
    expect(CandidateRejectionRecordSchema.safeParse({
      ...base, subject: "feed", candidate_id: null, canonical_url: null,
      url_key: null, title: null, stage: "harvest-feeds", drop_reason: "FEED_EMPTY", details: {},
    }).success).toBe(true);
    expect(CandidateRejectionRecordSchema.safeParse({
      ...base, canonical_url: null, url_key: null, title: null,
      stage: "harvest-feeds", drop_reason: "MISSING_REQUIRED_FIELDS", details: {},
    }).success).toBe(true);
    expect(CandidateRejectionRecordSchema.safeParse({ ...base, subject: "feed" }).success).toBe(false);
    expect(CandidateRejectionRecordSchema.safeParse({ ...base, canonical_url: null }).success).toBe(false);
    for (const drop_reason of ["MEDIA_CONTENT", "PRESS_RELEASE", "LINK_HEAVY"]) {
      expect(CandidateRejectionRecordSchema.safeParse({
        ...base, subject: "feed", candidate_id: null, canonical_url: null, url_key: null, title: null,
        stage: "harvest-feeds", drop_reason, details: { media_match: "url", matched_url_marker: "configured/" },
      }).success).toBe(false);
    }
  });

  test("enforces every reason's stage and required measurements", () => {
    const details = RejectionDetailsSchema.parse({
      http_status: 503, timeout_ms: 200, words_found: 3, words_required: 100,
      age_hours: 60, max_age_hours: 48,
      matched_url_key: digest, published_on: day, failure_code: "network_error",
      matched_url_marker: "blocked", history_window_days: 7,
      media_match: "url",
      content_evidence: {
        markdown_chars: 1000, linked_label_chars: 500, link_density: 0.5,
        list_items: 11, opening_sample_chars: 600, press_release_marker_index: 0,
      },
      sample_chars_limit: 600, max_link_density: 0.4, max_list_items: 10, list_word_limit: 150,
      diagnostics: HarvestDiagnosticsSchema.parse({
        extraction_failure: "missing-document-root", failure_code: "unknown",
        stopped_stage: "extract", detail: "missing-document-root", fetch_ms: 1, extract_ms: 1,
      }),
    });
    for (const [reason, stages] of Object.entries(REASON_STAGES)) {
      const feedOnly = ["SOURCE_INACTIVE", "FEED_PARSE_FAILED", "FEED_EMPTY"].includes(reason);
      const row = { ...rejection(), stage: stages[0], drop_reason: reason, details,
        ...(feedOnly ? { subject: "feed", candidate_id: null, canonical_url: null, url_key: null, title: null } : {}) };
      expect(CandidateRejectionRecordSchema.safeParse(row).success).toBe(true);
      expect(CandidateRejectionRecordSchema.safeParse({ ...row, stage: "seal-article-ledger" }).success).toBe(false);
      for (const field of REQUIRED_DETAILS[reason as keyof typeof REQUIRED_DETAILS] ?? []) {
        expect(CandidateRejectionRecordSchema.safeParse({ ...row, details: { ...details, [field]: null } }).success).toBe(false);
      }
    }
  });

  test("separates strict current reasons from bounded retained ledger reasons", async () => {
    const fixture = await Bun.file(new URL(
      "../../../tests/fixtures/contracts/rejected-article/retained-reasons.json", import.meta.url,
    )).json();
    const row = {
      run_id: run, attempt: 1, date: day, candidate_id: digest, url_key: digest,
      feed_id: "example", stage: "curate-article-portfolio", freshness_cutoff_at: null,
    };

    expect(RejectedArticleRowSchema.parse({
      ...row, reason_code: fixture.known_active_reason,
    }).reason_code).toBe(fixture.known_active_reason);
    expect(RejectedArticleRowSchema.parse({
      ...row, reason_code: fixture.unknown_retained_reason,
    }).reason_code).toBe(fixture.unknown_retained_reason);
    expect(CandidateRejectionRecordSchema.safeParse({
      ...rejection(), drop_reason: "UNKNOWN_CANDIDATE_REASON",
    }).success).toBe(false);
    expect(RetainedRejectionReasonSchema.safeParse("lowercase_reason").success).toBe(false);
    expect(RetainedRejectionReasonSchema.safeParse("UNKNOWN REASON").success).toBe(false);
    expect(RetainedRejectionReasonSchema.safeParse("X".repeat(129)).success).toBe(false);
  });

  test("refuses unknown fields, coercion, nonfinite values and non-UTC timestamps", () => {
    const row = rejection();
    for (const changed of [
      { ...row, extra: true }, { ...row, details: { ...row.details, untyped: 1 } },
      { ...row, details: { ...row.details, words_found: "3" } },
      { ...row, details: { ...row.details, words_found: Infinity } },
      { ...row, details: { ...row.details, words_found: NaN } },
      { ...row, rejected_at: "2026-10-20T12:00:00+00:00" },
      { ...row, date: "2026-10-19" }, { ...row, url_key: digest },
    ]) expect(CandidateRejectionRecordSchema.safeParse(changed).success).toBe(false);
    const measured = {
      markdown_chars: 1000, linked_label_chars: 400, link_density: 0.4,
      list_items: 10, opening_sample_chars: 600, press_release_marker_index: null,
    };
    expect(ArticleContentEvidenceSchema.parse(measured)).toEqual(measured);
    for (const invalid of [
      { markdown_chars: -1 }, { linked_label_chars: 1001 }, { list_items: 1.5 },
      { opening_sample_chars: 1001 }, { press_release_marker_index: -1 }, { link_density: NaN },
      { link_density: 0.39 },
      { link_density: 1.1 }, { link_density: "0.4" }, { raw_markdown: "untrusted" }, { href: "https://untrusted.example" },
    ]) expect(ArticleContentEvidenceSchema.safeParse({ ...measured, ...invalid }).success).toBe(false);
  });

  test("hashes exact canonical URL bytes and newline-separated candidate identity", () => {
    expect(deriveUrlKey(url)).toBe(createHash("sha256").update(url).digest("hex"));
    expect(deriveCandidateId(run, "example", 0)).toBe(createHash("sha256").update(`${run}\nexample\n0`).digest("hex"));
    expect(deriveCandidateId(run, "example", 0)).not.toBe(deriveCandidateId(run, "example", 1));
    expect(() => deriveCandidateId(run, "example", -1)).toThrow();
    expect(() => deriveCandidateId(run, "example", 0.5)).toThrow();
    expect(FeedIngestCandidateSchema.safeParse({ ...candidate(), candidate_id: digest }).success).toBe(false);
    expect(FeedIngestCandidateSchema.safeParse({ ...candidate(), vertical: "other" }).success).toBe(false);
  });

  test("projects selected metadata without mutating its text-bearing artifact", () => {
    const row = selection();
    const { run_id: _run, attempt: _attempt, date: _day, ...metadata } = row;
    const article = SelectedArtifactArticleSchema.parse({ ...metadata, article_text: "Artifact-only text." });
    const before = structuredClone(article);
    const projected = selectedArticleMetadata(article);
    expect(projected).toEqual(metadata);
    expect(article).toEqual(before);
    projected.categories.push("not-shared");
    projected.ratings.adjustments[0]!.value = 0.5;
    expect(article).toEqual(before);
    expect(SelectedArticleRowSchema.safeParse({ ...row, article_text: article.article_text }).success).toBe(false);
    expect(SelectedArticleRowSchema.safeParse({ ...row, evaluated_at: at }).success).toBe(false);
    expect(SelectedArticleRowSchema.safeParse({ ...row, age_hours: -1, timing_basis: "published_at", published_at_source: "source" }).success).toBe(true);
    expect(SelectedArticleRowSchema.safeParse({ ...row, published_at: null }).success).toBe(false);
    expect(SelectedArticleRowSchema.safeParse({ ...row, published_at_source: "source" }).success).toBe(false);
    expect(SelectedArticleRowSchema.safeParse({ ...row, timing_basis: "published_at" }).success).toBe(false);
    expect(SelectedArticleRowSchema.safeParse({ ...row, timing_basis: "fetched_at" }).success).toBe(false);
    expect(SelectedArticleRowSchema.safeParse({
      ...row, published_at_source: "selection", timing_basis: "unavailable", timing_at: null, age_hours: null,
    }).success).toBe(true);
    expect(SelectedArticleRowSchema.safeParse({
      ...row, published_at_source: "other",
    }).success).toBe(false);
    for (const published_at_source of ["source", "selection"]) {
      expect(SelectedArticleRowSchema.safeParse({
        ...row, published_at_source, published_at: null,
      }).success).toBe(false);
    }
    const artifact = SelectedArticlesArtifactSchema.parse({
      schema_version: SELECTED_ARTICLE_VERSION, run_id: run, attempt: 1, date: day, evaluated_at: at, articles: [article],
    });
    expect(artifact.schema_version).toBe(SELECTED_ARTICLE_VERSION);
    expect(SelectedArticlesArtifactSchema.safeParse({
      run_id: run, attempt: 1, date: day, evaluated_at: at, articles: [article],
    }).success).toBe(false);
    expect(SelectedArticlesArtifactSchema.safeParse({ ...artifact, articles: [{ ...article, run_id: run }] }).success).toBe(false);
    expect(() => readSelectedArticlesArtifact({ ...artifact, schema_version: PLANNER_LEDGER_VERSION })).toThrow();
    expect(() => readSelectedArticlesArtifact({ ...artifact, schema_version: "2026-10-24" })).toThrow();
    expect(() => readSelectedArticlesArtifact({
      ...artifact, articles: [{ ...article, published_at_source: "other" }],
    })).toThrow();
  });

  test("reads finite historical provenance while refusing incompatible formats and identities", () => {
    const row = envelope();
    expect(validateEnvelopeContainer(row, "parquet")).toEqual(row);
    expect(() => validateEnvelopeContainer(row, "json")).toThrow();
    expect(FileEnvelopeSchema.safeParse({ ...row, version: "2026-10-19" }).success).toBe(false);
    expect(FileEnvelopeSchema.safeParse({ ...row, version: "2026-10-14" }).success).toBe(false);
    expect(FileEnvelopeSchema.safeParse({ ...row, version: "2026-10-14", writer: "idhazh.ledger.parquet" }).success).toBe(true);
    const historical = { ...row, version: "2026-10-10", row_schema_version: "2026-10-10",
      writer: "idhazh_rust.ledger.parquet", identity: { ...row.identity, producer: "telemetry.silicon" } };
    expect(FileEnvelopeSchema.safeParse(historical).success).toBe(true);
    expect(FileEnvelopeSchema.safeParse({ ...historical, ledger: "seen" }).success).toBe(false);
    expect(FileEnvelopeSchema.safeParse({ ...row, writer: "idhazh.ledger.json_lines" }).success).toBe(false);
    expect(FileEnvelopeSchema.safeParse({ ...row, covers: "2026-10" }).success).toBe(false);
    expect(FileEnvelopeSchema.safeParse({ ...row, unit_id: row.file_id }).success).toBe(false);
    expect(WriterIdentitySchema.safeParse({ ...row.identity, task_name: null }).success).toBe(false);
    expect(FileEnvelopeSchema.safeParse({ ...row, ledger: "selected-articles" }).success).toBe(false);
    const planner = PlannerFileEnvelopeSchema.parse({
      row_schema_version: FEED_HEALTH_STATE_VERSION, ledger: "feed-health-state", tier: "raw", covers: day,
      file_id: row.file_id, content_sha256: digest, writer: row.writer, writer_version: row.writer_version,
      compression: "snappy", updated_at: at,
    });
    for (const field of ["unit_id", "git_sha", "identity", "run_id", "job", "shard", "producer", "written_at_ms", "built_from"]) {
      expect(PlannerFileEnvelopeSchema.safeParse({ ...planner, [field]: "not-declared" }).success).toBe(false);
    }
    expect(PlannerFileEnvelopeSchema.safeParse({ ...planner, updated_at: null }).success).toBe(false);
    expect(PlannerFileEnvelopeSchema.safeParse({ ...planner, ledger: "selected-articles" }).success).toBe(false);
    expect(PlannerFileEnvelopeSchema.safeParse({
      ...planner, row_schema_version: SELECTED_ARTICLE_VERSION,
      ledger: "selected-articles", updated_at: null,
    }).success).toBe(true);
    expect(PlannerFileEnvelopeSchema.safeParse({
      ...planner, row_schema_version: PLANNER_LEDGER_VERSION, ledger: "selected-articles", updated_at: null,
    }).success).toBe(false);
    expect(PlannerFileEnvelopeSchema.safeParse({
      ...planner, row_schema_version: PLANNER_LEDGER_VERSION,
      ledger: "plan-runs", updated_at: null,
    }).success).toBe(false);
    expect(PlannerFileEnvelopeSchema.safeParse({
      ...planner, row_schema_version: PLAN_RUN_VERSION,
      ledger: "plan-runs", updated_at: null,
    }).success).toBe(true);
  });
});

describe("current planner contracts", () => {
  test("keeps health counts integral and captured ratios within their domain", () => {
    const row = sourceRun();
    for (const field of ["feed_reads", "productive_reads", "failed_reads", "article_candidates", "articles_selected", "feed_requests", "article_requests", "robots_requests", "items"]) {
      for (const value of [0, 1, 42]) expect(FeedHealthStateRowSchema.safeParse({ ...row, [field]: value }).success).toBe(true);
      for (const value of [-1, 0.5, Infinity, NaN, true]) expect(FeedHealthStateRowSchema.safeParse({ ...row, [field]: value }).success).toBe(false);
    }
    for (const value of [0, 0.5, 1]) expect(FeedHealthStateRowSchema.safeParse({ ...row, reliability: { ...row.reliability, success_fraction: value } }).success).toBe(true);
    for (const value of [-0.1, 1.1, Infinity, NaN]) expect(FeedHealthStateRowSchema.safeParse({ ...row, reliability: { ...row.reliability, success_fraction: value } }).success).toBe(false);
  });

  test("keeps signed score adjustments distinct from unavailable values", () => {
    const row = selection();
    for (const value of [-1, 0, 0.25, null]) {
      expect(SelectedArticleRowSchema.safeParse({ ...row, ratings: {
        ...row.ratings, adjustments: [{ term: "domain", value }],
      } }).success).toBe(true);
    }
    for (const value of [Infinity, NaN]) expect(SelectedArticleRowSchema.safeParse({ ...row, ratings: {
      ...row.ratings, adjustments: [{ term: "domain", value }],
    } }).success).toBe(false);
    expect(SelectedArticleRowSchema.safeParse({ ...row, ratings: {
      ...row.ratings, adjustments: [{ term: 7, value: 0 }],
    } }).success).toBe(false);
  });

  test("records explicit empty runs and honest unavailable total duration", () => {
    const row = assessment();
    expect(row.selected_count).toBe(0);
    expect(row.selected_articles_artifact).toBeNull();
    const { selected_count: _count, ...missing } = row;
    expect(PlanRunRowSchema.safeParse(missing).success).toBe(false);
    expect(PlanRunRowSchema.safeParse({ ...row, completion_evidence: [] }).success).toBe(false);
    for (const reference of ["https://example.org/signed?token=secret", "/tmp/a.json", "C:\\tmp\\a.json",
      "../a.json", "a/../a.json", "./a.json", "a//b.json", "a\nb.json"]) {
      expect(PlanRunRowSchema.safeParse({ ...row, selected_articles_artifact: reference }).success).toBe(false);
    }
    expect(PlanRunRowSchema.parse({ ...row, selected_articles_artifact: "backend/var/run/selected-articles.json" }).selected_articles_artifact)
      .toBe("backend/var/run/selected-articles.json");
    expect(PlanRunRowSchema.safeParse({ ...row, duration_ms: 0.5 }).success).toBe(false);
    expect(PlanRunRowSchema.parse({ ...row, duration_ms: null }).duration_ms).toBeNull();
    const { duration_ms: _duration, ...missingDuration } = row;
    expect(PlanRunRowSchema.safeParse(missingDuration).success).toBe(false);
    expect(PlanRunRowSchema.safeParse({ ...row, status: "failed", failure_code: "fetch-failed", selection_started_at_utc: null, dispatch_count: 0 }).success).toBe(true);
    for (const operation of ["fetch", "parse", "select", "partition", "persist", "feed-health-summary",
      "feed-health-before-fetch", "feed-health-for-selection"]) {
      expect(PlanRunRowSchema.safeParse({ ...row, api_timings: [{ operation, duration_ms: 0, status: "interrupted" }] }).success).toBe(true);
    }
  });

  test("does not turn unassessed or missing measurements into evidence", () => {
    const row = sourceRun();
    expect(FeedHealthStateRowSchema.parse({ ...row, reliability: null }).reliability).toBeNull();
    expect(FeedHealthStateRowSchema.parse({ ...row, counts_complete: false, article_requests: null }).article_requests).toBeNull();
    expect(FeedHealthStateRowSchema.safeParse({ ...row, article_requests: null }).success).toBe(false);
    const articleOnly = { ...row, date: "2026-10-21", checked_at: null, items: null, outcome: null,
      feed_reads: 0, productive_reads: 0, failed_reads: 0, feed_requests: 0, article_requests: 2 };
    expect(FeedHealthStateRowSchema.parse(articleOnly).counts_complete).toBe(true);
    expect(FeedHealthStateRowSchema.safeParse({ ...row, checked_at: null, availability: "probe-due" }).success).toBe(false);
    expect(FeedHealthStateRowSchema.safeParse({ ...row, reliability: { ...row.reliability, window_days: 30 } }).success).toBe(false);
    expect(DiscoveredArticleRowSchema.parse({ url_key: digest, first_seen_at: at, date: day })).toEqual({ url_key: digest, first_seen_at: at, date: day });
    expect(DiscoveredArticleRowSchema.safeParse({ url_key: digest, first_seen_at: at, date: "2026-10-21" }).success).toBe(false);
  });

  test("binds event discriminators, candidate identities and stages", () => {
    const row = event();
    expect(row.version).toBe("2026-10-30T22:25");
    expect(FeedIngestEventSchema.safeParse({ ...row, payload: { article_text: "must not escape" } }).success).toBe(false);
    expect(FeedIngestEventSchema.safeParse({ ...row, operation: "article-assessment" }).success).toBe(false);
    expect(FeedIngestEventSchema.safeParse({ ...row, details: { duration_ms: 0.5 } }).success).toBe(true);
    expect(FeedIngestEventSchema.safeParse({ ...row, details: { publisher_id: "recorded-publication" } }).success).toBe(true);
    expect(FeedIngestEventSchema.safeParse({ ...row, details: { publisher_id: "Recorded_Publisher" } }).success).toBe(true);
    expect(FeedIngestEventSchema.safeParse({ ...row, details: { future_field: { sample: [1, true, null] } } }).success).toBe(true);
    expect(PlannerWorkEventSchema.safeParse({ stage: "unknown", payload: {} }).success).toBe(false);
    const request = {
      request_id: "00000000-0000-4000-8000-000000000010",
      correlation_id: "00000000-0000-4000-8000-000000000011",
      feed_id: source.feed_id, fetch_item_type: "article", batch_id: "00000000-0000-4000-8000-000000000012",
      offer_id: digest,
    };
    expect(FetchRequestSchema.safeParse(request).success).toBe(true);
    expect(FetchRequestSchema.safeParse({ ...request, source_id: source.feed_id }).success).toBe(false);
    expect(FetchRequestSchema.safeParse({ ...request, offer_id: undefined }).success).toBe(false);
    expect(FetchRequestSchema.safeParse({ ...request, url }).success).toBe(false);
  });

  test("refuses old progress shapes through the sole TypeScript event declaration", () => {
    const row = event();
    expect(readFeedIngestEvent(JSON.parse(JSON.stringify(row)))).toEqual(row);
    expect(() => readFeedIngestEvent({ ...row, version: "2026-10-28" })).toThrow();
    expect(() => readFeedIngestEvent({ ...row, feed_id: null })).toThrow();
    const schema = z.toJSONSchema(FeedIngestEventSchema);
    expect(schema.version).toBe("2026-10-30T22:25");
    expect(schema.changelog).toEqual([
      { version: "2026-10-30T22:25", change: "Record safe feed failure targets and response byte-limit evidence." },
      { version: "2026-10-29T08:00", change: "Add artifact-upload inventory and publisher-controlled failure article addresses." },
      { version: "2026-10-29", change: "Move operation-specific fields into flexible details." },
      { version: "2026-10-28", change: "Name the publisher on sparse article progress events." },
      { version: "2026-10-26", change: "Earlier changes are in git." },
    ]);
    expect(schema.additionalProperties).toBe(false);
  });

  test("exports the actual runtime input JSON schemas, including nested strict objects", async () => {
    expect(Object.keys(schemas)).toHaveLength(Object.keys(runtimeSchemas).length);
    for (const [name, schema] of Object.entries(runtimeSchemas)) {
      expect(schemas[name]).toEqual(z.toJSONSchema(schema, { io: "input" }));
      const output = schemas[name];
      const branches = output?.oneOf ?? output?.anyOf ?? [output];
      expect(branches.every(branch => branch?.additionalProperties === false)).toBe(true);
    }
    expect(schemas.FeedIngestCandidate?.properties?.version).toMatchObject({
      const: FEED_INGEST_CANDIDATE_VERSION, default: FEED_INGEST_CANDIDATE_VERSION,
    });
    expect(schemas.FeedIngestCandidate?.required).not.toContain("version");
    for (const [name, path] of [["FetchedDocument", "fetched-document/refused.json"], ["PlannerOperation", "planner-operation/started.json"]] as const) {
      const original = await Bun.file(new URL(`../../../tests/fixtures/contracts/${path}`, import.meta.url)).json();
      expect(runtimeSchemas[name].parse(original).version).toBe(original.version);
      expect(runtimeSchemas[name].parse({ ...original, version: undefined }).version).toBe(name === "PlannerOperation" ? PLANNER_OPERATION_VERSION : OPERATION_VERSION);
      if (name === "PlannerOperation") {
        expect(runtimeSchemas[name].parse({ ...original, version: PLANNER_OPERATION_VERSION, created_at: `${at.slice(0, -1)}.123Z` }).created_at).toBe(`${at.slice(0, -1)}.123Z`);
        expect(runtimeSchemas[name].safeParse({ ...original, version: "2026-10-23T18:50", created_at: `${at.slice(0, -1)}.123Z` }).success).toBe(false);
      } else {
        const saved = runtimeSchemas[name].parse(original);
        expect(saved.parent_fetch_request_id).toBeNull();
        expect(saved.parent_batch_id).toBeNull();
        expect(saved.entry_ordinal).toBeNull();
        const linked = runtimeSchemas[name].parse({
          ...original, version: OPERATION_VERSION,
          parent_fetch_request_id: "00000000-0000-4000-8000-000000000010",
          parent_batch_id: "00000000-0000-4000-8000-000000000012", entry_ordinal: 1,
        });
        expect(linked.entry_ordinal).toBe(1);
        expect(runtimeSchemas[name].safeParse({ ...original, version: "2026-10-25" }).success).toBe(false);
      }
    }
    expect(FetchAttemptSchema.parse({ phase: "target", sequence: 0, retry: 0, duration_ms: 0, http_status: 404, failure: "http", error_code: null }).backoff_ms).toBeNull();
    for (const value of [at, `${at.slice(0, -1)}.000Z`, `${at.slice(0, -1)}.123Z`]) expect(RecordedInstantSchema.parse(value)).toBe(value);
    expect(TimestampSchema.safeParse(`${at.slice(0, -1)}.123Z`).success).toBe(false);
    expect(RecordedInstantSchema.safeParse("2026-02-31T00:00:00.123Z").success).toBe(false);
    const batch_id = "00000000-0000-4000-8000-000000000001";
    const context = {
      now: at, captured_at: `${at.slice(0, -1)}.999Z`, date: day, run_id: run,
      correlation_id: "00000000-0000-4000-8000-000000000002",
      writer: { run_id: run, attempt: 1, job: null, pipeline_name: "feed-ingest-plan", task_name: "plan",
        shard: 0, producer: "feed-ingest-plan", git_sha: "a".repeat(40) },
    };
    const parsed = { batch_id, config_sha256: digest, context, request: {}, candidates: [],
      observations: {}, discovered: { availability: "available", rows: [] }, evidence: {},
      history_rows: [], history_days: [], work_rows: [], exclusions: [] };
    expect(PlannerStageContextSchema.parse(context).captured_at).toBe(context.captured_at);
    expect(PlannerStageRequestSchema.parse({})).toEqual({});
    expect(PlannerStageRequestSchema.safeParse({ article_limit: null }).success).toBe(false);
    const parsedBatch = ParsedFeedBatchSchema.parse(parsed);
    expect(parsedBatch.version).toBe(PARSED_FEED_BATCH_VERSION);
    expect(parsedBatch.offers).toEqual([]);
    expect(parsedBatch.feed_fetch_request_id).toBeNull();
    expect(parsedBatch.input_complete).toBe(true);
    const offered = ParsedFeedBatchSchema.parse({
      ...parsed, input_complete: false, feed_fetch_request_id: batch_id,
      offers: [{
        offer_id: digest, source,
        entry: { entry_ordinal: 0, title: null, link: url, categories: [], author: null, published_at: null },
        state: "pending", fetch_request_id: null,
      }],
    });
    expect(offered.offers[0]!.source.feed_id).toBe(source.feed_id);
    expect(offered.input_complete).toBe(false);
    expect(ParsedFeedBatchSchema.safeParse({ ...parsed, input_complete: "true" }).success).toBe(false);
    const batchCandidate = FeedIngestCandidateSchema.parse({
      ...candidate(), correlation_id: context.correlation_id,
    });
    const oldBatch = ParsedFeedBatchSchema.parse({
      ...parsed, version: LEGACY_PARSED_FEED_BATCH_VERSION, candidates: [batchCandidate],
      observations: {
        [batchCandidate.candidate_id]: {
          candidate_id: batchCandidate.candidate_id, http_status: null, robots: "allowed",
          fetch_failure: "network", paywall: null, paywall_evidence: "not-observed",
          extraction: "not-attempted", observed_at: context.now, diagnostics: { fetch_failure: "network" },
        },
      },
    });
    expect(oldBatch.version).toBe(LEGACY_PARSED_FEED_BATCH_VERSION);
    expect(oldBatch.observations[batchCandidate.candidate_id]!.diagnostics?.body_limit).toBeNull();
    expect(ParsedFeedBatchSchema.safeParse({ ...parsed, version: "2026-10-24" }).success).toBe(false);
    expect(ParsedFeedBatchSchema.safeParse({ ...parsed, observations: { [digest]: { candidate_id: digest } } }).success).toBe(false);
    const selected = SelectedFeedBatchSchema.parse({
      batch_id, config_sha256: digest, parsed_batch_id: batch_id, context, articles: [],
      rejected_articles: [],
      selection_started_at_utc: at, evaluated_at: at, health_rows: [], exclusions: [],
      request_report: { from_day: day, through_day: day, complete: false,
        missing_days: [day], unattributed_days: [], input_complete: true, feeds: [] },
    });
    expect(selected.version).toBe("2026-10-29");
    expect(SelectedFeedBatchSchema.safeParse({ ...selected, version: "2026-10-27" }).success).toBe(false);
    expect(PartitionedFeedBatchSchema.parse({ ...selected, selection_batch_id: batch_id, strategy: "none", dispatch_count: 1, work: [0] }).version).toBe(selected.version);
    const observation = PlannerHarvestObservationSchema.parse({
      candidate_id: digest, http_status: null, robots: null, fetch_failure: null, paywall: null,
      paywall_evidence: "not-observed", extraction: "not-attempted", observed_at: context.now,
    });
    expect(observation.diagnostics).toBeNull();
    expect(PlannerHarvestObservationSchema.safeParse({ ...observation, preflight_freshness: null }).success).toBe(false);
    expect(PlannerDiscoveredRowSchema.safeParse({ url_key: digest, first_seen_at: at, date: day, first_seen_run: run }).success).toBe(false);
    expect(plannerStageSchemas.PlannerDiscoveredEvidence).toEqual(z.toJSONSchema(PlannerDiscoveredEvidenceSchema, { io: "input" }));
    expect(StageReferenceRequestSchema.safeParse({ batch_id, path: "batch.json" }).success).toBe(false);
    expect(PartitionArticlesRequestSchema.parse({ batch_id, strategy: "round-robin", shards: 2 })).toEqual({ batch_id, strategy: "round-robin", shards: 2 });
  });
});
