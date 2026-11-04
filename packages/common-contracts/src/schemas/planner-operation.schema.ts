/** Which native request, document and attempt shapes can live operator APIs use? */
import { z } from "zod";
import { CountSchema, RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, UrlSchema } from "./primitives";
import { BodyLimitEvidenceSchema, FetchFailureSchema } from "./harvest-diagnostics.schema";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { SourceArticleRefusalReasonSchema } from "./rejection.schema";
import { HttpResponseEvidenceSchema, RequestProfileSchema } from "./http-response-evidence.schema";
import { RequestPacingSettingsSchema } from "./config.schema";
import { OperationLinkSchema, OperationMetadataSchema, TraceIdSchema } from "./operation-metadata.schema";

export const OPERATION_VERSION = "2026-11-04" as const;
const NETWORK_FAILURE_VERSION = "2026-11-03" as const;
const OperationVersionSchema = z.literal(OPERATION_VERSION).default(OPERATION_VERSION);
export const SourceArticleOutcomeSchema = z.strictObject({
  disposition: z.enum(["admitted", "source_refused"]),
  reason_code: SourceArticleRefusalReasonSchema.nullable(), settled_at: RecordedInstantSchema,
}).superRefine((value, ctx) => {
  if ((value.disposition === "admitted") !== (value.reason_code === null)) {
    ctx.addIssue({ code: "custom", message: "Only a source refusal carries a technical reason" });
  }
});
export type SourceArticleOutcome = z.infer<typeof SourceArticleOutcomeSchema>;
export const FetchAttemptSchema = z.strictObject({
  phase: z.enum(["validation", "target"]), sequence: CountSchema, retry: CountSchema,
  duration_ms: CountSchema, backoff_ms: CountSchema.nullable().default(null),
  retry_total_ms: CountSchema.nullable().default(null),
  http_status: z.int().min(100).max(599).nullable(),
  failure: FetchFailureSchema.nullable(),
  error_code: z.string().max(64).regex(/^[A-Z][A-Z0-9_]*$/).nullable(),
  request_profile: RequestProfileSchema.nullable().default(null),
  request_url: UrlSchema.nullable().default(null),
  response_evidence: HttpResponseEvidenceSchema.nullable().default(null),
  pacing_wait_ms: CountSchema.nullable().default(null),
});
export type FetchAttempt = z.infer<typeof FetchAttemptSchema>;
export const NetworkFailureDetailsSchema = z.strictObject({
  requested_url: UrlSchema.nullable(), final_attempted_url: UrlSchema.nullable(), failed_url: UrlSchema.nullable(),
  http_status: FetchAttemptSchema.shape.http_status,
  request_profile: RequestProfileSchema.nullable(),
  response_evidence: HttpResponseEvidenceSchema.nullable(),
  pacing_time_ms: CountSchema.nullable().default(null),
  pacing_settings: RequestPacingSettingsSchema.nullable().default(null),
  attempt: FetchAttemptSchema.nullable(),
}).meta({
  version: NETWORK_FAILURE_VERSION,
  changelog: [
    { version: NETWORK_FAILURE_VERSION, change: "Retain only target request failures and response evidence." },
    { version: "2026-11-01", change: "Retain request pacing waits and effective settings in failure details." },
    { version: "2026-11-01", change: "Validate body-free failure details separately from flexible log fields." },
  ],
});
export type NetworkFailureDetails = z.infer<typeof NetworkFailureDetailsSchema>;
export const PlannerObservationSchema = OperationMetadataSchema.safeExtend({
  run_id: RunIdSchema, article_id: Sha256Schema,
  feed_id: SlugSchema, occurred_at: TimestampSchema,
  operation: z.enum(["fetch", "parse", "attempt"]),
});
export const FetchedDocumentSchema = z.strictObject({
  version: OperationVersionSchema,
  fetch_item_type: z.enum(["feed", "article"]), canonical_url: UrlSchema, article_id: Sha256Schema, feed_id: SlugSchema,
  body: z.string().nullable(), http_status: z.int().min(100).max(599).nullable(),
  failure: FetchFailureSchema.nullable(),
  error_code: FetchAttemptSchema.shape.error_code,
  body_limit: BodyLimitEvidenceSchema.nullable().default(null),
  response_evidence: HttpResponseEvidenceSchema.nullable().default(null),
  requested_url: UrlSchema.nullable().default(null),
  final_attempted_url: UrlSchema.nullable().default(null),
  failed_url: UrlSchema.nullable().default(null),
  redirects: z.array(z.strictObject({
    request_url: UrlSchema.nullable(), destination_url: UrlSchema.nullable(),
    http_status: z.int().min(300).max(399),
  })).default([]),
  pacing_time_ms: CountSchema,
  pacing_settings: RequestPacingSettingsSchema,
  attempts: z.array(FetchAttemptSchema), observation: PlannerObservationSchema,
  attempt_observations: z.array(PlannerObservationSchema), body_sha256: Sha256Schema.nullable(),
  entry_ordinal: CountSchema.nullable().default(null),
}).superRefine((value, ctx) => {
  if (value.canonical_url.includes("#")) {
    ctx.addIssue({ code: "custom", message: "canonical resource address must not contain a fragment" });
  }
  if (value.body === null ? value.body_sha256 !== null : value.body_sha256 === null) {
    ctx.addIssue({ code: "custom", message: "body and body digest must be available together" });
  }
  const bodyLimitFailure = value.failure === "body-too-large";
  if ((value.body_limit !== null && !bodyLimitFailure)
    || (bodyLimitFailure && value.body_limit === null)) {
    ctx.addIssue({ code: "custom", message: "current body-limit failures require their measured cutoff evidence" });
  }
  if (value.observation.operation !== "fetch" || value.observation.article_id !== value.article_id
    || value.observation.feed_id !== value.feed_id) {
    ctx.addIssue({ code: "custom", message: "fetch observation must retain document identity" });
  }
  if (value.attempts.length !== value.attempt_observations.length
    || value.attempts.some((attempt, index) => attempt.sequence !== index)
    || value.attempt_observations.some(observation => observation.operation !== "attempt"
      || observation.feed_id !== value.feed_id || observation.article_id !== value.article_id
      || observation.run_id !== value.observation.run_id || observation.traceId !== value.observation.traceId
      || observation.parentSpanId !== value.observation.spanId)) {
    ctx.addIssue({ code: "custom", message: "attempt observations must match the ordered attempts" });
  }
}).meta({
  version: OPERATION_VERSION,
  changelog: [
    { version: OPERATION_VERSION, change: "Preserve normalized feed and article queries while refusing canonical fragments." },
    { version: "2026-11-03", change: "Identify fetch and attempt operations with native context and input links." },
    { version: "2026-11-02", change: "Remove robots fields and attempts from current fetched documents." },
    { version: "2026-11-01", change: "Preserve request pacing waits and effective settings." },
    { version: "2026-10-28", change: "Earlier changes are in this file's Git history." },
  ],
});
export type FetchedDocument = z.infer<typeof FetchedDocumentSchema>;

export const FetchRequestSchema = z.union([
  z.strictObject({ feed_id: SlugSchema, fetch_item_type: z.literal("feed"), traceId: TraceIdSchema.optional() }),
  z.strictObject({ feed_id: SlugSchema, fetch_item_type: z.literal("article"), url: UrlSchema, traceId: TraceIdSchema.optional() }),
  z.strictObject({ fetch_item_type: z.literal("article"), offer_id: Sha256Schema, links: z.tuple([OperationLinkSchema]) }),
]);
export const ParseRequestSchema = z.strictObject({
  links: z.tuple([OperationLinkSchema]),
});
