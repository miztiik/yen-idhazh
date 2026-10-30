/** Which explicit operation summarizes or records one server-owned batch's feed work? */
import { z } from "zod";
import {
  RequestIdSchema, PlannerRequestReportSchema, FeedHealthStateRowSchema, PositiveCountSchema,
  FeedAvailabilityRecordSchema, CountSchema, RecordedInstantSchema, SlugSchema,
} from "@idhazh/common-contracts";
import { StageWriteResultSchema } from "./stage-response.schema";

export const FeedHealthStateUpdateRequestSchema = z.strictObject({
  batch_id: RequestIdSchema, action: z.enum(["summarize", "record"]).default("record"),
});
export const FeedAvailabilityViewSchema = z.strictObject({
  feed_id: FeedAvailabilityRecordSchema.shape.feed_id,
  endpoint_key: FeedAvailabilityRecordSchema.shape.endpoint_key,
  consecutive_failed_checks: FeedAvailabilityRecordSchema.shape.consecutive_failed_checks,
  rest_until: FeedAvailabilityRecordSchema.shape.rest_until,
  retired_at: FeedAvailabilityRecordSchema.shape.retired_at,
  status: z.enum(["eligible", "resting", "retired", "unknown"]),
  failed_recovery_checks: CountSchema, first_confirmed_failure_at: RecordedInstantSchema.nullable(),
});
export const FeedAvailabilitySnapshotSchema = z.strictObject({
  revision: z.string().min(1), feeds: z.array(FeedAvailabilityViewSchema),
  eligible_feed_ids: z.array(SlugSchema),
});
export const FeedHealthStateUpdateResponseSchema = z.strictObject({
  batch_id: RequestIdSchema, status: z.enum(["summarized", "recorded"]),
  rows: z.array(FeedHealthStateRowSchema), request_report: PlannerRequestReportSchema,
  reliability: z.strictObject({ window_days: PositiveCountSchema }),
  availability: FeedAvailabilitySnapshotSchema.optional(),
  files: StageWriteResultSchema.optional(),
}).superRefine((value, ctx) => {
  if ((value.status === "recorded") !== (value.files !== undefined)) ctx.addIssue({ code: "custom", message: "Recorded health returns its actual file receipt; summary does not write" });
});
