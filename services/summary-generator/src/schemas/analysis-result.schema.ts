import { z } from "zod";
import {
  DetailedTokenMetricsSchema,
  SwapActivityMetricsSchema,
  SourceAuditSchema,
} from "./system-telemetry.schema.js";

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

export const RawModelAnalysisSchema = z.object({
  headline: z.string().min(1),
  executive_summary: z.string().min(1),
  key_points: z.array(z.string().min(1)),
  sentiment: SentimentEnum,
  stance_on_change: StanceOnChangeEnum,
  stance_on_economic_power: StanceOnEconomicPowerEnum,
  stance_on_state_power: StanceOnStatePowerEnum,
  stance_on_borders: StanceOnBordersEnum,
  stance_on_personal_sphere: StanceOnPersonalSphereEnum,
});

export type RawModelAnalysis = z.infer<typeof RawModelAnalysisSchema>;

export const SummaryStructuredOutputSchema = RawModelAnalysisSchema.extend({
  compression_ratio: z.string(),
  raw_output: z.string(),
  source_audit: SourceAuditSchema,
  token_metrics: DetailedTokenMetricsSchema,
  swap_metrics: SwapActivityMetricsSchema,
  input_text: z.string(),
  system_prompt: z.string(),
  user_prompt: z.string(),
});

export type SummaryStructuredOutput = z.infer<typeof SummaryStructuredOutputSchema>;