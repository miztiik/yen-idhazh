/** Which body-free payload starts or completes a run-owned collection? */
import { z } from "zod";
import { PlannerStageContextSchema, RequestIdSchema, SlugSchema } from "@idhazh/common-contracts";
import { PlanRequestSchema } from "./plan-request";
import { StageWriteResultSchema } from "./stage-response.schema";

export const BeginCollectionSchema = z.strictObject({
  collection_id: RequestIdSchema, request: PlanRequestSchema,
});
export const CollectionReferenceSchema = z.strictObject({ collection_id: RequestIdSchema });
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
  batch_id: RequestIdSchema, rejected_articles: StageWriteResultSchema,
});
