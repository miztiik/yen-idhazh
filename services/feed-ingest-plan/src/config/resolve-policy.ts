/** Apply the planner's global numeric controls and explicit per-run age override. */
import {
  EffectiveFeedPolicySchema, FeedIngestConfigSchema, FeedScreeningPolicySchema, PlanningRunOverridesSchema,
} from "@idhazh/common-contracts";
import type { EffectiveFeedPolicy, FeedIngestConfig, PlanningRunOverrides } from "@idhazh/common-contracts";

export type PlanningConfig = Readonly<{ config: FeedIngestConfig }>;
export function loadPlanningConfig(config: unknown): PlanningConfig { return { config: FeedIngestConfigSchema.parse(config) }; }
export function resolvePolicy(loaded: PlanningConfig, overrides: PlanningRunOverrides = {}): EffectiveFeedPolicy {
  const run = PlanningRunOverridesSchema.parse(overrides);
  const { blocked_http_statuses: _statuses, ...screening } = loaded.config.triage;
  const { article_limit: _limit, source_reliability_penalty_enabled: _reliability,
    soft_caps: _caps, exploration_slot_share: _exploration, website_grouping: _websiteGrouping,
    ...curateArticles } = loaded.config.curate_articles;
  return EffectiveFeedPolicySchema.parse({
    triage: FeedScreeningPolicySchema.parse({
      ...screening, ...(run.freshness_hours === undefined ? {} : { max_age_hours: run.freshness_hours }),
    }), curate_articles: curateArticles,
  });
}
