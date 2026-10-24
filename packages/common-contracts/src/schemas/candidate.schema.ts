/** Which validated content belongs to one offered feed entry? */
import { z } from "zod";
import {
  ArticleLabelsSchema, PolicyIdentitySchema, PreviousSourceSnapshotSchema, SourceSnapshotSchema,
} from "./source.schema";
import { CountSchema, DateStampSchema, NonEmptySchema, RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, UrlSchema, checkUrlIdentity, deriveCandidateId, reject } from "./primitives";
import { CONTRACT_VERSION, PLANNING_OBSERVATIONS_VERSION, PUBLISHER_IDENTITY_VERSION } from "../version";
import { PlanningObservationsSchema } from "./planning-observations.schema";

export const FeedIngestCandidateSchema = z.strictObject({
  version: z.literal(PUBLISHER_IDENTITY_VERSION).default(PUBLISHER_IDENTITY_VERSION), date: DateStampSchema, correlation_id: NonEmptySchema,
  run_id: RunIdSchema, candidate_id: Sha256Schema, entry_ordinal: CountSchema,
  source_id: SlugSchema, vertical: SlugSchema, source: SourceSnapshotSchema,
  canonical_url: UrlSchema, url_key: Sha256Schema, title: NonEmptySchema,
  categories: z.array(z.string()), article_text: z.string(), word_count: CountSchema,
  author: z.string().nullable(), published_at: TimestampSchema.nullable(),
  fetched_at: TimestampSchema, labels: ArticleLabelsSchema, policy: PolicyIdentitySchema,
  planning_observations: PlanningObservationsSchema.nullable().default(null),
}).superRefine((value, ctx) => {
  checkUrlIdentity(value, ctx);
  if (value.source_id !== value.source.source_id || value.vertical !== value.source.vertical) reject(ctx, "source identity must match source snapshot");
  if (value.candidate_id !== deriveCandidateId(value.run_id, value.source.source_id, value.entry_ordinal)) reject(ctx, "candidate_id must match run/source/entry ordinal");
  if (value.date !== value.fetched_at.slice(0, 10)) reject(ctx, "date must match the UTC fetch day");
});
export const CandidateSchema = FeedIngestCandidateSchema;
export type FeedIngestCandidate = z.infer<typeof FeedIngestCandidateSchema>;

const {
  planning_observations: _observations, source: _source, ...previousCandidateFields
} = FeedIngestCandidateSchema.shape;
export const PreviousContractFeedIngestCandidateSchema = z.strictObject({
  ...previousCandidateFields, source: PreviousSourceSnapshotSchema, version: z.literal(CONTRACT_VERSION),
});
export const PreviousObservedFeedIngestCandidateSchema = z.strictObject({
  ...FeedIngestCandidateSchema.shape, source: PreviousSourceSnapshotSchema,
  version: z.literal(PLANNING_OBSERVATIONS_VERSION),
});
export const PreviousFeedIngestCandidateSchema = z.union([
  PreviousContractFeedIngestCandidateSchema, PreviousObservedFeedIngestCandidateSchema,
]);
export function readFeedIngestCandidate(raw: unknown): FeedIngestCandidate {
  if (typeof raw === "object" && raw !== null && "version" in raw && raw.version === CONTRACT_VERSION) {
    return FeedIngestCandidateSchema.parse({ ...PreviousFeedIngestCandidateSchema.parse(raw), version: PUBLISHER_IDENTITY_VERSION });
  }
  if (typeof raw === "object" && raw !== null && "version" in raw && raw.version === PLANNING_OBSERVATIONS_VERSION) {
    return FeedIngestCandidateSchema.parse({ ...PreviousFeedIngestCandidateSchema.parse(raw), version: PUBLISHER_IDENTITY_VERSION });
  }
  return FeedIngestCandidateSchema.parse(raw);
}
