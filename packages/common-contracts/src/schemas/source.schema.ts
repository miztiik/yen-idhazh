/** Which recorded source facts and independent labels accompanied an article? */
import { z } from "zod";
import { CountSchema, FiniteSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema, PositiveSchema, Sha256Schema, SlugSchema, UrlSchema, reject } from "./primitives";

export const SourceKindSchema = SlugSchema;
export const SourceTierSchema = PositiveCountSchema;
export const SourceFormSchema = z.enum(["article", "abstract"]);
export const LifecycleStatusSchema = z.enum(["draft", "active", "retired"]);
export const SourceSnapshotSchema = z.strictObject({
  source_id: SlugSchema, feed_url: UrlSchema, title: NonEmptySchema,
  vertical: SlugSchema, kind: SourceKindSchema, tier: SourceTierSchema,
  form: SourceFormSchema, status: LifecycleStatusSchema,
  weight: FiniteSchema.min(0).max(1), applied_tier_weight: FiniteSchema.min(0).max(1),
});
export const ArticleLabelsSchema = z.strictObject({
  assigned_desk: SlugSchema.nullable(), lenses: z.array(SlugSchema).nullable(),
  event_types: z.array(SlugSchema).nullable(), event_cluster_id: NonEmptySchema.nullable(),
  entities: z.array(SlugSchema).nullable(), origin: NonEmptySchema.nullable(),
  matcher_version: NonEmptySchema.nullable(),
}).superRefine((value, ctx) => {
  if ((value.origin === null) !== (value.matcher_version === null)) reject(ctx, "label origin and matcher_version must be available together");
  if ([value.assigned_desk, value.lenses, value.event_types, value.event_cluster_id, value.entities].some(v => v !== null) && value.origin === null) reject(ctx, "known labels require origin and matcher_version");
});
export const PenaltyEvidenceSchema = z.strictObject({
  available: z.boolean(), value: NonNegativeSchema.nullable(),
}).superRefine((value, ctx) => {
  if (value.available !== (value.value !== null)) reject(ctx, "penalty availability must match its value");
});
export const OperationalHistorySchema = z.strictObject({
  success_fraction: NonNegativeSchema.max(1),
  attempted: PositiveCountSchema, window_days: PositiveCountSchema,
});
export const SourceReliabilityPenaltySchema = z.strictObject({
  enabled: z.boolean(), source_authority_score: NonNegativeSchema,
  reliability_floor: NonNegativeSchema.max(1), history: OperationalHistorySchema.nullable(),
  production_factor: NonNegativeSchema.max(1).nullable(), value: NonNegativeSchema.nullable(),
}).superRefine((value, ctx) => {
  if (value.history === null) {
    if (value.production_factor !== null || value.value !== null) reject(ctx, "unavailable reliability carries no factor or measured penalty");
  } else {
    const factor = Math.max(value.reliability_floor, value.history.success_fraction);
    if (value.production_factor !== factor) reject(ctx, "reliability factor must match the measured fraction and floor");
    if (value.value !== (value.enabled ? value.source_authority_score * (1 - factor) : 0)) {
      reject(ctx, "reliability penalty must reduce only source authority");
    }
  }
});
export const ScoreEvidenceSchema = z.strictObject({
  base_article_score: FiniteSchema, marginal_score: FiniteSchema,
  source_reliability: SourceReliabilityPenaltySchema.nullable().default(null),
  source: PenaltyEvidenceSchema, source_kind: PenaltyEvidenceSchema,
  domain: PenaltyEvidenceSchema, vertical: PenaltyEvidenceSchema,
  desk: PenaltyEvidenceSchema, lens: PenaltyEvidenceSchema,
  event_type: PenaltyEvidenceSchema, event_cluster: PenaltyEvidenceSchema,
  entity: PenaltyEvidenceSchema, coverage: PenaltyEvidenceSchema,
  source_allowance: CountSchema, bonus_uncovered_event_cluster: z.boolean(),
  bonus_underrepresented_vertical: z.boolean(), bonus_unique_evidence: z.boolean(),
  carrier_outlets: z.array(NonEmptySchema), representative_url_key: Sha256Schema.nullable(),
  replacement_url_key: Sha256Schema.nullable(), exploration_slot: z.boolean(),
  cap_relaxations: z.array(z.enum(["distinct_sources", "source_share"])),
});
export const PreviousScoreEvidenceSchema = ScoreEvidenceSchema.omit({ source_reliability: true });
export const PolicyIdentitySchema = z.strictObject({
  policy_version: NonEmptySchema, config_sha256: Sha256Schema,
  min_words_article: PositiveCountSchema, min_words_abstract: PositiveCountSchema,
  max_age_hours: PositiveSchema, recency_half_life_hours: PositiveSchema,
  recency_weight: NonNegativeSchema, source_authority_weight: NonNegativeSchema,
  base_source_allowance: CountSchema, bonus_uncovered_event_cluster: CountSchema,
  bonus_underrepresented_vertical: CountSchema, bonus_unique_evidence: CountSchema,
  lambda_source: NonNegativeSchema, lambda_source_kind: NonNegativeSchema,
  lambda_domain: NonNegativeSchema, lambda_vertical: NonNegativeSchema,
  lambda_desk: NonNegativeSchema, lambda_lens: NonNegativeSchema,
  lambda_event_type: NonNegativeSchema, lambda_event_cluster: NonNegativeSchema,
  lambda_entity: NonNegativeSchema, lambda_coverage: NonNegativeSchema,
});
export type SourceSnapshot = z.infer<typeof SourceSnapshotSchema>;
export type ArticleLabels = z.infer<typeof ArticleLabelsSchema>;
export type ScoreEvidence = z.infer<typeof ScoreEvidenceSchema>;
export type OperationalHistory = z.infer<typeof OperationalHistorySchema>;
export type SourceReliabilityPenalty = z.infer<typeof SourceReliabilityPenaltySchema>;
export type PolicyIdentity = z.infer<typeof PolicyIdentitySchema>;
