/** Which selected fields are committed, and which text travels only in the artifact? */
import { z } from "zod";
import { SELECTED_ARTICLE_VERSION } from "../version";
import {
  CountSchema, DateStampSchema, FiniteSchema, NonEmptySchema,
  PositiveCountSchema, RunIdSchema, Sha256Schema, SlugSchema, UrlSchema,
  checkUrlIdentity, reject,
} from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";

export const SelectedArticleAdjustmentSchema = z.strictObject({
  term: z.enum(["article_pass_rate", "substance_quality_score", "domain_diversity_penalty", "feed_diversity_penalty", "novelty_bonus"]),
  value: FiniteSchema,
});
export const SelectedArticleRatingsSchema = z.strictObject({
  base_article_score: FiniteSchema, marginal_score: FiniteSchema,
  adjustments: z.array(SelectedArticleAdjustmentSchema).length(SelectedArticleAdjustmentSchema.shape.term.options.length),
  recency_score: FiniteSchema, feed_authority_score: FiniteSchema,
}).superRefine((value, ctx) => {
  const terms = SelectedArticleAdjustmentSchema.shape.term.options;
  if (value.adjustments.length !== terms.length
    || value.adjustments.some((entry, index) => entry.term !== terms[index])) {
    reject(ctx, "ratings require all five adjustments in their declared order", ["adjustments"]);
    return;
  }
  const [pass, substance, domain, feed, novelty] = value.adjustments;
  const base = ((value.feed_authority_score + value.recency_score) + pass!.value) + substance!.value;
  const marginal = ((value.base_article_score + domain!.value) + feed!.value) + novelty!.value;
  if (base !== value.base_article_score) reject(ctx, "base score must match its cached components", ["base_article_score"]);
  if (marginal !== value.marginal_score) reject(ctx, "marginal score must match its ordered adjustments", ["marginal_score"]);
});
const MetadataFields = {
  url_key: Sha256Schema, feed_id: SlugSchema, publisher_id: SlugSchema.nullable(),
  canonical_url: UrlSchema, title: NonEmptySchema, categories: z.array(z.string()),
  author: z.string().nullable(), published_at: RecordedInstantSchema.nullable(),
  published_at_source: z.enum(["source", "selection"]),
  weight: FiniteSchema.min(0).max(1), word_count: CountSchema, substance_word_count: CountSchema,
  editorial_rank: PositiveCountSchema, estimated_work: CountSchema,
  worker_assignment: CountSchema.nullable(), ratings: SelectedArticleRatingsSchema,
  timing_at: RecordedInstantSchema.nullable(),
  timing_basis: z.enum(["published_at", "first_seen", "unavailable"]),
  age_hours: FiniteSchema.nullable(), freshness_cutoff_at: RecordedInstantSchema,
};
function validateMetadata(value: {
  canonical_url: string; url_key: string; timing_basis: string;
  timing_at: string | null; age_hours: number | null;
  word_count: number; substance_word_count: number; ratings: { recency_score: number };
}, ctx: z.RefinementCtx): void {
  checkUrlIdentity(value, ctx);
  if (value.canonical_url.includes("#")) reject(ctx, "current selected article address must not contain a fragment");
  const unavailable = value.timing_basis === "unavailable";
  if (unavailable !== (value.timing_at === null && value.age_hours === null)
    || (!unavailable && (value.timing_at === null || value.age_hours === null))) {
    reject(ctx, "timing availability must match its instant and measured age");
  }
  if (unavailable && value.ratings.recency_score !== 0) reject(ctx, "unknown timing requires zero recency");
  if (value.substance_word_count > value.word_count) reject(ctx, "substance_word_count must not exceed word_count", ["substance_word_count"]);
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
  { version: SELECTED_ARTICLE_VERSION, change: "Preserve resource queries in selected addresses and their full hashes." },
  { version: "2026-11-02", change: "Require both word counts, complete diversity scores and global timing without retired selection fields." },
  { version: "2026-10-29", change: "Identify query-free article selection." },
  { version: "2026-10-27", change: "Record the applied freshness cutoff and percentage-based feed limit." },
  { version: "2026-10-26", change: "Earlier changes are in git." },
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
  schema_version: z.literal(SELECTED_ARTICLE_VERSION),
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
} as const;

export function readSelectedArticlesArtifact(raw: unknown): SelectedArticlesArtifact {
  return SelectedArticlesArtifactSchema.parse(raw);
}
export function selectedArticleMetadata(article: SelectedArtifactArticle): SelectedArticleMetadata {
  return SelectedArticleMetadataSchema.parse({
    url_key: article.url_key, feed_id: article.feed_id, publisher_id: article.publisher_id,
    canonical_url: article.canonical_url, title: article.title, categories: article.categories,
    author: article.author, published_at: article.published_at, published_at_source: article.published_at_source,
    weight: article.weight, word_count: article.word_count, substance_word_count: article.substance_word_count,
    editorial_rank: article.editorial_rank, estimated_work: article.estimated_work,
    worker_assignment: article.worker_assignment, ratings: article.ratings,
    timing_at: article.timing_at,
    timing_basis: article.timing_basis, age_hours: article.age_hours,
    freshness_cutoff_at: article.freshness_cutoff_at,
  });
}
