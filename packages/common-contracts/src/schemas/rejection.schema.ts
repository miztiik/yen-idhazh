/** Validate one transient terminal exclusion before reducing it to body-free grouped counts. */
import { z } from "zod";
import {
  CountSchema, DateStampSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema, PositiveSchema,
  RejectionStageSchema, Sha256Schema, SlugSchema, TimestampSchema, UrlSchema, checkUrlIdentity, reject,
} from "./primitives";
import { HarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";
import { ItemHealthFailureCodeSchema } from "./item-health-failure.schema";

export const DropReasonSchema = z.enum([
  "SOURCE_INACTIVE", "FETCH_FAILED", "FETCH_FAILED_HTTP", "FETCH_TIMEOUT", "EXTRACT_FAILED", "EXTRACT_EMPTY",
  "ALREADY_PUBLISHED", "SETTLED_FAILURE", "BLOCKED_URL_MARKER", "PAYWALL_OR_BLOCKED", "FEED_PARSE_FAILED",
  "FEED_EMPTY", "MISSING_REQUIRED_FIELDS", "CATEGORY_EXCLUDED", "STUB_CONTENT", "STALE_MAX_AGE_EXCEEDED",
  "MEDIA_CONTENT",
]);
export type DropReason = z.infer<typeof DropReasonSchema>;
export type RejectionStage = z.infer<typeof RejectionStageSchema>;
export const RejectionDetailsSchema = z.strictObject({
  http_status: z.int().min(100).max(599).nullable().default(null), timeout_ms: PositiveSchema.nullable().default(null),
  words_found: CountSchema.nullable().default(null), words_required: PositiveCountSchema.nullable().default(null),
  age_hours: NonNegativeSchema.nullable().default(null), max_age_hours: PositiveSchema.nullable().default(null),
  matched_url_key: Sha256Schema.nullable().default(null), published_on: DateStampSchema.nullable().default(null),
  failure_code: ItemHealthFailureCodeSchema.nullable().default(null), matched_url_marker: NonEmptySchema.nullable().default(null),
  history_window_days: PositiveCountSchema.nullable().default(null), diagnostics: HarvestDiagnosticsSchema.nullable().default(null),
  media_match: z.enum(["enclosure", "url"]).nullable().default(null),
  matched_media_type_prefix: NonEmptySchema.nullable().default(null),
});
export const REASON_STAGES: Readonly<Record<DropReason, readonly RejectionStage[]>> = {
  SOURCE_INACTIVE: ["harvest-feeds"], FETCH_FAILED: ["harvest-feeds"], FETCH_FAILED_HTTP: ["harvest-feeds"],
  FETCH_TIMEOUT: ["harvest-feeds"], EXTRACT_FAILED: ["harvest-feeds"], EXTRACT_EMPTY: ["harvest-feeds"],
  FEED_PARSE_FAILED: ["harvest-feeds"], FEED_EMPTY: ["harvest-feeds"], MISSING_REQUIRED_FIELDS: ["harvest-feeds"],
  ALREADY_PUBLISHED: ["harvest-feeds", "screen-article-candidates"],
  SETTLED_FAILURE: ["harvest-feeds", "screen-article-candidates"], BLOCKED_URL_MARKER: ["harvest-feeds", "screen-article-candidates"],
  PAYWALL_OR_BLOCKED: ["screen-article-candidates"], CATEGORY_EXCLUDED: ["screen-article-candidates"],
  STUB_CONTENT: ["screen-article-candidates"], STALE_MAX_AGE_EXCEEDED: ["harvest-feeds", "screen-article-candidates"],
  MEDIA_CONTENT: ["harvest-feeds", "screen-article-candidates"],
};
export const REQUIRED_DETAILS: Readonly<Partial<Record<DropReason, readonly (keyof z.infer<typeof RejectionDetailsSchema>)[]>>> = {
  FETCH_FAILED_HTTP: ["http_status"], FETCH_TIMEOUT: ["timeout_ms"], STUB_CONTENT: ["words_found", "words_required"],
  STALE_MAX_AGE_EXCEEDED: ["age_hours", "max_age_hours"], ALREADY_PUBLISHED: ["matched_url_key", "published_on", "history_window_days"],
  SETTLED_FAILURE: ["matched_url_key", "failure_code"], BLOCKED_URL_MARKER: ["matched_url_key", "matched_url_marker"],
  MEDIA_CONTENT: ["media_match"],
};
export const CandidateRejectionRecordSchema = z.strictObject({
  version: z.literal("2026-10-25").default("2026-10-25"), date: DateStampSchema, correlation_id: NonEmptySchema,
  source_id: SlugSchema, feed_url: UrlSchema, subject: z.enum(["feed", "article"]),
  candidate_id: Sha256Schema.nullable(), url_key: Sha256Schema.nullable(), canonical_url: UrlSchema.nullable(),
  title: z.string().nullable(), categories: z.array(z.string()), stage: RejectionStageSchema,
  drop_reason: DropReasonSchema, details: RejectionDetailsSchema, rejected_at: TimestampSchema,
}).superRefine((value, ctx) => {
  const article = value.subject === "article";
  if (article !== (value.candidate_id !== null)) reject(ctx, "Only an article exclusion has a candidate identity");
  for (const field of ["url_key", "canonical_url", "title"] as const) {
    if (!article && value[field] !== null) reject(ctx, `Feed exclusions have no ${field}`, [field]);
    const missingTitle = field === "title" && [
      "FETCH_FAILED", "FETCH_FAILED_HTTP", "FETCH_TIMEOUT", "EXTRACT_FAILED", "EXTRACT_EMPTY",
      "ALREADY_PUBLISHED", "SETTLED_FAILURE", "BLOCKED_URL_MARKER", "MEDIA_CONTENT",
    ].includes(value.drop_reason);
    if (article && value[field] === null && value.drop_reason !== "MISSING_REQUIRED_FIELDS" && !missingTitle) {
      reject(ctx, `Article exclusion requires ${field}`, [field]);
    }
  }
  if (value.canonical_url !== null && value.url_key !== null) checkUrlIdentity({ canonical_url: value.canonical_url, url_key: value.url_key }, ctx);
  if (value.date !== value.rejected_at.slice(0, 10)) reject(ctx, "Exclusion date must match its actual UTC decision day");
  if (!REASON_STAGES[value.drop_reason].includes(value.stage)) reject(ctx, "Reason does not belong to this stage");
  if (article && ["SOURCE_INACTIVE", "FEED_PARSE_FAILED", "FEED_EMPTY"].includes(value.drop_reason)) reject(ctx, "Reason requires a feed");
  if (!article && (value.stage !== "harvest-feeds" || ["MISSING_REQUIRED_FIELDS", "EXTRACT_FAILED", "EXTRACT_EMPTY"].includes(value.drop_reason))) {
    reject(ctx, "Feed outcome does not describe an article exclusion");
  }
  for (const field of REQUIRED_DETAILS[value.drop_reason] ?? []) {
    if (value.details[field] === null) reject(ctx, `${value.drop_reason} requires details.${field}`, ["details", field]);
  }
  if (value.drop_reason === "MEDIA_CONTENT") {
    const field = value.details.media_match === "enclosure" ? "matched_media_type_prefix" : "matched_url_marker";
    if (value.details[field] === null) reject(ctx, `MEDIA_CONTENT requires details.${field}`, ["details", field]);
  }
});
export type CandidateRejectionRecord = z.infer<typeof CandidateRejectionRecordSchema>;
export type RejectionDetails = z.infer<typeof RejectionDetailsSchema>;
