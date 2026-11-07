/** Which complete summary and classifications belong to a private full-analysis result? */
import { z } from "zod";
import { SummaryFieldsSchema } from "../../../../services/summary-generator/src/schemas/summary-result.schema.js";
import {
  DETAILED_TOKEN_METRICS_VERSION,
  DetailedTokenMetricsSchema,
  LegacyDetailedTokenMetricsSchema,
  SwapActivityMetricsSchema,
  SourceAuditSchema,
} from "./system-telemetry.schema.js";

export const ANALYSIS_RESULT_VERSION = DETAILED_TOKEN_METRICS_VERSION;
export const ANALYSIS_RESULT_CHANGELOG = [
  { version: ANALYSIS_RESULT_VERSION, change: "Save dated nullable token metrics with the complete analysis." },
] as const;

export const StanceOnChangeEnum = z.enum(["conservatism", "progressivism", "not_applicable"]);
export const StanceOnEconomicPowerEnum = z.enum(["socialism", "libertarianism", "not_applicable"]);
export const StanceOnStatePowerEnum = z.enum(["statism", "constitutionalism", "not_applicable"]);
export const StanceOnBordersEnum = z.enum(["nationalism", "internationalism", "not_applicable"]);
export const StanceOnPersonalSphereEnum = z.enum(["civil_libertarianism", "communitarianism", "not_applicable"]);
export const SentimentEnum = z.enum(["positive", "neutral", "negative", "mixed"]);

export type StanceOnChange = z.infer<typeof StanceOnChangeEnum>;
export type StanceOnEconomicPower = z.infer<typeof StanceOnEconomicPowerEnum>;
export type StanceOnStatePower = z.infer<typeof StanceOnStatePowerEnum>;
export type StanceOnBorders = z.infer<typeof StanceOnBordersEnum>;
export type StanceOnPersonalSphere = z.infer<typeof StanceOnPersonalSphereEnum>;
export type Sentiment = z.infer<typeof SentimentEnum>;

export const RawModelAnalysisSchema = SummaryFieldsSchema.extend({
  sentiment: SentimentEnum,
  stance_on_change: StanceOnChangeEnum,
  stance_on_economic_power: StanceOnEconomicPowerEnum,
  stance_on_state_power: StanceOnStatePowerEnum,
  stance_on_borders: StanceOnBordersEnum,
  stance_on_personal_sphere: StanceOnPersonalSphereEnum,
});

export type RawModelAnalysis = z.infer<typeof RawModelAnalysisSchema>;

export const LegacySummaryStructuredOutputSchema = RawModelAnalysisSchema.extend({
  compression_ratio: z.string(),
  raw_output: z.string(),
  source_audit: SourceAuditSchema.passthrough(),
  token_metrics: LegacyDetailedTokenMetricsSchema,
  swap_metrics: SwapActivityMetricsSchema.passthrough(),
  input_text: z.string(),
  system_prompt: z.string(),
  user_prompt: z.string(),
}).passthrough();

export const SummaryStructuredOutputSchema = LegacySummaryStructuredOutputSchema.extend({
  source_audit: SourceAuditSchema,
  token_metrics: DetailedTokenMetricsSchema,
  swap_metrics: SwapActivityMetricsSchema,
}).strict();

export type SummaryStructuredOutput = z.infer<typeof SummaryStructuredOutputSchema>;
export type LegacySummaryStructuredOutput = z.infer<typeof LegacySummaryStructuredOutputSchema>;
export type RecordedSummaryStructuredOutput = SummaryStructuredOutput | LegacySummaryStructuredOutput;

export function readSummaryStructuredOutput(value: unknown): RecordedSummaryStructuredOutput {
  const { token_metrics } = z.object({ token_metrics: z.record(z.unknown()) }).parse(value);
  return Object.hasOwn(token_metrics, "version")
    ? SummaryStructuredOutputSchema.parse(value)
    : LegacySummaryStructuredOutputSchema.parse(value);
}