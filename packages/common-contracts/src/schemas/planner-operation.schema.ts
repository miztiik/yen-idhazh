/** Which native request journal and document shapes may operator APIs read? */
import { z } from "zod";
import { CountSchema, NonEmptySchema, RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, UrlSchema } from "./primitives";
import { FetchFailureSchema } from "./harvest-diagnostics.schema";
import { RecordedInstantSchema } from "./recorded-instant.schema";

export const OPERATION_VERSION = "2026-10-23T09:22";
const OperationVersionSchema = z.enum(["2026-10-23", OPERATION_VERSION]).default(OPERATION_VERSION);
export const PLANNER_OPERATION_VERSION = "2026-10-23T18:50";
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
  source_id: SlugSchema, occurred_at: TimestampSchema,
  operation: z.enum(["fetch", "parse", "attempt"]),
});
export const FetchedDocumentSchema = z.strictObject({
  version: OperationVersionSchema,
  kind: z.enum(["feed", "article"]), canonical_url: UrlSchema, article_id: Sha256Schema, source_id: SlugSchema,
  body: z.string().nullable(), http_status: z.int().min(100).max(599).nullable(),
  failure: FetchFailureSchema.nullable(), robots: z.enum(["allowed", "denied", "unknown"]).nullable(),
  error_code: FetchAttemptSchema.shape.error_code, robots_failure: FetchFailureSchema.nullable(),
  robots_http_status: z.int().min(100).max(599).nullable(),
  attempts: z.array(FetchAttemptSchema), observation: PlannerObservationSchema,
  attempt_observations: z.array(PlannerObservationSchema), body_sha256: Sha256Schema.nullable(),
}).superRefine((value, ctx) => {
  if (value.body === null ? value.body_sha256 !== null : value.body_sha256 === null) {
    ctx.addIssue({ code: "custom", message: "body and body digest must be available together" });
  }
  if (value.observation.operation !== "fetch" || value.observation.article_id !== value.article_id
    || value.observation.source_id !== value.source_id) {
    ctx.addIssue({ code: "custom", message: "fetch observation must retain document identity" });
  }
  if (value.attempts.length !== value.attempt_observations.length
    || value.attempts.some((attempt, index) => attempt.sequence !== index)) {
    ctx.addIssue({ code: "custom", message: "attempt observations must match the ordered attempts" });
  }
}).meta({
  version: OPERATION_VERSION,
  changelog: [
    { version: OPERATION_VERSION, change: "Record actual retry waits and elapsed retry time." },
    { version: "2026-10-23", change: "Declare durable fetched documents and causal observations." },
  ],
});
export const PlannerOperationSchema = z.strictObject({
  version: z.enum(["2026-10-23", OPERATION_VERSION, PLANNER_OPERATION_VERSION]).default(PLANNER_OPERATION_VERSION),
  request_id: RequestIdSchema, operation: z.enum(["fetch", "parse", "plan"]),
  input_sha256: Sha256Schema, config_sha256: Sha256Schema, run_id: RunIdSchema,
  correlation_id: RequestIdSchema, created_at: RecordedInstantSchema, state: z.enum(["started", "complete"]),
  response_json: z.string().nullable(), artifact: FetchedDocumentSchema.nullable(),
}).superRefine((value, ctx) => {
  if (value.created_at.includes(".") && value.version < PLANNER_OPERATION_VERSION) {
    ctx.addIssue({ code: "custom", message: "legacy operations use whole-second created_at" });
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
    { version: PLANNER_OPERATION_VERSION, change: "Retain the original captured clock precision through replay." },
    { version: OPERATION_VERSION, change: "Retain measured retry waits on fetched artifacts." },
    { version: "2026-10-23", change: "Declare durable keyed operator request replay." },
  ],
});
export type PlannerOperation = z.infer<typeof PlannerOperationSchema>;
export type FetchedDocument = z.infer<typeof FetchedDocumentSchema>;

export const FetchRequestSchema = z.strictObject({
  request_id: RequestIdSchema, correlation_id: RequestIdSchema,
  source_id: SlugSchema, kind: z.enum(["feed", "article"]), url: UrlSchema.optional(),
  caused_by_event_id: z.uuid({ version: "v5" }).optional(),
}).refine(value => value.kind === "article" || value.url === undefined, {
  message: "feed URLs come only from the configured source", path: ["url"],
}).refine(value => value.kind === "feed" || value.url !== undefined, {
  message: "article fetch requires an operator-owned URL", path: ["url"],
});
export const ParseRequestSchema = z.strictObject({
  request_id: RequestIdSchema, fetch_request_id: RequestIdSchema,
  article_id: Sha256Schema, correlation_id: RequestIdSchema,
});
