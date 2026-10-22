/** Which prior audit rows can be read without inventing evidence? */
import { z } from "zod";
import {
  ArticleAssessmentRecordSchema,
  DiversityMetricRowSchema,
  FEED_INGEST_AUDIT_VERSION,
  FeedIngestDispatchSchema,
  SourceRunRecordSchema,
} from "@idhazh/common-contracts";
import type {
  ArticleAssessmentRecord,
  DiversityMetricRow,
  FeedIngestDispatch,
  SourceRunRecord,
} from "@idhazh/common-contracts";
import type { LedgerRowContract } from "@idhazh/ledger-file-writer";
import { FiniteSchema, TimestampSchema } from "@idhazh/common-contracts";

const PREVIOUS_VERSION = "2026-10-20";
const previousVersion = z.literal(PREVIOUS_VERSION);

const { timing_at: _timingAt, timing_basis: _timingBasis, ...assessmentFields } =
  ArticleAssessmentRecordSchema.shape;
const LegacyArticleAssessmentSchema = z.strictObject({
  ...assessmentFields,
  version: previousVersion,
  effective_published_at: TimestampSchema.nullable(),
  publication_clock: z.enum(["published_at", "fetched_at", "unavailable"]),
  age_hours: FiniteSchema.min(0).nullable(),
});
type LegacyArticleAssessment = z.infer<typeof LegacyArticleAssessmentSchema>;

const { top_k: _topK, ...diversityFields } = DiversityMetricRowSchema.shape;
const LegacyDiversityMetricSchema = z.strictObject({
  ...diversityFields,
  version: previousVersion,
  top_k: z.literal([1, 5, 10]).nullable().default(null),
});
type LegacyDiversityMetric = z.infer<typeof LegacyDiversityMetricSchema>;

const { version: _sourceVersion, ...sourceRunFields } = SourceRunRecordSchema.shape;
const LegacySourceRunSchema = z.strictObject({
  ...sourceRunFields,
  version: previousVersion,
});
type LegacySourceRun = z.infer<typeof LegacySourceRunSchema>;

const { version: _dispatchVersion, ...dispatchFields } = FeedIngestDispatchSchema.shape;
const LegacyDispatchSchema = z.strictObject({
  ...dispatchFields,
  version: previousVersion,
});
type LegacyDispatch = z.infer<typeof LegacyDispatchSchema>;

function migrateAssessment(row: object): ArticleAssessmentRecord {
  const old = LegacyArticleAssessmentSchema.parse(row) as LegacyArticleAssessment;
  const { effective_published_at, publication_clock, ...rest } = old;
  return ArticleAssessmentRecordSchema.parse({
    ...rest,
    version: FEED_INGEST_AUDIT_VERSION,
    timing_at: effective_published_at,
    timing_basis: publication_clock,
  });
}

function migrateDiversity(row: object): DiversityMetricRow {
  const old = LegacyDiversityMetricSchema.parse(row) as LegacyDiversityMetric;
  return DiversityMetricRowSchema.parse({ ...old, version: FEED_INGEST_AUDIT_VERSION });
}

function migrateSourceRun(row: object): SourceRunRecord {
  const old = LegacySourceRunSchema.parse(row) as LegacySourceRun;
  return SourceRunRecordSchema.parse({ ...old, version: FEED_INGEST_AUDIT_VERSION });
}

function migrateDispatch(row: object): FeedIngestDispatch {
  const old = LegacyDispatchSchema.parse(row) as LegacyDispatch;
  return FeedIngestDispatchSchema.parse({ ...old, version: FEED_INGEST_AUDIT_VERSION });
}

export const ArticleAssessmentContract: LedgerRowContract<ArticleAssessmentRecord> = {
  schema: ArticleAssessmentRecordSchema,
  schemaVersion: FEED_INGEST_AUDIT_VERSION,
  legacyVersions: { [PREVIOUS_VERSION]: { schema: LegacyArticleAssessmentSchema, migrate: migrateAssessment } },
};
export const DiversityMetricContract: LedgerRowContract<DiversityMetricRow> = {
  schema: DiversityMetricRowSchema,
  schemaVersion: FEED_INGEST_AUDIT_VERSION,
  legacyVersions: { [PREVIOUS_VERSION]: { schema: LegacyDiversityMetricSchema, migrate: migrateDiversity } },
};
export const SourceRunContract: LedgerRowContract<SourceRunRecord> = {
  schema: SourceRunRecordSchema,
  schemaVersion: FEED_INGEST_AUDIT_VERSION,
  legacyVersions: { [PREVIOUS_VERSION]: { schema: LegacySourceRunSchema, migrate: migrateSourceRun } },
};
export const DispatchContract: LedgerRowContract<FeedIngestDispatch> = {
  schema: FeedIngestDispatchSchema,
  schemaVersion: FEED_INGEST_AUDIT_VERSION,
  legacyVersions: { [PREVIOUS_VERSION]: { schema: LegacyDispatchSchema, migrate: migrateDispatch } },
};

export const legacyAuditSchemas = {
  ArticleAssessment: LegacyArticleAssessmentSchema,
  DiversityMetric: LegacyDiversityMetricSchema,
  SourceRun: LegacySourceRunSchema,
  Dispatch: LegacyDispatchSchema,
};
