/** Which complete feed-planning snapshots may cross from one stage to the next? */
import { z } from "zod";
import { FeedIngestCandidateSchema, PreviousFeedIngestCandidateSchema, readFeedIngestCandidate } from "./candidate.schema";
import {
  FeedIngestDispatchSchema, PreviousReliableFeedIngestDispatchSchema, readFeedIngestDispatch,
} from "./dispatch.schema";
import { WriterIdentitySchema } from "./envelope.schema";
import { CandidateRejectionRecordSchema } from "./rejection.schema";
import { HarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";
import {
  EditorialSelectionContract, EditorialSelectionRowSchema, PreviousReliableEditorialSelectionSchema,
} from "./editorial-selection.schema";
import { OperationalHistorySchema } from "./source.schema";
import {
  DateStampSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema,
  PositiveSchema, RunIdSchema, SchemaVersionSchema, Sha256Schema, SlugSchema,
  TimestampSchema, reject,
} from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { PLANNER_STAGE_VERSION, SOURCE_RELIABILITY_VERSION } from "../version";

export const PlannerStageContextSchema = z.strictObject({
  now: TimestampSchema.refine(value => {
    const instant = Date.parse(value);
    return Number.isFinite(instant)
      && new Date(instant).toISOString().replace(".000Z", "Z") === value;
  }, "must be a valid UTC instant"),
  captured_at: RecordedInstantSchema, date: DateStampSchema,
  run_id: RunIdSchema, correlation_id: z.uuid({ version: "v4" }), writer: WriterIdentitySchema,
}).superRefine((value, ctx) => {
  if (`${value.captured_at.slice(0, 19)}Z` !== value.now || value.date !== value.now.slice(0, 10)) {
    reject(ctx, "context clock, captured instant and UTC date must agree");
  }
  if (!value.run_id.startsWith(`${value.date}-`) || value.writer.run_id !== value.run_id) {
    reject(ctx, "context run and writer must match its UTC date");
  }
  if (value.writer.pipeline_name !== "feed-ingest-plan" || value.writer.task_name !== "plan") {
    reject(ctx, "context writer must identify the feed-ingest-plan task");
  }
});
export type PlannerStageContext = z.infer<typeof PlannerStageContextSchema>;

export const PlannerStageRequestSchema = z.strictObject({
  freshness_hours: z.number().finite().optional(),
  article_limit: PositiveCountSchema.optional(),
  shards: PositiveCountSchema.optional(),
  partition_strategy: z.enum(["bin-pack", "round-robin", "none"]).optional(),
});
export type PlannerStageRequest = z.infer<typeof PlannerStageRequestSchema>;

export const RecordedIdentitySchema = z.strictObject({
  value: NonEmptySchema, origin: NonEmptySchema,
});
export const PrimaryEvidenceSchema = z.strictObject({
  ids: z.array(NonEmptySchema).min(1), origin: NonEmptySchema,
});
export const PlannerArticleEvidenceSchema = z.strictObject({
  publisher: RecordedIdentitySchema.nullable(),
  parent_domain: RecordedIdentitySchema.nullable(),
  operational: OperationalHistorySchema.nullable(),
  primary_evidence: PrimaryEvidenceSchema.nullable(),
  estimated_work: NonNegativeSchema,
});
export type PlannerArticleEvidence = z.infer<typeof PlannerArticleEvidenceSchema>;

export const PlannerOpportunityEvidenceSchema = z.strictObject({
  covered_event_clusters: z.array(NonEmptySchema).nullable(),
  underrepresented_verticals: z.array(NonEmptySchema).nullable(),
  origin: NonEmptySchema.nullable(),
}).superRefine((value, ctx) => {
  const hasEvidence = value.covered_event_clusters !== null
    || value.underrepresented_verticals !== null;
  if (hasEvidence !== (value.origin !== null)) {
    reject(ctx, "opportunity origin must match recorded opportunity evidence");
  }
});
export type PlannerOpportunityEvidence = z.infer<typeof PlannerOpportunityEvidenceSchema>;

export const PreflightFreshnessSchema = z.strictObject({
  timing_at: TimestampSchema, timing_source: z.literal("published_at"),
  age_hours: PositiveSchema, recency_bonus: NonNegativeSchema,
});
export type PreflightFreshness = z.infer<typeof PreflightFreshnessSchema>;

export const PlannerHarvestObservationSchema = z.strictObject({
  candidate_id: Sha256Schema,
  http_status: z.int().min(100).max(599).nullable(),
  robots: z.enum(["allowed", "denied", "unknown"]).nullable(),
  fetch_failure: z.enum([
    "http", "timeout", "unsafe-target", "dns", "network", "robots-denied",
    "robots-unknown", "body-too-large", "redirect-loop",
  ]).nullable(),
  paywall: z.boolean().nullable(),
  paywall_evidence: z.enum(["json-ld", "configured-marker", "none", "not-observed"]),
  extraction: z.enum(["success", "empty", "failed", "not-attempted"]),
  observed_at: TimestampSchema,
  diagnostics: HarvestDiagnosticsSchema.nullable().default(null),
  preflight_freshness: PreflightFreshnessSchema.optional(),
});
export type PlannerHarvestObservation = z.infer<typeof PlannerHarvestObservationSchema>;

export const PlannerSeenRowSchema = z.strictObject({
  version: SchemaVersionSchema,
  url_key: Sha256Schema,
  first_seen_at: TimestampSchema.refine(value => {
    const instant = Date.parse(value);
    return Number.isFinite(instant)
      && new Date(instant).toISOString().replace(".000Z", "Z") === value;
  }, "must be a valid UTC instant"),
  first_seen_run: RunIdSchema,
});
export const PlannerSeenAvailableSchema = z.strictObject({
  availability: z.literal("available"), rows: z.array(PlannerSeenRowSchema),
});
export const PlannerSeenUnavailableSchema = z.strictObject({
  availability: z.literal("unavailable"),
});
export const PlannerSeenEvidenceSchema = z.discriminatedUnion("availability", [
  PlannerSeenAvailableSchema, PlannerSeenUnavailableSchema,
]);
export type PlannerSeenEvidence = z.infer<typeof PlannerSeenEvidenceSchema>;

export const ParsedFeedBatchSchema = z.strictObject({
  version: z.literal(PLANNER_STAGE_VERSION).default(PLANNER_STAGE_VERSION),
  batch_id: z.uuid({ version: "v4" }),
  config_sha256: Sha256Schema,
  context: PlannerStageContextSchema,
  request: PlannerStageRequestSchema,
  candidates: z.array(FeedIngestCandidateSchema),
  observations: z.record(Sha256Schema, PlannerHarvestObservationSchema),
  seen: PlannerSeenEvidenceSchema,
  evidence: z.record(Sha256Schema, PlannerArticleEvidenceSchema),
  opportunity: PlannerOpportunityEvidenceSchema,
  operational_history: z.record(SlugSchema, OperationalHistorySchema.nullable()),
  rejections: z.array(CandidateRejectionRecordSchema),
}).superRefine((value, ctx) => {
  const candidateIds = value.candidates.map(candidate => candidate.candidate_id);
  if (new Set(candidateIds).size !== candidateIds.length) {
    reject(ctx, "candidate identities must be distinct");
  }
  const expectedCorrelation = value.context.correlation_id;
  for (const candidate of value.candidates) {
    if (
      candidate.run_id !== value.context.run_id
      || candidate.correlation_id !== expectedCorrelation
      || candidate.date !== value.context.date
    ) reject(ctx, "candidate identity must match the batch context");
  }
  for (const rejection of value.rejections) {
    if (
      rejection.date !== value.context.date
      || rejection.correlation_id !== expectedCorrelation
    ) reject(ctx, "rejection identity must match the batch context");
  }
  const ids = new Set(candidateIds);
  const observationIds = Object.keys(value.observations);
  if (observationIds.length !== ids.size || observationIds.some(id => !ids.has(id))) {
    reject(ctx, "observation keys must match candidate identities");
  }
  for (const [key, observation] of Object.entries(value.observations)) {
    if (key !== observation.candidate_id) {
      reject(ctx, "observation identity must match its key", ["observations", key]);
    }
  }
  if (Object.keys(value.evidence).some(id => !ids.has(id))) {
    reject(ctx, "article evidence keys must identify candidates");
  }
});
export type ParsedFeedBatch = z.infer<typeof ParsedFeedBatchSchema>;

export const SelectedFeedBatchSchema = z.strictObject({
  version: z.literal(PLANNER_STAGE_VERSION).default(PLANNER_STAGE_VERSION),
  batch_id: z.uuid({ version: "v4" }),
  config_sha256: Sha256Schema,
  parsed_batch_id: z.uuid({ version: "v4" }),
  context: PlannerStageContextSchema,
  selections: z.array(EditorialSelectionRowSchema),
  rejections: z.array(CandidateRejectionRecordSchema),
}).superRefine((value, ctx) => {
  const ids = value.selections.map(row => row.candidate_id);
  const ranks = value.selections.map(row => row.editorial_rank);
  if (new Set(ids).size !== ids.length || new Set(ranks).size !== ranks.length) {
    reject(ctx, "selected identities and ranks must be distinct");
  }
  for (const row of value.selections) {
    if (
      row.date !== value.context.date
      || row.correlation_id !== value.context.correlation_id
    ) {
      reject(ctx, "selection identity must match the batch context");
    }
  }
  for (const rejection of value.rejections) {
    if (
      rejection.date !== value.context.date
      || rejection.correlation_id !== value.context.correlation_id
    ) reject(ctx, "rejection identity must match the batch context");
  }
  const rejectedIds = new Set(value.rejections.flatMap(row =>
    row.candidate_id === null ? [] : [row.candidate_id]));
  if (ids.some(id => rejectedIds.has(id))) {
    reject(ctx, "a candidate cannot be both selected and rejected");
  }
});
export type SelectedFeedBatch = z.infer<typeof SelectedFeedBatchSchema>;

export const PartitionedFeedBatchSchema = z.strictObject({
  version: z.literal(PLANNER_STAGE_VERSION).default(PLANNER_STAGE_VERSION),
  batch_id: z.uuid({ version: "v4" }),
  config_sha256: Sha256Schema,
  selection_batch_id: z.uuid({ version: "v4" }),
  context: PlannerStageContextSchema,
  strategy: z.enum(["bin-pack", "round-robin", "none"]),
  dispatch_count: PositiveCountSchema,
  work: z.array(NonNegativeSchema),
  dispatches: z.array(FeedIngestDispatchSchema),
}).superRefine((value, ctx) => {
  if (value.work.length !== value.dispatch_count) {
    reject(ctx, "work must contain one total per dispatch");
  }
  if (value.strategy === "none" && value.dispatch_count !== 1) {
    reject(ctx, "none requires one dispatch");
  }
  const ids = value.dispatches.map(dispatch => dispatch.selection.candidate_id);
  const ranks = value.dispatches.map(dispatch => dispatch.selection.editorial_rank);
  if (new Set(ids).size !== ids.length || new Set(ranks).size !== ranks.length) {
    reject(ctx, "dispatch identities and ranks must be distinct");
  }
  for (const dispatch of value.dispatches) {
    if (dispatch.partition.strategy !== value.strategy
      || dispatch.partition.dispatch_count !== value.dispatch_count
      || dispatch.selection.date !== value.context.date
      || dispatch.selection.correlation_id !== value.context.correlation_id) {
      reject(ctx, "dispatch assignment must match the batch context and strategy");
    }
  }
  if (value.strategy === "round-robin") {
    const ranked = [...value.dispatches].sort((left, right) =>
      left.selection.editorial_rank - right.selection.editorial_rank);
    if (ranked.some(
      (dispatch, index) => dispatch.partition.worker_assignment !== index % value.dispatch_count,
    )) {
      reject(ctx, "round-robin assignments must follow editorial rank");
    }
  }
});
export type PartitionedFeedBatch = z.infer<typeof PartitionedFeedBatchSchema>;

export const StageReferenceRequestSchema = z.strictObject({
  batch_id: z.uuid({ version: "v4" }),
});
export type StageReferenceRequest = z.infer<typeof StageReferenceRequestSchema>;

export const PartitionArticlesRequestSchema = z.strictObject({
  batch_id: z.uuid({ version: "v4" }),
  strategy: z.enum(["bin-pack", "round-robin", "none"]).optional(),
  shards: PositiveCountSchema.optional(),
});
export type PartitionArticlesRequest = z.infer<typeof PartitionArticlesRequestSchema>;

const PreviousPlannerStageVersion = z.literal("2026-10-24");
export const PreviousParsedFeedBatchSchema = z.strictObject({
  ...ParsedFeedBatchSchema.shape,
  version: PreviousPlannerStageVersion,
  candidates: z.array(PreviousFeedIngestCandidateSchema),
});
export const PreviousSelectedFeedBatchSchema = z.strictObject({
  ...SelectedFeedBatchSchema.shape,
  version: PreviousPlannerStageVersion,
  selections: z.array(PreviousReliableEditorialSelectionSchema),
});
export const PreviousPartitionedFeedBatchSchema = z.strictObject({
  ...PartitionedFeedBatchSchema.shape,
  version: PreviousPlannerStageVersion,
  dispatches: z.array(PreviousReliableFeedIngestDispatchSchema),
});

export function readParsedFeedBatch(raw: unknown): ParsedFeedBatch {
  if (typeof raw === "object" && raw !== null && "version" in raw && raw.version === "2026-10-24") {
    const previous = PreviousParsedFeedBatchSchema.parse(raw);
    return ParsedFeedBatchSchema.parse({
      ...previous, version: PLANNER_STAGE_VERSION,
      candidates: previous.candidates.map(readFeedIngestCandidate),
    });
  }
  return ParsedFeedBatchSchema.parse(raw);
}

export function readSelectedFeedBatch(raw: unknown): SelectedFeedBatch {
  if (typeof raw === "object" && raw !== null && "version" in raw && raw.version === "2026-10-24") {
    const previous = PreviousSelectedFeedBatchSchema.parse(raw);
    return SelectedFeedBatchSchema.parse({
      ...previous, version: PLANNER_STAGE_VERSION,
      selections: previous.selections.map(row =>
        EditorialSelectionContract.legacyVersions[SOURCE_RELIABILITY_VERSION].migrate(row)),
    });
  }
  return SelectedFeedBatchSchema.parse(raw);
}

export function readPartitionedFeedBatch(raw: unknown): PartitionedFeedBatch {
  if (typeof raw === "object" && raw !== null && "version" in raw && raw.version === "2026-10-24") {
    const previous = PreviousPartitionedFeedBatchSchema.parse(raw);
    return PartitionedFeedBatchSchema.parse({
      ...previous, version: PLANNER_STAGE_VERSION,
      dispatches: previous.dispatches.map(readFeedIngestDispatch),
    });
  }
  return PartitionedFeedBatchSchema.parse(raw);
}
