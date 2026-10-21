/** Which actual input JSON schemas must stay aligned with their Python models? */
import { z } from "zod";
import {
  ArticleAssessmentRecordSchema, ArticleLabelsSchema, CandidateDecisionPayloadSchema,
  CandidateRejectionRecordSchema, CompletedFileSchema, DiversityMetricRowSchema,
  DropReasonCountSchema, EditorialSelectionRowSchema, FeedIngestCandidateSchema,
  FeedIngestDispatchSchema, FeedIngestEventSchema, FeedOutcomePayloadSchema,
  FileEnvelopeSchema, FOOTER_METADATA_KEYS, OPTIONAL_FOOTER_METADATA_KEYS,
  LedgerCompletionEvidenceSchema, PartitionAssignmentSchema,
  PenaltyEvidenceSchema, PolicyIdentitySchema, PortfolioChoicePayloadSchema,
  RejectionDetailsSchema, RowIdentitySchema, ScoreEvidenceSchema, SourceRunRecordSchema,
  SourceSnapshotSchema, StageCompletionPayloadSchema, WriterIdentitySchema,
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
  FeedOutcomePayload: FeedOutcomePayloadSchema, CandidateDecisionPayload: CandidateDecisionPayloadSchema,
  PortfolioChoicePayload: PortfolioChoicePayloadSchema, StageCompletionPayload: StageCompletionPayloadSchema,
  FeedIngestEvent: FeedIngestEventSchema,
} satisfies Record<string, z.ZodType>;

export const schemas = Object.fromEntries(
  Object.entries(runtimeSchemas).map(([name, schema]) => [name, z.toJSONSchema(schema, { io: "input" })]),
);
export default schemas;

export const footerKeys = FOOTER_METADATA_KEYS;
export const optionalFooterKeys = OPTIONAL_FOOTER_METADATA_KEYS;

if (import.meta.main) process.stdout.write(`${JSON.stringify({
  ...schemas, __footer_keys: footerKeys, __optional_footer_keys: optionalFooterKeys,
})}\n`);
