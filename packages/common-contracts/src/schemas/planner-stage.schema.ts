/** Which current, server-owned payload crosses each planner stage in memory? */
import { z } from "zod";
import { FeedIngestCandidateSchema } from "./candidate.schema";
import { WriterIdentitySchema } from "./envelope.schema";
import { HarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";
import { ArticleContentEvidenceSchema } from "./content-filter-evidence.schema";
import { DiscoveredArticleRowSchema } from "./discovered-article.schema";
import { SelectedArticleRowSchema } from "./selected-article.schema";
import { RejectedArticleRowSchema } from "./rejected-article.schema";
import { FeedHealthStateRowSchema } from "./feed-health-state.schema";
import {
  CountSchema, DateStampSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema,
  RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, reject,
} from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { SourceSnapshotSchema } from "./source.schema";
import { UrlSchema } from "./primitives";
import { PARSED_FEED_BATCH_VERSION } from "../version";

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
  offer_id: Sha256Schema, source: SourceSnapshotSchema, entry: PlannerFeedEntrySchema,
  state: z.enum(["pending", "fetched", "parsed", "rejected"]),
  fetch_request_id: z.uuid({ version: "v4" }).nullable(),
});
export type PlannerFeedOffer = z.infer<typeof PlannerFeedOfferSchema>;
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
  ...batchIdentity, version: z.literal(PARSED_FEED_BATCH_VERSION).default(PARSED_FEED_BATCH_VERSION), request: PlannerStageRequestSchema,
  candidates: z.array(FeedIngestCandidateSchema),
  observations: z.record(Sha256Schema, PlannerHarvestObservationSchema),
  discovered: PlannerDiscoveredEvidenceSchema,
  evidence: z.record(Sha256Schema, PlannerArticleEvidenceSchema),
  history_rows: z.array(FeedHealthStateRowSchema), history_days: z.array(PlannerHealthDaySchema),
  work_rows: z.array(FeedHealthStateRowSchema), exclusions: z.array(PlannerRejectionCountSchema),
  offers: z.array(PlannerFeedOfferSchema).default([]),
  feed_fetch_request_id: z.uuid({ version: "v4" }).nullable().default(null),
  article_fetch_request_id: z.uuid({ version: "v4" }).nullable().default(null),
  input_complete: z.boolean().default(true),
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
}).meta({
  version: PARSED_FEED_BATCH_VERSION,
  changelog: [
    { version: PARSED_FEED_BATCH_VERSION, change: "Link standalone article batches to their original source-outcome receipt." },
    { version: "2026-10-27", change: "Name planner discovery evidence and derive website groups from canonical URLs." },
    { version: "2026-10-25", change: "Declare complete parsed feed batches and their source evidence." },
  ],
});
export type ParsedFeedBatch = z.infer<typeof ParsedFeedBatchSchema>;
export const SelectedFeedBatchSchema = z.strictObject({
  ...batchIdentity, version: z.literal("2026-10-27").default("2026-10-27"), parsed_batch_id: z.uuid({ version: "v4" }),
  selection_started_at_utc: TimestampSchema, evaluated_at: TimestampSchema,
  articles: z.array(SelectedArticleContentSchema), health_rows: z.array(FeedHealthStateRowSchema),
  rejected_articles: z.array(RejectedArticleRowSchema),
  exclusions: z.array(PlannerRejectionCountSchema), request_report: PlannerRequestReportSchema,
}).meta({
  version: "2026-10-27",
  changelog: [{ version: "2026-10-27", change: "Carry terminal rejected article metadata with the complete selection." }],
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
