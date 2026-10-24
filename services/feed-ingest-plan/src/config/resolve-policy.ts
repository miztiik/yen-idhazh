/** Which screening and scoring settings apply to one configured feed vertical? */
import {
  EffectiveFeedPolicySchema, FeedIngestConfigSchema,
  FeedScreeningPolicySchema, PlanningRunOverridesSchema, PlanningTaxonomySchema,
  SlugSchema, validatePlanningReferences,
} from "@idhazh/common-contracts";
import type {
  EffectiveFeedPolicy, FeedIngestConfig, PlanningRunOverrides, PlanningTaxonomy,
} from "@idhazh/common-contracts";

export type PlanningConfig = Readonly<{ config: FeedIngestConfig; taxonomy: PlanningTaxonomy }>;

export function loadPlanningConfig(config: unknown, taxonomy: unknown): PlanningConfig {
  const loaded = {
    config: FeedIngestConfigSchema.parse(config),
    taxonomy: PlanningTaxonomySchema.parse(taxonomy),
  };
  validatePlanningReferences(loaded.config, loaded.taxonomy);
  return loaded;
}

export function resolvePolicy(
  loaded: PlanningConfig, vertical: string, overrides: PlanningRunOverrides = {},
): EffectiveFeedPolicy {
  SlugSchema.parse(vertical);
  if (!loaded.taxonomy.verticals.some(entry => entry.id === vertical)) {
    throw new Error(`vertical.${vertical}: unknown taxonomy vertical`);
  }
  const run = PlanningRunOverridesSchema.parse(overrides);
  const patch = loaded.config.vertical_overrides[vertical];
  const { blocked_http_statuses, ...globalTriage } = loaded.config.triage;
  const triage = FeedScreeningPolicySchema.parse({
    ...globalTriage,
    ...patch?.triage,
    ...(run.freshness_hours === undefined ? {} : { max_age_hours: run.freshness_hours }),
  });
  const { article_limit, source_reliability_penalty_enabled, soft_caps, exploration_slot_share, ...globalCurate } = loaded.config.curate;
  return EffectiveFeedPolicySchema.parse({
    triage,
    curate: {
      ...globalCurate, ...patch?.curate,
      mmr_weights: { ...globalCurate.mmr_weights, ...patch?.curate?.mmr_weights },
    },
  });
}
