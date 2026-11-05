/** Which current, server-owned payload crosses each planner stage in memory? */
import { z } from "zod";
import { FeedIngestCandidateSchema } from "./candidate.schema";
import { WriterIdentitySchema } from "./envelope.schema";
import { FetchFailureSchema, HarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";
import { ArticleContentEvidenceSchema } from "./content-filter-evidence.schema";
import { DiscoveredArticleRowSchema } from "./discovered-article.schema";
import { SelectedArticleRowSchema } from "./selected-article.schema";
import { RejectedArticleRowSchema } from "./rejected-article.schema";
import { FeedHealthStateRowSchema } from "./feed-health-state.schema";
import {
  CandidateIdSchema, CountSchema, DateStampSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema,
  RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, reject,
} from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { SourceSnapshotSchema } from "./source.schema";
import { UrlSchema } from "./primitives";
import {
  PARSED_FEED_BATCH_VERSION, SELECTED_FEED_BATCH_VERSION,
} from "../version";
import { PlannerRequestReportSchema } from "./planner-request-report.schema";
import { OperationLinkSchema, OperationMetadataSchema } from "./operation-metadata.schema";
export { PlannerRequestReportSchema } from "./planner-request-report.schema";
export type { PlannerRequestReport } from "./planner-request-report.schema";

export const PlannerStageContextSchema = z.strictObject({
  now: TimestampSchema, captured_at: RecordedInstantSchema, date: DateStampSchema,
  run_id: RunIdSchema, writer: WriterIdentitySchema,
}).superRefine((value, ctx) => {
  if (value.now.slice(0, 19) !== value.captured_at.slice(0, 19) || value.date !== value.now.slice(0, 10)
    || value.writer.run_id !== value.run_id || !value.run_id.startsWith(`${value.date}-`)) {
    reject(ctx, "stage context must retain its original UTC clock and run");
  }
});
export type PlannerStageContext = z.infer<typeof PlannerStageContextSchema>;
export const PlannerStageRequestSchema = z.strictObject({
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
  candidate_id: CandidateIdSchema, http_status: z.int().min(100).max(599).nullable(),
  fetch_failure: FetchFailureSchema.nullable(),
  paywall: z.boolean().nullable(),
  paywall_evidence: z.enum(["json-ld", "configured-marker", "none", "not-observed"]),
  extraction: z.enum(["success", "empty", "failed", "not-attempted"]),
  observed_at: TimestampSchema, diagnostics: HarvestDiagnosticsSchema.nullable().default(null),
  preflight_freshness: PreflightFreshnessSchema.optional(),
  content_evidence: ArticleContentEvidenceSchema.optional(),
});
export type PlannerHarvestObservation = z.infer<typeof PlannerHarvestObservationSchema>;
export const PlannerDiscoveredRowSchema = DiscoveredArticleRowSchema;
export const PlannerDiscoveredAvailableSchema = z.strictObject({
  availability: z.literal("available"), rows: z.array(PlannerDiscoveredRowSchema),
});
export const PlannerDiscoveredUnavailableSchema = z.strictObject({ availability: z.literal("unavailable") });
export const PlannerDiscoveredEvidenceSchema = z.discriminatedUnion("availability", [
  PlannerDiscoveredAvailableSchema, PlannerDiscoveredUnavailableSchema,
]);
export type PlannerDiscoveredEvidence = z.infer<typeof PlannerDiscoveredEvidenceSchema>;
export const RecordedIdentitySchema = z.strictObject({ value: NonEmptySchema, origin: NonEmptySchema });
export const PlannerArticleEvidenceSchema = z.strictObject({
  website_group: RecordedIdentitySchema.nullable(), estimated_work: NonNegativeSchema,
});
export type PlannerArticleEvidence = z.infer<typeof PlannerArticleEvidenceSchema>;
export const PlannerFeedEntrySchema = z.strictObject({
  entry_ordinal: CountSchema, title: z.string().nullable(), link: UrlSchema.nullable(),
  categories: z.array(z.string()), author: z.string().nullable(), published_at: TimestampSchema.nullable(),
  media_types: z.array(NonEmptySchema).default([]),
});
export const PlannerFeedOfferSchema = z.strictObject({
  candidate_id: CandidateIdSchema, source: SourceSnapshotSchema, entry: PlannerFeedEntrySchema,
  state: z.enum(["pending", "fetched", "parsed", "rejected"]),
  links: z.array(OperationLinkSchema).max(1),
}).meta({
  version: PARSED_FEED_BATCH_VERSION,
  changelog: [
    { version: PARSED_FEED_BATCH_VERSION, change: "Retain captured candidate UUIDv4 values under their native name." },
    { version: "2026-11-03", change: "Link an offered article to its claimed fetch operation." },
    { version: "2026-11-02", change: "Retain configured feed weights without planner tier fields." },
  ],
});
export type PlannerFeedOffer = z.infer<typeof PlannerFeedOfferSchema>;
export const PlannerRejectionCountSchema = z.strictObject({
  feed_id: SlugSchema, subject: z.enum(["feed", "article"]), stage: NonEmptySchema,
  reason_code: NonEmptySchema, attribution: z.enum(["feed", "pipeline", "unknown"]).nullable(), count: CountSchema,
});
export type PlannerRejectionCount = z.infer<typeof PlannerRejectionCountSchema>;
export const PlannerHealthDaySchema = z.strictObject({ day: DateStampSchema, complete: z.boolean() });
export const SelectedArticleContentSchema = SelectedArticleRowSchema.safeExtend({ article_text: z.string() });
const batchIdentity = {
  config_sha256: Sha256Schema, context: PlannerStageContextSchema,
};
export const ParsedFeedBatchSchema = OperationMetadataSchema.safeExtend({
  ...batchIdentity, version: z.literal(PARSED_FEED_BATCH_VERSION).default(PARSED_FEED_BATCH_VERSION), request: PlannerStageRequestSchema,
  candidates: z.array(FeedIngestCandidateSchema),
  observations: z.record(CandidateIdSchema, PlannerHarvestObservationSchema),
  discovered: PlannerDiscoveredEvidenceSchema,
  evidence: z.record(CandidateIdSchema, PlannerArticleEvidenceSchema),
  history_rows: z.array(FeedHealthStateRowSchema), history_days: z.array(PlannerHealthDaySchema),
  work_rows: z.array(FeedHealthStateRowSchema), exclusions: z.array(PlannerRejectionCountSchema),
  offers: z.array(PlannerFeedOfferSchema).default([]),
  input_complete: z.boolean().default(true),
}).superRefine((value, ctx) => {
  const ids = new Set(value.candidates.map(candidate => candidate.candidate_id));
  if (ids.size !== value.candidates.length) reject(ctx, "parsed candidate identities must be distinct");
  for (const candidate of value.candidates) {
    if (candidate.run_id !== value.context.run_id) {
      reject(ctx, "parsed candidates must belong to their batch run");
    }
  }
  if (Object.keys(value.observations).length !== ids.size
    || Object.entries(value.observations).some(([id, observation]) => !ids.has(id) || id !== observation.candidate_id)) {
    reject(ctx, "parsed observations must match the complete candidate batch");
  }
}).meta({
  version: PARSED_FEED_BATCH_VERSION,
  changelog: [
    { version: PARSED_FEED_BATCH_VERSION, change: "Carry captured UUIDv4 candidates through offers and keyed article evidence." },
    { version: "2026-11-03", change: "Address parsed output by its producing operation and input links." },
    { version: "2026-11-02", change: "Remove robots evidence and health counters from parsed work." },
    { version: "2026-11-02", change: "Retain candidates and offers without planner tier fields." },
    { version: "2026-10-25", change: "Earlier changes are in git." },
  ],
});
export type ParsedFeedBatch = z.infer<typeof ParsedFeedBatchSchema>;
export const SelectedFeedBatchSchema = OperationMetadataSchema.safeExtend({
  ...batchIdentity, version: z.literal(SELECTED_FEED_BATCH_VERSION).default(SELECTED_FEED_BATCH_VERSION),
  selection_started_at_utc: TimestampSchema, evaluated_at: TimestampSchema,
  articles: z.array(SelectedArticleContentSchema), health_rows: z.array(FeedHealthStateRowSchema),
  rejected_articles: z.array(RejectedArticleRowSchema),
  exclusions: z.array(PlannerRejectionCountSchema), request_report: PlannerRequestReportSchema,
}).meta({
  version: SELECTED_FEED_BATCH_VERSION,
  changelog: [
    { version: SELECTED_FEED_BATCH_VERSION, change: "Require captured UUIDv4 identities in terminal article rows." },
    { version: "2026-11-03", change: "Address selected output by its producing operation and input links." },
    { version: "2026-11-02", change: "Give private selections their own stamp and target-only health and reports." },
    { version: "2026-11-02", change: "Carry both word counts, complete diversity scores and global timing." },
    { version: "2026-10-27", change: "Earlier changes are in git." },
  ],
});
export type SelectedFeedBatch = z.infer<typeof SelectedFeedBatchSchema>;
export const PartitionedFeedBatchSchema = SelectedFeedBatchSchema.safeExtend({
  strategy: z.enum(["bin-pack", "round-robin", "none"]), dispatch_count: PositiveCountSchema,
  work: z.array(NonNegativeSchema),
});
export type PartitionedFeedBatch = z.infer<typeof PartitionedFeedBatchSchema>;
export const StageReferenceRequestSchema = z.strictObject({ links: z.tuple([OperationLinkSchema]) });
export const PartitionArticlesRequestSchema = StageReferenceRequestSchema.extend({
  strategy: z.enum(["bin-pack", "round-robin", "none"]).optional(), shards: PositiveCountSchema.optional(),
});
export const readParsedFeedBatch = (value: unknown) => ParsedFeedBatchSchema.parse(value);
export const readSelectedFeedBatch = (value: unknown) => SelectedFeedBatchSchema.parse(value);
export const readPartitionedFeedBatch = (value: unknown) => PartitionedFeedBatchSchema.parse(value);
