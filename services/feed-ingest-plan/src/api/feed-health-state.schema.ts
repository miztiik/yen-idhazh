/** Which explicit operation summarizes or records one server-owned result's feed work? */
import { z } from "zod";
import { StageReferenceRequestSchema } from "@idhazh/common-contracts";
export {
  FeedAvailabilityViewSchema, FeedAvailabilitySnapshotSchema, FeedHealthStateUpdateResponseSchema,
} from "@idhazh/common-contracts";

export const FeedHealthStateUpdateRequestSchema = StageReferenceRequestSchema.extend({
  action: z.enum(["summarize", "record"]).default("record"),
});
