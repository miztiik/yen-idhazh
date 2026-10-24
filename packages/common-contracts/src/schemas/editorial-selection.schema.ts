/** Which ranked articles were selected before assigning workers? */
import { z } from "zod";
import { ArticleLabelsSchema, PolicyIdentitySchema, PreviousScoreEvidenceSchema, ScoreEvidenceSchema, SourceSnapshotSchema } from "./source.schema";
import { DateStampSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema, Sha256Schema, SlugSchema, UrlSchema, checkUrlIdentity, reject } from "./primitives";
import { CONTRACT_VERSION, SOURCE_RELIABILITY_VERSION } from "../version";

export const EditorialSelectionRowSchema = z.strictObject({
  version: z.literal(SOURCE_RELIABILITY_VERSION).default(SOURCE_RELIABILITY_VERSION),
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
export const PreviousEditorialSelectionSchema = z.strictObject({
  ...EditorialSelectionRowSchema.shape, version: z.literal(CONTRACT_VERSION).default(CONTRACT_VERSION),
  ratings: PreviousScoreEvidenceSchema,
});
export const EditorialSelectionContract = {
  schema: EditorialSelectionRowSchema, schemaVersion: SOURCE_RELIABILITY_VERSION,
  legacyVersions: {
    [CONTRACT_VERSION]: {
      schema: PreviousEditorialSelectionSchema,
      migrate: (row: object): EditorialSelectionRow => EditorialSelectionRowSchema.parse({
        ...PreviousEditorialSelectionSchema.parse(row), version: SOURCE_RELIABILITY_VERSION,
      }),
    },
  },
};
