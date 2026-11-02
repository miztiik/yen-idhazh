/** Do selected projections preserve both measured counts, exact scores and timing evidence? */
import { expect, test } from "bun:test";
import {
  SELECTED_ARTICLE_VERSION, SelectedArticleMetadataSchema, SelectedArtifactArticleSchema,
  SelectedArticleRowSchema, SelectedArticlesArtifactSchema, SelectedArticleRatingsSchema,
  deriveUrlKey, selectedArticleMetadata,
} from "../src";

const at = "2026-11-02T12:00:00Z";
function selectedArticle() {
  const pass = -0.2;
  const substance = 0.8;
  const authority = 1;
  const recency = 0.6;
  const domain = -0.04;
  const feed = -0.02;
  const novelty = 0.15;
  const base = ((authority + recency) + pass) + substance;
  return SelectedArtifactArticleSchema.parse({
    url_key: deriveUrlKey("https://article.example/story"), canonical_url: "https://article.example/story",
    feed_id: "recorded-feed", publisher_id: null, title: "Recorded article", categories: [],
    author: null, published_at: at, published_at_source: "source", weight: 1,
    word_count: 1000, substance_word_count: 150, article_text: "Unchanged sanitized article text.",
    editorial_rank: 1, estimated_work: 1000, worker_assignment: null,
    timing_at: at, timing_basis: "published_at", age_hours: -1,
    freshness_cutoff_at: "2026-11-01T00:00:00Z",
    ratings: {
      feed_authority_score: authority, recency_score: recency, base_article_score: base,
      marginal_score: ((base + domain) + feed) + novelty,
      adjustments: [
        { term: "article_pass_rate", value: pass }, { term: "substance_quality_score", value: substance },
        { term: "domain_diversity_penalty", value: domain }, { term: "feed_diversity_penalty", value: feed },
        { term: "novelty_bonus", value: novelty },
      ],
    },
  });
}

test("every selected projection requires integral counts and retained words no greater than raw words", () => {
  const article = selectedArticle();
  const metadata = selectedArticleMetadata(article);
  const row = { ...metadata, run_id: "2026-11-02-1", attempt: 1, date: "2026-11-02" };
  for (const [schema, value] of [
    [SelectedArticleMetadataSchema, metadata], [SelectedArtifactArticleSchema, article],
    [SelectedArticleRowSchema, row],
  ] as const) {
    for (const count of [0, 150, 1000]) {
      expect(schema.parse({ ...value, substance_word_count: count }).substance_word_count).toBe(count);
    }
    for (const field of ["word_count", "substance_word_count"]) {
      for (const count of [undefined, null, -1, 0.5, Infinity, NaN]) {
        expect(schema.safeParse({ ...value, [field]: count }).success).toBe(false);
      }
    }
    expect(schema.safeParse({ ...value, substance_word_count: 1001 }).success).toBe(false);
    for (const field of ["tier", "applied_tier_weight", "feed_limit", "exploration_slot", "cap_relaxations"]) {
      expect(schema.safeParse({ ...value, [field]: 1 }).success).toBe(false);
    }
  }
  expect(article.article_text).toBe("Unchanged sanitized article text.");
  expect(metadata).not.toHaveProperty("article_text");
});

test("selected unknown timing has no recency but still requires the global policy cutoff", () => {
  const article = selectedArticle();
  const ratings = {
    ...article.ratings, recency_score: 0,
    base_article_score: ((1 + 0) + -0.2) + 0.8,
    marginal_score: (((1 + -0.2) + 0.8) + -0.04) + -0.02 + 0.15,
  };
  const unknown = {
    ...article, ratings, timing_at: null, timing_basis: "unavailable" as const, age_hours: null,
    published_at_source: "selection" as const,
  };
  expect(SelectedArtifactArticleSchema.parse(unknown)).toEqual(unknown);
  for (const patch of [
    { timing_at: at }, { age_hours: 0 }, { timing_basis: "first_seen" },
    { published_at_source: "source" }, { freshness_cutoff_at: null }, { freshness_cutoff_at: undefined },
    { ratings: article.ratings },
  ]) expect(SelectedArtifactArticleSchema.safeParse({ ...unknown, ...patch }).success).toBe(false);
  expect(SelectedArtifactArticleSchema.parse({
    ...article, timing_basis: "first_seen", published_at_source: "selection",
  }).timing_basis).toBe("first_seen");
});

test("score components use exact native arithmetic and survive JSON round trips without rounding", () => {
  const article = selectedArticle();
  expect(SelectedArticleRatingsSchema.parse(JSON.parse(JSON.stringify(article.ratings)))).toEqual(article.ratings);
  const precise = {
    feed_authority_score: 0.1, recency_score: 0.2, base_article_score: 0.1 + 0.2,
    marginal_score: 0.1 + 0.2,
    adjustments: article.ratings.adjustments.map(entry => ({ ...entry, value: 0 })),
  };
  expect(SelectedArticleRatingsSchema.parse(precise)).toEqual(precise);
  expect(SelectedArticleRatingsSchema.safeParse({ ...precise, base_article_score: 0.3 }).success).toBe(false);
  expect(SelectedArticleRatingsSchema.safeParse({ ...precise, marginal_score: 0.3 }).success).toBe(false);
  const artifact = {
    schema_version: SELECTED_ARTICLE_VERSION, run_id: "2026-11-02-1", attempt: 1,
    date: "2026-11-02", evaluated_at: at, articles: [article],
  };
  expect(SelectedArticlesArtifactSchema.parse(JSON.parse(JSON.stringify(artifact)))).toEqual(artifact);
});
