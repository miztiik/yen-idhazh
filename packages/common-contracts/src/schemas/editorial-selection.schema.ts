/** Which ranked articles were selected before assigning workers? */
import { z } from "zod";
import {
  ArticleLabelsSchema, PolicyIdentitySchema, PreviousScoreEvidenceSchema, PreviousSourceSnapshotSchema,
  PreviousPublisherScoreEvidenceSchema, ScoreEvidenceSchema, SourceSnapshotSchema,
} from "./source.schema";
import { DateStampSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema, Sha256Schema, SlugSchema, UrlSchema, checkUrlIdentity, reject } from "./primitives";
import { CONTRACT_VERSION, PUBLISHER_EXPOSURE_VERSION, PUBLISHER_IDENTITY_VERSION, SOURCE_RELIABILITY_VERSION } from "../version";

export const EditorialSelectionRowSchema = z.strictObject({
  version: z.literal(PUBLISHER_EXPOSURE_VERSION).default(PUBLISHER_EXPOSURE_VERSION),
  date: DateStampSchema, correlation_id: NonEmptySchema,
  candidate_id: Sha256Schema, source_id: SlugSchema, vertical: SlugSchema,
  source: SourceSnapshotSchema, canonical_url: UrlSchema, url_key: Sha256Schema,
  labels: ArticleLabelsSchema, editorial_rank: PositiveCountSchema,
  estimated_work: NonNegativeSchema, ratings: ScoreEvidenceSchema, policy: PolicyIdentitySchema,
}).superRefine((value, ctx) => {
  checkUrlIdentity(value, ctx);
  if (value.source_id !== value.source.source_id || value.vertical !== value.source.vertical) reject(ctx, "source identity must match source snapshot");
});
export type EditorialSelectionRow = z.infer<typeof EditorialSelectionRowSchema>;
const previousSelectionFields = EditorialSelectionRowSchema.shape;
export const PreviousEditorialSelectionSchema = z.strictObject({
  ...previousSelectionFields, source: PreviousSourceSnapshotSchema,
  version: z.literal(CONTRACT_VERSION).default(CONTRACT_VERSION),
  ratings: PreviousScoreEvidenceSchema,
});
export const PreviousReliableEditorialSelectionSchema = z.strictObject({
  ...previousSelectionFields, source: PreviousSourceSnapshotSchema, version: z.literal(SOURCE_RELIABILITY_VERSION),
  ratings: PreviousPublisherScoreEvidenceSchema,
});
export const PreviousPublisherEditorialSelectionSchema = z.strictObject({
  ...previousSelectionFields, version: z.literal(PUBLISHER_IDENTITY_VERSION),
  ratings: PreviousPublisherScoreEvidenceSchema,
});
export const EditorialSelectionContract = {
  schema: EditorialSelectionRowSchema, schemaVersion: PUBLISHER_EXPOSURE_VERSION,
  legacyVersions: {
    [PUBLISHER_IDENTITY_VERSION]: {
      schema: PreviousPublisherEditorialSelectionSchema,
      migrate: (row: object): EditorialSelectionRow => EditorialSelectionRowSchema.parse({
        ...PreviousPublisherEditorialSelectionSchema.parse(row), version: PUBLISHER_EXPOSURE_VERSION,
      }),
    },
    [CONTRACT_VERSION]: {
      schema: PreviousEditorialSelectionSchema,
      migrate: (row: object): EditorialSelectionRow => EditorialSelectionRowSchema.parse({
        ...PreviousEditorialSelectionSchema.parse(row), version: PUBLISHER_EXPOSURE_VERSION,
      }),
    },
    [SOURCE_RELIABILITY_VERSION]: {
      schema: PreviousReliableEditorialSelectionSchema,
      migrate: (row: object): EditorialSelectionRow => EditorialSelectionRowSchema.parse({
        ...PreviousReliableEditorialSelectionSchema.parse(row), version: PUBLISHER_EXPOSURE_VERSION,
      }),
    },
  },
};
