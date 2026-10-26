/** What did one planner execution finish, including empty and failed runs? */
import { z } from "zod";
import { PLANNER_LEDGER_VERSION } from "../version";
import { CountSchema, DateStampSchema, FiniteSchema, NonEmptySchema, PositiveCountSchema, RelPathSchema, RunIdSchema, reject } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";

export const PlanApiTimingSchema = z.strictObject({
  operation: z.enum(["fetch", "parse", "select", "partition", "persist", "feed-health-summary"]),
  duration_ms: CountSchema, status: z.enum(["completed", "failed", "interrupted"]),
});
export const PlanRunRowSchema = z.strictObject({
  run_id: RunIdSchema, started_at: RecordedInstantSchema, duration_ms: CountSchema.nullable(),
  status: z.enum(["completed", "partial", "failed"]), failure_code: NonEmptySchema.nullable(),
  selected_count: CountSchema, strategy: z.enum(["bin-pack", "round-robin", "none"]),
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
});
export type PlanRunRow = z.infer<typeof PlanRunRowSchema>;
export type PlanApiTiming = z.infer<typeof PlanApiTimingSchema>;
export const PlanRunRowContract = {
  schema: PlanRunRowSchema, schemaVersion: PLANNER_LEDGER_VERSION,
} as const;
