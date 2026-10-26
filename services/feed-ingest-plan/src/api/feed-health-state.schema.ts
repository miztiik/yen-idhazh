/** Which explicit operation summarizes or records one server-owned batch's feed work? */
import { z } from "zod";
import { RequestIdSchema, PlannerRequestReportSchema, FeedHealthStateRowSchema } from "@idhazh/common-contracts";

export const FeedHealthStateUpdateRequestSchema = z.strictObject({
  batch_id: RequestIdSchema, action: z.enum(["summarize", "record"]).default("record"),
});
export const FeedHealthStateUpdateResponseSchema = z.strictObject({
  batch_id: RequestIdSchema, status: z.enum(["summarized", "recorded"]),
  rows: z.array(FeedHealthStateRowSchema), request_report: PlannerRequestReportSchema,
});
