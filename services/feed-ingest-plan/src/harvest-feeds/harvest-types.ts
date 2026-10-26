/** Which transient observations accompany the existing validated harvest payloads? */
import { z } from "zod";
import {
  CandidateRejectionRecordSchema, FeedIngestCandidateSchema,
  SourceSnapshotSchema, TimestampSchema,
  FetchFailureSchema, PlannerHarvestObservationSchema,
} from "@idhazh/common-contracts";
import type { FeedIngestConfig, FeedOutcomePayload, ItemHealthFailureCode, WriterIdentity } from "@idhazh/common-contracts";
import type { HarvestInputs } from "./load-harvest-inputs";
import type { ProgressDetails, ProgressEventType } from "../logging/progress-logger";
import type { SourceHistoryEvidence } from "../read-ledger-history/read-feed-history";
import type { IngestObservations } from "../ingest-observations";
import type { ArticleParserPool } from "./article-parser-pool";

export { FetchFailureSchema } from "@idhazh/common-contracts";
export type FetchFailure = z.infer<typeof FetchFailureSchema>;
export const HarvestObservationSchema = PlannerHarvestObservationSchema;
export type HarvestObservation = z.infer<typeof HarvestObservationSchema>;
export const HarvestArticleResultSchema = z.strictObject({
  candidate: FeedIngestCandidateSchema.nullable(),
  rejection: CandidateRejectionRecordSchema.nullable(),
  observation: HarvestObservationSchema,
}).superRefine((value, ctx) => {
  if ((value.candidate === null) === (value.rejection === null)) {
    ctx.addIssue({ code: "custom", message: "one candidate or rejection is required" });
  }
  if ((value.candidate ?? value.rejection)?.candidate_id !== value.observation.candidate_id) {
    ctx.addIssue({ code: "custom", message: "observation must name its candidate" });
  }
});
export type HarvestArticleResult = z.infer<typeof HarvestArticleResultSchema>;

export type FeedEntry = {
  entry_ordinal: number;
  title: string | null;
  link: string | null;
  categories: string[];
  author: string | null;
  published_at: string | null;
  media_types?: string[];
};
export type OfferedArticle = {
  source: z.infer<typeof SourceSnapshotSchema>;
  entry: FeedEntry;
};
export type HarvestContext = {
  writer: WriterIdentity;
  correlation_id: string;
  max_future_hours: number;
  feed_history?: ReadonlyMap<string, SourceHistoryEvidence>;
  exclusions?: {
    published_window_days: number;
    published_on: ReadonlyMap<string, string>;
    settled_failure_codes: ReadonlyMap<string, ItemHealthFailureCode>;
  };
  overrides?: { freshness_hours?: number };
  clock?: () => Date;
  observation_clock?: () => Date;
  observations?: IngestObservations;
  parser_pool?: ArticleParserPool;
  parser_options?: Parameters<ArticleParserPool["parse"]>[4];
  on_feed?: (outcome: FeedOutcomePayload, entries: readonly FeedEntry[], checked_at: string) => void;
  on_article?: (result: HarvestArticleResult) => void;
  log?: (record: z.infer<typeof CandidateRejectionRecordSchema>) => void;
  progress?: (event: ProgressEventType, details?: ProgressDetails) => void;
};
export type HarvestResult = {
  inputs: HarvestInputs;
  config: FeedIngestConfig;
  articles: HarvestArticleResult[];
  first_sight_candidates: { url_key: string }[];
  feed_outcomes: FeedOutcomePayload[];
  salience: { feed_id: string; available: boolean; unavailable_reason: string | null }[];
  candidates: z.infer<typeof FeedIngestCandidateSchema>[];
  rejections: z.infer<typeof CandidateRejectionRecordSchema>[];
};

export function utcTimestamp(clock: () => Date = () => new Date()): string {
  return TimestampSchema.parse(clock().toISOString().replace(/\.\d{3}Z$/, "Z"));
}
