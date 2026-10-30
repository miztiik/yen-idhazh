/** Which native request journal and document shapes may operator APIs read? */
import { z } from "zod";
import { CountSchema, NonEmptySchema, RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, UrlSchema } from "./primitives";
import { FetchFailureSchema } from "./harvest-diagnostics.schema";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { SourceArticleRefusalReasonSchema } from "./rejection.schema";

export const LEGACY_OPERATION_VERSION = "2026-10-28" as const;
export const OPERATION_VERSION = "2026-10-29" as const;
export const OPERATION_ACCEPTED_SCHEMA_VERSIONS = [LEGACY_OPERATION_VERSION, OPERATION_VERSION] as const;
const OperationVersionSchema = z.enum(OPERATION_ACCEPTED_SCHEMA_VERSIONS).default(OPERATION_VERSION);
export const LEGACY_PLANNER_OPERATION_VERSION = "2026-10-28" as const;
export const PLANNER_OPERATION_VERSION = "2026-10-29" as const;
export const PLANNER_OPERATION_ACCEPTED_SCHEMA_VERSIONS = [
  LEGACY_PLANNER_OPERATION_VERSION, PLANNER_OPERATION_VERSION,
] as const;
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
});
export type FetchAttempt = z.infer<typeof FetchAttemptSchema>;
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
  attempts: z.array(FetchAttemptSchema), observation: PlannerObservationSchema,
  attempt_observations: z.array(PlannerObservationSchema), body_sha256: Sha256Schema.nullable(),
  parent_fetch_request_id: RequestIdSchema.nullable().default(null),
  parent_batch_id: RequestIdSchema.nullable().default(null),
  entry_ordinal: CountSchema.nullable().default(null),
}).superRefine((value, ctx) => {
  if (value.version === OPERATION_VERSION && value.fetch_item_type === "article" && /[?#]/.test(value.canonical_url)) {
    ctx.addIssue({ code: "custom", message: "current article address must not contain a query or fragment" });
  }
  if (value.body === null ? value.body_sha256 !== null : value.body_sha256 === null) {
    ctx.addIssue({ code: "custom", message: "body and body digest must be available together" });
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
    { version: OPERATION_VERSION, change: "Identify shared query-free article captures while preserving legacy receipts unchanged." },
    { version: LEGACY_OPERATION_VERSION, change: "Rename fetched document and observation feed identity from source_id to feed_id." },
    { version: "2026-10-27", change: "Name the fetched item type and refuse older fetch artifacts." },
    { version: "2026-10-26", change: "Link fetched articles to bounded server-owned feed offers." },
    { version: "2026-10-23", change: "Earlier changes are in git." },
  ],
});
export const PlannerOperationSchema = z.strictObject({
  version: z.enum(PLANNER_OPERATION_ACCEPTED_SCHEMA_VERSIONS).default(PLANNER_OPERATION_VERSION),
  request_id: RequestIdSchema, operation: z.enum(["fetch", "parse", "plan"]),
  input_sha256: Sha256Schema, config_sha256: Sha256Schema, run_id: RunIdSchema,
  correlation_id: RequestIdSchema, created_at: RecordedInstantSchema, state: z.enum(["started", "complete"]),
  response_json: z.string().nullable(), artifact: FetchedDocumentSchema.nullable(),
  source_outcome: SourceArticleOutcomeSchema.nullable().default(null),
  article_capture_request_ids: z.array(RequestIdSchema).default([]),
}).superRefine((value, ctx) => {
  if (new Set(value.article_capture_request_ids).size !== value.article_capture_request_ids.length
    || (value.article_capture_request_ids.length > 0
      && (value.state !== "complete" || value.operation !== "fetch" || value.artifact?.fetch_item_type !== "feed"))) {
    ctx.addIssue({ code: "custom", message: "Only a completed feed capture has distinct bounded article receipt references" });
  }
  if (value.source_outcome !== null && (value.state !== "complete" || value.operation !== "fetch" || value.artifact?.fetch_item_type !== "article")) {
    ctx.addIssue({ code: "custom", message: "A source outcome belongs only to a completed article capture" });
  }
  if (value.state === "started" && (value.response_json !== null || value.artifact !== null)) {
    ctx.addIssue({ code: "custom", message: "started requests cannot carry completed output" });
  }
  if (value.state === "complete") {
    if (value.response_json === null || ((value.operation === "fetch") !== (value.artifact !== null))) {
      ctx.addIssue({ code: "custom", message: "completed requests need a response and only fetch carries an artifact" });
    } else {
      try { JSON.parse(value.response_json); }
      catch { ctx.addIssue({ code: "custom", message: "completed response must be valid JSON" }); }
    }
  }
}).meta({
  version: PLANNER_OPERATION_VERSION,
  changelog: [
    { version: PLANNER_OPERATION_VERSION, change: "Retain legacy operation responses and identify shared article-cleanup captures." },
    { version: LEGACY_PLANNER_OPERATION_VERSION, change: "Rename nested fetched feed identity from source_id to feed_id." },
    { version: "2026-10-27T18:30", change: "Settle original article outcomes and retain their bounded receipt membership on the feed capture." },
    { version: "2026-10-27", change: "Refuse prior operation formats after renaming fetch routing." },
    { version: "2026-10-23", change: "Earlier changes are in git." },
  ],
});
export type PlannerOperation = z.infer<typeof PlannerOperationSchema>;
export type FetchedDocument = z.infer<typeof FetchedDocumentSchema>;

export const FetchRequestSchema = z.strictObject({
  request_id: RequestIdSchema, correlation_id: RequestIdSchema,
  feed_id: SlugSchema, fetch_item_type: z.enum(["feed", "article"]), url: UrlSchema.optional(),
  batch_id: RequestIdSchema.optional(), offer_id: Sha256Schema.optional(),
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
