/** Which selected fields are committed, and which text travels only in the artifact? */
import { z } from "zod";
import {
  LEGACY_SELECTED_ARTICLE_VERSION, SELECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS, SELECTED_ARTICLE_VERSION,
} from "../version";
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
  published_at_source: z.enum(["source", "selection"]),
  tier: PositiveCountSchema, weight: FiniteSchema.min(0).max(1),
  applied_tier_weight: FiniteSchema.min(0).max(1),
  editorial_rank: PositiveCountSchema, estimated_work: CountSchema,
  worker_assignment: CountSchema.nullable(), ratings: SelectedArticleRatingsSchema,
  feed_limit: CountSchema, exploration_slot: z.boolean(),
  cap_relaxations: z.array(NonEmptySchema), timing_at: RecordedInstantSchema.nullable(),
  timing_basis: z.enum(["published_at", "first_seen", "unavailable"]),
  age_hours: FiniteSchema.nullable(), freshness_cutoff_at: RecordedInstantSchema.nullable(),
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
function validatePublication(value: {
  published_at: string | null; published_at_source: string; timing_basis: string; timing_at: string | null;
}, ctx: z.RefinementCtx) {
  if (value.published_at === null) reject(ctx, "source or selection publication time requires a UTC instant");
  if (value.published_at_source === "source"
    && (value.timing_basis !== "published_at" || value.published_at !== value.timing_at)) {
    reject(ctx, "source publication must retain the trusted admission instant");
  }
  if (value.published_at_source === "selection" && value.timing_basis === "published_at") {
    reject(ctx, "selection time must not replace the original age basis");
  }
}
const changelog = [
  { version: SELECTED_ARTICLE_VERSION, change: "Identify query-free article selection while retaining historical URLs and keys unchanged." },
  { version: LEGACY_SELECTED_ARTICLE_VERSION, change: "Record the applied freshness cutoff and percentage-based feed limit." },
  { version: "2026-10-26", change: "Require source or selection publication provenance and refuse obsolete selected rows." },
];
export const SelectedArticleMetadataSchema = z.strictObject(MetadataFields)
  .superRefine(validateMetadata).superRefine(validatePublication);
export const SelectedArtifactArticleSchema = z.strictObject({
  ...MetadataFields, article_text: z.string(),
}).superRefine(validateMetadata).superRefine(validatePublication);
const RowSchema = z.strictObject({
  ...MetadataFields, run_id: RunIdSchema, attempt: PositiveCountSchema, date: DateStampSchema,
});
function validateRow(value: Parameters<typeof validateMetadata>[0] & { run_id: string; date: string }, ctx: z.RefinementCtx) {
  validateMetadata(value, ctx);
  if (!value.run_id.startsWith(`${value.date}-`)) reject(ctx, "selected date must be its run's UTC accounting day");
}
export const SelectedArticleRowSchema = RowSchema.superRefine(validateRow).superRefine(validatePublication)
  .meta({ version: SELECTED_ARTICLE_VERSION, changelog });
const ArtifactFields = {
  schema_version: z.enum(SELECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS),
  run_id: RunIdSchema, attempt: PositiveCountSchema, date: DateStampSchema,
  evaluated_at: RecordedInstantSchema, articles: z.array(SelectedArtifactArticleSchema),
};
export const SelectedArticlesArtifactSchema = z.strictObject(ArtifactFields).superRefine((value, ctx) => {
  if (!value.run_id.startsWith(`${value.date}-`)) reject(ctx, "artifact date must be its run's UTC accounting day");
}).meta({ version: SELECTED_ARTICLE_VERSION, changelog });
export type SelectedArticleMetadata = z.infer<typeof SelectedArticleMetadataSchema>;
export type SelectedArtifactArticle = z.infer<typeof SelectedArtifactArticleSchema>;
export type SelectedArticleRow = z.infer<typeof SelectedArticleRowSchema>;
export type SelectedArticlesArtifact = z.infer<typeof SelectedArticlesArtifactSchema>;
export const SelectedArticleRowContract = {
  schema: SelectedArticleRowSchema, schemaVersion: SELECTED_ARTICLE_VERSION,
  acceptedSchemaVersions: SELECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS,
} as const;

export function readSelectedArticlesArtifact(raw: unknown): SelectedArticlesArtifact {
  return SelectedArticlesArtifactSchema.parse(raw);
}
export function selectedArticleMetadata(article: SelectedArtifactArticle): SelectedArticleMetadata {
  return SelectedArticleMetadataSchema.parse({
    url_key: article.url_key, feed_id: article.feed_id, publisher_id: article.publisher_id,
    canonical_url: article.canonical_url, title: article.title, categories: article.categories,
    author: article.author, published_at: article.published_at, published_at_source: article.published_at_source, tier: article.tier,
    weight: article.weight, applied_tier_weight: article.applied_tier_weight,
    editorial_rank: article.editorial_rank, estimated_work: article.estimated_work,
    worker_assignment: article.worker_assignment, ratings: article.ratings,
    feed_limit: article.feed_limit, exploration_slot: article.exploration_slot,
    cap_relaxations: article.cap_relaxations, timing_at: article.timing_at,
    timing_basis: article.timing_basis, age_hours: article.age_hours,
    freshness_cutoff_at: article.freshness_cutoff_at,
  });
}
