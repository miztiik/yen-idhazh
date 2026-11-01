/** Which native request, document and attempt shapes can live operator APIs use? */
import { z } from "zod";
import { CountSchema, NonEmptySchema, RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, UrlSchema } from "./primitives";
import { BodyLimitEvidenceSchema, FetchFailureSchema } from "./harvest-diagnostics.schema";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { SourceArticleRefusalReasonSchema } from "./rejection.schema";
import { HttpResponseEvidenceSchema, RequestProfileSchema } from "./http-response-evidence.schema";

export const OPERATION_VERSION = "2026-11-01" as const;
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
export const RequestIdSchema = z.uuid({ version: "v4" });
export const FetchAttemptSchema = z.strictObject({
  phase: z.enum(["validation", "robots", "target"]), sequence: CountSchema, retry: CountSchema,
  duration_ms: CountSchema, backoff_ms: CountSchema.nullable().default(null),
  retry_total_ms: CountSchema.nullable().default(null),
  http_status: z.int().min(100).max(599).nullable(),
  failure: FetchFailureSchema.nullable(),
  error_code: z.string().max(64).regex(/^[A-Z][A-Z0-9_]*$/).nullable(),
  request_profile: RequestProfileSchema.nullable().default(null),
  request_url: UrlSchema.nullable().default(null),
  response_evidence: HttpResponseEvidenceSchema.nullable().default(null),
});
export type FetchAttempt = z.infer<typeof FetchAttemptSchema>;
export const NetworkFailureDetailsSchema = z.strictObject({
  requested_url: UrlSchema.nullable(), final_attempted_url: UrlSchema.nullable(), failed_url: UrlSchema.nullable(),
  http_status: FetchAttemptSchema.shape.http_status,
  request_profile: RequestProfileSchema.nullable(),
  response_evidence: HttpResponseEvidenceSchema.nullable(),
  robots_response_evidence: HttpResponseEvidenceSchema.nullable(),
  robots_http_status: FetchAttemptSchema.shape.http_status,
  robots_failure: FetchFailureSchema.nullable(),
  attempt: FetchAttemptSchema.nullable(),
}).meta({
  version: OPERATION_VERSION,
  changelog: [{ version: OPERATION_VERSION, change: "Validate body-free failure details separately from flexible log fields." }],
});
export type NetworkFailureDetails = z.infer<typeof NetworkFailureDetailsSchema>;
export const PlannerObservationSchema = z.strictObject({
  event_id: z.uuid({ version: "v5" }), caused_by_event_id: z.uuid({ version: "v5" }).nullable(),
  correlation_id: NonEmptySchema, run_id: RunIdSchema, article_id: Sha256Schema,
  feed_id: SlugSchema, occurred_at: TimestampSchema,
  operation: z.enum(["fetch", "parse", "attempt"]),
});
export const FetchedDocumentSchema = z.strictObject({
  version: OperationVersionSchema,
  fetch_item_type: z.enum(["feed", "article"]), canonical_url: UrlSchema, article_id: Sha256Schema, feed_id: SlugSchema,
  body: z.string().nullable(), http_status: z.int().min(100).max(599).nullable(),
  failure: FetchFailureSchema.nullable(), robots: z.enum(["allowed", "denied", "unknown"]).nullable(),
  error_code: FetchAttemptSchema.shape.error_code, robots_failure: FetchFailureSchema.nullable(),
  robots_http_status: z.int().min(100).max(599).nullable(),
  body_limit: BodyLimitEvidenceSchema.nullable().default(null),
  response_evidence: HttpResponseEvidenceSchema.nullable().default(null),
  robots_response_evidence: HttpResponseEvidenceSchema.nullable().default(null),
  requested_url: UrlSchema.nullable().default(null),
  final_attempted_url: UrlSchema.nullable().default(null),
  failed_url: UrlSchema.nullable().default(null),
  redirects: z.array(z.strictObject({
    request_url: UrlSchema.nullable(), destination_url: UrlSchema.nullable(),
    http_status: z.int().min(300).max(399),
  })).default([]),
  attempts: z.array(FetchAttemptSchema), observation: PlannerObservationSchema,
  attempt_observations: z.array(PlannerObservationSchema), body_sha256: Sha256Schema.nullable(),
  parent_fetch_request_id: RequestIdSchema.nullable().default(null),
  parent_batch_id: RequestIdSchema.nullable().default(null),
  entry_ordinal: CountSchema.nullable().default(null),
}).superRefine((value, ctx) => {
  if (value.fetch_item_type === "article" && /[?#]/.test(value.canonical_url)) {
    ctx.addIssue({ code: "custom", message: "current article address must not contain a query or fragment" });
  }
  if (value.body === null ? value.body_sha256 !== null : value.body_sha256 === null) {
    ctx.addIssue({ code: "custom", message: "body and body digest must be available together" });
  }
  const bodyLimitFailure = value.failure === "body-too-large" || value.robots_failure === "body-too-large";
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
      || observation.run_id !== value.observation.run_id || observation.correlation_id !== value.observation.correlation_id
      || observation.caused_by_event_id !== value.observation.event_id)) {
    ctx.addIssue({ code: "custom", message: "attempt observations must match the ordered attempts" });
  }
}).meta({
  version: OPERATION_VERSION,
  changelog: [
    { version: OPERATION_VERSION, change: "Add native response, profile and safe request-address evidence." },
    { version: OPERATION_VERSION, change: "Require current fetched documents without older-format readers." },
    { version: "2026-10-30", change: "Retain configured response limits and observed cutoff bytes." },
    { version: "2026-10-29", change: "Identify shared query-free article captures." },
    { version: "2026-10-28", change: "Earlier changes are in this file's Git history." },
  ],
});
export type FetchedDocument = z.infer<typeof FetchedDocumentSchema>;

export const FetchRequestSchema = z.strictObject({
  request_id: RequestIdSchema, correlation_id: RequestIdSchema,
  feed_id: SlugSchema, fetch_item_type: z.enum(["feed", "article"]), url: UrlSchema.optional(),
  batch_id: RequestIdSchema.optional(), offer_id: Sha256Schema.optional(),
  collection_id: RequestIdSchema.optional(),
  caused_by_event_id: z.uuid({ version: "v5" }).optional(),
}).refine(value => value.fetch_item_type === "article" || (value.url === undefined && value.batch_id === undefined && value.offer_id === undefined), {
  message: "feed URLs come only from the configured source", path: ["url"],
}).refine(value => value.fetch_item_type === "feed" || (value.url !== undefined
  ? value.batch_id === undefined && value.offer_id === undefined : value.batch_id !== undefined && value.offer_id !== undefined), {
  message: "article fetch requires an operator URL or a complete server-owned offer reference", path: ["url"],
});
export const ParseRequestSchema = z.strictObject({
  request_id: RequestIdSchema, fetch_request_id: RequestIdSchema,
  article_id: Sha256Schema, correlation_id: RequestIdSchema,
});
