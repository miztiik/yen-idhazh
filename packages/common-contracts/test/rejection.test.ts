/** Which malformed identities and missing evidence must contract readers refuse? */
import { describe, expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { z } from "zod";
import {
  ArticleAssessmentRecordSchema, ArticleLabelsSchema, CandidateRejectionRecordSchema,
  DiversityMetricRowSchema, EditorialSelectionRowSchema, FeedIngestCandidateSchema,
  FeedIngestDispatchSchema, FeedIngestEventSchema, FileEnvelopeSchema,
  LedgerCompletionEvidenceSchema, PartitionAssignmentSchema, PenaltyEvidenceSchema,
  PolicyIdentitySchema, REASON_STAGES, REQUIRED_DETAILS, RejectionDetailsSchema,
  SourceRunRecordSchema, SourceSnapshotSchema, StageCompletionPayloadSchema,
  WriterIdentitySchema, deriveCandidateId, deriveUrlKey, validateEnvelopeContainer,
} from "../src/index";
import { runtimeSchemas, schemas } from "./schema-binding";

const day = "2026-10-20";
const at = `${day}T12:00:00Z`;
const run = `${day}-7`;
const url = "https://example.com/article?x=1";
const digest = "a".repeat(64);
const source = SourceSnapshotSchema.parse({
  source_id: "example", feed_url: "https://example.com/feed", title: "Example",
  vertical: "science", kind: "new-kind", tier: 4, form: "article", status: "active",
  weight: 1, applied_tier_weight: 0.6,
});
const labels = ArticleLabelsSchema.parse({
  assigned_desk: null, lenses: null, event_types: null, event_cluster_id: null,
  entities: null, origin: null, matcher_version: null,
});
const policy = PolicyIdentitySchema.parse({
  policy_version: "initial", config_sha256: digest, min_words_article: 100,
  min_words_abstract: 20, max_age_hours: 48, recency_half_life_hours: 12,
  recency_weight: 1, source_authority_weight: 1, base_source_allowance: 3,
  bonus_uncovered_event_cluster: 1, bonus_underrepresented_vertical: 1,
  bonus_unique_evidence: 1, lambda_source: 1, lambda_source_kind: 0.1,
  lambda_domain: 1, lambda_vertical: 1, lambda_desk: 1, lambda_lens: 1,
  lambda_event_type: 1, lambda_event_cluster: 1, lambda_entity: 1, lambda_coverage: 1,
});
const ratings = {
  base_article_score: 1, marginal_score: 1,
  ...Object.fromEntries(["source", "source_kind", "domain", "vertical", "desk", "lens", "event_type", "event_cluster", "entity", "coverage"].map(key => [key, { available: false, value: null }])),
  source_allowance: 3, bonus_uncovered_event_cluster: false,
  bonus_underrepresented_vertical: false, bonus_unique_evidence: false,
  carrier_outlets: [], representative_url_key: null, replacement_url_key: null,
  exploration_slot: false, cap_relaxations: [],
};
function candidate() {
  return FeedIngestCandidateSchema.parse({
    date: day, correlation_id: "correlation", run_id: run,
    candidate_id: deriveCandidateId(run, source.source_id, 0), entry_ordinal: 0,
    source_id: source.source_id, vertical: source.vertical, source,
    canonical_url: url, url_key: deriveUrlKey(url), title: "An article", categories: [],
    article_text: "A recorded article.", word_count: 3, author: null,
    published_at: null, fetched_at: at, labels, policy,
  });
}
function selection() {
  const content = candidate();
  return EditorialSelectionRowSchema.parse({
    date: day, correlation_id: content.correlation_id, candidate_id: content.candidate_id,
    source_id: source.source_id, vertical: source.vertical, source, canonical_url: url,
    url_key: content.url_key, labels, editorial_rank: 1, estimated_work: 3, ratings, policy,
  });
}
function rejection() {
  return CandidateRejectionRecordSchema.parse({
    date: day, correlation_id: "correlation", source_id: source.source_id,
    feed_url: source.feed_url, subject: "article", candidate_id: candidate().candidate_id,
    url_key: deriveUrlKey(url), canonical_url: url, title: "An article", categories: [],
    stage: "screen-article-candidates", drop_reason: "STUB_CONTENT",
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
    file_id: "0199ba8e-9920-8000-8000-000000000001",
    content_sha256: digest, writer: "idhazh_typescript.ledger.parquet",
    writer_version: "1", compression: "zstd",
  });
}
function sourceRun() {
  return SourceRunRecordSchema.parse({
    date: day, correlation_id: "correlation", run_id: run, attempt: 1,
    source_id: source.source_id, source, status: "active",
    fetch_status: "success", parse_status: "empty", parsed_count: 0,
    harvested_count: 0, fresh_count: 0, duplicate_count: 0, eligible_count: 0,
    normalized_count: 0, selected_count: 0, published_count: null, lead_count: null,
    drop_reasons: [], fetch_duration_ms: 1, parse_duration_ms: 1,
    last_failure_at: null, last_failure_reason: null, history_success_fraction: null,
    history_success_attempts: null, history_window_days: null,
    observation_phase: "plan_complete", observed_at: at, expected_source_count: 1,
    completion_evidence: ["article-assessments", "diversity", "editorial-selections", "dispatches", "rejections"].map(ledger => ({ ledger, row_count: 0, files: [] })),
  });
}
function assessment() {
  return ArticleAssessmentRecordSchema.parse({
    date: day, correlation_id: "correlation", candidate_id: candidate().candidate_id,
    source_id: source.source_id, source, labels, canonical_url: null, url_key: null,
    stage: "harvest-feeds", decision: "rejected", reason: "MISSING_REQUIRED_FIELDS",
    observed_at: at, policy, effective_published_at: null,
    publication_clock: "unavailable", age_hours: null, max_age_hours: null,
    extracted_word_count: null, source_form: "article", extraction_outcome: "not_attempted",
    word_threshold: null, author_present: null, publisher_identity: null,
    attribution_status: "unavailable", paywall: null, categories: null,
    required_fields_present: null, suitability_status: "unavailable",
    informative_verdict_status: "not_assessed", informative_verdict: null,
    informative_evaluator_version: null, suitability_verdict_status: "not_assessed",
    suitability_verdict: null, suitability_evaluator_version: null, score_evidence: null,
    score_evidence_status: "not_assessed",
  });
}
function diversity() {
  return DiversityMetricRowSchema.parse({
    date: day, correlation_id: "correlation", run_id: run, metric: "selection_coverage",
    basis: "selected", as_of: at, window_start: null, window_end: null,
    dimension: "source", stage: null, window_days: null, dimension_value: null,
    value: null, unit: "ratio", before_value: null, after_value: null,
    numerator: 0, denominator: 0, item_count: 0, source_count: 0,
    history_coverage_days: null, history_required_days: null, algorithm_version: "initial",
    config_sha256: digest, availability: "unavailable", unavailable_reason: "empty_denominator",
  });
}
function event() {
  return FeedIngestEventSchema.parse({
    event_id: digest, correlation_id: "correlation", run_id: run, attempt: 1,
    sequence: 0, occurred_at: at, stage: "harvest-feeds", audit_event_type: "stage_completion",
    source_id: null, candidate_id: null, elapsed_ms: 1, step_elapsed_ms: 1, policy,
    payload: { kind: "stage_completion", stage: "harvest-feeds", input_count: 0,
      output_count: 0, terminal_rejection_count: 0, source_count: 1 },
  });
}

describe("rejection evidence", () => {
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
  });

  test("enforces every reason's stage and required measurements", () => {
    const observations = RejectionDetailsSchema.parse({
      http_status: 503, timeout_ms: 200, words_found: 3, words_required: 100,
      age_hours: 60, max_age_hours: 48, observed_value: 1, limit: 2,
      matched_url_key: digest, history_window_days: 7,
    });
    for (const [reason, stages] of Object.entries(REASON_STAGES)) {
      const feedOnly = ["SOURCE_INACTIVE", "FEED_PARSE_FAILED", "FEED_EMPTY"].includes(reason);
      const row = { ...rejection(), stage: stages[0], drop_reason: reason, details: observations,
        ...(feedOnly ? { subject: "feed", candidate_id: null, canonical_url: null, url_key: null, title: null } : {}) };
      expect(CandidateRejectionRecordSchema.safeParse(row).success).toBe(true);
      expect(CandidateRejectionRecordSchema.safeParse({ ...row, stage: "seal-article-ledger" }).success).toBe(false);
      for (const field of REQUIRED_DETAILS[reason as keyof typeof REQUIRED_DETAILS] ?? []) {
        expect(CandidateRejectionRecordSchema.safeParse({ ...row, details: { ...observations, [field]: null } }).success).toBe(false);
      }
    }
  });

  test("refuses unknown fields, coercion, nonfinite values and non-UTC timestamps", () => {
    const row = rejection();
    for (const changed of [
      { ...row, extra: true }, { ...row, details: { ...row.details, untyped: 1 } },
      { ...row, details: { ...row.details, words_found: "3" } },
      { ...row, details: { ...row.details, observed_value: Infinity } },
      { ...row, details: { ...row.details, observed_value: NaN } },
      { ...row, rejected_at: "2026-10-20T12:00:00+00:00" },
      { ...row, date: "2026-10-19" }, { ...row, url_key: digest },
    ]) expect(CandidateRejectionRecordSchema.safeParse(changed).success).toBe(false);
  });
});

describe("content and writer identity", () => {
  test("hashes exact canonical URL bytes and newline-separated candidate identity", () => {
    expect(deriveUrlKey(url)).toBe(createHash("sha256").update(url).digest("hex"));
    expect(deriveCandidateId(run, "example", 0)).toBe(createHash("sha256").update(`${run}\nexample\n0`).digest("hex"));
    expect(deriveCandidateId(run, "example", 0)).not.toBe(deriveCandidateId(run, "example", 1));
    expect(() => deriveCandidateId(run, "example", -1)).toThrow();
    expect(() => deriveCandidateId(run, "example", 0.5)).toThrow();
    expect(FeedIngestCandidateSchema.safeParse({ ...candidate(), candidate_id: digest }).success).toBe(false);
    expect(FeedIngestCandidateSchema.safeParse({ ...candidate(), vertical: "other" }).success).toBe(false);
  });

  test("retains unknown label evidence and compares nested dispatch identity structurally", () => {
    expect(ArticleLabelsSchema.safeParse({ ...labels, lenses: [] }).success).toBe(false);
    expect(PenaltyEvidenceSchema.safeParse({ available: false, value: 0 }).success).toBe(false);
    const row = { content: candidate(), selection: selection(), partition: { strategy: "none", worker_assignment: 0, dispatch_count: 1 } };
    expect(FeedIngestDispatchSchema.safeParse(row).success).toBe(true);
    expect(FeedIngestDispatchSchema.safeParse({ ...row, selection: { ...row.selection, correlation_id: "other" } }).success).toBe(false);
    expect(PartitionAssignmentSchema.safeParse({ strategy: "none", worker_assignment: 0, dispatch_count: 2 }).success).toBe(false);
    expect(PartitionAssignmentSchema.safeParse({ strategy: "round-robin", worker_assignment: 2, dispatch_count: 2 }).success).toBe(false);
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
  });
});

describe("planning audit contracts", () => {
  test("validates diversity values by unit without rounding fractional source estimates", () => {
    const base = { ...diversity(), availability: "available", unavailable_reason: null };
    const ratio = { ...base, unit: "ratio" };
    const count = { ...base, metric: "source_event_overlap", unit: "count", window_days: 7 };
    const sources = { ...base, metric: "effective_number_of_sources", unit: "sources" };
    for (const value of [0, 0.5, 1]) expect(DiversityMetricRowSchema.safeParse({ ...ratio, value }).success).toBe(true);
    for (const value of [-0.1, 1.1, Infinity, NaN]) expect(DiversityMetricRowSchema.safeParse({ ...ratio, value }).success).toBe(false);
    for (const value of [0, 1, 42]) expect(DiversityMetricRowSchema.safeParse({ ...count, value }).success).toBe(true);
    for (const value of [-1, 0.5, Infinity, NaN]) expect(DiversityMetricRowSchema.safeParse({ ...count, value }).success).toBe(false);
    for (const value of [0, 1, 2.5]) expect(DiversityMetricRowSchema.safeParse({ ...sources, value }).success).toBe(true);
    for (const value of [-0.1, Infinity, NaN]) expect(DiversityMetricRowSchema.safeParse({ ...sources, value }).success).toBe(false);
  });

  test("permits signed diversity loss only with nonnegative finite source readings", () => {
    const base = {
      ...diversity(), availability: "available", unavailable_reason: null,
      metric: "lost_diversity_by_stage", unit: "source_difference",
      basis: "stage", stage: "selection",
    };
    for (const [before_value, after_value] of [[1, 2.5], [2.5, 1], [0, 0]] as const) {
      expect(DiversityMetricRowSchema.safeParse({ ...base, before_value, after_value, value: before_value - after_value }).success).toBe(true);
    }
    for (const [before_value, after_value] of [[-1, 0], [0, -1], [Infinity, 1], [1, Infinity], [NaN, 1], [1, NaN]] as const) {
      expect(DiversityMetricRowSchema.safeParse({ ...base, before_value, after_value, value: before_value - after_value }).success).toBe(false);
    }
    expect(DiversityMetricRowSchema.safeParse({ ...base, before_value: 1, after_value: 2, value: 1 }).success).toBe(false);
  });

  test("retains known-empty completion evidence and refuses partial or conflicting totals", () => {
    const row = sourceRun();
    expect(SourceRunRecordSchema.safeParse({ ...row, completion_evidence: [] }).success).toBe(false);
    expect(SourceRunRecordSchema.safeParse({ ...row, published_count: 0 }).success).toBe(false);
    expect(SourceRunRecordSchema.safeParse({ ...row, history_success_fraction: 0.5 }).success).toBe(false);
    expect(LedgerCompletionEvidenceSchema.safeParse({ ledger: "rejections", row_count: 1, files: [] }).success).toBe(false);
    expect(SourceRunRecordSchema.safeParse({ ...row, fetch_status: "not_requested" }).success).toBe(false);
  });

  test("does not turn unassessed or missing measurements into evidence", () => {
    const row = assessment();
    expect(ArticleAssessmentRecordSchema.safeParse({ ...row, informative_verdict_status: "assessed" }).success).toBe(false);
    expect(ArticleAssessmentRecordSchema.safeParse({ ...row, score_evidence_status: "assessed" }).success).toBe(false);
    expect(ArticleAssessmentRecordSchema.safeParse({ ...row, publication_clock: "fetched_at" }).success).toBe(false);
    expect(ArticleAssessmentRecordSchema.safeParse({ ...row, suitability_status: "available" }).success).toBe(false);
    const metric = diversity();
    expect(DiversityMetricRowSchema.safeParse({ ...metric, availability: "available" }).success).toBe(false);
    expect(DiversityMetricRowSchema.safeParse({ ...metric, value: Infinity }).success).toBe(false);
    expect(DiversityMetricRowSchema.safeParse({ ...metric, top_k: 1 }).success).toBe(false);
    expect(DiversityMetricRowSchema.safeParse({ ...metric, basis: "stage" }).success).toBe(false);
  });

  test("binds event discriminators, candidate identities and stages", () => {
    const row = event();
    expect(FeedIngestEventSchema.safeParse({ ...row, audit_event_type: "feed_outcome" }).success).toBe(false);
    expect(FeedIngestEventSchema.safeParse({ ...row, candidate_id: digest }).success).toBe(false);
    expect(FeedIngestEventSchema.safeParse({ ...row, stage: "seal-article-ledger" }).success).toBe(false);
    expect(StageCompletionPayloadSchema.safeParse({ ...row.payload, article_text: "Do not log" }).success).toBe(false);
  });

  test("exports the actual runtime input JSON schemas, including nested strict objects", () => {
    expect(Object.keys(schemas)).toHaveLength(Object.keys(runtimeSchemas).length);
    for (const [name, schema] of Object.entries(runtimeSchemas)) {
      expect(schemas[name]).toEqual(z.toJSONSchema(schema, { io: "input" }));
      expect(schemas[name]?.additionalProperties).toBe(false);
    }
    const version = schemas.FeedIngestCandidate?.properties?.version;
    expect(version).toMatchObject({ const: "2026-10-20", default: "2026-10-20" });
    expect(schemas.FeedIngestCandidate?.required).not.toContain("version");
  });
});
