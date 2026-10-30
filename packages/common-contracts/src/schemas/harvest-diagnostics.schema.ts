/** Which bounded fetch and extraction evidence survives every planner boundary? */
import { z } from "zod";
import { CountSchema, NonEmptySchema, reject } from "./primitives";

export const ExtractionSignalSchema = z.enum(["contaminated", "boilerplate", "not_prose", "too_short"]);
export const ExtractionQualitySchema = z.strictObject({
  source_word_count: CountSchema, word_count: CountSchema,
  corroborated_word_count: CountSchema.nullable(),
  token_count: CountSchema.nullable(), truncated: z.boolean().nullable(),
  truncated_at_tokens: z.int().min(1).nullable(), truncation_cap_tokens: z.int().min(256),
  too_short: z.boolean(), not_prose: z.boolean(),
  boilerplate: z.boolean().nullable(), contaminated: z.boolean().nullable(),
  failure_code: ExtractionSignalSchema.nullable(), rejected: z.boolean(),
  extractor_version: NonEmptySchema, sanitizer_version: NonEmptySchema,
}).superRefine((value, ctx) => {
  if (value.source_word_count < value.word_count) reject(ctx, "source_word_count counts the body before a cap");
  if ((value.corroborated_word_count === null) !== (value.contaminated === null)) reject(ctx, "contamination requires an independent length reading");
  if (value.corroborated_word_count === 0) reject(ctx, "an independent length reading must contain words");
  if ((value.truncated === true) !== (value.truncated_at_tokens !== null)) reject(ctx, "a truncation point requires an applied cut");
  const expected = value.contaminated ? "contaminated" : value.boilerplate ? "boilerplate"
    : value.not_prose ? "not_prose" : value.too_short ? "too_short" : null;
  if (value.failure_code !== expected) reject(ctx, "failure_code must follow native signal precedence");
  if (value.rejected && value.failure_code === null) reject(ctx, "a quality rejection requires a measured signal");
});
export type ExtractionQuality = z.infer<typeof ExtractionQualitySchema>;

export const FetchFailureSchema = z.enum([
  "http", "timeout", "unsafe-target", "dns", "network", "robots-denied",
  "robots-unknown", "body-too-large", "redirect-loop",
]);
export const BodyLimitEvidenceSchema = z.strictObject({
  configured_limit_bytes: CountSchema, observed_at_least_bytes: CountSchema,
}).superRefine((value, ctx) => {
  if (value.observed_at_least_bytes <= value.configured_limit_bytes) {
    reject(ctx, "cutoff evidence must exceed the configured byte limit");
  }
});
export type BodyLimitEvidence = z.infer<typeof BodyLimitEvidenceSchema>;
export const ExtractionFailureSchema = z.enum([
  "missing-document-root", "dom-depth-exceeded", "empty-content", "missing-title",
  "parser-timeout", "parser-cancelled", "parser-failed",
]);
const HarvestDiagnosticsBaseSchema = z.strictObject({
  http_status: z.int().min(100).max(599).nullable().default(null),
  robots: z.enum(["allowed", "denied", "unknown"]).nullable().default(null),
  fetch_failure: FetchFailureSchema.nullable().default(null),
  robots_failure: FetchFailureSchema.nullable().default(null),
  robots_http_status: z.int().min(100).max(599).nullable().default(null),
  body_limit: BodyLimitEvidenceSchema.nullable().default(null),
  error_code: z.string().max(64).regex(/^[A-Z][A-Z0-9_]*$/).nullable().default(null),
  extraction_failure: ExtractionFailureSchema.nullable().default(null),
  failure_code: z.enum([
    "robots_denied", "robots_unreachable", "blocked_address", "http_client_error",
    "http_rate_limited", "http_server_error", "network_error", "no_text", "no_title", "unknown",
    ...ExtractionSignalSchema.options,
  ]).nullable().default(null),
  stopped_stage: z.enum(["fetch", "extract", "parse"]).nullable().default(null),
  detail: z.enum([
    ...FetchFailureSchema.options, ...ExtractionFailureSchema.options, "malformed-feed", "empty-feed",
    ...ExtractionSignalSchema.options,
  ]).nullable().default(null),
  fetch_ms: CountSchema.nullable().default(null),
  extract_ms: CountSchema.nullable().default(null),
  warnings: z.array(z.enum(["malformed-json-ld", "semantic-dom-fallback"])).max(2).default([]),
  quality: ExtractionQualitySchema.nullable().default(null),
}).meta({
  version: "2026-10-30",
  changelog: [
    { version: "2026-10-30", change: "Distinguish parser deadline, cancellation and worker failures from source failures." },
  ],
});
export const HarvestDiagnosticsSchema = HarvestDiagnosticsBaseSchema.superRefine((value, ctx) => {
  if (value.body_limit !== null && value.fetch_failure !== "body-too-large"
    && value.robots_failure !== "body-too-large") {
    reject(ctx, "byte-limit evidence requires a body-too-large fetch or robots failure", ["body_limit"]);
  }
});
export type HarvestDiagnostics = z.infer<typeof HarvestDiagnosticsSchema>;
export const ArticleFetchEvidenceSchema = HarvestDiagnosticsBaseSchema.pick({
  http_status: true, fetch_failure: true, error_code: true,
  robots: true, robots_http_status: true, robots_failure: true,
});
export type ArticleFetchEvidence = z.infer<typeof ArticleFetchEvidenceSchema>;
export type FetchFailure = z.infer<typeof FetchFailureSchema>;
export type ExtractionFailure = z.infer<typeof ExtractionFailureSchema>;
