/** Which body-free payload starts or completes a run-owned collection? */
import { z } from "zod";
import {
  NonEmptySchema, PlanApiTimingSchema, PlannerStageContextSchema, PositiveCountSchema, RequestIdSchema,
  RunIdSchema, SlugSchema,
} from "@idhazh/common-contracts";
import { PlanRequestSchema } from "./plan-request";
import { StageWriteResultSchema } from "./stage-response.schema";

export const BeginCollectionSchema = z.strictObject({
  collection_id: RequestIdSchema, request: PlanRequestSchema,
});
export const CollectionReferenceSchema = z.strictObject({ collection_id: RequestIdSchema });
export const CollectionExistsResponseSchema = z.strictObject({
  collection_id: RequestIdSchema, exists: z.boolean(),
});
export const CollectionResponseSchema = z.strictObject({
  collection_id: RequestIdSchema, context: PlannerStageContextSchema,
  feeds: z.array(SlugSchema),
});
export const CompletedCollectionSchema = z.strictObject({
  collection_id: RequestIdSchema, batch_id: RequestIdSchema,
  discovered_articles: StageWriteResultSchema,
  rejected_articles: StageWriteResultSchema,
});
export const CancelledCollectionSchema = z.strictObject({
  collection_id: RequestIdSchema, status: z.literal("cancelled"),
  batch_id: RequestIdSchema, rejected_articles: StageWriteResultSchema, has_work: z.boolean(),
});
export const FinalizeCollectionRequestSchema = z.strictObject({
  collection_id: RequestIdSchema, failure_code: NonEmptySchema.nullable(),
  collection_timing: z.strictObject({
    duration_ms: z.int().nonnegative(), status: z.enum(["completed", "failed"]),
  }),
});
export const FinalizedCollectionSchema = z.strictObject({
  collection_id: RequestIdSchema, status: z.enum(["completed", "partial", "failed"]),
  failure_code: NonEmptySchema.nullable(), api_timings: z.array(PlanApiTimingSchema),
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
