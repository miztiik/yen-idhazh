/** What feed work did one run attempt perform on one actual UTC day? */
import { z } from "zod";
import { FEED_HEALTH_STATE_VERSION } from "../version";
import { CountSchema, DateStampSchema, FiniteSchema, NonEmptySchema, PositiveCountSchema, RunIdSchema, Sha256Schema, SlugSchema, reject } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";

const Ratio = FiniteSchema.min(0).max(1);
export const FeedCheckResultSchema = z.enum([
  "valid-feed", "confirmed-http-failure", "other-http-failure", "timeout",
  "robots", "transport-unknown", "local-failure", "interrupted",
]);
export type FeedCheckResult = z.infer<typeof FeedCheckResultSchema>;
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
  strikes: CountSchema.nullable().describe("Observed consecutive logical failures; partial history keeps this a supported lower bound, not an exact historical total."),
  check_request_id: z.uuid({ version: "v4" }).nullable(),
  check_result: FeedCheckResultSchema.nullable(),
  rest_until: RecordedInstantSchema.nullable().describe("Supported UTC recovery deadline; a carried value is not a new check."),
  first_confirmed_failure_at: RecordedInstantSchema.nullable().describe("UTC first confirmed failure in the known episode; partial history does not claim an earlier unseen start."),
  failed_recovery_checks: CountSchema.nullable().describe("Observed qualifying confirmed recovery failures; missing earlier evidence stays partial."),
  retired_at: RecordedInstantSchema.nullable(),
  retirement_reason: z.literal("confirmed-recovery-failures").nullable(),
  availability_updated_at: RecordedInstantSchema.nullable(),
  availability_complete: z.boolean(),
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
  if (value.check_result !== null && (value.check_request_id === null || value.checked_at === null)) {
    reject(ctx, "a check result requires its actual request identity and UTC check instant");
  }
  if (value.check_result === "confirmed-http-failure"
    && !(value.status === 404 || value.status === 410 || (value.status !== null && value.status >= 500))) {
    reject(ctx, "only target HTTP 404, 410 or 5xx proves a confirmed source failure");
  }
  if ((value.retired_at === null) !== (value.retirement_reason === null)) reject(ctx, "retirement instant and reason must be recorded together");
  if (value.retired_at !== null && value.rest_until !== null) reject(ctx, "retired feeds cannot have a rest deadline");
  if (value.counts_complete && [
    value.feed_reads, value.productive_reads, value.failed_reads, value.article_candidates,
    value.articles_selected, value.feed_requests, value.article_requests, value.robots_requests,
  ].some((count) => count === null)) reject(ctx, "complete accounting requires every run counter");
}).meta({
  version: FEED_HEALTH_STATE_VERSION,
  changelog: [
    { version: FEED_HEALTH_STATE_VERSION, change: "Keep observed failure and recovery counts usable when earlier history is partial." },
    { version: FEED_HEALTH_STATE_VERSION, change: "Save logical checks and supported timed lifecycle calculations without availability sidecars." },
    { version: "2026-10-30", change: "Save feed-read fractions and floor-applied factors downward to three decimal places." },
    { version: "2026-10-27", change: "Count admitted original article captures before selection instead of screening admissions." },
  ],
});
export type FeedHealthStateRow = z.infer<typeof FeedHealthStateRowSchema>;
export type FeedHealthReliability = z.infer<typeof FeedHealthReliabilitySchema>;
export type FeedHealthRejectionCount = z.infer<typeof FeedHealthRejectionCountSchema>;
export const FeedLifecycleFieldsSchema = z.object(FeedHealthStateRowSchema.shape).pick({
  availability: true, strikes: true, rest_until: true, first_confirmed_failure_at: true,
  failed_recovery_checks: true, retired_at: true, retirement_reason: true,
  availability_updated_at: true, availability_complete: true,
});
export type FeedLifecycleFields = z.infer<typeof FeedLifecycleFieldsSchema>;
export const FeedHealthStateRowContract = {
  schema: FeedHealthStateRowSchema, schemaVersion: FEED_HEALTH_STATE_VERSION,
} as const;
