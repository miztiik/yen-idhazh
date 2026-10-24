/** Which selected article content is assigned to one worker? */
import { isDeepStrictEqual } from "node:util";
import { z } from "zod";
import { FeedIngestCandidateSchema, PreviousFeedIngestCandidateSchema, readFeedIngestCandidate } from "./candidate.schema";
import { EditorialSelectionContract, EditorialSelectionRowSchema, PreviousEditorialSelectionSchema, PreviousReliableEditorialSelectionSchema } from "./editorial-selection.schema";
import { PartitionAssignmentSchema } from "./partition.schema";
import { reject } from "./primitives";
import { CONTRACT_VERSION, FEED_INGEST_AUDIT_VERSION, PLANNING_OBSERVATIONS_VERSION, PUBLISHER_IDENTITY_VERSION, SOURCE_RELIABILITY_VERSION } from "../version";

export const FeedIngestDispatchSchema = z.strictObject({
  version: z.literal(PUBLISHER_IDENTITY_VERSION).default(PUBLISHER_IDENTITY_VERSION), content: FeedIngestCandidateSchema,
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
  content: PreviousFeedIngestCandidateSchema, selection: PreviousEditorialSelectionSchema,
});
export const PreviousObservedFeedIngestDispatchSchema = z.strictObject({
  ...FeedIngestDispatchSchema.shape, version: z.literal(PLANNING_OBSERVATIONS_VERSION),
  content: PreviousFeedIngestCandidateSchema, selection: PreviousEditorialSelectionSchema,
});
export const PreviousReliableFeedIngestDispatchSchema = z.strictObject({
  ...FeedIngestDispatchSchema.shape, version: z.literal(SOURCE_RELIABILITY_VERSION),
  content: PreviousFeedIngestCandidateSchema, selection: PreviousReliableEditorialSelectionSchema,
});
export function readFeedIngestDispatch(raw: unknown): FeedIngestDispatch {
  if (typeof raw === "object" && raw !== null && "version" in raw
    && (raw.version === CONTRACT_VERSION || raw.version === FEED_INGEST_AUDIT_VERSION
      || raw.version === PLANNING_OBSERVATIONS_VERSION || raw.version === SOURCE_RELIABILITY_VERSION)) {
    const previous = raw.version === PLANNING_OBSERVATIONS_VERSION
      ? PreviousObservedFeedIngestDispatchSchema.parse(raw)
      : raw.version === SOURCE_RELIABILITY_VERSION
        ? PreviousReliableFeedIngestDispatchSchema.parse(raw)
        : PreviousFeedIngestDispatchSchema.parse(raw);
    const selection = raw.version === SOURCE_RELIABILITY_VERSION
      ? EditorialSelectionContract.legacyVersions[SOURCE_RELIABILITY_VERSION].migrate(previous.selection)
      : EditorialSelectionContract.legacyVersions[CONTRACT_VERSION].migrate(previous.selection);
    return FeedIngestDispatchSchema.parse({
      ...previous, version: PUBLISHER_IDENTITY_VERSION, content: readFeedIngestCandidate(previous.content), selection,
    });
  }
  return FeedIngestDispatchSchema.parse(raw);
}
