/** Which actual input schemas bind the native payloads and their TypeScript copies? */
import { z } from "zod";
import {
  DiscoveredArticleRowSchema,
  ENVELOPE_VERSIONS, FILE_ENVELOPE_VERSION, FileEnvelopeSchema, FOOTER_METADATA_KEYS,
  OPTIONAL_FOOTER_METADATA_KEYS, PLANNER_FOOTER_METADATA_KEYS,
  PLANNER_OPTIONAL_FOOTER_METADATA_KEYS, FeedHealthRowSchema, FeedHealthStateRowSchema,
  FeedHealthReliabilitySchema, FeedHealthRejectionCountSchema, FeedIngestCandidateSchema,
  FetchedDocumentSchema, PlannerOperationSchema, ExtractionQualitySchema,
  ParsedFeedBatchSchema, SelectedFeedBatchSchema, PartitionedFeedBatchSchema,
  PlannerStageContextSchema, PlannerStageRequestSchema, PlannerArticleEvidenceSchema,
  PlannerHarvestObservationSchema, PlannerSeenEvidenceSchema, PlannerSeenRowSchema,
  PlannerSeenAvailableSchema, PlannerSeenUnavailableSchema, PreflightFreshnessSchema,
  StageReferenceRequestSchema, PartitionArticlesRequestSchema,
  PlannerRejectionCountSchema, PlannerHealthDaySchema, PlannerRequestReportSchema,
  SelectedArticleContentSchema, PlanRunRowSchema, PlanApiTimingSchema,
  PlannerFileEnvelopeSchema, RecordedIdentitySchema, PrimaryEvidenceSchema,
  RowIdentitySchema,
  ROW_IDENTITY_COLUMN_VERSIONS, SourceSnapshotSchema, WriterIdentitySchema,
  SelectedArticleRowSchema, SelectedArticleRatingsSchema, SelectedArticleAdjustmentSchema,
  SelectedArticleMetadataSchema, SelectedArtifactArticleSchema, SelectedArticlesArtifactSchema,
  PublicationEntryInputSchema, PublicationInventoryInputSchema, PUBLICATION_INVENTORY_VERSION,
} from "../src/index";

export const runtimeSchemas = {
  SourceSnapshot: SourceSnapshotSchema, FeedIngestCandidate: FeedIngestCandidateSchema,
  WriterIdentity: WriterIdentitySchema, RowIdentity: RowIdentitySchema, FileEnvelope: FileEnvelopeSchema,
  PlannerFileEnvelope: PlannerFileEnvelopeSchema, FeedHealthRow: FeedHealthRowSchema,
  FetchedDocument: FetchedDocumentSchema, PlannerOperation: PlannerOperationSchema,
  ExtractionQuality: ExtractionQualitySchema, PlannerStageContext: PlannerStageContextSchema,
  PlannerStageRequest: PlannerStageRequestSchema, PlannerArticleEvidence: PlannerArticleEvidenceSchema,
  RecordedIdentity: RecordedIdentitySchema, PrimaryEvidence: PrimaryEvidenceSchema,
  PlannerHarvestObservation: PlannerHarvestObservationSchema,
  PlannerSeenRow: PlannerSeenRowSchema, PlannerSeenAvailable: PlannerSeenAvailableSchema,
  PlannerSeenUnavailable: PlannerSeenUnavailableSchema, PreflightFreshness: PreflightFreshnessSchema,
  ParsedFeedBatch: ParsedFeedBatchSchema, SelectedFeedBatch: SelectedFeedBatchSchema,
  PartitionedFeedBatch: PartitionedFeedBatchSchema, StageReferenceRequest: StageReferenceRequestSchema,
  PartitionArticlesRequest: PartitionArticlesRequestSchema,
  PlannerRejectionCount: PlannerRejectionCountSchema, PlannerHealthDay: PlannerHealthDaySchema,
  PlannerRequestReport: PlannerRequestReportSchema, SelectedArticleContent: SelectedArticleContentSchema,
  DiscoveredArticleRow: DiscoveredArticleRowSchema, SelectedArticleRow: SelectedArticleRowSchema,
  SelectedArticleRatings: SelectedArticleRatingsSchema,
  SelectedArticleAdjustment: SelectedArticleAdjustmentSchema,
  SelectedArticleMetadata: SelectedArticleMetadataSchema, SelectedArtifactArticle: SelectedArtifactArticleSchema,
  SelectedArticlesArtifact: SelectedArticlesArtifactSchema,
  FeedHealthStateRow: FeedHealthStateRowSchema, FeedHealthReliability: FeedHealthReliabilitySchema,
  FeedHealthRejectionCount: FeedHealthRejectionCountSchema, PlanRunRow: PlanRunRowSchema,
  PlanApiTiming: PlanApiTimingSchema,
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
  __planner_footer_keys: PLANNER_FOOTER_METADATA_KEYS,
  __planner_optional_footer_keys: PLANNER_OPTIONAL_FOOTER_METADATA_KEYS,
  __envelope_versions: ENVELOPE_VERSIONS, __file_envelope_version: FILE_ENVELOPE_VERSION,
  __planner_stage_schemas: plannerStageSchemas,
  __row_identity_column_versions: ROW_IDENTITY_COLUMN_VERSIONS,
  __publication_inputs: publicationInputSchemas,
  __publication_input_versions: { PublicationInventory: PUBLICATION_INVENTORY_VERSION },
})}\n`);
