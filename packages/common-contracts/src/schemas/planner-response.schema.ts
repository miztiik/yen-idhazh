/** Which saved planner response retains outcomes without private batches or article bodies? */
import { z } from "zod";
import { CountSchema, NonEmptySchema, RelPathSchema, Sha256Schema } from "./primitives";
import { RequestIdSchema } from "./planner-operation.schema";
import { PlanRunRowSchema } from "./plan-run.schema";
import { PlannerErrorResponseSchema, PlannerFailureSchema } from "./planner-failure.schema";

export const PLANNER_RESPONSE_VERSION = "2026-11-02" as const;
export const PlannerLedgerWriteResultSchema = z.discriminatedUnion("status", [
  z.strictObject({ status: z.literal("written"), files: z.array(z.strictObject({
    path: RelPathSchema, file_id: z.uuid(), covers: NonEmptySchema,
    content_sha256: Sha256Schema, row_count: CountSchema,
  })).min(1) }),
  z.strictObject({ status: z.literal("empty"), files: z.tuple([]) }),
]);
export const PlannerRunResponseSchema = PlanRunRowSchema.safeExtend({
  planning_complete: z.boolean(), correlation_id: RequestIdSchema,
  batches: z.strictObject({
    parsed_batch_id: RequestIdSchema.optional(), selection_batch_id: RequestIdSchema.optional(),
    partition_batch_id: RequestIdSchema.optional(),
  }),
  files: z.strictObject({
    discovered_articles: PlannerLedgerWriteResultSchema.optional(), selected_articles: PlannerLedgerWriteResultSchema.optional(),
    rejected_articles: PlannerLedgerWriteResultSchema.optional(),
    feed_health_state: PlannerLedgerWriteResultSchema.optional(), plan_runs: PlannerLedgerWriteResultSchema.optional(),
  }),
  selected_url_keys: z.array(Sha256Schema),
  assignments: z.array(z.strictObject({
    url_key: Sha256Schema, editorial_rank: CountSchema.positive(), worker_assignment: CountSchema.nullable(),
  })),
  failure: PlannerFailureSchema.nullable().default(null),
}).superRefine((value, ctx) => {
  if (value.planning_complete !== (value.status === "completed") || value.selected_url_keys.length !== value.selected_count
    || value.assignments.length !== value.selected_count || new Set(value.selected_url_keys).size !== value.selected_count) {
    ctx.addIssue({ code: "custom", message: "Run status, chosen identities and assignments must reconcile" });
  }
  if ((value.status === "completed") !== (value.failure_code === null)) {
    ctx.addIssue({ code: "custom", message: "Only an unsuccessful run has a failure cause" });
  }
  if (value.failure !== null && (value.failure.execution.run_id !== value.run_id
    || value.failure.execution.attempt !== value.attempt
    || value.failure.execution.correlation_id !== value.correlation_id)) {
    ctx.addIssue({ code: "custom", message: "Execution failure must belong to the saved response" });
  }
  if (value.assignments.some((article, index) => article.url_key !== value.selected_url_keys[index]
    || article.editorial_rank !== index + 1 || (article.worker_assignment === null
      ? value.planning_complete && value.dispatch_count !== 0 : article.worker_assignment >= value.dispatch_count))) {
    ctx.addIssue({ code: "custom", message: "Selected order, ranks and worker assignments must match the run" });
  }
}).meta({
  version: PLANNER_RESPONSE_VERSION,
  changelog: [
    { version: PLANNER_RESPONSE_VERSION, change: "Retain optional execution failures; read earlier responses with null evidence." },
  ],
});
export const PlannerSavedResponseSchema = z.union([PlannerRunResponseSchema, PlannerErrorResponseSchema]).meta({
  version: PLANNER_RESPONSE_VERSION,
  changelog: [
    { version: PLANNER_RESPONSE_VERSION, change: "Use the existing response file for both saved outcomes and safe execution errors." },
  ],
});
export type PlannerRunResponse = z.infer<typeof PlannerRunResponseSchema>;
