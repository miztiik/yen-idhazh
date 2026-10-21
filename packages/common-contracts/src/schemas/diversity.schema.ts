/** Which diversity reading or missing-evidence reason was recorded? */
import { z } from "zod";
import { CountSchema, DateStampSchema, FiniteSchema, NonEmptySchema, PositiveCountSchema, RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, VersionSchema, reject } from "./primitives";

export const DiversityMetricSchema = z.enum([
  "active_source_coverage", "selection_coverage", "effective_number_of_sources",
  "top_source_concentration", "source_gini", "source_kind_distribution",
  "lost_diversity_by_stage", "event_repetition_rate", "source_event_overlap", "novel_source_contribution",
]);
export const DiversityMetricRowSchema = z.strictObject({
  version: VersionSchema, date: DateStampSchema, correlation_id: NonEmptySchema, run_id: RunIdSchema,
  metric: DiversityMetricSchema, basis: z.enum(["eligible", "selected", "published", "leads", "stage"]),
  as_of: TimestampSchema, window_start: DateStampSchema.nullable(), window_end: DateStampSchema.nullable(),
  dimension: z.enum(["source", "source_kind", "event_cluster"]).nullable(),
  stage: z.enum(["input", "freshness", "deduplication", "normalization", "selection", "publication", "lead_selection"]).nullable(),
  window_days: PositiveCountSchema.nullable(), dimension_value: SlugSchema.nullable(),
  value: FiniteSchema.nullable(), unit: z.enum(["ratio", "count", "sources", "source_difference"]),
  before_value: FiniteSchema.nullable(), after_value: FiniteSchema.nullable(),
  numerator: CountSchema.nullable(), denominator: CountSchema.nullable(),
  item_count: CountSchema.nullable(), source_count: CountSchema.nullable(),
  history_coverage_days: CountSchema.nullable(), history_required_days: CountSchema.nullable(),
  algorithm_version: NonEmptySchema, config_sha256: Sha256Schema,
  availability: z.enum(["available", "unavailable"]),
  unavailable_reason: z.enum(["empty_denominator", "incomplete_history", "missing_publication", "missing_event_evidence"]).nullable(),
  top_k: z.literal([1, 5, 10]).nullable().default(null),
}).superRefine((value, ctx) => {
  if (value.date !== value.as_of.slice(0, 10)) reject(ctx, "date must match the UTC as_of day");
  if ((value.window_start === null) !== (value.window_end === null)) reject(ctx, "window boundaries are recorded together");
  if (value.window_start !== null && value.window_end !== null && value.window_start > value.window_end) reject(ctx, "window_start must not follow window_end");
  if (value.availability === "available") {
    if (value.value === null || value.unavailable_reason !== null) reject(ctx, "an available metric has a finite value and no missing reason");
  } else if (value.value !== null || value.unavailable_reason === null) reject(ctx, "an unavailable metric has a reason and no value");
  if ((value.numerator === null) !== (value.denominator === null)) reject(ctx, "numerator and denominator are recorded together");
  if (value.unit === "ratio" && value.value !== null && (value.value < 0 || value.value > 1)) reject(ctx, "ratio readings are in the range [0, 1]");
  if (value.unit === "count" && value.value !== null && (value.value < 0 || !Number.isInteger(value.value))) reject(ctx, "count readings are nonnegative integers");
  if (value.unit === "sources" && value.value !== null && value.value < 0) reject(ctx, "effective source readings are nonnegative");
  if ((value.history_coverage_days === null) !== (value.history_required_days === null)) reject(ctx, "history coverage and its requirement are recorded together");
  if (value.history_coverage_days !== null && value.history_required_days !== null && value.history_coverage_days > value.history_required_days) reject(ctx, "history coverage cannot exceed the requested window");
  if ((value.basis === "stage") !== (value.stage !== null)) reject(ctx, "only stage-basis readings name their stage");
  if ((value.metric === "top_source_concentration") !== (value.top_k !== null)) reject(ctx, "top-source concentration records its configured k");
  const expectedUnits: Record<z.infer<typeof DiversityMetricSchema>, readonly string[]> = {
    active_source_coverage: ["ratio"], selection_coverage: ["ratio"],
    effective_number_of_sources: ["sources"], top_source_concentration: ["ratio"],
    source_gini: ["ratio"], source_kind_distribution: ["count", "ratio"],
    lost_diversity_by_stage: ["source_difference"], event_repetition_rate: ["ratio"],
    source_event_overlap: ["count", "ratio"], novel_source_contribution: ["count", "ratio"],
  };
  if (!expectedUnits[value.metric].includes(value.unit)) reject(ctx, "unit does not match the metric");
  if (value.metric === "source_kind_distribution") {
    if (value.dimension !== "source_kind" || value.dimension_value === null) reject(ctx, "source-kind distribution names its kind or unknown bucket");
  } else if (value.dimension_value !== null) reject(ctx, "only source-kind distribution names a dimension value");
  if (value.metric === "lost_diversity_by_stage") {
    if (value.before_value === null || value.after_value === null || value.value === null) reject(ctx, "lost diversity records before, after, and signed difference");
    else {
      if (value.before_value < 0 || value.after_value < 0) reject(ctx, "lost-diversity source readings are nonnegative");
      if (value.value !== value.before_value - value.after_value) reject(ctx, "lost-diversity value equals before minus after");
    }
  } else if (value.before_value !== null || value.after_value !== null) reject(ctx, "only lost-diversity readings carry before and after values");
  if (["event_repetition_rate", "source_event_overlap", "novel_source_contribution"].includes(value.metric) && value.window_days === null) reject(ctx, "history-dependent metrics identify their configured UTC window");
});
export type DiversityMetricRow = z.infer<typeof DiversityMetricRowSchema>;
