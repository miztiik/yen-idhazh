/** Which global numeric controls score and screen an individual candidate? */
import {
  EffectiveFeedPolicySchema, FeedIngestConfigSchema, FeedScreeningPolicySchema,
} from "@idhazh/common-contracts";
import type { EffectiveFeedPolicy, FeedIngestConfig } from "@idhazh/common-contracts";

export type PlanningConfig = Readonly<{ config: FeedIngestConfig }>;
export function loadPlanningConfig(config: unknown): PlanningConfig { return { config: FeedIngestConfigSchema.parse(config) }; }
export function resolvePolicy(loaded: PlanningConfig): EffectiveFeedPolicy {
  const { blocked_http_statuses: _statuses, ...screening } = loaded.config.triage;
  const { article_limit: _limit, source_reliability_penalty_enabled: _reliability,
    soft_caps: _caps, exploration_slot_share: _exploration, website_grouping: _websiteGrouping,
    article_quality_buckets: _buckets,
    ...curateArticles } = loaded.config.curate_articles;
  return EffectiveFeedPolicySchema.parse({
    triage: FeedScreeningPolicySchema.parse(screening), curate_articles: curateArticles,
  });
}
