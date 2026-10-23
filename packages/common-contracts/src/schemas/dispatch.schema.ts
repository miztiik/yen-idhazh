/** Which selected article content is assigned to one worker? */
import { isDeepStrictEqual } from "node:util";
import { z } from "zod";
import { FeedIngestCandidateSchema, PreviousFeedIngestCandidateSchema, readFeedIngestCandidate } from "./candidate.schema";
import { EditorialSelectionRowSchema } from "./editorial-selection.schema";
import { PartitionAssignmentSchema } from "./partition.schema";
import { reject } from "./primitives";
import { CONTRACT_VERSION, FEED_INGEST_AUDIT_VERSION, PLANNING_OBSERVATIONS_VERSION } from "../version";

export const FeedIngestDispatchSchema = z.strictObject({
  version: z.literal(PLANNING_OBSERVATIONS_VERSION).default(PLANNING_OBSERVATIONS_VERSION), content: FeedIngestCandidateSchema,
  selection: EditorialSelectionRowSchema, partition: PartitionAssignmentSchema,
}).superRefine((value, ctx) => {
  for (const field of ["candidate_id", "source_id", "vertical", "source", "canonical_url", "url_key", "labels"] as const) {
    if (!isDeepStrictEqual(value.content[field], value.selection[field])) reject(ctx, `dispatch content and selection disagree on ${field}`, ["selection", field]);
  }
});
export type FeedIngestDispatch = z.infer<typeof FeedIngestDispatchSchema>;
export const PreviousFeedIngestDispatchSchema = z.strictObject({
  ...FeedIngestDispatchSchema.shape,
  version: z.enum([CONTRACT_VERSION, FEED_INGEST_AUDIT_VERSION]),
  content: PreviousFeedIngestCandidateSchema,
});
export function readFeedIngestDispatch(raw: unknown): FeedIngestDispatch {
  if (typeof raw === "object" && raw !== null && "version" in raw
    && (raw.version === CONTRACT_VERSION || raw.version === FEED_INGEST_AUDIT_VERSION)) {
    const previous = PreviousFeedIngestDispatchSchema.parse(raw);
    return FeedIngestDispatchSchema.parse({
      ...previous, version: PLANNING_OBSERVATIONS_VERSION, content: readFeedIngestCandidate(previous.content),
    });
  }
  return FeedIngestDispatchSchema.parse(raw);
}
