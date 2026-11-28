/** Which producer facts may reach a planner workflow's stderr and same-run mirror? */
import { z } from "zod";
import { CloudEventSchema } from "./cloud-event.schema";
import { PlannerLedgerNameSchema } from "./envelope.schema";
import { FeedIngestEventDataSchema, PLANNER_PROGRESS_DETAIL_LIMITS } from "./event.schema";
import { FeedHealthFieldUseSchema } from "./feed-health-fields.schema";
import { ExtractionFailureSchema, ExtractionSignalSchema, FetchFailureSchema } from "./harvest-diagnostics.schema";
import { PlannerErrorResponseSchema, PlannerFailureDetailSchema } from "./planner-failure.schema";
import { FetchAttemptSchema } from "./planner-operation.schema";
import { CandidateIdSchema, PositiveCountSchema, RunIdSchema, Sha256Schema, SlugSchema } from "./primitives";
import { DropReasonSchema } from "./rejection.schema";

export const PLANNER_WORKFLOW_FAILURE_TYPE = "planner.workflow-failure";
export const PLANNER_WORKFLOW_FAILURE_VERSION = "2026-11-28";
const identityLimit = PLANNER_PROGRESS_DETAIL_LIMITS.stringLength;
const SourceIdSchema = SlugSchema.max(identityLimit);
const DestinationDomainSchema = z.union([z.hostname().max(253), z.ipv4(), z.ipv6()])
  .refine(value => value === value.toLowerCase() && !value.endsWith("."));
const HistoryCheckSchema = z.string().max(64).regex(/^(?:[a-z][a-z0-9_-]*|\$row)$/);
// Inventory notices can identify a calendar period, never a path or free text.
const HistoryCauseSchema = z.string().max(64)
  .regex(/^[a-z][a-z0-9_-]*(?::(?:yearly|monthly|daily|\d{4}(?:-\d{2}){0,2}))?$/);
const base = {
  version: z.literal(PLANNER_WORKFLOW_FAILURE_VERSION), run_id: RunIdSchema.max(identityLimit), attempt: PositiveCountSchema,
};
const document = {
  document_kind: z.enum(["feed", "article"]), feed_id: SourceIdSchema, publisher_id: SourceIdSchema.nullable(),
  document_id: Sha256Schema, candidate_id: CandidateIdSchema.nullable(),
};
const target = {
  destination_domain: DestinationDomainSchema.nullable(),
  http_status: FetchAttemptSchema.shape.http_status, error_code: FetchAttemptSchema.shape.error_code,
};
const documentFailure = { ...base, ...document, kind: z.literal("document-failure") };
export const PlannerWorkflowFailureDataSchema = z.discriminatedUnion("kind", [
  z.strictObject({
    ...base, ...document, ...target, kind: z.literal("failed-dispatch"), operation: z.literal("request-attempt"),
    cause: FetchFailureSchema.nullable(), sequence: FetchAttemptSchema.shape.sequence, retry: FetchAttemptSchema.shape.retry,
  }),
  z.discriminatedUnion("operation", [
    z.strictObject({
      ...documentFailure, ...target, operation: z.literal("fetch"),
      cause: z.union([FetchFailureSchema, z.literal("FETCH_FAILED")]).nullable(),
    }),
    z.strictObject({
      ...documentFailure, operation: z.literal("parse"),
      cause: z.union([ExtractionFailureSchema, z.enum(["malformed-feed", "PARSE_FAILED"])]).nullable(),
    }),
    z.strictObject({
      ...documentFailure, operation: z.literal("quality"), cause: ExtractionSignalSchema,
    }),
  ]),
  z.strictObject({
    ...base, ...document, kind: z.literal("policy-refusal"), operation: z.literal("fetch"),
    cause: DropReasonSchema.nullable(),
  }),
  z.strictObject({
    ...base, kind: z.literal("history-gap"), operation: z.literal("history"),
    scope: z.enum(["planner-ledger", "feed-health-field", "feed-health-calculation", "health-inventory"]),
    check: HistoryCheckSchema, cause: HistoryCauseSchema,
    ledger: PlannerLedgerNameSchema.nullable(), day: z.iso.date().nullable(),
    use: FeedHealthFieldUseSchema.nullable(), feed_id: SourceIdSchema.nullable(), endpoint_key: Sha256Schema.nullable(),
  }),
  z.strictObject({
    ...base, kind: z.literal("stage-failure"),
    operation: FeedIngestEventDataSchema.shape.operation.exclude(["history", "request-attempt", "quality"]),
    scope: z.literal("plan").nullable(), code: PlannerErrorResponseSchema.shape.code,
    cause: PlannerFailureDetailSchema.shape.safe_cause.nullable(),
    cause_operation: PlannerFailureDetailSchema.shape.operation.nullable(),
    system_code: PlannerFailureDetailSchema.shape.system_code,
  }),
]);
export const PlannerWorkflowFailureSchema = CloudEventSchema.safeExtend({
  type: z.literal(PLANNER_WORKFLOW_FAILURE_TYPE), data: PlannerWorkflowFailureDataSchema,
}).meta({
  version: PLANNER_WORKFLOW_FAILURE_VERSION,
  readCompatibility: "current_only; the child and relay use the same schema",
  changelog: [
    { version: PLANNER_WORKFLOW_FAILURE_VERSION, change: "Retain the native cause of a failed planner occurrence in workflow logs." },
  ],
});
export type PlannerWorkflowFailure = z.infer<typeof PlannerWorkflowFailureSchema>;
