/** Validate the public run result without accepting private work batches or article bodies. */
import { z } from "zod";
import { CountSchema, PlanRunRowSchema, RequestIdSchema, Sha256Schema } from "@idhazh/common-contracts";
import { StageWriteResultSchema } from "./stage-response.schema";

export const PlanResponseSchema = PlanRunRowSchema.safeExtend({
  planning_complete: z.boolean(), correlation_id: RequestIdSchema,
  batches: z.strictObject({
    parsed_batch_id: RequestIdSchema.optional(), selection_batch_id: RequestIdSchema.optional(), partition_batch_id: RequestIdSchema.optional(),
  }),
  files: z.strictObject({
    discovered_articles: StageWriteResultSchema.optional(), selected_articles: StageWriteResultSchema.optional(),
    rejected_articles: StageWriteResultSchema.optional(),
    feed_health_state: StageWriteResultSchema.optional(), plan_runs: StageWriteResultSchema.optional(),
  }),
  selected_url_keys: z.array(Sha256Schema),
  assignments: z.array(z.strictObject({ url_key: Sha256Schema, editorial_rank: CountSchema.positive(), worker_assignment: CountSchema.nullable() })),
}).superRefine((value, ctx) => {
  if (value.planning_complete !== (value.status === "completed") || value.selected_url_keys.length !== value.selected_count
    || value.assignments.length !== value.selected_count || new Set(value.selected_url_keys).size !== value.selected_count) {
    ctx.addIssue({ code: "custom", message: "Run status, chosen identities and assignments must reconcile" });
  }
  if ((value.status === "completed") !== (value.failure_code === null)) ctx.addIssue({ code: "custom", message: "Only an unsuccessful run has a failure cause" });
  if (value.assignments.some((article, index) => article.url_key !== value.selected_url_keys[index]
    || article.editorial_rank !== index + 1 || (article.worker_assignment === null
      ? value.planning_complete && value.dispatch_count !== 0 : article.worker_assignment >= value.dispatch_count))) {
    ctx.addIssue({ code: "custom", message: "Selected order, ranks and worker assignments must match the run" });
  }
});
