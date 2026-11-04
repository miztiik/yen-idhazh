/** Which sanitized article and configured feed facts belong to one transient offered entry? */
import { z } from "zod";
import { SourceSnapshotSchema } from "./source.schema";
import {
  CountSchema, DateStampSchema, NonEmptySchema, RunIdSchema, Sha256Schema, SlugSchema,
  TimestampSchema, UrlSchema, checkUrlIdentity, deriveCandidateId, reject,
} from "./primitives";
import { FEED_INGEST_CANDIDATE_VERSION } from "../version";
import { TraceIdSchema } from "./operation-metadata.schema";

export const FeedIngestCandidateSchema = z.strictObject({
  version: z.literal(FEED_INGEST_CANDIDATE_VERSION).default(FEED_INGEST_CANDIDATE_VERSION),
  date: DateStampSchema, traceId: TraceIdSchema, run_id: RunIdSchema,
  candidate_id: Sha256Schema, entry_ordinal: CountSchema,
  feed_id: SlugSchema, source: SourceSnapshotSchema,
  canonical_url: UrlSchema, url_key: Sha256Schema, title: NonEmptySchema, categories: z.array(z.string()),
  article_text: z.string(), word_count: CountSchema, author: z.string().nullable(),
  published_at: TimestampSchema.nullable(), fetched_at: TimestampSchema,
}).superRefine((value, ctx) => {
  checkUrlIdentity(value, ctx);
  if (value.canonical_url.includes("#")) reject(ctx, "candidate article address must not contain a fragment");
  if (value.feed_id !== value.source.feed_id) reject(ctx, "candidate feed must match configured feed facts");
  if (value.candidate_id !== deriveCandidateId(value.run_id, value.feed_id, value.entry_ordinal)) reject(ctx, "candidate identity must match run, feed and offered ordinal");
  if (value.date !== value.fetched_at.slice(0, 10)) reject(ctx, "candidate date must match its actual UTC fetch day");
}).meta({
  version: FEED_INGEST_CANDIDATE_VERSION,
  changelog: [
    { version: FEED_INGEST_CANDIDATE_VERSION, change: "Preserve resource queries in normalized article addresses and their hashes." },
    { version: "2026-11-03", change: "Associate candidates with their producing execution." },
    { version: "2026-11-02", change: "Retain configured source weights without planner tier fields." },
    { version: "2026-10-31", change: "Identify candidates with the shared query-free article cleanup policy." },
    { version: "2026-10-25", change: "Earlier changes are in git." },
  ],
});
export const CandidateSchema = FeedIngestCandidateSchema;
export type FeedIngestCandidate = z.infer<typeof FeedIngestCandidateSchema>;
export const readFeedIngestCandidate = (raw: unknown) => FeedIngestCandidateSchema.parse(raw);
