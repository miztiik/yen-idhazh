/** Which selected article content is assigned to one worker? */
import { isDeepStrictEqual } from "node:util";
import { z } from "zod";
import { FeedIngestCandidateSchema } from "./candidate.schema";
import { EditorialSelectionRowSchema } from "./editorial-selection.schema";
import { PartitionAssignmentSchema } from "./partition.schema";
import { VersionSchema, reject } from "./primitives";

export const FeedIngestDispatchSchema = z.strictObject({
  version: VersionSchema, content: FeedIngestCandidateSchema,
  selection: EditorialSelectionRowSchema, partition: PartitionAssignmentSchema,
}).superRefine((value, ctx) => {
  for (const field of ["date", "correlation_id", "candidate_id", "source_id", "vertical", "source", "canonical_url", "url_key", "labels", "policy"] as const) {
    if (!isDeepStrictEqual(value.content[field], value.selection[field])) reject(ctx, `dispatch content and selection disagree on ${field}`, ["selection", field]);
  }
});
export type FeedIngestDispatch = z.infer<typeof FeedIngestDispatchSchema>;
