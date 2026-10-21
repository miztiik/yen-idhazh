/** Which ranked articles were selected before assigning workers? */
import { z } from "zod";
import { ArticleLabelsSchema, PolicyIdentitySchema, ScoreEvidenceSchema, SourceSnapshotSchema } from "./source.schema";
import { DateStampSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema, Sha256Schema, SlugSchema, UrlSchema, VersionSchema, checkUrlIdentity, reject } from "./primitives";

export const EditorialSelectionRowSchema = z.strictObject({
  version: VersionSchema, date: DateStampSchema, correlation_id: NonEmptySchema,
  candidate_id: Sha256Schema, source_id: SlugSchema, vertical: SlugSchema,
  source: SourceSnapshotSchema, canonical_url: UrlSchema, url_key: Sha256Schema,
  labels: ArticleLabelsSchema, editorial_rank: PositiveCountSchema,
  estimated_work: NonNegativeSchema, ratings: ScoreEvidenceSchema, policy: PolicyIdentitySchema,
}).superRefine((value, ctx) => {
  checkUrlIdentity(value, ctx);
  if (value.source_id !== value.source.source_id || value.vertical !== value.source.vertical) reject(ctx, "source identity must match source snapshot");
});
export type EditorialSelectionRow = z.infer<typeof EditorialSelectionRowSchema>;
