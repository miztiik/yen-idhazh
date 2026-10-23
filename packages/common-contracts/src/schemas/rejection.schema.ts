/** Why did a feed or candidate receive a terminal rejection? */
import { z } from "zod";
import { CountSchema, DateStampSchema, FiniteSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema, PositiveSchema, RejectionStageSchema, Sha256Schema, SlugSchema, TimestampSchema, UrlSchema, checkUrlIdentity, reject } from "./primitives";
import { CONTRACT_VERSION, EXTRACTION_QUALITY_VERSION, FEED_INGEST_AUDIT_VERSION, HARVEST_DIAGNOSTICS_VERSION, PLANNER_EXCLUSIONS_VERSION } from "../version";
import { HarvestDiagnosticsSchema, PreviousHarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";
import { ItemHealthFailureCodeSchema } from "./item-health-failure.schema";

export const DropReasonSchema = z.enum([
  "SOURCE_INACTIVE", "FETCH_FAILED", "FETCH_FAILED_HTTP", "FETCH_TIMEOUT",
  "EXTRACT_FAILED", "EXTRACT_EMPTY",
  "ALREADY_PUBLISHED", "SETTLED_FAILURE", "BLOCKED_URL_MARKER",
  "PAYWALL_OR_BLOCKED", "FEED_PARSE_FAILED", "FEED_EMPTY", "MISSING_REQUIRED_FIELDS",
  "CATEGORY_EXCLUDED", "STUB_CONTENT", "STALE_MAX_AGE_EXCEEDED", "STALE_HALF_LIFE_DECAY",
  "DUPLICATE_CANONICAL_URL", "EVENT_CLUSTER_SIMILARITY", "SOURCE_QUOTA_EXCEEDED",
  "DESK_QUOTA_EXCEEDED", "KIND_QUOTA_EXCEEDED", "MMR_PORTFOLIO_CUTOFF",
  "REPLACED_BY_CARRIER", "PUBLICATION_BUDGET_EXCEEDED", "ROLLING_HISTORY_REPEAT",
]);
export type DropReason = z.infer<typeof DropReasonSchema>;
export type RejectionStage = z.infer<typeof RejectionStageSchema>;
export const RejectionDetailsSchema = z.strictObject({
  http_status: z.int().min(100).max(599).nullable().default(null),
  timeout_ms: PositiveSchema.nullable().default(null),
  words_found: CountSchema.nullable().default(null),
  words_required: PositiveCountSchema.nullable().default(null),
  age_hours: NonNegativeSchema.nullable().default(null),
  max_age_hours: PositiveSchema.nullable().default(null),
  observed_value: FiniteSchema.nullable().default(null),
  limit: FiniteSchema.nullable().default(null),
  matched_url_key: Sha256Schema.nullable().default(null),
  published_on: DateStampSchema.nullable().default(null),
  failure_code: ItemHealthFailureCodeSchema.nullable().default(null),
  matched_url_marker: NonEmptySchema.nullable().default(null),
  history_window_days: PositiveCountSchema.nullable().default(null),
  diagnostics: HarvestDiagnosticsSchema.nullable().default(null),
});
export const REASON_STAGES: Readonly<Record<DropReason, readonly RejectionStage[]>> = {
  SOURCE_INACTIVE: ["harvest-feeds"], FETCH_FAILED: ["harvest-feeds"],
  FETCH_FAILED_HTTP: ["harvest-feeds"], FETCH_TIMEOUT: ["harvest-feeds"],
  EXTRACT_FAILED: ["harvest-feeds"], EXTRACT_EMPTY: ["harvest-feeds"],
  ALREADY_PUBLISHED: ["harvest-feeds"], SETTLED_FAILURE: ["harvest-feeds"],
  BLOCKED_URL_MARKER: ["harvest-feeds"],
  FEED_PARSE_FAILED: ["harvest-feeds"], FEED_EMPTY: ["harvest-feeds"],
  MISSING_REQUIRED_FIELDS: ["harvest-feeds"],
  PAYWALL_OR_BLOCKED: ["screen-article-candidates"], CATEGORY_EXCLUDED: ["screen-article-candidates"],
  STUB_CONTENT: ["screen-article-candidates"], STALE_MAX_AGE_EXCEEDED: ["harvest-feeds", "screen-article-candidates"],
  STALE_HALF_LIFE_DECAY: ["screen-article-candidates"],
  DUPLICATE_CANONICAL_URL: ["screen-article-candidates", "curate-article-portfolio"],
  ROLLING_HISTORY_REPEAT: ["screen-article-candidates", "curate-article-portfolio"],
  EVENT_CLUSTER_SIMILARITY: ["curate-article-portfolio"], SOURCE_QUOTA_EXCEEDED: ["curate-article-portfolio"],
  DESK_QUOTA_EXCEEDED: ["curate-article-portfolio"], KIND_QUOTA_EXCEEDED: ["curate-article-portfolio"],
  MMR_PORTFOLIO_CUTOFF: ["curate-article-portfolio"], REPLACED_BY_CARRIER: ["curate-article-portfolio"],
  PUBLICATION_BUDGET_EXCEEDED: ["curate-article-portfolio"],
};
export const REQUIRED_DETAILS: Readonly<Partial<Record<DropReason, readonly (keyof z.infer<typeof RejectionDetailsSchema>)[]>>> = {
  FETCH_FAILED_HTTP: ["http_status"], FETCH_TIMEOUT: ["timeout_ms"],
  EXTRACT_FAILED: ["diagnostics"], EXTRACT_EMPTY: ["diagnostics"],
  STUB_CONTENT: ["words_found", "words_required"],
  STALE_MAX_AGE_EXCEEDED: ["age_hours", "max_age_hours"],
  ALREADY_PUBLISHED: ["matched_url_key", "published_on", "history_window_days"],
  SETTLED_FAILURE: ["matched_url_key", "failure_code"],
  BLOCKED_URL_MARKER: ["matched_url_key", "matched_url_marker"],
  STALE_HALF_LIFE_DECAY: ["observed_value", "limit"],
  DUPLICATE_CANONICAL_URL: ["matched_url_key"],
  EVENT_CLUSTER_SIMILARITY: ["matched_url_key", "observed_value", "limit"],
  REPLACED_BY_CARRIER: ["matched_url_key"],
  ROLLING_HISTORY_REPEAT: ["matched_url_key", "history_window_days"],
  SOURCE_QUOTA_EXCEEDED: ["observed_value", "limit"],
  DESK_QUOTA_EXCEEDED: ["observed_value", "limit"],
  KIND_QUOTA_EXCEEDED: ["observed_value", "limit"],
  MMR_PORTFOLIO_CUTOFF: ["observed_value", "limit"],
  PUBLICATION_BUDGET_EXCEEDED: ["observed_value", "limit"],
};
export const CandidateRejectionRecordSchema = z.strictObject({
  version: z.literal(EXTRACTION_QUALITY_VERSION).default(EXTRACTION_QUALITY_VERSION), date: DateStampSchema, correlation_id: NonEmptySchema,
  source_id: SlugSchema, feed_url: UrlSchema, subject: z.enum(["feed", "article"]),
  candidate_id: Sha256Schema.nullable(), url_key: Sha256Schema.nullable(),
  canonical_url: UrlSchema.nullable(), title: z.string().nullable(), categories: z.array(z.string()),
  stage: RejectionStageSchema, drop_reason: DropReasonSchema, details: RejectionDetailsSchema,
  rejected_at: TimestampSchema,
}).superRefine((value, ctx) => {
  const article = value.subject === "article";
  if (article !== (value.candidate_id !== null)) reject(ctx, "candidate_id is required only for an article");
  for (const field of ["url_key", "canonical_url", "title"] as const) {
    if (!article && value[field] !== null) reject(ctx, `feed rejection requires null ${field}`, [field]);
    const missingTitle = field === "title" && [
      "FETCH_FAILED", "FETCH_FAILED_HTTP", "FETCH_TIMEOUT", "EXTRACT_FAILED", "EXTRACT_EMPTY",
      "ALREADY_PUBLISHED", "SETTLED_FAILURE", "BLOCKED_URL_MARKER",
    ].includes(value.drop_reason);
    if (article && value.drop_reason !== "MISSING_REQUIRED_FIELDS" && value[field] === null && !missingTitle) reject(ctx, `article rejection requires ${field}`, [field]);
  }
  if (value.canonical_url !== null && value.url_key !== null) checkUrlIdentity({ canonical_url: value.canonical_url, url_key: value.url_key }, ctx);
  if (value.date !== value.rejected_at.slice(0, 10)) reject(ctx, "date must match the UTC rejection day");
  if (!REASON_STAGES[value.drop_reason].includes(value.stage)) reject(ctx, "drop_reason is not valid for stage");
  if (article && ["SOURCE_INACTIVE", "FEED_PARSE_FAILED", "FEED_EMPTY"].includes(value.drop_reason)) reject(ctx, "drop_reason requires a feed subject");
  if (!article && value.stage !== "harvest-feeds") reject(ctx, "feed failures belong to harvest-feeds");
  if (!article && value.drop_reason === "MISSING_REQUIRED_FIELDS") reject(ctx, "missing article fields require an article subject");
  if (!article && ["EXTRACT_FAILED", "EXTRACT_EMPTY"].includes(value.drop_reason)) reject(ctx, "extraction failures require an article subject");
  for (const field of REQUIRED_DETAILS[value.drop_reason] ?? []) {
    if (value.details[field] === null) reject(ctx, `${value.drop_reason} requires details.${field}`, ["details", field]);
  }
});
export type CandidateRejectionRecord = z.infer<typeof CandidateRejectionRecordSchema>;
export type RejectionDetails = z.infer<typeof RejectionDetailsSchema>;

const { diagnostics: _diagnostics, published_on: _publishedOn, failure_code: _failureCode,
  matched_url_marker: _matchedUrlMarker, ...previousDetails } = RejectionDetailsSchema.shape;
const PreviousRejectionSchema = z.strictObject({
  ...CandidateRejectionRecordSchema.shape, version: z.literal(CONTRACT_VERSION),
  details: z.strictObject(previousDetails),
  drop_reason: DropReasonSchema.exclude(["EXTRACT_FAILED", "EXTRACT_EMPTY", "ALREADY_PUBLISHED", "SETTLED_FAILURE", "BLOCKED_URL_MARKER"]),
});
const PriorHarvestRejectionSchema = PreviousRejectionSchema.extend({ version: z.literal(FEED_INGEST_AUDIT_VERSION) });
export const PreviousPreDiagnosticsDropReasonSchema = DropReasonSchema.exclude([
  "EXTRACT_FAILED", "EXTRACT_EMPTY", "ALREADY_PUBLISHED", "SETTLED_FAILURE", "BLOCKED_URL_MARKER",
]);
export const PreviousDiagnosticDropReasonSchema = DropReasonSchema.exclude([
  "ALREADY_PUBLISHED", "SETTLED_FAILURE", "BLOCKED_URL_MARKER",
]);
const PreviousDiagnosticRejectionSchema = z.strictObject({
  ...CandidateRejectionRecordSchema.shape, version: z.literal(HARVEST_DIAGNOSTICS_VERSION),
  details: z.strictObject({ ...previousDetails, diagnostics: PreviousHarvestDiagnosticsSchema.nullable().default(null) }),
  drop_reason: PreviousDiagnosticDropReasonSchema,
});
const PreviousExclusionRejectionSchema = z.strictObject({
  ...CandidateRejectionRecordSchema.shape, version: z.literal(PLANNER_EXCLUSIONS_VERSION),
  details: RejectionDetailsSchema.extend({ diagnostics: PreviousHarvestDiagnosticsSchema.nullable().default(null) }),
});
export const CandidateRejectionContract = {
  schema: CandidateRejectionRecordSchema, schemaVersion: EXTRACTION_QUALITY_VERSION,
  legacyVersions: {
    [PLANNER_EXCLUSIONS_VERSION]: {
      schema: PreviousExclusionRejectionSchema,
      migrate: (row: object): CandidateRejectionRecord => CandidateRejectionRecordSchema.parse({
        ...PreviousExclusionRejectionSchema.parse(row), version: EXTRACTION_QUALITY_VERSION,
      }),
    },
    [CONTRACT_VERSION]: {
      schema: PreviousRejectionSchema,
      migrate: (row: object): CandidateRejectionRecord => CandidateRejectionRecordSchema.parse({
        ...PreviousRejectionSchema.parse(row), version: EXTRACTION_QUALITY_VERSION,
      }),
    },
    [FEED_INGEST_AUDIT_VERSION]: {
      schema: PriorHarvestRejectionSchema,
      migrate: (row: object): CandidateRejectionRecord => CandidateRejectionRecordSchema.parse({
        ...PriorHarvestRejectionSchema.parse(row), version: EXTRACTION_QUALITY_VERSION,
      }),
    },
    [HARVEST_DIAGNOSTICS_VERSION]: {
      schema: PreviousDiagnosticRejectionSchema,
      migrate: (row: object): CandidateRejectionRecord => CandidateRejectionRecordSchema.parse({
        ...PreviousDiagnosticRejectionSchema.parse(row), version: EXTRACTION_QUALITY_VERSION,
      }),
    },
  },
};
