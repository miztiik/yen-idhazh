/** Which measured feed and document operations can later feedback read? */
import { z } from "zod";
import {
  CountSchema, NonEmptySchema, PositiveCountSchema, RunIdSchema, Sha256Schema, SlugSchema,
  TimestampSchema,
} from "./primitives";
import { DOCUMENT_OBSERVATION_VERSION } from "../version";

export const DocumentObservationRecordSchema = z.strictObject({
  version: z.literal(DOCUMENT_OBSERVATION_VERSION).default(DOCUMENT_OBSERVATION_VERSION),
  event_id: z.uuid({ version: "v5" }),
  caused_by_event_id: z.uuid({ version: "v5" }).nullable(),
  observed_run_id: RunIdSchema.nullable(),
  observed_attempt: PositiveCountSchema.nullable(),
  correlation_id: NonEmptySchema.nullable(),
  source_id: SlugSchema.nullable(),
  publisher_id: SlugSchema.nullable(),
  article_id: Sha256Schema.nullable(),
  candidate_id: Sha256Schema.nullable(),
  operation: z.enum(["fetch", "parse", "attempt"]),
  outcome: z.enum(["success", "empty", "failed", "not_attempted", "unavailable"]),
  occurred_at: TimestampSchema,
  duration_ms: CountSchema.nullable(),
  http_status: z.int().min(100).max(599).nullable(),
  attribution: z.enum(["source", "pipeline", "unresolved"]).nullable(),
  failure_code: z.enum([
    "http", "timeout", "unsafe-target", "dns", "network", "robots-denied",
    "robots-unknown", "body-too-large", "redirect-loop", "missing-document-root",
    "dom-depth-exceeded", "empty-content", "missing-title", "malformed-feed",
  ]).nullable(),
  request_phase: z.enum(["validation", "robots", "target"]).nullable(),
  request_sequence: CountSchema.nullable(),
  retry: CountSchema.nullable(),
  dispatched_request_count: CountSchema.nullable(),
  request_coverage: z.enum(["complete", "partial", "unknown"]).nullable(),
}).superRefine((value, ctx) => {
  if (value.event_id === value.caused_by_event_id) {
    ctx.addIssue({ code: "custom", message: "an observation cannot cause itself" });
  }
  if (value.observed_attempt !== null && value.observed_run_id === null) {
    ctx.addIssue({ code: "custom", message: "an observed run attempt requires its run identity" });
  }
  if (value.publisher_id !== null && value.source_id === null) {
    ctx.addIssue({ code: "custom", message: "a publisher identity requires its source identity" });
  }
  if (value.outcome === "failed") {
    if (value.attribution === null) {
      ctx.addIssue({ code: "custom", message: "a failed operation records its attribution status" });
    }
  } else if (value.attribution !== null || value.failure_code !== null) {
    ctx.addIssue({ code: "custom", message: "only a failed operation records failure attribution or cause" });
  }

  const requestFields = [
    value.request_phase, value.request_sequence, value.retry,
    value.dispatched_request_count, value.request_coverage,
  ];
  if (value.operation === "attempt") {
    if (value.request_phase === null || value.request_sequence === null || value.retry === null
      || value.request_coverage === null) {
      ctx.addIssue({ code: "custom", message: "an attempt records its phase, order, retry and request coverage" });
    }
    if (value.request_coverage === "complete" && value.dispatched_request_count === null) {
      ctx.addIssue({ code: "custom", message: "complete request coverage records its measured count" });
    }
    if (value.request_coverage === "unknown" && value.dispatched_request_count !== null) {
      ctx.addIssue({ code: "custom", message: "unknown request coverage has no measured count" });
    }
  } else if (requestFields.some(field => field !== null)) {
    ctx.addIssue({ code: "custom", message: "phase-specific request accounting belongs to attempt observations" });
  }
}).meta({
  version: DOCUMENT_OBSERVATION_VERSION,
  changelog: [
    { version: DOCUMENT_OBSERVATION_VERSION, change: "Declare per-operation observations with scoped request accounting." },
  ],
});
export type DocumentObservationRecord = z.infer<typeof DocumentObservationRecordSchema>;
