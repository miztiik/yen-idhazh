/** Which explicit operation summarizes or records one server-owned batch's feed work? */
import { z } from "zod";
import { RequestIdSchema, PlannerRequestReportSchema, FeedHealthStateRowSchema, PositiveCountSchema } from "@idhazh/common-contracts";
import { StageWriteResultSchema } from "./stage-response.schema";

export const FeedHealthStateUpdateRequestSchema = z.strictObject({
  batch_id: RequestIdSchema, action: z.enum(["summarize", "record"]).default("record"),
});
export const FeedHealthStateUpdateResponseSchema = z.strictObject({
  batch_id: RequestIdSchema, status: z.enum(["summarized", "recorded"]),
  rows: z.array(FeedHealthStateRowSchema), request_report: PlannerRequestReportSchema,
  reliability: z.strictObject({ window_days: PositiveCountSchema }),
  files: StageWriteResultSchema.optional(),
}).superRefine((value, ctx) => {
  if ((value.status === "recorded") !== (value.files !== undefined)) ctx.addIssue({ code: "custom", message: "Recorded health returns its actual file receipt; summary does not write" });
});
