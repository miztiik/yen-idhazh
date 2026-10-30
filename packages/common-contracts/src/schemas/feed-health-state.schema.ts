/** What feed work did one run attempt perform on one actual UTC day? */
import { z } from "zod";
import { FEED_HEALTH_STATE_ACCEPTED_SCHEMA_VERSIONS, FEED_HEALTH_STATE_VERSION, LEGACY_FEED_HEALTH_STATE_VERSION } from "../version";
import { CountSchema, DateStampSchema, FiniteSchema, NonEmptySchema, PositiveCountSchema, RunIdSchema, Sha256Schema, SlugSchema, reject } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";

const Ratio = FiniteSchema.min(0).max(1);
export const FeedHealthReliabilitySchema = z.strictObject({
  productive: CountSchema.nullable(), attempted: CountSchema.nullable(),
  success_fraction: Ratio.nullable().describe("Productive reads divided by attempted reads, saved downward to three decimal places by current producers."),
  from_day: DateStampSchema.nullable(),
  through_day: DateStampSchema.nullable(),
  production_factor: Ratio.nullable().describe("The original read fraction with its configured floor applied, then saved downward to three decimal places by current producers."),
  complete: z.boolean(),
}).superRefine((value, ctx) => {
  if (value.productive !== null && value.attempted !== null && value.productive > value.attempted) reject(ctx, "productive reads cannot exceed attempted reads");
  if ((value.from_day === null) !== (value.through_day === null)) reject(ctx, "reliability bounds must both be known or unavailable");
  if (value.from_day !== null && value.through_day !== null && value.from_day > value.through_day) reject(ctx, "reliability bounds must be ordered");
});
export const FeedHealthRejectionCountSchema = z.strictObject({
  reason_code: NonEmptySchema, count: CountSchema, subject: z.enum(["feed", "article"]),
  stage: NonEmptySchema, attribution: z.enum(["feed", "pipeline", "unknown"]).nullable(),
});
export const FeedHealthStateRowSchema = z.strictObject({
  feed_id: SlugSchema, endpoint_key: Sha256Schema, checked_at: RecordedInstantSchema.nullable(),
  permission: z.enum(["allowed", "denied", "unknown"]),
  availability: z.enum(["eligible", "resting", "retired", "unknown"]),
  strikes: CountSchema.nullable(), rested_runs: CountSchema.nullable(),
  last_failure_code: NonEmptySchema.nullable(), status: z.int().min(100).max(599).nullable(),
  reliability: FeedHealthReliabilitySchema.nullable(), date: DateStampSchema,
  feed_reads: CountSchema.nullable(), productive_reads: CountSchema.nullable(),
  failed_reads: CountSchema.nullable(), article_candidates: CountSchema.nullable(),
  articles_selected: CountSchema.nullable(), feed_requests: CountSchema.nullable(),
  article_requests: CountSchema.nullable(), robots_requests: CountSchema.nullable(),
  counts_complete: z.boolean(), rejection_counts: z.array(FeedHealthRejectionCountSchema),
  run_id: RunIdSchema, attempt: PositiveCountSchema, items: CountSchema.nullable(),
  outcome: z.enum(["ok", "robots_denied", "blocked", "permanent", "transient", "skipped"]).nullable(),
}).superRefine((value, ctx) => {
  if (value.checked_at !== null && value.date !== value.checked_at.slice(0, 10)) reject(ctx, "health date must name the actual UTC work day");
  if (value.counts_complete && [
    value.feed_reads, value.productive_reads, value.failed_reads, value.article_candidates,
    value.articles_selected, value.feed_requests, value.article_requests, value.robots_requests,
  ].some((count) => count === null)) reject(ctx, "complete accounting requires every run counter");
}).meta({
  version: FEED_HEALTH_STATE_VERSION,
  changelog: [
    { version: FEED_HEALTH_STATE_VERSION, change: "Save feed-read fractions and floor-applied factors downward to three decimal places." },
    { version: LEGACY_FEED_HEALTH_STATE_VERSION, change: "Count admitted original article captures before selection instead of screening admissions." },
  ],
});
export type FeedHealthStateRow = z.infer<typeof FeedHealthStateRowSchema>;
export type FeedHealthReliability = z.infer<typeof FeedHealthReliabilitySchema>;
export type FeedHealthRejectionCount = z.infer<typeof FeedHealthRejectionCountSchema>;
export const FeedHealthStateRowContract = {
  schema: FeedHealthStateRowSchema, schemaVersion: FEED_HEALTH_STATE_VERSION,
  acceptedSchemaVersions: FEED_HEALTH_STATE_ACCEPTED_SCHEMA_VERSIONS,
} as const;
