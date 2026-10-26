/** Which selected fields are committed, and which text travels only in the artifact? */
import { z } from "zod";
import { PLANNER_LEDGER_VERSION } from "../version";
import {
  CountSchema, DateStampSchema, FiniteSchema, NonEmptySchema,
  PositiveCountSchema, RunIdSchema, Sha256Schema, SlugSchema, UrlSchema,
  checkUrlIdentity, reject,
} from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";

export const SelectedArticleAdjustmentSchema = z.strictObject({
  term: NonEmptySchema, value: FiniteSchema.nullable(),
});
export const SelectedArticleRatingsSchema = z.strictObject({
  base_article_score: FiniteSchema, marginal_score: FiniteSchema,
  adjustments: z.array(SelectedArticleAdjustmentSchema),
  recency_score: FiniteSchema, feed_authority_score: FiniteSchema,
});
const MetadataFields = {
  url_key: Sha256Schema, feed_id: SlugSchema, publisher_id: SlugSchema.nullable(),
  canonical_url: UrlSchema, title: NonEmptySchema, categories: z.array(z.string()),
  author: z.string().nullable(), published_at: RecordedInstantSchema.nullable(),
  tier: PositiveCountSchema, weight: FiniteSchema.min(0).max(1),
  applied_tier_weight: FiniteSchema.min(0).max(1),
  editorial_rank: PositiveCountSchema, estimated_work: CountSchema,
  worker_assignment: CountSchema.nullable(), ratings: SelectedArticleRatingsSchema,
  feed_allowance: CountSchema, exploration_slot: z.boolean(),
  cap_relaxations: z.array(NonEmptySchema), timing_at: RecordedInstantSchema.nullable(),
  timing_basis: z.enum(["published_at", "first_seen", "unavailable"]),
  age_hours: FiniteSchema.nullable(), allowance_reasons: z.array(NonEmptySchema),
};
function validateMetadata(value: {
  canonical_url: string; url_key: string; timing_basis: string;
  timing_at: string | null; age_hours: number | null;
}, ctx: z.RefinementCtx): void {
  checkUrlIdentity(value, ctx);
  const unavailable = value.timing_basis === "unavailable";
  if (unavailable !== (value.timing_at === null && value.age_hours === null)
    || (!unavailable && (value.timing_at === null || value.age_hours === null))) {
    reject(ctx, "timing availability must match its instant and measured age");
  }
}
export const SelectedArticleMetadataSchema = z.strictObject(MetadataFields).superRefine(validateMetadata);
export const SelectedArtifactArticleSchema = z.strictObject({
  ...MetadataFields, article_text: z.string(),
}).superRefine(validateMetadata);
export const SelectedArticleRowSchema = z.strictObject({
  ...MetadataFields, run_id: RunIdSchema, attempt: PositiveCountSchema, date: DateStampSchema,
}).superRefine((value, ctx) => {
  validateMetadata(value, ctx);
  if (!value.run_id.startsWith(`${value.date}-`)) reject(ctx, "selected date must be its run's UTC accounting day");
});
export const SelectedArticlesArtifactSchema = z.strictObject({
  schema_version: z.literal(PLANNER_LEDGER_VERSION).default(PLANNER_LEDGER_VERSION),
  run_id: RunIdSchema, attempt: PositiveCountSchema, date: DateStampSchema,
  evaluated_at: RecordedInstantSchema, articles: z.array(SelectedArtifactArticleSchema),
}).superRefine((value, ctx) => {
  if (!value.run_id.startsWith(`${value.date}-`)) reject(ctx, "artifact date must be its run's UTC accounting day");
});
export type SelectedArticleMetadata = z.infer<typeof SelectedArticleMetadataSchema>;
export type SelectedArtifactArticle = z.infer<typeof SelectedArtifactArticleSchema>;
export type SelectedArticleRow = z.infer<typeof SelectedArticleRowSchema>;
export type SelectedArticlesArtifact = z.infer<typeof SelectedArticlesArtifactSchema>;
export const SelectedArticleRowContract = {
  schema: SelectedArticleRowSchema, schemaVersion: PLANNER_LEDGER_VERSION,
} as const;

export function selectedArticleMetadata(article: SelectedArtifactArticle): SelectedArticleMetadata {
  return SelectedArticleMetadataSchema.parse({
    url_key: article.url_key, feed_id: article.feed_id, publisher_id: article.publisher_id,
    canonical_url: article.canonical_url, title: article.title, categories: article.categories,
    author: article.author, published_at: article.published_at, tier: article.tier,
    weight: article.weight, applied_tier_weight: article.applied_tier_weight,
    editorial_rank: article.editorial_rank, estimated_work: article.estimated_work,
    worker_assignment: article.worker_assignment, ratings: article.ratings,
    feed_allowance: article.feed_allowance, exploration_slot: article.exploration_slot,
    cap_relaxations: article.cap_relaxations, timing_at: article.timing_at,
    timing_basis: article.timing_basis, age_hours: article.age_hours,
    allowance_reasons: article.allowance_reasons,
  });
}
