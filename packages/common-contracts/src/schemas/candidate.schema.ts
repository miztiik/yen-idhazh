/** Which sanitized article and configured feed facts belong to one transient offered entry? */
import { z } from "zod";
import { SourceSnapshotSchema } from "./source.schema";
import {
  CountSchema, DateStampSchema, NonEmptySchema, RunIdSchema, Sha256Schema, SlugSchema,
  TimestampSchema, UrlSchema, checkUrlIdentity, deriveCandidateId, reject,
} from "./primitives";
import { FEED_INGEST_CANDIDATE_VERSION } from "../version";

export const FeedIngestCandidateSchema = z.strictObject({
  version: z.literal(FEED_INGEST_CANDIDATE_VERSION).default(FEED_INGEST_CANDIDATE_VERSION),
  date: DateStampSchema, correlation_id: NonEmptySchema, run_id: RunIdSchema,
  candidate_id: Sha256Schema, entry_ordinal: CountSchema,
  source_id: SlugSchema, source: SourceSnapshotSchema,
  canonical_url: UrlSchema, url_key: Sha256Schema, title: NonEmptySchema, categories: z.array(z.string()),
  article_text: z.string(), word_count: CountSchema, author: z.string().nullable(),
  published_at: TimestampSchema.nullable(), fetched_at: TimestampSchema,
}).superRefine((value, ctx) => {
  checkUrlIdentity(value, ctx);
  if (value.source_id !== value.source.source_id) reject(ctx, "candidate feed must match configured feed facts");
  if (value.candidate_id !== deriveCandidateId(value.run_id, value.source_id, value.entry_ordinal)) reject(ctx, "candidate identity must match run, feed and offered ordinal");
  if (value.date !== value.fetched_at.slice(0, 10)) reject(ctx, "candidate date must match its actual UTC fetch day");
}).meta({
  version: FEED_INGEST_CANDIDATE_VERSION,
  changelog: [
    { version: FEED_INGEST_CANDIDATE_VERSION, change: "Remove source classification fields from planner candidates." },
    { version: "2026-10-25", change: "Bind candidates to their actual fetch and configured source facts." },
  ],
});
export const CandidateSchema = FeedIngestCandidateSchema;
export type FeedIngestCandidate = z.infer<typeof FeedIngestCandidateSchema>;
export const readFeedIngestCandidate = (raw: unknown) => FeedIngestCandidateSchema.parse(raw);
