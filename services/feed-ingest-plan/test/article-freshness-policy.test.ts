/** Do configured percentages and run clamps preserve the finite requested budget? */
import { expect, test } from "bun:test";
import { FeedIngestConfigSchema } from "@idhazh/common-contracts";
import { allocateTierBudgets, freshnessCutoff, resolveTierWindows, rejectArticleAge } from "../src/article-freshness-policy";

async function config() {
  const authored = await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();
  return FeedIngestConfigSchema.parse({
    ...authored, curate_articles: { ...authored.curate_articles, feed_quality_tiers: [
      { tier: 1, share_pct: 60, buffer_pct: 10, ladder_hours: [24, 36, 48] },
      { tier: 2, share_pct: 30, buffer_pct: 5, ladder_hours: [24, 30] },
      { tier: 3, share_pct: 10, buffer_pct: 5, ladder_hours: [24] },
    ] },
  });
}

test("largest remainders keep every requested place and ceilings never reduce a target", async () => {
  const loaded = await config();
  expect(allocateTierBudgets(loaded, 10).map(({ target, ceiling }) => [target, ceiling]))
    .toEqual([[6, 7], [3, 4], [1, 2]]);
  for (const limit of [1, 2, 3, 7, 11, 100]) {
    const budgets = allocateTierBudgets(loaded, limit);
    expect(budgets.reduce((sum, budget) => sum + budget.target, 0)).toBe(limit);
    expect(budgets.every(budget => budget.ceiling >= budget.target)).toBe(true);
  }
  loaded.curate_articles.feed_quality_tiers = [
    { tier: 8, share_pct: 50, buffer_pct: 0, ladder_hours: [24] },
    { tier: 4, share_pct: 50, buffer_pct: 0, ladder_hours: [24] },
  ];
  expect(allocateTierBudgets(loaded, 1).map(budget => budget.target)).toEqual([1, 0]);
});

test("run freshness only tightens and removes repeated steps", async () => {
  const loaded = await config();
  expect(loaded.curate_articles.feed_quality_tiers.map(rule => resolveTierWindows(rule, 30).steps))
    .toEqual([[24, 30], [24, 30], [24]]);
  expect(resolveTierWindows(loaded.curate_articles.feed_quality_tiers[0]!, 100).steps).toEqual([24, 36, 48]);
  expect(freshnessCutoff("2026-10-27T12:00:00Z", 30)).toBe("2026-10-26T06:00:00.000Z");
});

test("normal age refusal precedes a tighter run clamp and unknown time stays unknown", async () => {
  const loaded = await config();
  expect(rejectArticleAge(loaded, 1, 49, 30)?.drop_reason).toBe("REJECTED_AGE_EXCEEDS_MAX_TIER_ENVELOPE");
  expect(rejectArticleAge(loaded, 1, 31, 30)?.drop_reason).toBe("REJECTED_RUN_FRESHNESS_OVERRIDE");
  expect(rejectArticleAge(loaded, 1, 30, 30)).toBeNull();
  expect(rejectArticleAge(loaded, 1, null, 30)).toBeNull();
  expect(rejectArticleAge(loaded, 2, 31)?.details.max_age_hours).toBe(30);
  expect(() => rejectArticleAge(loaded, 99, 1)).toThrow("missing tier 99");
});

test("invalid percentages, tier inventories, age steps and unlimited output fail validation", async () => {
  const loaded = await config();
  for (const article_limit of [null, 0, -1, 0.5, Infinity, NaN, Number.MAX_SAFE_INTEGER + 1]) {
    expect(() => FeedIngestConfigSchema.parse({
      ...loaded, curate_articles: { ...loaded.curate_articles, article_limit },
    })).toThrow("article_limit");
  }
  for (const patch of [
    { share_pct: 61 }, { buffer_pct: 41 }, { ladder_hours: [24, 24] }, { ladder_hours: [0] },
  ]) {
    expect(() => FeedIngestConfigSchema.parse({
      ...loaded, curate_articles: { ...loaded.curate_articles, feed_quality_tiers:
        loaded.curate_articles.feed_quality_tiers.map((rule, index) => index ? rule : { ...rule, ...patch }) },
    })).toThrow("feed_quality_tiers");
  }
});
