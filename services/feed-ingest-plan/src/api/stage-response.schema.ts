/** Which validated success and failure payloads do the planning stage routes return? */
import { z } from "zod";
import {
  CandidateRejectionRecordSchema, EditorialSelectionRowSchema, FeedIngestDispatchSchema,
  CountSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema,
  RequestIdSchema, RunIdSchema, Sha256Schema,
} from "@idhazh/common-contracts";
import { RelativePathSchema } from "../config/service-settings";

const FileSchema = z.strictObject({
  path: RelativePathSchema, file_id: z.uuid(), unit_id: z.uuid(), covers: NonEmptySchema,
  content_sha256: Sha256Schema, row_count: CountSchema,
});
export const StageWriteResultSchema = z.discriminatedUnion("status", [
  z.strictObject({ status: z.literal("written"), files: z.array(FileSchema).min(1) }),
  z.strictObject({ status: z.literal("empty"), files: z.tuple([]) }),
]);
export const StageErrorResponseSchema = z.strictObject({
  code: NonEmptySchema,
  issues: z.array(z.strictObject({ field: z.string().nullable(), message: NonEmptySchema })).min(1),
});
export const SelectionResponseSchema = z.strictObject({
  batch_id: RequestIdSchema, parsed_batch_id: RequestIdSchema,
  run_id: RunIdSchema, correlation_id: RequestIdSchema,
  selections: z.array(EditorialSelectionRowSchema),
  exclusions: z.array(CandidateRejectionRecordSchema),
  files: z.strictObject({
    screening_rejections: StageWriteResultSchema,
    selections: StageWriteResultSchema, rejections: StageWriteResultSchema,
  }),
});
export const PartitionResponseSchema = z.strictObject({
  batch_id: RequestIdSchema, selection_batch_id: RequestIdSchema,
  run_id: RunIdSchema, correlation_id: RequestIdSchema,
  strategy: z.enum(["bin-pack", "round-robin", "none"]), dispatch_count: PositiveCountSchema,
  work: z.array(NonNegativeSchema), dispatches: z.array(FeedIngestDispatchSchema),
});
export const PersistenceResponseSchema = z.strictObject({
  batch_id: RequestIdSchema, files: StageWriteResultSchema,
});
