/** Which global numeric controls score and screen an individual candidate? */
import {
  EffectiveFeedPolicySchema, FeedHarvestConfigSchema, FeedIngestConfigSchema, FeedScreeningPolicySchema,
} from "@idhazh/common-contracts";
import type { EffectiveFeedPolicy, FeedIngestConfig } from "@idhazh/common-contracts";
import { z } from "zod";

export type PlanningConfig = Readonly<{ config: FeedIngestConfig }>;
const AuthoredWordLimitSchema = z.object({
  harvest: z.object({ max_input_words: FeedHarvestConfigSchema.shape.max_input_words.unwrap() }),
});
export function loadPlanningConfig(config: unknown): PlanningConfig {
  AuthoredWordLimitSchema.parse(config);
  return { config: FeedIngestConfigSchema.parse(config) };
}
export function resolvePolicy(loaded: PlanningConfig): EffectiveFeedPolicy {
  const { blocked_http_statuses: _statuses, ...screening } = loaded.config.triage;
  const { article_limit: _limit, source_reliability_penalty_enabled: _reliability,
    website_grouping: _websiteGrouping,
    global_age_ceiling_hours: _ageCeiling, diversity: _diversity, substance: _substance,
    ...curateArticles } = loaded.config.curate_articles;
  return EffectiveFeedPolicySchema.parse({
    triage: FeedScreeningPolicySchema.parse(screening), curate_articles: curateArticles,
  });
}
