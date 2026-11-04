/** Which body-free payload starts or completes a run-owned collection? */
import { z } from "zod";
import {
  NonEmptySchema, PlanApiTimingSchema, PlannerStageContextSchema, PositiveCountSchema, TraceIdSchema, OperationMetadataSchema,
  RunIdSchema, SlugSchema, PlannerFailureSchema,
} from "@idhazh/common-contracts";
import { PlanRequestSchema } from "./plan-request";
import { StageWriteResultSchema } from "./stage-response.schema";

export const BeginCollectionSchema = z.strictObject({
  request: PlanRequestSchema,
});
export const CollectionReferenceSchema = z.strictObject({ traceId: TraceIdSchema });
export const CollectionExistsResponseSchema = z.strictObject({
  traceId: TraceIdSchema, exists: z.boolean(),
});
export const CollectionResponseSchema = OperationMetadataSchema.safeExtend({
  context: PlannerStageContextSchema,
  feeds: z.array(SlugSchema),
});
export const CompletedCollectionSchema = OperationMetadataSchema.safeExtend({
  discovered_articles: StageWriteResultSchema,
  rejected_articles: StageWriteResultSchema,
});
export const CancelledCollectionSchema = OperationMetadataSchema.safeExtend({
  status: z.literal("cancelled"),
  rejected_articles: StageWriteResultSchema, has_work: z.boolean(),
});
export const FinalizeCollectionRequestSchema = z.strictObject({
  traceId: TraceIdSchema, failure_code: NonEmptySchema.nullable(),
  failure: PlannerFailureSchema.nullable().default(null),
  collection_timing: z.strictObject({
    duration_ms: z.int().nonnegative(), status: z.enum(["completed", "failed"]),
  }),
});
export const FinalizedCollectionSchema = z.strictObject({
  traceId: TraceIdSchema, status: z.enum(["completed", "partial", "failed"]),
  failure_code: NonEmptySchema.nullable(), api_timings: z.array(PlanApiTimingSchema),
  failure: PlannerFailureSchema.nullable().default(null),
}).superRefine((value, ctx) => {
  if ((value.status === "completed") !== (value.failure_code === null)) {
    ctx.addIssue({ code: "custom", message: "Only a completed collection has no failure cause" });
  }
});
export const ReleaseCollectionRequestSchema = z.strictObject({
  run_id: RunIdSchema, attempt: PositiveCountSchema,
});
export const ReleasedCollectionSchema = z.strictObject({
  run_id: RunIdSchema, attempt: PositiveCountSchema, released: z.boolean(),
});
