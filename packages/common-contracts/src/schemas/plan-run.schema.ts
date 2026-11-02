/** What did one planner execution finish, including empty and failed runs? */
import { z } from "zod";
import { PLAN_RUN_VERSION } from "../version";
import { CountSchema, DateStampSchema, FiniteSchema, NonEmptySchema, PositiveCountSchema, RelPathSchema, RunIdSchema, reject } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";

export const PlanApiTimingSchema = z.strictObject({
  operation: z.enum(["fetch", "parse", "select", "partition", "persist", "feed-health-summary",
    "feed-health-before-fetch", "feed-health-for-selection"]),
  duration_ms: CountSchema, status: z.enum(["completed", "failed", "interrupted"]),
});
export const SelectionMetricsSchema = z.strictObject({
  selected_website_groups: CountSchema, selected_feeds: CountSchema,
  mean_substance_score: FiniteSchema.nullable(),
});
export const PlanRunRowSchema = z.strictObject({
  run_id: RunIdSchema, started_at: RecordedInstantSchema, duration_ms: CountSchema.nullable(),
  status: z.enum(["completed", "partial", "failed"]), failure_code: NonEmptySchema.nullable(),
  selected_count: CountSchema, selection_metrics: SelectionMetricsSchema.nullable(),
  strategy: z.enum(["bin-pack", "round-robin", "none"]),
  dispatch_count: CountSchema, selected_articles_artifact: RelPathSchema.nullable(),
  api_timings: z.array(PlanApiTimingSchema), date: DateStampSchema, attempt: PositiveCountSchema,
  lifecycle_window_days: PositiveCountSchema, reliability_floor: FiniteSchema.min(0).max(1),
  reliability_penalty_enabled: z.boolean(), evaluated_at: RecordedInstantSchema,
  request_report_closed_days: PositiveCountSchema, reliability_window_days: PositiveCountSchema,
  selection_started_at_utc: RecordedInstantSchema.nullable(),
}).superRefine((value, ctx) => {
  if (value.date !== value.started_at.slice(0, 10) || !value.run_id.startsWith(`${value.date}-`)) {
    reject(ctx, "run date and run_id must match the UTC day of started_at");
  }
  const metrics = value.selection_metrics;
  if (metrics === null) {
    if (value.selected_count !== 0) reject(ctx, "selection not completed requires zero selected_count", ["selected_count"]);
  } else if (value.selected_count === 0) {
    if (metrics.selected_website_groups !== 0 || metrics.selected_feeds !== 0 || metrics.mean_substance_score !== null) {
      reject(ctx, "completed empty selection requires zero group/feed counts and null mean", ["selection_metrics"]);
    }
  } else if (metrics.selected_website_groups < 1 || metrics.selected_website_groups > value.selected_count
    || metrics.selected_feeds < 1 || metrics.selected_feeds > value.selected_count
    || metrics.mean_substance_score === null) {
    reject(ctx, "nonempty selection requires positive bounded group/feed counts and finite mean", ["selection_metrics"]);
  }
}).meta({
  version: PLAN_RUN_VERSION,
  changelog: [
    { version: PLAN_RUN_VERSION, change: "Require nullable completed-selection diversity counts and mean substance score." },
    { version: "2026-10-26", change: "Name pre-fetch and fresh selection health captures separately." },
    { version: "2026-10-25", change: "Declare the metadata-only planner ledgers without generic writer identity." },
  ],
});
export type PlanRunRow = z.infer<typeof PlanRunRowSchema>;
export type PlanApiTiming = z.infer<typeof PlanApiTimingSchema>;
export const PlanRunRowContract = {
  schema: PlanRunRowSchema, schemaVersion: PLAN_RUN_VERSION,
} as const;
