/** Do per-request age controls remain separate from source authority and concurrent runs? */
import { expect, test } from "bun:test";
import { FeedIngestConfigSchema, SourceBasedQualityBucketsSchema } from "@idhazh/common-contracts";
import { parseAgeWindows, resolveRunPolicy } from "../src/config/resolve-run-policy";
import { allocateSourceBasedQualityBucketBudgets, rejectArticleAge } from "../src/article-freshness-policy";
import { readWorkflowRequest } from "../scripts/feed-ingest-plan-workflow-inputs";
import { formatWorkflowPolicy } from "../scripts/feed-ingest-plan-policy-report";

async function config() {
  const authored = await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();
  return FeedIngestConfigSchema.parse({
    ...authored, curate_articles: { ...authored.curate_articles, source_based_quality_buckets: [
      { id: "institutional", source_tier_id: 1, share_pct: 60, buffer_pct: 10, ladder_hours: [24, 36, 48] },
      { id: "trade-press", source_tier_id: 2, share_pct: 30, buffer_pct: 5, ladder_hours: [24, 30] },
      { id: "community", source_tier_id: 3, share_pct: 10, buffer_pct: 5, ladder_hours: [24] },
    ] },
  });
}

test("blank age controls retain config and populated controls require strictly increasing positive ages", () => {
  expect(parseAgeWindows(" \t")).toBeUndefined();
  expect(parseAgeWindows(undefined)).toBeUndefined();
  expect(parseAgeWindows("12, 24,36.5")).toEqual([12, 24, 36.5]);
  for (const value of ["0", "-1", "24,24", "36,24", "24,", ",24", "24,,48", "NaN", "Infinity", "0x18", "1e2", "one"]) {
    expect(() => parseAgeWindows(value)).toThrow();
  }
  expect(readWorkflowRequest({
    INSTITUTIONAL_AGE_HOURS: "12, 24", TRADE_PRESS_AGE_HOURS: "  ", COMMUNITY_AGE_HOURS: "6",
  })).toEqual({ institutional_age_hours: [12, 24], community_age_hours: [6] });
});

test("source-based budgets use list order and source tier mapping, not matching identifiers", async () => {
  const original = await config();
  const changed = FeedIngestConfigSchema.parse({
    ...original, curate_articles: { ...original.curate_articles, source_based_quality_buckets: [
      { id: "third-first", source_tier_id: 3, share_pct: 50, buffer_pct: 0, ladder_hours: [6] },
      { id: "first-second", source_tier_id: 1, share_pct: 50, buffer_pct: 0, ladder_hours: [12] },
    ] },
  });
  expect(allocateSourceBasedQualityBucketBudgets(changed, 3).map(budget =>
    [budget.rule.id, budget.target])).toEqual([["third-first", 2], ["first-second", 1]]);
  expect(rejectArticleAge(changed, 3, 7)?.details.max_age_hours).toBe(6);
  expect(rejectArticleAge(changed, 1, 7)).toBeNull();
  const rules = changed.curate_articles.source_based_quality_buckets;
  expect(SourceBasedQualityBucketsSchema.safeParse([rules[0], { ...rules[1], id: rules[0]!.id }]).success).toBe(false);
  expect(SourceBasedQualityBucketsSchema.safeParse([rules[0], { ...rules[1], source_tier_id: 3 }]).success).toBe(false);
});

test("effective settings do not mutate the shared config or another request", async () => {
  const original = await config();
  const before = structuredClone(original);
  const [first, second] = await Promise.all([
    Promise.resolve().then(() => resolveRunPolicy(original, { institutional_age_hours: [6, 12] })),
    Promise.resolve().then(() => resolveRunPolicy(original, { institutional_age_hours: [48, 72], trade_press_age_hours: [30] })),
  ]);
  expect(original).toEqual(before);
  expect(first.curate_articles.source_based_quality_buckets[0]!.ladder_hours).toEqual([6, 12]);
  expect(second.curate_articles.source_based_quality_buckets[0]!.ladder_hours).toEqual([48, 72]);
  expect(first.curate_articles.source_based_quality_buckets[1]!.ladder_hours).toEqual(
    original.curate_articles.source_based_quality_buckets[1]!.ladder_hours);
  expect(first.curate_articles.source_authority_weight).toBe(original.curate_articles.source_authority_weight);
  first.curate_articles.source_based_quality_buckets[0]!.ladder_hours.push(18);
  expect(second.curate_articles.source_based_quality_buckets[0]!.ladder_hours).toEqual([48, 72]);
  expect(original).toEqual(before);
  expect(() => resolveRunPolicy(original, { community_age_hours: [24, 12] })).toThrow();
});

test("policy reporting records effective ages and names their actual origin", async () => {
  const original = await config();
  const settings = await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json();
  const report = formatWorkflowPolicy({
    config: original, request: { institutional_age_hours: [6, 12], community_age_hours: [3] },
    history: settings.collect, parser_concurrency: 4,
  }, true);
  expect(report.rows.find(([name]) => name === "institutional age steps (hours)"))
    .toEqual(["institutional age steps (hours)", "6 / 12", "workflow override"]);
  expect(report.rows.find(([name]) => name === "trade-press age steps (hours)"))
    .toEqual(["trade-press age steps (hours)", "24 / 30", "configuration"]);
  expect(report.rows.find(([name]) => name === "community age steps (hours)"))
    .toEqual(["community age steps (hours)", "3", "workflow override"]);
  expect(original.curate_articles.source_based_quality_buckets[0]!.ladder_hours).toEqual([24, 36, 48]);
});
