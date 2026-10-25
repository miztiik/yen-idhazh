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
  readFeedIngestEvent, HarvestDiagnosticsSchema, PLANNER_EXCLUSIONS_VERSION,
  FetchAttemptSchema, OPERATION_VERSION, PLANNER_OPERATION_VERSION, RecordedInstantSchema, TimestampSchema,
  EXTRACTION_QUALITY_VERSION,
  PreviousHarvestDiagnosticsSchema,
  ArticleAssessmentContract, EditorialSelectionContract, SourceReliabilityPenaltySchema,
  PUBLISHER_IDENTITY_VERSION, PublisherExposurePenaltySchema, FEED_HISTORY_EVENT_VERSION, CONTRACT_VERSION,
  SOURCE_OPERATIONAL_SCORE_VERSION, SELECTED_FEED_BATCH_VERSION, readSelectedFeedBatch,
  ParsedFeedBatchSchema, SelectedFeedBatchSchema, PartitionedFeedBatchSchema,
  PlannerHarvestObservationSchema, PlannerSeenEvidenceSchema, PlannerSeenRowSchema,
  PlannerStageContextSchema, PlannerStageRequestSchema, StageReferenceRequestSchema,
  PartitionArticlesRequestSchema, OperationalStateReadSchema, SelectionStateCaptureSchema,
  FeedHealthStateSnapshotSchema, FeedHealthStateHeadIndexSchema,
} from "../src/index";
import { plannerStageSchemas, runtimeSchemas, schemas } from "./schema-binding";

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
    observed_at: at, policy, timing_at: null,
    timing_basis: "unavailable", age_hours: null, max_age_hours: null,
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
    event_id: "01504bcb-60d1-5d4d-b92f-d6f0abee2022",
    correlation_id: "7cef34e3-dd9f-40ce-9a56-4d01ff5115cc", run_id: run, attempt: 1,
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
      matched_url_key: digest, published_on: day, failure_code: "network_error",
      matched_url_marker: "blocked", history_window_days: 7,
      diagnostics: HarvestDiagnosticsSchema.parse({
        extraction_failure: "missing-document-root", failure_code: "unknown",
        stopped_stage: "extract", detail: "missing-document-root", fetch_ms: 1, extract_ms: 1,
      }),
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
    for (const diagnostics of [
      { http_status: 600 }, { fetch_ms: -1 }, { extract_ms: 1.5 },
      { error_code: "https://private.example/token" }, { detail: "untrusted page instructions" },
      { warnings: ["malformed-json-ld", "malformed-json-ld"] },
    ]) expect(HarvestDiagnosticsSchema.safeParse(diagnostics).success).toBe(false);
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

  test("retains independent stage context but enforces shared dispatch identity", () => {
    expect(ArticleLabelsSchema.safeParse({ ...labels, lenses: [] }).success).toBe(false);
    expect(PenaltyEvidenceSchema.safeParse({ available: false, value: 0 }).success).toBe(false);
    const row = { content: candidate(), selection: selection(), partition: { strategy: "none", worker_assignment: 0, dispatch_count: 1 } };
    expect(FeedIngestDispatchSchema.safeParse(row).success).toBe(true);
    expect(FeedIngestDispatchSchema.safeParse({ ...row, selection: {
      ...row.selection, date: "2026-10-21", correlation_id: "other",
      policy: { ...row.selection.policy, max_age_hours: 24 },
    } }).success).toBe(true);
    expect(FeedIngestDispatchSchema.safeParse({ ...row, selection: { ...row.selection, candidate_id: "c".repeat(64) } }).success).toBe(false);
    expect(FeedIngestDispatchSchema.safeParse({ ...row, selection: { ...row.selection, source_id: "other" } }).success).toBe(false);
    expect(FeedIngestDispatchSchema.safeParse({ ...row, selection: { ...row.selection, vertical: "other" } }).success).toBe(false);
    expect(FeedIngestDispatchSchema.safeParse({ ...row, selection: { ...row.selection, labels: { ...row.selection.labels, assigned_desk: "other" } } }).success).toBe(false);
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

  test("does not turn unassessed or missing measurements into evidence", async () => {
    const staleOperationalState = OperationalStateReadSchema.parse({
      status: "stale_fallback", state_revision: 4,
      lifecycle_status: "complete", request_status: "complete",
      lifecycle_window_days: 31, lifecycle_window_start: "2026-09-20", lifecycle_window_end: "2026-10-20",
      request_window_days: 7, request_window_start: "2026-10-14", request_window_end: "2026-10-20",
    });
    expect(staleOperationalState).toMatchObject({
      status: "stale_fallback", state_revision: 4,
      lifecycle_window_start: "2026-09-20", request_window_start: "2026-10-14",
    });
    const savedWithoutLifecycleEvidence = OperationalStateReadSchema.parse({
      status: "stale_fallback", state_revision: 5,
      lifecycle_status: "unavailable", lifecycle_window_days: 31,
      lifecycle_window_start: null, lifecycle_window_end: null,
      request_status: "complete", request_window_days: 7,
      request_window_start: "2026-10-14", request_window_end: "2026-10-20",
    });
    expect(savedWithoutLifecycleEvidence.lifecycle_window_start).toBeNull();
    expect(OperationalStateReadSchema.safeParse({
      ...staleOperationalState, status: "unavailable",
    }).success).toBe(false);
    const unavailableOperationalState = OperationalStateReadSchema.parse({
      status: "unavailable", state_revision: null, notices: ["restrictions_unverified"],
      lifecycle_status: "unavailable", request_status: "unavailable",
      lifecycle_window_days: 31, lifecycle_window_start: null, lifecycle_window_end: null,
      request_window_days: 7, request_window_start: null, request_window_end: null,
    });
    expect(unavailableOperationalState.notices).toEqual(["restrictions_unverified"]);
    expect(SelectionStateCaptureSchema.parse({ capture_status: "not_recorded" })).toEqual({
      capture_status: "not_recorded", selection_started_at_utc: null, state: null,
    });
    const snapshot = FeedHealthStateSnapshotSchema.parse(await Bun.file(new URL(
      "../../../tests/fixtures/contracts/feed-health-state/one-complete-snapshot.json", import.meta.url,
    )).json());
    expect(snapshot.request_days[0]!.rows).toHaveLength(3);
    const emptyRosterDigest = createHash("sha256").update("[]", "utf8").digest("hex");
    expect(FeedHealthStateSnapshotSchema.safeParse({
      ...snapshot,
      source_inventory_sha256: emptyRosterDigest,
      source_inventory: [],
      source_results: [],
    }).success).toBe(true);
    expect(FeedHealthStateSnapshotSchema.safeParse({
      ...snapshot, source_inventory_sha256: "d".repeat(64),
    }).success).toBe(false);
    expect(FeedHealthStateSnapshotSchema.safeParse({
      ...snapshot,
      lifecycle_availability: "unavailable",
      lifecycle_days: [{
        ...snapshot.lifecycle_days[0]!,
        read_status: "gap", gap_reason: "index-identity-unavailable", input_identity: null, rows: [],
      }],
      source_results: [{
        ...snapshot.source_results[0]!,
        lifecycle: {
          ...snapshot.source_results[0]!.lifecycle,
          input_status: "unavailable",
          lifecycle: "unknown",
          strikes: null,
          rested_runs: null,
        },
      }],
    }).success).toBe(true);
    const compactFile = snapshot.request_days[0]!.input_identity!.files.find(file => file.tier === "compact")!;
    expect(FeedHealthStateSnapshotSchema.safeParse({
      ...snapshot,
      request_days: [{
        ...snapshot.request_days[0]!,
        input_identity: {
          ...snapshot.request_days[0]!.input_identity!,
          files: snapshot.request_days[0]!.input_identity!.files.map(file =>
            file.file_id === compactFile.file_id ? { ...file, file_sha256: null } : file),
        },
      }],
    }).success).toBe(false);
    expect(FeedHealthStateSnapshotSchema.safeParse({
      ...snapshot,
      request_days: [{
        ...snapshot.request_days[0]!,
        input_identity: {
          ...snapshot.request_days[0]!.input_identity!,
          files: snapshot.request_days[0]!.input_identity!.files.map(file =>
            file.file_id === compactFile.file_id
              ? { ...file, path: file.path.replace("2026/2026.parquet", "2026/2027.parquet") }
              : file),
        },
      }],
    }).success).toBe(false);
    expect(FeedHealthStateSnapshotSchema.safeParse({
      ...snapshot, request_days: [],
    }).success).toBe(false);
    expect(FeedHealthStateSnapshotSchema.safeParse({
      ...snapshot,
      source_results: [{
        ...snapshot.source_results[0]!,
        requests: { ...snapshot.source_results[0]!.requests, request_component_weight: 1.1 },
      }],
    }).success).toBe(false);
    expect(FeedHealthStateSnapshotSchema.safeParse({
      ...snapshot, snapshot_role: "latest",
    }).success).toBe(false);
    const headIndex = FeedHealthStateHeadIndexSchema.parse(await Bun.file(new URL(
      "../../../tests/fixtures/contracts/feed-health-state-head-index/two-snapshots.json", import.meta.url,
    )).json());
    expect(headIndex.latest.state_revision).toBe(4);
    expect(FeedHealthStateHeadIndexSchema.safeParse({
      ...headIndex, previous: { ...headIndex.latest, snapshot_role: "previous" },
    }).success).toBe(false);
    expect(FeedHealthStateHeadIndexSchema.safeParse({
      ...headIndex,
      latest: {
        ...headIndex.latest,
        path: "state/raw/feed-ingest-plan/feed-health-state/snapshots/00000000-0000-8000-8000-000000000003.parquet",
      },
    }).success).toBe(false);
    expect(FeedHealthStateHeadIndexSchema.safeParse({
      ...headIndex,
      previous: {
        ...headIndex.previous!,
        path: headIndex.latest.path,
        file_id: headIndex.latest.file_id,
        state_revision: 3,
        parent_revision: 2,
      },
    }).success).toBe(false);
    const row = assessment();
    expect(ArticleAssessmentRecordSchema.safeParse({ ...row, informative_verdict_status: "assessed" }).success).toBe(false);
    expect(ArticleAssessmentRecordSchema.safeParse({ ...row, score_evidence_status: "assessed" }).success).toBe(false);
    expect(ArticleAssessmentRecordSchema.safeParse({ ...row, timing_basis: "fetched_at" }).success).toBe(false);
    expect(ArticleAssessmentRecordSchema.safeParse({ ...row, suitability_status: "available" }).success).toBe(false);
    const metric = diversity();
    expect(DiversityMetricRowSchema.safeParse({ ...metric, availability: "available" }).success).toBe(false);
    expect(DiversityMetricRowSchema.safeParse({ ...metric, value: Infinity }).success).toBe(false);
    expect(DiversityMetricRowSchema.safeParse({ ...metric, top_k: 1 }).success).toBe(false);
    expect(DiversityMetricRowSchema.safeParse({ ...metric, basis: "stage" }).success).toBe(false);
    const reliability = SourceReliabilityPenaltySchema.parse({
      enabled: true, source_authority_score: 2, reliability_floor: 0.5,
      history: { success_fraction: 0.25, attempted: 4, window_days: 7 },
      production_factor: 0.5, value: 1,
    });
    for (const change of [
      { history: null }, { production_factor: 0.25 }, { value: 0.5 }, { enabled: false },
      { history: { ...reliability.history, attempted: 0 } },
      { history: { ...reliability.history, success_fraction: 1.1 } },
      { history: { ...reliability.history, window_days: 0 } },
    ]) expect(SourceReliabilityPenaltySchema.safeParse({ ...reliability, ...change }).success).toBe(false);
    expect(SourceReliabilityPenaltySchema.safeParse({
      ...reliability, history: null, production_factor: null, value: null,
    }).success).toBe(true);
    expect(SourceReliabilityPenaltySchema.safeParse({ ...reliability, enabled: false, value: 0 }).success).toBe(true);
    const oldSelection = EditorialSelectionContract.legacyVersions[CONTRACT_VERSION];
    const {
      source_reliability: _reliability, source_operational: _sourceOperational,
      publisher_exposure: _exposure, ...previousRatings
    } = selection().ratings;
    const currentSelection = selection();
    const { publisher_id: _publisherId, ...previousSource } = currentSelection.source;
    const original = oldSelection.schema.parse({
      ...currentSelection, source: previousSource, version: CONTRACT_VERSION, ratings: previousRatings,
    });
    const migrated = oldSelection.migrate(original);
    expect(migrated.ratings.source_reliability).toBeNull();
    const {
      source_reliability: _migratedReliability,
      source_operational: _migratedOperational,
      publisher_exposure: _migratedExposure,
      ...migratedRatings
    } = migrated.ratings;
    const { publisher_id: _migratedPublisherId, ...migratedSource } = migrated.source;
    expect({
      ...migrated, source: migratedSource, version: original.version, ratings: migratedRatings,
    }).toEqual(original);
    expect(oldSelection.schema.safeParse({
      ...original, ratings: { ...original.ratings, source_reliability: reliability },
    }).success).toBe(false);
    const exposure = PublisherExposurePenaltySchema.parse({
      day, publisher_id: "recorded-publisher", history_status: "available",
      published_today: 2, selected_so_far: 1, planned_slots: 2, coefficient: 0.25, exposure: 1, value: 0.25,
    });
    const scores = { ...currentSelection.ratings, publisher_exposure: exposure, source: { available: false, value: null } };
    expect(EditorialSelectionContract.schema.safeParse({ ...currentSelection, ratings: scores }).success).toBe(true);
    expect(EditorialSelectionContract.schema.safeParse({
      ...currentSelection, ratings: { ...scores, source: { available: true, value: 0 } },
    }).success).toBe(false);
    for (const change of [
      { published_today: null }, { history_status: "unavailable" }, { exposure: 1.5 },
      { value: 0.5 }, { planned_slots: 0 }, { selected_so_far: -1 },
      { publisher_id: null }, { coefficient: -1 },
    ]) expect(PublisherExposurePenaltySchema.safeParse({ ...exposure, ...change }).success).toBe(false);
    const publisherLegacy = EditorialSelectionContract.legacyVersions[PUBLISHER_IDENTITY_VERSION];
    const prior = publisherLegacy.schema.parse({
      ...currentSelection, version: PUBLISHER_IDENTITY_VERSION,
      ratings: { ...previousRatings, source_reliability: reliability },
    });
    expect(publisherLegacy.migrate(prior).ratings.publisher_exposure).toBeNull();
    expect(publisherLegacy.migrate(prior).ratings.source).toEqual(prior.ratings.source);
    expect(publisherLegacy.schema.safeParse({
      ...prior, ratings: { ...prior.ratings, publisher_exposure: exposure },
    }).success).toBe(false);
  });

  test("binds event discriminators, candidate identities and stages", () => {
    const row = event();
    expect(FeedIngestEventSchema.safeParse({ ...row, audit_event_type: "feed_outcome" }).success).toBe(false);
    expect(FeedIngestEventSchema.safeParse({ ...row, candidate_id: digest }).success).toBe(false);
    expect(FeedIngestEventSchema.safeParse({ ...row, stage: "seal-article-ledger" }).success).toBe(false);
    expect(StageCompletionPayloadSchema.safeParse({ ...row.payload, article_text: "Do not log" }).success).toBe(false);
    expect(FeedIngestEventSchema.safeParse({ ...row, payload: { ...row.payload, kind: "unregistered_observation" } }).success).toBe(false);
    expect(FeedIngestEventSchema.safeParse({ ...row, payload: { ...row.payload, article_text: "Do not log" } }).success).toBe(false);
    expect(FeedIngestEventSchema.safeParse({ ...row, event_id: digest }).success).toBe(false);
    expect(FeedIngestEventSchema.safeParse({ ...row, correlation_id: run }).success).toBe(false);
    expect(FeedIngestEventSchema.safeParse({ ...row, event_id: row.correlation_id }).success).toBe(false);
    expect(FeedIngestEventSchema.safeParse({ ...row, correlation_id: row.event_id }).success).toBe(false);
  });

  test("migrates the historical event fixture with its sole native declaration", async () => {
    const fixture = await Bun.file(new URL(
      "../../../tests/fixtures/contracts/feed-ingest-event/one-observation.json", import.meta.url,
    )).json();
    const incompatible = structuredClone(fixture);
    incompatible.payload.assessment.reason = "ALREADY_PUBLISHED";
    incompatible.payload.assessment.decision = "rejected";
    expect(() => readFeedIngestEvent(incompatible)).toThrow();
    const record = readFeedIngestEvent(fixture);
    expect(record.payload.kind).toBe("candidate_decision");
    if (record.payload.kind !== "candidate_decision") throw new Error("Fixture must carry an article assessment");
    expect(record.payload.assessment.diagnostics).toBeNull();
    expect(record.payload.assessment.version).toBe(ArticleAssessmentContract.schemaVersion);
    expect(record.payload.assessment).toEqual({
      ...fixture.payload.assessment, version: SOURCE_OPERATIONAL_SCORE_VERSION,
      source: { ...fixture.payload.assessment.source, publisher_id: null }, diagnostics: null,
    });
    expect(readFeedIngestEvent(JSON.parse(JSON.stringify(record)))).toEqual(record);
    const prior = {
      ...fixture, version: PLANNER_EXCLUSIONS_VERSION, payload: {
        ...fixture.payload, assessment: {
          ...fixture.payload.assessment, version: PLANNER_EXCLUSIONS_VERSION,
          diagnostics: PreviousHarvestDiagnosticsSchema.parse({ extract_ms: 2 }),
        },
      },
    };
    const migrated = readFeedIngestEvent(prior);
    if (migrated.payload.kind !== "candidate_decision") throw new Error("Fixture must retain its assessment");
    expect(migrated.payload.assessment.diagnostics).toMatchObject({ extract_ms: 2, quality: null });
    expect(migrated.payload.assessment.version).toBe(ArticleAssessmentContract.schemaVersion);
    expect(() => readFeedIngestEvent({
      ...prior, payload: { ...prior.payload, assessment: {
        ...prior.payload.assessment, diagnostics: { ...prior.payload.assessment.diagnostics, quality: null },
      } },
    })).toThrow();
    const schema = z.toJSONSchema(FeedIngestEventSchema, { io: "input" });
    expect(schema.$id).toBe("feed-ingest-event");
    expect(schema.version).toBe(record.version);
    expect(schema.changelog).toEqual([{
      version: record.version,
      change: "Carry the current article-assessment schema in planner events.",
    }, {
      version: PUBLISHER_IDENTITY_VERSION,
      change: "Record curated publisher identity in source snapshots.",
    }, {
      version: "2026-10-24",
      change: "Record separate source-reliability penalties on portfolio decisions.",
    }, {
      version: FEED_HISTORY_EVENT_VERSION,
      change: "Record native feed rest, retirement, reliability and daily publication evidence.",
    }, {
      version: "2026-10-22T20:30",
      change: "Earlier changes are in git.",
    }]);
    expect(schema.additionalProperties).toBe(false);
    const { publisher_id: _publisherId, ...previousSource } = source;
    const historicalFeed = {
      ...event(), version: PLANNER_EXCLUSIONS_VERSION,
      audit_event_type: "feed_outcome", source_id: source.source_id,
      payload: {
        kind: "feed_outcome", source: previousSource, fetch_status: "success", parse_status: "empty",
        parsed_count: 0, harvested_count: 0, fetch_duration_ms: 1, parse_duration_ms: 1,
        rejection_reason: "FEED_EMPTY", diagnostics: null,
      },
    };
    const migratedFeed = readFeedIngestEvent(historicalFeed);
    expect(migratedFeed.payload).toMatchObject({ history: null });
    expect(migratedFeed.version).toBe(record.version);
    for (const version of [EXTRACTION_QUALITY_VERSION, FEED_HISTORY_EVENT_VERSION]) {
      const previous = { ...prior, version, payload: { ...prior.payload, assessment: {
        ...prior.payload.assessment, version: EXTRACTION_QUALITY_VERSION,
        diagnostics: HarvestDiagnosticsSchema.parse({ extract_ms: 2 }),
      } } };
      const migrated = readFeedIngestEvent(previous);
      expect(migrated.payload).toMatchObject({ assessment: {
        version: SOURCE_OPERATIONAL_SCORE_VERSION, diagnostics: { extract_ms: 2, quality: null },
      } });
      expect(readFeedIngestEvent(JSON.parse(JSON.stringify(migrated)))).toEqual(migrated);
    }
  });

  test("exports the actual runtime input JSON schemas, including nested strict objects", async () => {
    expect(Object.keys(schemas)).toHaveLength(Object.keys(runtimeSchemas).length);
    for (const [name, schema] of Object.entries(runtimeSchemas)) {
      expect(schemas[name]).toEqual(z.toJSONSchema(schema, { io: "input" }));
      const output = schemas[name];
      const branches = output?.oneOf ?? output?.anyOf ?? [output];
      expect(branches.every(branch => branch?.additionalProperties === false)).toBe(true);
    }
    const version = schemas.FeedIngestCandidate?.properties?.version;
    expect(version).toMatchObject({ const: PUBLISHER_IDENTITY_VERSION, default: PUBLISHER_IDENTITY_VERSION });
    expect(schemas.FeedIngestCandidate?.required).not.toContain("version");
    for (const [name, path] of [
      ["FetchedDocument", "fetched-document/refused.json"],
      ["PlannerOperation", "planner-operation/started.json"],
    ] as const) {
      const original = await Bun.file(new URL(
        `../../../tests/fixtures/contracts/${path}`, import.meta.url,
      )).json();
      expect(runtimeSchemas[name].parse(original).version).toBe("2026-10-23");
      expect(runtimeSchemas[name].parse({ ...original, version: undefined }).version)
        .toBe(name === "PlannerOperation" ? PLANNER_OPERATION_VERSION : OPERATION_VERSION);
      if (name === "PlannerOperation") {
        expect(runtimeSchemas[name].parse(original).created_at).toBe(original.created_at);
        expect(runtimeSchemas[name].parse({ ...original, version: PLANNER_OPERATION_VERSION,
          created_at: `${at.slice(0, -1)}.123Z` }).created_at)
          .toBe(`${at.slice(0, -1)}.123Z`);
      }
    }
    const earlierAttempt = FetchAttemptSchema.parse({
      phase: "target", sequence: 0, retry: 0, duration_ms: 0,
      http_status: 404, failure: "http", error_code: null,
    });
    expect(earlierAttempt.backoff_ms).toBeNull();
    expect(earlierAttempt.retry_total_ms).toBeNull();
    for (const value of [at, `${at.slice(0, -1)}.000Z`, `${at.slice(0, -1)}.123Z`]) {
      expect(RecordedInstantSchema.parse(value)).toBe(value);
    }
    expect(TimestampSchema.safeParse(`${at.slice(0, -1)}.123Z`).success).toBe(false);
    expect(RecordedInstantSchema.safeParse("2026-02-31T00:00:00.123Z").success).toBe(false);

    const batchId = "00000000-0000-4000-8000-000000000001";
    const correlationId = "00000000-0000-4000-8000-000000000002";
    const context = {
      now: "2026-10-24T12:34:56Z", captured_at: "2026-10-24T12:34:56.999Z",
      date: "2026-10-24", run_id: "2026-10-24-1", correlation_id: correlationId,
      writer: {
        run_id: "2026-10-24-1", attempt: 1, job: null, pipeline_name: "feed-ingest-plan",
        task_name: "plan", shard: 0, producer: "feed-ingest-plan", git_sha: "a".repeat(40),
      },
    };
    const parsed = {
      batch_id: batchId, config_sha256: digest, context, request: {},
      candidates: [], observations: {}, seen: { availability: "available", rows: [] },
      evidence: {}, opportunity: {
        covered_event_clusters: null, underrepresented_verticals: null, origin: null,
      },
      operational_history: {}, rejections: [],
    };
    expect(PlannerStageContextSchema.parse(context).captured_at).toBe(context.captured_at);
    expect(PlannerStageRequestSchema.parse({})).toEqual({});
    expect(PlannerStageRequestSchema.safeParse({ article_limit: null }).success).toBe(false);
    expect(ParsedFeedBatchSchema.parse(parsed).version).toBe(PUBLISHER_IDENTITY_VERSION);
    const selected = SelectedFeedBatchSchema.parse({
      version: SELECTED_FEED_BATCH_VERSION,
      batch_id: batchId, config_sha256: digest, parsed_batch_id: batchId,
      context, selection_state: {
        capture_status: "captured", selection_started_at_utc: context.now,
        state: {
          status: "unavailable", state_revision: null, notices: ["restrictions_unverified"],
          lifecycle_status: "unavailable", request_status: "unavailable",
          lifecycle_window_days: 31, lifecycle_window_start: null, lifecycle_window_end: null,
          request_window_days: 7, request_window_start: null, request_window_end: null,
        },
      },
      selections: [], rejections: [],
    });
    expect(selected.version).toBe(SELECTED_FEED_BATCH_VERSION);
    const legacySelection = await Bun.file(new URL(
      "../../../tests/fixtures/contracts/selected-feed-batch/empty.json", import.meta.url,
    )).json();
    expect(readSelectedFeedBatch(legacySelection).selection_state.capture_status).toBe("not_recorded");
    expect(PartitionedFeedBatchSchema.parse({
      batch_id: batchId, config_sha256: digest, selection_batch_id: batchId,
      context, strategy: "none", dispatch_count: 1, work: [0], dispatches: [],
    }).version).toBe(SOURCE_OPERATIONAL_SCORE_VERSION);
    expect(ParsedFeedBatchSchema.safeParse({
      ...parsed, observations: { [digest]: { candidate_id: digest } },
    }).success).toBe(false);
    expect(PartitionedFeedBatchSchema.safeParse({
      batch_id: batchId, config_sha256: digest, selection_batch_id: batchId,
      context, strategy: "none", dispatch_count: 2, work: [0], dispatches: [],
    }).success).toBe(false);
    const observation = PlannerHarvestObservationSchema.parse({
      candidate_id: digest, http_status: null, robots: null, fetch_failure: null,
      paywall: null, paywall_evidence: "not-observed", extraction: "not-attempted",
      observed_at: context.now,
    });
    expect(observation.diagnostics).toBeNull();
    expect(PlannerHarvestObservationSchema.safeParse({
      ...observation, preflight_freshness: null,
    }).success).toBe(false);
    expect(PlannerSeenEvidenceSchema.safeParse({
      availability: "available", rows: [{
        url_key: digest, first_seen_at: context.now, first_seen_run: context.run_id,
      }],
    }).success).toBe(false);
    expect(PlannerSeenRowSchema.safeParse({
      version: "2026-10-24", url_key: digest,
      first_seen_at: context.now, first_seen_run: context.run_id,
    }).success).toBe(true);
    expect(plannerStageSchemas.PlannerSeenEvidence).toEqual(
      z.toJSONSchema(PlannerSeenEvidenceSchema, { io: "input" }),
    );
    expect(StageReferenceRequestSchema.safeParse({
      batch_id: batchId, path: "batch.json",
    }).success).toBe(false);
    expect(PartitionArticlesRequestSchema.parse({
      batch_id: batchId, strategy: "round-robin", shards: 2,
    })).toEqual({
      batch_id: batchId, strategy: "round-robin", shards: 2,
    });
  });
});
