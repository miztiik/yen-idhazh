/** Which numeric rules govern article screening and selection? */
import { z } from "zod";
import { NonEmptySchema, NonNegativeSchema, PositiveCountSchema, PositiveSchema, reject } from "./primitives";

export const FeedDiversityPolicySchema = z.strictObject({
  lambda_domain: NonNegativeSchema,
  lambda_feed: NonNegativeSchema,
  novelty_bonus: NonNegativeSchema,
});

export const FeedHeadlinePolicySchema = z.strictObject({
  shouting_weight: NonNegativeSchema,
  punctuation_weight: NonNegativeSchema,
  opening_mismatch_weight: NonNegativeSchema,
  opening_text_max_characters: PositiveCountSchema,
  keyword_min_letters: PositiveCountSchema,
  shouting_min_letters: PositiveCountSchema,
  shouting_min_words: PositiveCountSchema,
  shouting_min_uppercase_fraction: NonNegativeSchema.max(1),
  stop_words: z.array(NonEmptySchema.regex(/^\p{Ll}+$/u)),
  punctuation_patterns: z.array(NonEmptySchema).min(1),
}).superRefine((value, ctx) => {
  if (new Set(value.stop_words).size !== value.stop_words.length) {
    reject(ctx, "stop_words must contain distinct lowercase terms", ["stop_words"]);
  }
  for (const [index, pattern] of value.punctuation_patterns.entries()) {
    try { new RegExp(pattern, "u"); }
    catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
      reject(ctx, "punctuation_patterns must contain valid Unicode regular expressions", ["punctuation_patterns", index]);
    }
  }
});

export const FeedSubstancePolicySchema = z.strictObject({
  word_count_ramp_end: PositiveCountSchema,
  word_count_sweet_spot_max: PositiveCountSchema,
  word_count_plateau_start: PositiveCountSchema,
  length_scores: z.strictObject({ full: NonNegativeSchema }),
  long_form_floor_score: NonNegativeSchema,
  entity_density_weight: NonNegativeSchema,
  entity_density_full_credit: PositiveSchema,
  headline_hype_penalty: NonNegativeSchema,
  substantive_paragraph_min_words: PositiveCountSchema,
  substantive_paragraph_min_sentences: PositiveCountSchema,
  headline: FeedHeadlinePolicySchema,
}).superRefine((value, ctx) => {
  if (value.word_count_sweet_spot_max < value.word_count_ramp_end) {
    reject(ctx, "word_count_sweet_spot_max must be at least word_count_ramp_end", ["word_count_sweet_spot_max"]);
  }
  if (value.word_count_plateau_start <= value.word_count_sweet_spot_max) {
    reject(ctx, "word_count_plateau_start must exceed word_count_sweet_spot_max", ["word_count_plateau_start"]);
  }
  if (value.long_form_floor_score > value.length_scores.full) {
    reject(ctx, "long_form_floor_score must not exceed length_scores.full", ["long_form_floor_score"]);
  }
});

export const FeedScreeningPolicySchema = z.strictObject({
  min_words: PositiveCountSchema.default(180),
  recency_half_life_hours: PositiveSchema,
  recency_weight: NonNegativeSchema,
});

export const FeedCurationPolicySchema = z.strictObject({
  source_authority_weight: NonNegativeSchema,
});

export const EffectiveFeedPolicySchema = z.strictObject({
  triage: FeedScreeningPolicySchema,
  curate_articles: FeedCurationPolicySchema,
});

export type EffectiveFeedPolicy = z.infer<typeof EffectiveFeedPolicySchema>;
