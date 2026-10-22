/** Which measured evidence decided a candidate at one planning stage? */
import { z } from "zod";
import { ArticleLabelsSchema, PolicyIdentitySchema, ScoreEvidenceSchema, SourceFormSchema, SourceSnapshotSchema } from "./source.schema";
import { DropReasonSchema, REASON_STAGES } from "./rejection.schema";
import { CountSchema, DateStampSchema, FiniteSchema, NonEmptySchema, PlanningStageSchema, PositiveCountSchema, PositiveSchema, Sha256Schema, SlugSchema, TimestampSchema, UrlSchema, deriveUrlKey, reject } from "./primitives";
import { CONTRACT_VERSION, FEED_INGEST_AUDIT_VERSION, HARVEST_DIAGNOSTICS_VERSION } from "../version";
import { HarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";

export const VerdictStatusSchema = z.enum(["not_assessed", "assessed"]);
export const ArticleAssessmentRecordSchema = z.strictObject({
  version: z.literal(HARVEST_DIAGNOSTICS_VERSION).default(HARVEST_DIAGNOSTICS_VERSION), date: DateStampSchema, correlation_id: NonEmptySchema,
  diagnostics: HarvestDiagnosticsSchema.nullable().default(null),
  candidate_id: Sha256Schema, source_id: SlugSchema, source: SourceSnapshotSchema, labels: ArticleLabelsSchema,
  canonical_url: UrlSchema.nullable(), url_key: Sha256Schema.nullable(),
  stage: PlanningStageSchema, decision: z.enum(["admitted", "rejected", "selected"]),
  reason: DropReasonSchema.nullable(), observed_at: TimestampSchema, policy: PolicyIdentitySchema,
  timing_at: TimestampSchema.nullable(),
  timing_basis: z.enum(["published_at", "first_seen", "fetched_at", "unavailable"]),
  age_hours: FiniteSchema.nullable(), max_age_hours: PositiveSchema.nullable(),
  extracted_word_count: CountSchema.nullable(), source_form: SourceFormSchema,
  extraction_outcome: z.enum(["success", "failed", "not_attempted", "unavailable"]),
  word_threshold: PositiveCountSchema.nullable(), author_present: z.boolean().nullable(),
  publisher_identity: NonEmptySchema.nullable(), attribution_status: z.enum(["available", "unavailable"]),
  paywall: z.boolean().nullable(), categories: z.array(NonEmptySchema).nullable(),
  required_fields_present: z.boolean().nullable(), suitability_status: z.enum(["available", "unavailable"]),
  informative_verdict_status: VerdictStatusSchema, informative_verdict: z.boolean().nullable(),
  informative_evaluator_version: NonEmptySchema.nullable(),
  suitability_verdict_status: VerdictStatusSchema, suitability_verdict: z.boolean().nullable(),
  suitability_evaluator_version: NonEmptySchema.nullable(), score_evidence: ScoreEvidenceSchema.nullable(),
  score_evidence_status: VerdictStatusSchema,
}).superRefine((value, ctx) => {
  if (value.source_id !== value.source.source_id) reject(ctx, "source_id must match the recorded source snapshot");
  if (value.date !== value.observed_at.slice(0, 10)) reject(ctx, "date must match the UTC observation day");
  if ((value.canonical_url === null) !== (value.url_key === null)) reject(ctx, "article URL and url_key are available together");
  if (value.canonical_url !== null && value.url_key !== deriveUrlKey(value.canonical_url)) reject(ctx, "url_key must match canonical_url");
  if ((value.decision === "rejected") !== (value.reason !== null)) reject(ctx, "only rejected decisions carry a rejection reason");
  if (value.reason !== null && !(REASON_STAGES[value.reason] as readonly string[]).includes(value.stage)) reject(ctx, "rejection reason is not valid for the recorded stage");
  if (value.timing_basis === "unavailable") {
    if (value.timing_at !== null || value.age_hours !== null) reject(ctx, "unavailable timing carries no timestamp or age");
  } else if (value.timing_at === null || value.age_hours === null) reject(ctx, "available timing carries its measured timestamp and age");
  if ((value.age_hours === null) !== (value.max_age_hours === null)) reject(ctx, "age and its effective cutoff are recorded together");
  if (value.extraction_outcome === "success") {
    if (value.extracted_word_count === null || value.word_threshold === null) reject(ctx, "successful extraction records count and threshold");
  } else if (value.extraction_outcome === "failed") {
    if (value.word_threshold === null) reject(ctx, "failed extraction records the applied word threshold");
  } else if (value.extracted_word_count !== null || value.word_threshold !== null) reject(ctx, "unperformed extraction has no count or threshold");
  if (value.attribution_status === "unavailable") {
    if (value.author_present !== null || value.publisher_identity !== null) reject(ctx, "unavailable attribution carries no inferred values");
  } else if (value.author_present === null) reject(ctx, "available attribution records whether a byline exists");
  const suitability = [value.paywall, value.categories, value.required_fields_present];
  if (value.suitability_status === "unavailable" && suitability.some(v => v !== null)) reject(ctx, "unavailable suitability carries no inferred values");
  if (value.suitability_status === "available" && suitability.some(v => v === null)) reject(ctx, "available suitability records each required check");
  for (const [status, verdict, evaluator, name] of [
    [value.informative_verdict_status, value.informative_verdict, value.informative_evaluator_version, "informative"],
    [value.suitability_verdict_status, value.suitability_verdict, value.suitability_evaluator_version, "suitability"],
  ] as const) {
    if ((status === "assessed") !== (verdict !== null && evaluator !== null)) reject(ctx, `${name} verdict and evaluator version match assessed status`);
  }
  if ((value.score_evidence_status === "assessed") !== (value.score_evidence !== null)) reject(ctx, "score evidence must match its availability status");
});
export type ArticleAssessmentRecord = z.infer<typeof ArticleAssessmentRecordSchema>;

const { diagnostics: _diagnostics, ...previousFields } = ArticleAssessmentRecordSchema.shape;
export const PreviousArticleAssessmentSchema = z.strictObject({
  ...previousFields, version: z.literal("2026-10-22"),
  reason: DropReasonSchema.exclude(["EXTRACT_FAILED", "EXTRACT_EMPTY"]).nullable(),
});
const { timing_at: _timingAt, timing_basis: _timingBasis, ...legacyFields } = PreviousArticleAssessmentSchema.shape;
export const LegacyArticleAssessmentSchema = z.strictObject({
  ...legacyFields,
  version: z.literal("2026-10-20"),
  effective_published_at: TimestampSchema.nullable(),
  publication_clock: z.enum(["published_at", "fetched_at", "unavailable"]),
  age_hours: FiniteSchema.min(0).nullable(),
});

export function migrateArticleAssessment(row: object): ArticleAssessmentRecord {
  const { effective_published_at, publication_clock, ...rest } = LegacyArticleAssessmentSchema.parse(row);
  return ArticleAssessmentRecordSchema.parse({
    ...rest, version: HARVEST_DIAGNOSTICS_VERSION,
    timing_at: effective_published_at, timing_basis: publication_clock,
  });
}

export const ArticleAssessmentContract = {
  schema: ArticleAssessmentRecordSchema,
  schemaVersion: HARVEST_DIAGNOSTICS_VERSION,
  legacyVersions: {
    [CONTRACT_VERSION]: { schema: LegacyArticleAssessmentSchema, migrate: migrateArticleAssessment },
    [FEED_INGEST_AUDIT_VERSION]: {
      schema: PreviousArticleAssessmentSchema,
      migrate: (row: object): ArticleAssessmentRecord => ArticleAssessmentRecordSchema.parse({
        ...PreviousArticleAssessmentSchema.parse(row), version: HARVEST_DIAGNOSTICS_VERSION,
      }),
    },
  },
};
