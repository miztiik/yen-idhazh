/** Declare metadata-only API responses for selection, partitioning and persistence. */
import { z } from "zod";
import {
  CountSchema, NonNegativeSchema, PositiveCountSchema, RequestIdSchema, RunIdSchema,
  SelectedArticleRowSchema, PlannerRejectionCountSchema, PlannerRequestReportSchema, TimestampSchema,
  PlannerLedgerWriteResultSchema,
} from "@idhazh/common-contracts";
import { RelativePathSchema } from "../config/service-settings";

export { PlannerLedgerWriteResultSchema as StageWriteResultSchema, PlannerErrorResponseSchema as StageErrorResponseSchema } from "@idhazh/common-contracts";
const StageWriteResultSchema = PlannerLedgerWriteResultSchema;
export const SelectionResponseSchema = z.strictObject({
  batch_id: RequestIdSchema, parsed_batch_id: RequestIdSchema, run_id: RunIdSchema,
  selection_started_at_utc: TimestampSchema, evaluated_at: TimestampSchema,
  articles: z.array(SelectedArticleRowSchema), exclusions: z.array(PlannerRejectionCountSchema),
  request_report: PlannerRequestReportSchema,
});
export const PartitionResponseSchema = z.strictObject({
  batch_id: RequestIdSchema, selection_batch_id: RequestIdSchema, run_id: RunIdSchema,
  strategy: z.enum(["bin-pack", "round-robin", "none"]), dispatch_count: PositiveCountSchema,
  work: z.array(NonNegativeSchema), articles: z.array(SelectedArticleRowSchema),
});
export const PersistenceResponseSchema = z.strictObject({
  batch_id: RequestIdSchema, files: StageWriteResultSchema, artifact: RelativePathSchema, selected_count: CountSchema,
  rejected_files: StageWriteResultSchema,
  run_files: StageWriteResultSchema.optional(), run_status: z.enum(["completed", "partial", "failed"]).optional(),
});
