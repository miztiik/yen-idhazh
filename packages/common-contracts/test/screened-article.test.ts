/** Do screening and numerical declarations refuse missing or inconsistent measured evidence? */
import { expect, test } from "bun:test";
import {
  AdmittedArticleFreshnessSchema, FeedIngestCandidateSchema, NumericalSelectionInputSchema,
  NumericalSelectionOutputSchema, RawArticleFreshnessSchema, ScreenedCandidateSchema,
  deriveCandidateId, deriveUrlKey,
} from "../src/index";

const unknownTiming = { timing_at: null, timing_source: "unknown", age_hours: null, recency_bonus: 0 } as const;
const knownTiming = {
  timing_at: "2026-11-02T13:00:00Z", timing_source: "published_at", age_hours: -1, recency_bonus: 0.6,
} as const;

test("raw timing admits signed age and explicit unknown evidence only", () => {
  for (const timing of [unknownTiming, knownTiming, { ...knownTiming, timing_source: "first_seen" as const, age_hours: 18 }]) {
    expect(RawArticleFreshnessSchema.parse(timing)).toEqual(timing);
  }
  for (const timing of [
    { ...unknownTiming, timing_at: knownTiming.timing_at }, { ...unknownTiming, age_hours: 0 },
    { ...unknownTiming, recency_bonus: 0.6 }, { ...knownTiming, timing_at: null },
    { ...knownTiming, age_hours: null }, { ...knownTiming, age_hours: Infinity },
    { ...knownTiming, age_hours: NaN }, { ...knownTiming, timing_at: "2026-02-30T00:00:00Z" },
    { ...knownTiming, timing_at: "2026-11-02T13:00:00+01:00" }, { ...knownTiming, recency_bonus: -1 },
    { ...knownTiming, recency_bonus: Infinity }, { timing_source: "unknown" },
  ]) expect(RawArticleFreshnessSchema.safeParse(timing).success).toBe(false);
});

test("admitted freshness requires a measured count and finite score, including zero and negatives", () => {
  const freshness = { ...unknownTiming, substance_word_count: 0, substance_score: -0.25 };
  expect(AdmittedArticleFreshnessSchema.parse(freshness)).toEqual(freshness);
  expect(AdmittedArticleFreshnessSchema.parse({
    ...knownTiming, substance_word_count: 750, substance_score: 1.3,
  }).substance_word_count).toBe(750);
  for (const patch of [
    { substance_word_count: undefined }, { substance_word_count: null }, { substance_word_count: -1 },
    { substance_word_count: 0.5 }, { substance_word_count: Infinity }, { substance_score: undefined },
    { substance_score: null }, { substance_score: NaN }, { substance_score: Infinity },
  ]) expect(AdmittedArticleFreshnessSchema.safeParse({ ...freshness, ...patch }).success).toBe(false);
});

test("screened candidates bind retained counts to the original parsed count without changing text", () => {
  const canonical_url = "https://article.example/story";
  const candidate = FeedIngestCandidateSchema.parse({
    date: "2026-11-02", correlation_id: "recorded", run_id: "2026-11-02-1",
    candidate_id: deriveCandidateId("2026-11-02-1", "recorded-feed", 0), entry_ordinal: 0,
    feed_id: "recorded-feed", source: {
      feed_id: "recorded-feed", feed_url: "https://feed.example/rss", publisher_id: null,
      title: "Recorded feed", status: "active", weight: 1,
    },
    canonical_url, url_key: deriveUrlKey(canonical_url), title: "Recorded article", categories: [],
    article_text: "Two words", word_count: 2, author: null, published_at: null, fetched_at: "2026-11-02T13:00:00Z",
  });
  const screened = {
    candidate, policy: {
      triage: { min_words: 1, recency_half_life_hours: 18, recency_weight: 0.6 },
      curate_articles: { source_authority_weight: 1 },
    },
    freshness: { ...unknownTiming, substance_score: 0, substance_word_count: 0 },
    observation: null, discovered_availability: "unavailable",
  };
  for (const count of [0, 1, 2]) {
    expect(ScreenedCandidateSchema.parse({
      ...screened, freshness: { ...screened.freshness, substance_word_count: count },
    }).candidate).toEqual(candidate);
  }
  expect(ScreenedCandidateSchema.safeParse({
    ...screened, freshness: { ...screened.freshness, substance_word_count: 3 },
  }).success).toBe(false);
});

test("numerical records contain identity and finite cached scores, never article text", () => {
  const input = {
    candidate_id: "a".repeat(64), url_key: "b".repeat(64), feed_id: "recorded-feed",
    website_group: "article.example", base_score: -2,
  };
  expect(NumericalSelectionInputSchema.parse(input)).toEqual(input);
  for (const patch of [
    { candidate_id: "bad" }, { url_key: "" }, { feed_id: "" }, { website_group: "" },
    { website_group: "  " }, { base_score: Infinity }, { base_score: NaN }, { base_score: undefined },
    { article_text: "Not a numerical input" }, { substance_word_count: 25 },
  ]) expect(NumericalSelectionInputSchema.safeParse({ ...input, ...patch }).success).toBe(false);
  const output = {
    candidate_id: input.candidate_id, marginal_score: -5, domain_diversity_penalty: -4,
    feed_diversity_penalty: -2, novelty_bonus: 0,
  };
  expect(NumericalSelectionOutputSchema.parse(output)).toEqual(output);
  for (const patch of [
    { marginal_score: Infinity }, { domain_diversity_penalty: 1 }, { feed_diversity_penalty: 1 },
    { novelty_bonus: -1 }, { novelty_bonus: NaN }, { candidate_id: "" }, { article_text: "" },
  ]) expect(NumericalSelectionOutputSchema.safeParse({ ...output, ...patch }).success).toBe(false);
});
