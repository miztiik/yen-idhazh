/** Which prior audit rows can be read without inventing evidence? */
import { z } from "zod";
import {
  ArticleAssessmentRecordSchema,
  DiversityMetricRowSchema,
  FEED_INGEST_AUDIT_VERSION,
  FeedIngestDispatchSchema,
  LegacyArticleAssessmentSchema,
  migrateArticleAssessment,
  SourceRunRecordSchema,
} from "@idhazh/common-contracts";
import type {
  ArticleAssessmentRecord,
  DiversityMetricRow,
  FeedIngestDispatch,
  SourceRunRecord,
} from "@idhazh/common-contracts";
import type { LedgerRowContract } from "@idhazh/ledger-file-writer";

const PREVIOUS_VERSION = "2026-10-20";
const previousVersion = z.literal(PREVIOUS_VERSION);

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
  legacyVersions: { [PREVIOUS_VERSION]: { schema: LegacyArticleAssessmentSchema, migrate: migrateArticleAssessment } },
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
