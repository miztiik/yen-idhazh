/** Which numeric rules govern article screening and selection? */
import { z } from "zod";
import { CountSchema, NonNegativeSchema, PositiveCountSchema, PositiveSchema } from "./primitives";

export const FeedScreeningPolicySchema = z.strictObject({
  min_words: PositiveCountSchema.default(180),
  max_age_hours: PositiveSchema,
  recency_half_life_hours: PositiveSchema,
  recency_weight: NonNegativeSchema,
});

export const FeedPenaltyWeightsSchema = z.strictObject({
  lambda_source: NonNegativeSchema,
  lambda_website_group: NonNegativeSchema,
});

export const FeedCurationPolicySchema = z.strictObject({
  source_authority_weight: NonNegativeSchema,
  base_source_allowance: CountSchema,
  mmr_weights: FeedPenaltyWeightsSchema,
});

export const EffectiveFeedPolicySchema = z.strictObject({
  triage: FeedScreeningPolicySchema,
  curate_articles: FeedCurationPolicySchema,
});
export const PlanningRunOverridesSchema = z.strictObject({
  freshness_hours: PositiveSchema.optional(),
});

export type EffectiveFeedPolicy = z.infer<typeof EffectiveFeedPolicySchema>;
export type PlanningRunOverrides = z.infer<typeof PlanningRunOverridesSchema>;
