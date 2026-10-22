/** Which selected article content is assigned to one worker? */
import { isDeepStrictEqual } from "node:util";
import { z } from "zod";
import { FeedIngestCandidateSchema } from "./candidate.schema";
import { EditorialSelectionRowSchema } from "./editorial-selection.schema";
import { PartitionAssignmentSchema } from "./partition.schema";
import { reject } from "./primitives";
import { FEED_INGEST_AUDIT_VERSION } from "../version";

export const FeedIngestDispatchSchema = z.strictObject({
  version: z.literal(FEED_INGEST_AUDIT_VERSION).default(FEED_INGEST_AUDIT_VERSION), content: FeedIngestCandidateSchema,
  selection: EditorialSelectionRowSchema, partition: PartitionAssignmentSchema,
}).superRefine((value, ctx) => {
  for (const field of ["candidate_id", "source_id", "source", "canonical_url", "url_key", "labels"] as const) {
    if (!isDeepStrictEqual(value.content[field], value.selection[field])) reject(ctx, `dispatch content and selection disagree on ${field}`, ["selection", field]);
  }
});
export type FeedIngestDispatch = z.infer<typeof FeedIngestDispatchSchema>;
