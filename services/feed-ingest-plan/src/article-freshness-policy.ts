/** Which configured age windows and article-quality bucket budgets apply to one saved request? */
import { PositiveCountSchema } from "@idhazh/common-contracts";
import type { FeedIngestConfig } from "@idhazh/common-contracts";

type ArticleQualityBucketRule = FeedIngestConfig["curate_articles"]["article_quality_buckets"][number];
const millisecondsPerHour = 60 * 60 * 1000;

export function resolveArticleQualityBucketWindows(rule: ArticleQualityBucketRule) {
  const steps = [...new Set(rule.ladder_hours)];
  return { steps, maximum: steps.at(-1)! };
}

export function requireArticleQualityBucket(config: FeedIngestConfig, sourceClass: number): ArticleQualityBucketRule {
  const rule = config.curate_articles.article_quality_buckets.find(rule => rule.tier === sourceClass);
  if (rule === undefined) throw new Error(`curate_articles.article_quality_buckets: missing source class ${sourceClass}`);
  return rule;
}

export function freshnessCutoff(evaluatedAt: string, hours: number): string {
  return new Date(Date.parse(evaluatedAt) - hours * millisecondsPerHour).toISOString();
}

export function rejectArticleAge(config: FeedIngestConfig, sourceClass: number, ageHours: number | null) {
  const windows = resolveArticleQualityBucketWindows(requireArticleQualityBucket(config, sourceClass));
  if (ageHours === null) return null;
  if (ageHours > windows.maximum) return {
    drop_reason: "REJECTED_AGE_EXCEEDS_MAX_TIER_ENVELOPE" as const,
    details: { age_hours: ageHours, max_age_hours: windows.maximum },
  };
  return null;
}

export function allocateArticleQualityBucketBudgets(config: FeedIngestConfig, limit: number) {
  PositiveCountSchema.parse(limit);
  const budgets = config.curate_articles.article_quality_buckets.map((rule, order) => {
    const exact = limit * rule.share_pct / 100;
    return {
      rule, order, target: Math.floor(exact), remainder: exact - Math.floor(exact),
      ceiling: Math.ceil(limit * (rule.share_pct + rule.buffer_pct) / 100),
    };
  });
  const places = limit - budgets.reduce((sum, budget) => sum + budget.target, 0);
  const ordered = [...budgets].sort((a, b) => b.remainder - a.remainder || a.order - b.order);
  for (let index = 0; index < places; index++) ordered[index]!.target++;
  return budgets.map(({ rule, target, ceiling }) => ({ rule, target, ceiling: Math.max(target, ceiling) }));
}
