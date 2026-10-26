/** Declare metadata-only API responses for selection, partitioning and persistence. */
import { z } from "zod";
import {
  CountSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema, RequestIdSchema, RunIdSchema, Sha256Schema,
  SelectedArticleRowSchema, PlannerRejectionCountSchema, PlannerRequestReportSchema,
} from "@idhazh/common-contracts";
import { RelativePathSchema } from "../config/service-settings";

export const StageWriteResultSchema = z.discriminatedUnion("status", [
  z.strictObject({ status: z.literal("written"), files: z.array(z.strictObject({
    path: RelativePathSchema, file_id: z.uuid(), covers: NonEmptySchema,
    content_sha256: Sha256Schema, row_count: CountSchema,
  })).min(1) }),
  z.strictObject({ status: z.literal("empty"), files: z.tuple([]) }),
]);
export const StageErrorResponseSchema = z.strictObject({
  code: NonEmptySchema, issues: z.array(z.strictObject({ field: z.string().nullable(), message: NonEmptySchema })).min(1),
});
export const SelectionResponseSchema = z.strictObject({
  batch_id: RequestIdSchema, parsed_batch_id: RequestIdSchema, run_id: RunIdSchema,
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
});
