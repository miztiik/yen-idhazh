/** Which prior audit rows can be read without inventing evidence? */
import { z } from "zod";
import {
  DiversityMetricRowSchema,
  DocumentObservationRecordSchema,
  DropReasonCountSchema,
  FEED_INGEST_AUDIT_VERSION,
  FeedIngestDispatchSchema,
  LegacyArticleAssessmentSchema,
  SourceRunRecordSchema,
  LedgerCompletionEvidenceSchema,
  SOURCE_RUN_VERSION,
  PLANNING_OBSERVATIONS_VERSION,
  SOURCE_RELIABILITY_VERSION,
  PLANNER_EXCLUSIONS_VERSION,
  DOCUMENT_OBSERVATION_VERSION,
  PreviousFeedIngestDispatchSchema, PreviousObservedFeedIngestDispatchSchema,
  PreviousReliableFeedIngestDispatchSchema, readFeedIngestDispatch,
  PreviousSourceSnapshotSchema, PUBLISHER_IDENTITY_VERSION, PUBLISHER_EXPOSURE_VERSION,
  PreviousPublisherFeedIngestDispatchSchema,
} from "@idhazh/common-contracts";
import type {
  DocumentObservationRecord,
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
const PreviousDropReasonCountSchema = DropReasonCountSchema.extend({
  reason: DropReasonCountSchema.shape.reason.exclude([
    "ALREADY_PUBLISHED", "SETTLED_FAILURE", "BLOCKED_URL_MARKER",
  ]),
});
const previousSourceRunFields = {
  ...sourceRunFields,
  source: PreviousSourceSnapshotSchema,
  drop_reasons: z.array(PreviousDropReasonCountSchema),
  last_failure_reason: PreviousDropReasonCountSchema.shape.reason.nullable(),
};
const LegacySourceRunSchema = z.strictObject({
  ...previousSourceRunFields,
  version: previousVersion,
  completion_evidence: z.array(z.strictObject({
    ledger: LedgerCompletionEvidenceSchema.shape.ledger,
    row_count: LedgerCompletionEvidenceSchema.shape.row_count,
    files: LedgerCompletionEvidenceSchema.shape.files,
  })).nullable().default(null),
});
const PreviousSourceRunSchema = LegacySourceRunSchema.extend({ version: z.literal("2026-10-22") });
const PreviousDiagnosticSourceRunSchema = LegacySourceRunSchema.extend({ version: z.literal("2026-10-22T18:15") });
const PreviousExclusionSourceRunSchema = z.strictObject({
  ...sourceRunFields,
  source: PreviousSourceSnapshotSchema,
  version: z.literal(PLANNER_EXCLUSIONS_VERSION),
});
const PreviousLogicalSourceRunSchema = z.strictObject({
  ...previousSourceRunFields, version: z.literal("2026-10-22T10:05"),
});

const LegacyDispatchSchema = PreviousFeedIngestDispatchSchema.extend({ version: previousVersion });
const PreviousDispatchSchema = PreviousFeedIngestDispatchSchema.extend({ version: z.literal(FEED_INGEST_AUDIT_VERSION) });

function migrateDiversity(row: object): DiversityMetricRow {
  const old = LegacyDiversityMetricSchema.parse(row) as LegacyDiversityMetric;
  return DiversityMetricRowSchema.parse({ ...old, version: FEED_INGEST_AUDIT_VERSION });
}

function migrateSourceRun(row: object): SourceRunRecord {
  return SourceRunRecordSchema.parse({ ...row, version: SOURCE_RUN_VERSION });
}

function migrateDispatch(row: object): FeedIngestDispatch {
  return readFeedIngestDispatch(row);
}

export { ArticleAssessmentContract } from "@idhazh/common-contracts";
export const DiversityMetricContract: LedgerRowContract<DiversityMetricRow> = {
  schema: DiversityMetricRowSchema,
  schemaVersion: FEED_INGEST_AUDIT_VERSION,
  legacyVersions: { [PREVIOUS_VERSION]: { schema: LegacyDiversityMetricSchema, migrate: migrateDiversity } },
};
export const DocumentObservationContract: LedgerRowContract<DocumentObservationRecord> = {
  schema: DocumentObservationRecordSchema,
  schemaVersion: DOCUMENT_OBSERVATION_VERSION,
};
export const SourceRunContract: LedgerRowContract<SourceRunRecord> = {
  schema: SourceRunRecordSchema,
  schemaVersion: SOURCE_RUN_VERSION,
  legacyVersions: {
    [PREVIOUS_VERSION]: { schema: LegacySourceRunSchema, migrate: migrateSourceRun },
    "2026-10-22": { schema: PreviousSourceRunSchema, migrate: migrateSourceRun },
    "2026-10-22T18:15": { schema: PreviousDiagnosticSourceRunSchema, migrate: migrateSourceRun },
    [PLANNER_EXCLUSIONS_VERSION]: { schema: PreviousExclusionSourceRunSchema, migrate: migrateSourceRun },
    "2026-10-22T10:05": { schema: PreviousLogicalSourceRunSchema, migrate: migrateSourceRun },
  },
};
export const DispatchContract: LedgerRowContract<FeedIngestDispatch> = {
  schema: FeedIngestDispatchSchema,
  schemaVersion: PUBLISHER_EXPOSURE_VERSION,
  legacyVersions: {
    [PUBLISHER_IDENTITY_VERSION]: { schema: PreviousPublisherFeedIngestDispatchSchema, migrate: migrateDispatch },
    [PREVIOUS_VERSION]: { schema: LegacyDispatchSchema, migrate: migrateDispatch },
    [FEED_INGEST_AUDIT_VERSION]: { schema: PreviousDispatchSchema, migrate: migrateDispatch },
    [PLANNING_OBSERVATIONS_VERSION]: { schema: PreviousObservedFeedIngestDispatchSchema, migrate: migrateDispatch },
    [SOURCE_RELIABILITY_VERSION]: {
      schema: PreviousReliableFeedIngestDispatchSchema,
      migrate: migrateDispatch,
    },
  },
};

export const legacyAuditSchemas = {
  ArticleAssessment: LegacyArticleAssessmentSchema,
  DiversityMetric: LegacyDiversityMetricSchema,
  SourceRun: LegacySourceRunSchema,
  Dispatch: LegacyDispatchSchema,
};
