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
  SourceSnapshotSchema, WriterIdentitySchema,
  FetchedDocumentSchema, PlannerOperationSchema,
  PublicationEntryInputSchema, PublicationInventoryInputSchema, PublicationReceiptInputSchema,
  PUBLICATION_INVENTORY_VERSION, PUBLICATION_RECEIPT_VERSION,
  ExtractionQualitySchema,
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
  FetchedDocument: FetchedDocumentSchema, PlannerOperation: PlannerOperationSchema,
  ExtractionQuality: ExtractionQualitySchema,
} satisfies Record<string, z.ZodType>;

export const schemas = Object.fromEntries(
  Object.entries(runtimeSchemas).map(([name, schema]) => [name, z.toJSONSchema(schema, { io: "input" })]),
);
export default schemas;

export const footerKeys = FOOTER_METADATA_KEYS;
export const optionalFooterKeys = OPTIONAL_FOOTER_METADATA_KEYS;
export const publicationInputSchemas = {
  PublicationEntry: z.toJSONSchema(PublicationEntryInputSchema, { io: "input" }),
  PublicationInventory: z.toJSONSchema(PublicationInventoryInputSchema, { io: "input" }),
  PublicationReceipt: z.toJSONSchema(PublicationReceiptInputSchema, { io: "input" }),
};

if (import.meta.main) process.stdout.write(`${JSON.stringify({
  ...schemas, __footer_keys: footerKeys, __optional_footer_keys: optionalFooterKeys,
  __row_identity_column_versions: ROW_IDENTITY_COLUMN_VERSIONS,
  __publication_inputs: publicationInputSchemas,
  __publication_input_versions: {
    PublicationInventory: PUBLICATION_INVENTORY_VERSION, PublicationReceipt: PUBLICATION_RECEIPT_VERSION,
  },
})}\n`);
