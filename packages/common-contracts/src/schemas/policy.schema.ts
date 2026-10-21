/** Which candidate settings may a vertical override without changing global controls? */
import { z } from "zod";
import { CountSchema, NonNegativeSchema, PositiveCountSchema, PositiveSchema } from "./primitives";

export const FeedScreeningPolicySchema = z.strictObject({
  min_words_article: PositiveCountSchema,
  min_words_abstract: PositiveCountSchema,
  max_age_hours: PositiveSchema,
  recency_half_life_hours: PositiveSchema,
  recency_weight: NonNegativeSchema,
});

export const FeedPenaltyWeightsSchema = z.strictObject({
  lambda_source: NonNegativeSchema,
  lambda_source_kind: NonNegativeSchema,
  lambda_domain: NonNegativeSchema,
  lambda_vertical: NonNegativeSchema,
  lambda_desk: NonNegativeSchema,
  lambda_lens: NonNegativeSchema,
  lambda_event_type: NonNegativeSchema,
  lambda_event_cluster: NonNegativeSchema,
  lambda_entity: NonNegativeSchema,
  lambda_coverage: NonNegativeSchema,
});

export const FeedCurationPolicySchema = z.strictObject({
  source_authority_weight: NonNegativeSchema,
  base_source_allowance: CountSchema,
  bonus_uncovered_event_cluster: CountSchema,
  bonus_underrepresented_vertical: CountSchema,
  bonus_unique_evidence: CountSchema,
  mmr_weights: FeedPenaltyWeightsSchema,
});

export const FeedScreeningPatchSchema = FeedScreeningPolicySchema.partial();
export const FeedPenaltyWeightsPatchSchema = FeedPenaltyWeightsSchema.partial();
export const FeedCurationPatchSchema = FeedCurationPolicySchema.omit({ mmr_weights: true }).partial().extend({
  mmr_weights: FeedPenaltyWeightsPatchSchema.optional(),
});
export const VerticalPolicyOverrideSchema = z.strictObject({
  triage: FeedScreeningPatchSchema.optional(),
  curate: FeedCurationPatchSchema.optional(),
});
export const EffectiveFeedPolicySchema = z.strictObject({
  triage: FeedScreeningPolicySchema,
  curate: FeedCurationPolicySchema,
});
export const PlanningRunOverridesSchema = z.strictObject({
  freshness_hours: PositiveSchema.optional(),
});

export type EffectiveFeedPolicy = z.infer<typeof EffectiveFeedPolicySchema>;
export type PlanningRunOverrides = z.infer<typeof PlanningRunOverridesSchema>;
