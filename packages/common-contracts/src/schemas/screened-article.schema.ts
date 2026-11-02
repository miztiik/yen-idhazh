/** Which measured screening evidence and numerical records can selection consume? */
import { z } from "zod";
import { SCREENED_ARTICLE_VERSION } from "../version";
import { FeedIngestCandidateSchema } from "./candidate.schema";
import { EffectiveFeedPolicySchema } from "./policy.schema";
import { PlannerHarvestObservationSchema, PlannerDiscoveredEvidenceSchema } from "./planner-stage.schema";
import { CountSchema, FiniteSchema, NonEmptySchema, NonNegativeSchema, Sha256Schema, SlugSchema, reject } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";

const screeningMetadata = {
  version: SCREENED_ARTICLE_VERSION,
  changelog: [
    { version: SCREENED_ARTICLE_VERSION, change: "Declare raw timing, measured substance and text-free selection records." },
  ],
};

const RawFreshnessFields = {
  timing_at: RecordedInstantSchema.nullable().describe("Trusted publication or captured first sight in UTC; null when unknown."),
  timing_source: z.enum(["published_at", "first_seen", "unknown"]),
  age_hours: FiniteSchema.nullable().describe("Signed hours from the captured UTC evaluation instant; null when unknown."),
  recency_bonus: NonNegativeSchema,
};
const RawFreshnessObject = z.strictObject(RawFreshnessFields);

function checkTiming(value: z.infer<typeof RawFreshnessObject>, ctx: z.RefinementCtx): void {
  if (value.timing_source === "unknown") {
    if (value.timing_at !== null) reject(ctx, "unknown timing requires null timing_at", ["timing_at"]);
    if (value.age_hours !== null) reject(ctx, "unknown timing requires null age_hours", ["age_hours"]);
    if (value.recency_bonus !== 0) reject(ctx, "unknown timing requires zero recency_bonus", ["recency_bonus"]);
  } else {
    if (value.timing_at === null) reject(ctx, "known timing requires timing_at", ["timing_at"]);
    if (value.age_hours === null) reject(ctx, "known timing requires age_hours", ["age_hours"]);
  }
}

export const RawArticleFreshnessSchema = RawFreshnessObject
  .superRefine(checkTiming).meta(screeningMetadata);
export type RawArticleFreshness = z.infer<typeof RawArticleFreshnessSchema>;

export const AdmittedArticleFreshnessSchema = z.strictObject({
  ...RawFreshnessFields,
  substance_score: FiniteSchema,
  substance_word_count: CountSchema,
}).superRefine(checkTiming).meta(screeningMetadata);
export type AdmittedArticleFreshness = z.infer<typeof AdmittedArticleFreshnessSchema>;

export const ScreenedCandidateSchema = z.strictObject({
  candidate: FeedIngestCandidateSchema,
  policy: EffectiveFeedPolicySchema,
  freshness: AdmittedArticleFreshnessSchema,
  observation: PlannerHarvestObservationSchema.nullable(),
  discovered_availability: PlannerDiscoveredEvidenceSchema.options[0].shape.availability
    .or(PlannerDiscoveredEvidenceSchema.options[1].shape.availability),
}).superRefine((value, ctx) => {
  if (value.freshness.substance_word_count > value.candidate.word_count) {
    reject(ctx, "substance_word_count must not exceed candidate.word_count", ["freshness", "substance_word_count"]);
  }
}).meta(screeningMetadata);
export type ScreenedCandidate = z.infer<typeof ScreenedCandidateSchema>;

export const NumericalSelectionInputSchema = z.strictObject({
  candidate_id: Sha256Schema,
  url_key: Sha256Schema,
  feed_id: SlugSchema,
  website_group: NonEmptySchema.regex(/\S/u),
  base_score: FiniteSchema,
}).meta(screeningMetadata);
export type NumericalSelectionInput = z.infer<typeof NumericalSelectionInputSchema>;

export const NumericalSelectionOutputSchema = z.strictObject({
  candidate_id: Sha256Schema,
  marginal_score: FiniteSchema,
  domain_diversity_penalty: FiniteSchema.nonpositive(),
  feed_diversity_penalty: FiniteSchema.nonpositive(),
  novelty_bonus: NonNegativeSchema,
}).meta(screeningMetadata);
export type NumericalSelectionOutput = z.infer<typeof NumericalSelectionOutputSchema>;
