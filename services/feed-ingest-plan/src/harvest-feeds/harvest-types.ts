/** Which transient observations accompany the existing validated harvest payloads? */
import { z } from "zod";
import {
  CandidateRejectionRecordSchema, FeedIngestCandidateSchema,
  Sha256Schema, SourceSnapshotSchema, TimestampSchema,
  FetchFailureSchema, HarvestDiagnosticsSchema,
} from "@idhazh/common-contracts";
import type { FeedIngestConfig, FeedOutcomePayload, ItemHealthFailureCode, PolicyIdentity, WriterIdentity } from "@idhazh/common-contracts";
import type { LedgerRegistration, LedgerSettings, PersistLedgerResult } from "@idhazh/ledger-file-writer";
import type { HarvestInputs } from "./load-harvest-inputs";
import type { ProgressDetails, ProgressEventType } from "../logging/progress-logger";
import type { SourceHistoryEvidence } from "../read-ledger-history/read-feed-history";

export { FetchFailureSchema } from "@idhazh/common-contracts";
export type FetchFailure = z.infer<typeof FetchFailureSchema>;
export const HarvestObservationSchema = z.strictObject({
  candidate_id: Sha256Schema,
  http_status: z.int().min(100).max(599).nullable(),
  robots: z.enum(["allowed", "denied", "unknown"]).nullable(),
  fetch_failure: FetchFailureSchema.nullable(),
  paywall: z.boolean().nullable(),
  paywall_evidence: z.enum(["json-ld", "configured-marker", "none", "not-observed"]),
  extraction: z.enum(["success", "empty", "failed", "not-attempted"]),
  observed_at: TimestampSchema,
  diagnostics: HarvestDiagnosticsSchema.nullable().default(null),
  preflight_freshness: z.strictObject({
    timing_at: TimestampSchema, timing_source: z.literal("published_at"),
    age_hours: z.number().finite().positive(), recency_bonus: z.number().finite().nonnegative(),
  }).optional(),
});
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
};
export type OfferedArticle = {
  source: z.infer<typeof SourceSnapshotSchema>;
  entry: FeedEntry;
  policy: PolicyIdentity;
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
    blocked_url_markers: readonly string[];
  };
  overrides?: { freshness_hours?: number };
  clock?: () => Date;
  log?: (record: z.infer<typeof CandidateRejectionRecordSchema>) => void;
  progress?: (event: ProgressEventType, details?: ProgressDetails) => void;
};
export type RejectionDestination = {
  outputRoot: string;
  registryEntry: LedgerRegistration;
  ledgerSettings: LedgerSettings;
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
  rejection_files: PersistLedgerResult;
};

export function utcTimestamp(clock: () => Date = () => new Date()): string {
  return TimestampSchema.parse(clock().toISOString().replace(/\.\d{3}Z$/, "Z"));
}
