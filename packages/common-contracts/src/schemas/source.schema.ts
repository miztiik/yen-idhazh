/** Which recorded source facts and independent labels accompanied an article? */
import { z } from "zod";
import { CountSchema, DateStampSchema, FiniteSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema, PositiveSchema, Sha256Schema, SlugSchema, UrlSchema, reject } from "./primitives";

export const SourceKindSchema = SlugSchema;
export const SourceTierSchema = PositiveCountSchema;
export const PublisherIdSchema = SlugSchema;
export const SourceFormSchema = z.enum(["article", "abstract"]);
export const LifecycleStatusSchema = z.enum(["draft", "active", "retired"]);
export const SourceSnapshotSchema = z.strictObject({
  source_id: SlugSchema, publisher_id: PublisherIdSchema.nullable().default(null),
  feed_url: UrlSchema, title: NonEmptySchema,
  vertical: SlugSchema, kind: SourceKindSchema, tier: SourceTierSchema,
  form: SourceFormSchema, status: LifecycleStatusSchema,
  weight: FiniteSchema.min(0).max(1), applied_tier_weight: FiniteSchema.min(0).max(1),
});
const { publisher_id: _publisherId, ...previousSourceSnapshotFields } = SourceSnapshotSchema.shape;
export const PreviousSourceSnapshotSchema = z.strictObject(previousSourceSnapshotFields);
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
export const SourceOperationalEvidenceSchema = z.strictObject({
  status: z.enum(["qualified", "insufficient_support", "unavailable"]),
  state_status: z.enum(["current", "stale_fallback", "unavailable"]),
  state_revision: PositiveCountSchema.nullable(),
  window_days: PositiveCountSchema,
  window_start: DateStampSchema.nullable(), window_end: DateStampSchema.nullable(),
  total_requests: CountSchema.nullable(), wasted_requests: CountSchema.nullable(),
  observed_attempted_opportunities: CountSchema, observed_measured_opportunities: CountSchema,
  coverage: NonNegativeSchema.max(1).nullable(),
  operational_penalty: NonNegativeSchema.max(1).nullable(),
}).superRefine((value, ctx) => {
  if ((value.total_requests === null) !== (value.wasted_requests === null)) {
    reject(ctx, "request totals and waste are available together");
  }
  if (value.total_requests !== null && value.wasted_requests! > value.total_requests) {
    reject(ctx, "wasted requests cannot exceed total requests");
  }
  if (value.observed_measured_opportunities > value.observed_attempted_opportunities) {
    reject(ctx, "measured opportunities cannot exceed attempted opportunities");
  }
  if (value.window_start !== null && value.window_end !== null && value.window_start > value.window_end) {
    reject(ctx, "operational evidence window starts after it ends");
  }
  if (value.state_status === "unavailable") {
    if ([value.state_revision, value.window_start, value.window_end, value.operational_penalty]
      .some(item => item !== null) || value.status !== "unavailable") {
      reject(ctx, "unavailable state carries no saved revision, window or adjustment");
    }
  } else if (value.state_revision === null || value.window_start === null || value.window_end === null) {
    reject(ctx, "a saved operational state records its revision and original window");
  }
  if (value.status === "qualified") {
    if (value.total_requests === null || value.total_requests === 0
      || value.coverage === null || value.operational_penalty === null) {
      reject(ctx, "qualified operational evidence has positive measured requests and coverage");
    }
  } else if (value.operational_penalty !== null) {
    reject(ctx, "unqualified operational evidence has no score adjustment");
  }
});
export const PublisherExposurePenaltySchema = z.strictObject({
  day: DateStampSchema, publisher_id: PublisherIdSchema.nullable(),
  history_status: z.enum(["available", "unavailable"]),
  published_today: CountSchema.nullable(), selected_so_far: CountSchema,
  planned_slots: PositiveCountSchema, coefficient: NonNegativeSchema,
  exposure: NonNegativeSchema.max(1).nullable(), value: NonNegativeSchema.nullable(),
}).superRefine((value, ctx) => {
  const known = value.publisher_id !== null;
  if ((value.published_today !== null) !== (known && value.history_status === "available")) {
    reject(ctx, "publication count requires known publisher and available history");
  }
  if (!known) {
    if (value.selected_so_far !== 0 || value.exposure !== null || value.value !== null) {
      reject(ctx, "unknown publisher carries no count or adjustment");
    }
  } else {
    const exposure = Math.min(1, ((value.published_today ?? 0) + value.selected_so_far) / value.planned_slots);
    if (value.exposure !== exposure || value.value !== value.coefficient * exposure) {
      reject(ctx, "publisher adjustment must match capped day and selection counts");
    }
  }
});
export const ScoreEvidenceSchema = z.strictObject({
  base_article_score: FiniteSchema, marginal_score: FiniteSchema,
  source_reliability: SourceReliabilityPenaltySchema.nullable().default(null),
  source_operational: SourceOperationalEvidenceSchema.nullable().default(null),
  publisher_exposure: PublisherExposurePenaltySchema.nullable().default(null),
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
}).superRefine((value, ctx) => {
  if (value.publisher_exposure !== null && value.source.available) {
    reject(ctx, "publisher exposure replaces feed crowding rather than charging both");
  }
});
const {
  source_operational: _sourceOperational, publisher_exposure: _publisherExposure,
  ...previousPublisherScoreFields
} = ScoreEvidenceSchema.shape;
export const PreviousPublisherScoreEvidenceSchema = z.strictObject(previousPublisherScoreFields);
const { source_operational: _previousSourceOperational, ...previousExposureScoreFields } = ScoreEvidenceSchema.shape;
export const PreviousOperationalScoreEvidenceSchema = z.strictObject(previousExposureScoreFields);
export const PreviousScoreEvidenceSchema = PreviousPublisherScoreEvidenceSchema.omit({ source_reliability: true });
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
export type SourceOperationalEvidence = z.infer<typeof SourceOperationalEvidenceSchema>;
export type PolicyIdentity = z.infer<typeof PolicyIdentitySchema>;
