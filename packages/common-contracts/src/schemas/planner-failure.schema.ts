/** Which bounded, body-free execution failure may cross planner boundaries? */
import { z } from "zod";
import { CommitShaSchema, CountSchema, PositiveCountSchema, RelPathSchema, RunIdSchema } from "./primitives";
import { TraceIdSchema, SpanIdSchema } from "./operation-metadata.schema";

export const PLANNER_FAILURE_VERSION = "2026-11-03" as const;
// These protocol caps keep one failure inside the existing structured-event byte limit.
export const MAX_PLANNER_FAILURE_CAUSES = 3;
export const MAX_PLANNER_ERROR_ISSUES = 32;
export const PlannerFailureOperationSchema = z.enum([
  "plan", "collection-start", "collection-complete", "collection-cancel", "collection-finalize", "collection-release",
  "fetch", "parse", "select", "partition", "persist", "record-run",
  "feed-health-before-fetch", "feed-health-for-selection", "feed-health-state", "feed-health-summary",
  "recognize-entities", "write-entities", "write-document-failures",
  "listener-start", "listener-close", "workflow", "verify-output",
  "commit-ledgers", "write-report", "prepare-artifacts", "artifact-upload",
]);
export const PlannerFailureDetailSchema = z.strictObject({
  operation: PlannerFailureOperationSchema,
  error_type: z.enum([
    "Error", "TypeError", "SyntaxError", "RangeError", "ReferenceError", "AggregateError",
    "ZodError", "PlanError", "AbortError", "UnknownError",
  ]),
  safe_cause: z.enum([
    "invalid-input", "invalid-state", "undefined-value", "invalid-type", "invalid-syntax",
    "out-of-range", "missing-reference", "cancelled", "system-error", "execution-error",
  ]),
  system_code: z.enum([
    "EACCES", "EPERM", "ENOENT", "ENOTDIR", "EISDIR", "EEXIST", "ENOSPC", "EIO",
    "EMFILE", "ENFILE", "EROFS", "EBUSY", "EPIPE", "EADDRINUSE", "ECONNREFUSED", "ECONNRESET", "ETIMEDOUT",
  ]).nullable(),
  source: z.strictObject({ file: RelPathSchema.max(256), line: PositiveCountSchema }).nullable(),
});
export const PlannerFailureExecutionSchema = z.strictObject({
  run_id: RunIdSchema.max(512).nullable(), attempt: PositiveCountSchema.nullable(),
  traceId: TraceIdSchema.nullable(), spanId: SpanIdSchema.nullable(), git_sha: CommitShaSchema.nullable(),
}).refine(value => value.spanId === null || value.traceId !== null, {
  message: "an operation requires its execution identity", path: ["traceId"],
});
export const PlannerFailureSchema = PlannerFailureDetailSchema.extend({
  schema_version: z.literal(PLANNER_FAILURE_VERSION).default(PLANNER_FAILURE_VERSION),
  execution: PlannerFailureExecutionSchema,
  causes: z.array(PlannerFailureDetailSchema).max(MAX_PLANNER_FAILURE_CAUSES),
  omitted_causes: CountSchema,
}).meta({
  version: PLANNER_FAILURE_VERSION,
  changelog: [
    { version: PLANNER_FAILURE_VERSION, change: "Retain known execution and operation context without duplicate UUIDs." },
    { version: "2026-11-02", change: "Retain safe original frames and bounded secondary failures." },
  ],
});
export type PlannerFailure = z.infer<typeof PlannerFailureSchema>;
export type PlannerFailureDetail = z.infer<typeof PlannerFailureDetailSchema>;
export type PlannerFailureOperation = z.infer<typeof PlannerFailureOperationSchema>;
export type PlannerFailureExecution = z.infer<typeof PlannerFailureExecutionSchema>;
export const PlannerFailureReadSchema = PlannerFailureSchema.safeExtend({
  schema_version: PlannerFailureSchema.shape.schema_version.unwrap(),
});

export const PlannerErrorResponseSchema = z.strictObject({
  code: z.string().min(1).max(64).regex(/^[A-Z][A-Z0-9_]*$/),
  issues: z.array(z.strictObject({
    field: z.string().max(256).nullable(), message: z.string().min(1).max(256),
  })).min(1).max(MAX_PLANNER_ERROR_ISSUES),
  failure: PlannerFailureReadSchema.nullable().default(null),
}).meta({
  version: PLANNER_FAILURE_VERSION,
  changelog: [
    { version: PLANNER_FAILURE_VERSION, change: "Require current error context without earlier-format readers." },
  ],
});
