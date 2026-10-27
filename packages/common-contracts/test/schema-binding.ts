/** Which actual input schemas do contract-binding and planner tests exercise? */
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
  PlannerHarvestObservationSchema, PlannerDiscoveredEvidenceSchema, PlannerDiscoveredRowSchema,
  PlannerDiscoveredAvailableSchema, PlannerDiscoveredUnavailableSchema, PreflightFreshnessSchema,
  StageReferenceRequestSchema, PartitionArticlesRequestSchema,
  PlannerRejectionCountSchema, PlannerHealthDaySchema, PlannerRequestReportSchema,
  PlannerFeedEntrySchema, PlannerFeedOfferSchema,
  SelectedArticleContentSchema, PlanRunRowSchema, PlanApiTimingSchema,
  PlannerFileEnvelopeSchema, RecordedIdentitySchema,
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
  RecordedIdentity: RecordedIdentitySchema,
  PlannerHarvestObservation: PlannerHarvestObservationSchema,
  PlannerDiscoveredRow: PlannerDiscoveredRowSchema, PlannerDiscoveredAvailable: PlannerDiscoveredAvailableSchema,
  PlannerDiscoveredUnavailable: PlannerDiscoveredUnavailableSchema, PreflightFreshness: PreflightFreshnessSchema,
  ParsedFeedBatch: ParsedFeedBatchSchema, SelectedFeedBatch: SelectedFeedBatchSchema,
  PartitionedFeedBatch: PartitionedFeedBatchSchema, StageReferenceRequest: StageReferenceRequestSchema,
  PartitionArticlesRequest: PartitionArticlesRequestSchema,
  PlannerRejectionCount: PlannerRejectionCountSchema, PlannerHealthDay: PlannerHealthDaySchema,
  PlannerFeedEntry: PlannerFeedEntrySchema, PlannerFeedOffer: PlannerFeedOfferSchema,
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
  PlannerDiscoveredEvidence: z.toJSONSchema(PlannerDiscoveredEvidenceSchema, { io: "input" }),
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
