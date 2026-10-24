/** Which actual input JSON schemas must stay aligned with their Python models? */
import { z } from "zod";
import {
  ArticleAssessmentRecordSchema, ArticleLabelsSchema,
  CandidateRejectionRecordSchema, CompletedFileSchema, DiversityMetricRowSchema,
  DropReasonCountSchema, EditorialSelectionRowSchema, FeedIngestCandidateSchema,
  FeedIngestDispatchSchema,
  FileEnvelopeSchema, FOOTER_METADATA_KEYS, OPTIONAL_FOOTER_METADATA_KEYS,
  LedgerCompletionEvidenceSchema, PartitionAssignmentSchema,
  PenaltyEvidenceSchema, PolicyIdentitySchema,
  RejectionDetailsSchema, RowIdentitySchema, ROW_IDENTITY_COLUMN_VERSIONS, ScoreEvidenceSchema, SourceRunRecordSchema,
  SourceSnapshotSchema, WriterIdentitySchema, FeedHealthRowSchema,
  FetchedDocumentSchema, PlannerOperationSchema,
  PublicationEntryInputSchema, PublicationInventoryInputSchema, PUBLICATION_INVENTORY_VERSION,
  ExtractionQualitySchema, ParsedFeedBatchSchema, SelectedFeedBatchSchema,
  PartitionedFeedBatchSchema, PlannerStageContextSchema, PlannerStageRequestSchema,
  PlannerArticleEvidenceSchema, PlannerOpportunityEvidenceSchema,
  RecordedIdentitySchema, PrimaryEvidenceSchema,
  PlannerHarvestObservationSchema, PlannerSeenEvidenceSchema, PlannerSeenRowSchema,
  PlannerSeenAvailableSchema, PlannerSeenUnavailableSchema,
  PreflightFreshnessSchema, StageReferenceRequestSchema, PartitionArticlesRequestSchema,
  DocumentObservationRecordSchema,
} from "../src/index";

export const runtimeSchemas = {
  SourceSnapshot: SourceSnapshotSchema, ArticleLabels: ArticleLabelsSchema,
  PenaltyEvidence: PenaltyEvidenceSchema, ScoreEvidence: ScoreEvidenceSchema,
  PolicyIdentity: PolicyIdentitySchema, FeedIngestCandidate: FeedIngestCandidateSchema,
  EditorialSelectionRow: EditorialSelectionRowSchema, PartitionAssignment: PartitionAssignmentSchema,
  FeedIngestDispatch: FeedIngestDispatchSchema, RejectionDetails: RejectionDetailsSchema,
  CandidateRejectionRecord: CandidateRejectionRecordSchema, WriterIdentity: WriterIdentitySchema,
  RowIdentity: RowIdentitySchema, FileEnvelope: FileEnvelopeSchema,
  DropReasonCount: DropReasonCountSchema, CompletedFile: CompletedFileSchema,
  LedgerCompletionEvidence: LedgerCompletionEvidenceSchema, SourceRunRecord: SourceRunRecordSchema,
  ArticleAssessmentRecord: ArticleAssessmentRecordSchema, DiversityMetricRow: DiversityMetricRowSchema,
  FeedHealthRow: FeedHealthRowSchema,
  FetchedDocument: FetchedDocumentSchema, PlannerOperation: PlannerOperationSchema,
  ExtractionQuality: ExtractionQualitySchema, PlannerStageContext: PlannerStageContextSchema,
  PlannerStageRequest: PlannerStageRequestSchema, PlannerArticleEvidence: PlannerArticleEvidenceSchema,
  RecordedIdentity: RecordedIdentitySchema, PrimaryEvidence: PrimaryEvidenceSchema,
  PlannerOpportunityEvidence: PlannerOpportunityEvidenceSchema,
  PlannerHarvestObservation: PlannerHarvestObservationSchema,
  PlannerSeenRow: PlannerSeenRowSchema,
  PlannerSeenAvailable: PlannerSeenAvailableSchema,
  PlannerSeenUnavailable: PlannerSeenUnavailableSchema,
  PreflightFreshness: PreflightFreshnessSchema, ParsedFeedBatch: ParsedFeedBatchSchema,
  SelectedFeedBatch: SelectedFeedBatchSchema, PartitionedFeedBatch: PartitionedFeedBatchSchema,
  StageReferenceRequest: StageReferenceRequestSchema,
  PartitionArticlesRequest: PartitionArticlesRequestSchema,
  DocumentObservationRecord: DocumentObservationRecordSchema,
} satisfies Record<string, z.ZodType>;

export const schemas = Object.fromEntries(
  Object.entries(runtimeSchemas).map(([name, schema]) => [name, z.toJSONSchema(schema, { io: "input" })]),
);
export default schemas;

export const plannerStageSchemas = {
  PlannerSeenEvidence: z.toJSONSchema(PlannerSeenEvidenceSchema, { io: "input" }),
};
export const footerKeys = FOOTER_METADATA_KEYS;
export const optionalFooterKeys = OPTIONAL_FOOTER_METADATA_KEYS;
export const publicationInputSchemas = {
  PublicationEntry: z.toJSONSchema(PublicationEntryInputSchema, { io: "input" }),
  PublicationInventory: z.toJSONSchema(PublicationInventoryInputSchema, { io: "input" }),
};

if (import.meta.main) process.stdout.write(`${JSON.stringify({
  ...schemas, __footer_keys: footerKeys, __optional_footer_keys: optionalFooterKeys,
  __planner_stage_schemas: plannerStageSchemas,
  __row_identity_column_versions: ROW_IDENTITY_COLUMN_VERSIONS,
  __publication_inputs: publicationInputSchemas,
  __publication_input_versions: {
    PublicationInventory: PUBLICATION_INVENTORY_VERSION,
  },
})}\n`);
