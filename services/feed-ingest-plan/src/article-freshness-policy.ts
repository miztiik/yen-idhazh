/** Which configured age windows and integer tier budgets apply to one saved request? */
import { PositiveCountSchema } from "@idhazh/common-contracts";
import type { FeedIngestConfig } from "@idhazh/common-contracts";

type TierRule = FeedIngestConfig["curate_articles"]["feed_quality_tiers"][number];
const millisecondsPerHour = 60 * 60 * 1000;

export function resolveTierWindows(rule: TierRule, freshnessHours?: number) {
  const steps = [...new Set(rule.ladder_hours.map(hours =>
    freshnessHours === undefined ? hours : Math.min(hours, freshnessHours)))];
  return { steps, normalMaximum: rule.ladder_hours.at(-1)!, maximum: steps.at(-1)! };
}

export function requireTierRule(config: FeedIngestConfig, tier: number): TierRule {
  const rule = config.curate_articles.feed_quality_tiers.find(rule => rule.tier === tier);
  if (rule === undefined) throw new Error(`curate_articles.feed_quality_tiers: missing tier ${tier}`);
  return rule;
}

export function freshnessCutoff(evaluatedAt: string, hours: number): string {
  return new Date(Date.parse(evaluatedAt) - hours * millisecondsPerHour).toISOString();
}

export function rejectArticleAge(config: FeedIngestConfig, tier: number, ageHours: number | null, freshnessHours?: number) {
  const windows = resolveTierWindows(requireTierRule(config, tier), freshnessHours);
  if (ageHours === null) return null;
  if (ageHours > windows.normalMaximum) return {
    drop_reason: "REJECTED_AGE_EXCEEDS_MAX_TIER_ENVELOPE" as const,
    details: { age_hours: ageHours, max_age_hours: windows.normalMaximum },
  };
  if (ageHours > windows.maximum) return {
    drop_reason: "REJECTED_RUN_FRESHNESS_OVERRIDE" as const,
    details: { age_hours: ageHours, max_age_hours: windows.maximum },
  };
  return null;
}

export function allocateTierBudgets(config: FeedIngestConfig, limit: number) {
  PositiveCountSchema.parse(limit);
  const budgets = config.curate_articles.feed_quality_tiers.map((rule, order) => {
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
