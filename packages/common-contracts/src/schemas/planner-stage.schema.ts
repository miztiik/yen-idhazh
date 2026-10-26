/** Which current, server-owned payload crosses each planner stage in memory? */
import { z } from "zod";
import { FeedIngestCandidateSchema } from "./candidate.schema";
import { WriterIdentitySchema } from "./envelope.schema";
import { HarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";
import { DiscoveredArticleRowSchema } from "./discovered-article.schema";
import { SelectedArticleRowSchema } from "./selected-article.schema";
import { FeedHealthStateRowSchema } from "./feed-health-state.schema";
import {
  CountSchema, DateStampSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema,
  RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, reject,
} from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";

export const PlannerStageContextSchema = z.strictObject({
  now: TimestampSchema, captured_at: RecordedInstantSchema, date: DateStampSchema,
  run_id: RunIdSchema, correlation_id: z.uuid({ version: "v4" }), writer: WriterIdentitySchema,
}).superRefine((value, ctx) => {
  if (value.now.slice(0, 19) !== value.captured_at.slice(0, 19) || value.date !== value.now.slice(0, 10)
    || value.writer.run_id !== value.run_id || !value.run_id.startsWith(`${value.date}-`)) {
    reject(ctx, "stage context must retain its original UTC clock and run");
  }
});
export type PlannerStageContext = z.infer<typeof PlannerStageContextSchema>;
export const PlannerStageRequestSchema = z.strictObject({
  freshness_hours: z.number().finite().positive().optional(),
  article_limit: PositiveCountSchema.optional(), shards: PositiveCountSchema.optional(),
  partition_strategy: z.enum(["bin-pack", "round-robin", "none"]).optional(),
});
export type PlannerStageRequest = z.infer<typeof PlannerStageRequestSchema>;
export const PreflightFreshnessSchema = z.strictObject({
  timing_at: TimestampSchema, timing_source: z.literal("published_at"),
  age_hours: z.number().finite().positive(), recency_bonus: NonNegativeSchema,
});
export type PreflightFreshness = z.infer<typeof PreflightFreshnessSchema>;
export const PlannerHarvestObservationSchema = z.strictObject({
  candidate_id: Sha256Schema, http_status: z.int().min(100).max(599).nullable(),
  robots: z.enum(["allowed", "denied", "unknown"]).nullable(),
  fetch_failure: z.enum([
    "http", "timeout", "unsafe-target", "dns", "network", "robots-denied",
    "robots-unknown", "body-too-large", "redirect-loop",
  ]).nullable(),
  paywall: z.boolean().nullable(),
  paywall_evidence: z.enum(["json-ld", "configured-marker", "none", "not-observed"]),
  extraction: z.enum(["success", "empty", "failed", "not-attempted"]),
  observed_at: TimestampSchema, diagnostics: HarvestDiagnosticsSchema.nullable().default(null),
  preflight_freshness: PreflightFreshnessSchema.optional(),
});
export type PlannerHarvestObservation = z.infer<typeof PlannerHarvestObservationSchema>;
export const PlannerSeenRowSchema = DiscoveredArticleRowSchema;
export const PlannerSeenAvailableSchema = z.strictObject({
  availability: z.literal("available"), rows: z.array(PlannerSeenRowSchema),
});
export const PlannerSeenUnavailableSchema = z.strictObject({ availability: z.literal("unavailable") });
export const PlannerSeenEvidenceSchema = z.discriminatedUnion("availability", [
  PlannerSeenAvailableSchema, PlannerSeenUnavailableSchema,
]);
export type PlannerSeenEvidence = z.infer<typeof PlannerSeenEvidenceSchema>;
export const RecordedIdentitySchema = z.strictObject({ value: NonEmptySchema, origin: NonEmptySchema });
export const PrimaryEvidenceSchema = z.strictObject({ ids: z.array(NonEmptySchema).min(1), origin: NonEmptySchema });
export const PlannerArticleEvidenceSchema = z.strictObject({
  parent_domain: RecordedIdentitySchema.nullable(), primary_evidence: PrimaryEvidenceSchema.nullable(),
  estimated_work: NonNegativeSchema,
});
export type PlannerArticleEvidence = z.infer<typeof PlannerArticleEvidenceSchema>;
export const PlannerRejectionCountSchema = z.strictObject({
  feed_id: SlugSchema, subject: z.enum(["feed", "article"]), stage: NonEmptySchema,
  reason_code: NonEmptySchema, attribution: z.enum(["feed", "pipeline", "unknown"]).nullable(), count: CountSchema,
});
export type PlannerRejectionCount = z.infer<typeof PlannerRejectionCountSchema>;
export const PlannerHealthDaySchema = z.strictObject({ day: DateStampSchema, complete: z.boolean() });
export const PlannerRequestReportSchema = z.strictObject({
  from_day: DateStampSchema, through_day: DateStampSchema, complete: z.boolean(),
  feeds: z.array(z.strictObject({
    feed_id: SlugSchema, feed_requests: CountSchema.nullable(),
    article_requests: CountSchema.nullable(), robots_requests: CountSchema.nullable(),
    counts_complete: z.boolean(),
  })),
});
export const SelectedArticleContentSchema = SelectedArticleRowSchema.safeExtend({ article_text: z.string() });
const batchIdentity = {
  version: z.literal("2026-10-25").default("2026-10-25"),
  batch_id: z.uuid({ version: "v4" }), config_sha256: Sha256Schema, context: PlannerStageContextSchema,
};
export const ParsedFeedBatchSchema = z.strictObject({
  ...batchIdentity, request: PlannerStageRequestSchema,
  candidates: z.array(FeedIngestCandidateSchema),
  observations: z.record(Sha256Schema, PlannerHarvestObservationSchema),
  seen: PlannerSeenEvidenceSchema,
  evidence: z.record(Sha256Schema, PlannerArticleEvidenceSchema),
  history_rows: z.array(FeedHealthStateRowSchema), history_days: z.array(PlannerHealthDaySchema),
  work_rows: z.array(FeedHealthStateRowSchema), exclusions: z.array(PlannerRejectionCountSchema),
}).superRefine((value, ctx) => {
  const ids = new Set(value.candidates.map(candidate => candidate.candidate_id));
  if (ids.size !== value.candidates.length) reject(ctx, "parsed candidate identities must be distinct");
  for (const candidate of value.candidates) {
    if (candidate.run_id !== value.context.run_id || candidate.correlation_id !== value.context.correlation_id) {
      reject(ctx, "parsed candidates must belong to their batch run");
    }
  }
  if (Object.keys(value.observations).length !== ids.size
    || Object.entries(value.observations).some(([id, observation]) => !ids.has(id) || id !== observation.candidate_id)) {
    reject(ctx, "parsed observations must match the complete candidate batch");
  }
});
export type ParsedFeedBatch = z.infer<typeof ParsedFeedBatchSchema>;
export const SelectedFeedBatchSchema = z.strictObject({
  ...batchIdentity, parsed_batch_id: z.uuid({ version: "v4" }),
  selection_started_at_utc: TimestampSchema, evaluated_at: TimestampSchema,
  articles: z.array(SelectedArticleContentSchema), health_rows: z.array(FeedHealthStateRowSchema),
  exclusions: z.array(PlannerRejectionCountSchema), request_report: PlannerRequestReportSchema,
});
export type SelectedFeedBatch = z.infer<typeof SelectedFeedBatchSchema>;
export const PartitionedFeedBatchSchema = SelectedFeedBatchSchema.safeExtend({
  selection_batch_id: z.uuid({ version: "v4" }),
  strategy: z.enum(["bin-pack", "round-robin", "none"]), dispatch_count: PositiveCountSchema,
  work: z.array(NonNegativeSchema),
});
export type PartitionedFeedBatch = z.infer<typeof PartitionedFeedBatchSchema>;
export const StageReferenceRequestSchema = z.strictObject({ batch_id: z.uuid({ version: "v4" }) });
export const PartitionArticlesRequestSchema = StageReferenceRequestSchema.extend({
  strategy: z.enum(["bin-pack", "round-robin", "none"]).optional(), shards: PositiveCountSchema.optional(),
});
export const readParsedFeedBatch = (value: unknown) => ParsedFeedBatchSchema.parse(value);
export const readSelectedFeedBatch = (value: unknown) => SelectedFeedBatchSchema.parse(value);
export const readPartitionedFeedBatch = (value: unknown) => PartitionedFeedBatchSchema.parse(value);
