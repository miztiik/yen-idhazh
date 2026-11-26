/** Which measured cells can one terminal pipeline task file? */
import { z } from "zod";
import { validRecordedInstant } from "../observation-order";
import { RowIdentitySchema } from "./envelope.schema";
import { CountSchema, DateStampSchema, JobNameSchema, NonNegativeSchema, RunIdSchema, reject } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";

export const TASK_PERFORMANCE_VERSION = "2026-11-25" as const;
export const TaskPerformanceKindSchema = z.enum(["workflow-task", "model-serving", "judge"]);
export const TaskPerformanceOutcomeSchema = z.enum(["success", "error", "cancelled"]);

const accountingDay = DateStampSchema.refine(
  (day) => validRecordedInstant(`${day}T00:00:00Z`),
  "must be a valid UTC accounting day",
);
const instant = RecordedInstantSchema.nullable().default(null);
const reading = NonNegativeSchema.nullable().default(null);
const percent = NonNegativeSchema.max(100).nullable().default(null);
const count = CountSchema.nullable().default(null);

export const TaskPerformanceRowSchema = z.strictObject({
  version: z.literal(TASK_PERFORMANCE_VERSION),
  date: accountingDay,
  run_id: RunIdSchema,
  pipeline_name: JobNameSchema,
  task_name: JobNameSchema,
  shard: CountSchema,
  task_kind: TaskPerformanceKindSchema,
  outcome: TaskPerformanceOutcomeSchema,
  subject_id: JobNameSchema.nullable().default(null),
  started_at: instant,
  finished_at: instant,
  host_unit_id: RowIdentitySchema.shape.unit_id.nullable().default(null),
  elapsed_ms: reading,
  machine_cpu_busy_pct: percent,
  machine_cpu_steal_pct: percent,
  machine_memory_available_min_kib: count,
  worker_rss_peak_kib: count,
  worker_cpu_time_ms: reading,
  model_load_ms: reading,
  server_prompt_seconds: reading,
  server_prompt_tokens: count,
  model_calls: count,
  tokens_in: count,
  tokens_out: count,
  model_seconds: reading,
}).superRefine((row, ctx) => {
  if (row.started_at !== null && row.finished_at !== null && Date.parse(row.finished_at) < Date.parse(row.started_at)) {
    reject(ctx, "finished_at must be at or after started_at", ["finished_at"]);
  }
  if (row.task_kind !== "workflow-task" && row.subject_id === null) {
    reject(ctx, "model-serving and judge tasks require subject_id", ["subject_id"]);
  }
  const serving = [row.model_load_ms, row.server_prompt_seconds, row.server_prompt_tokens];
  if (row.task_kind === "model-serving") {
    const phase = [row.elapsed_ms, row.model_calls, row.tokens_in, row.tokens_out, row.model_seconds];
    if (phase.some((value) => value !== null)) reject(ctx, "model-serving tasks cannot report phase measurements or elapsed_ms");
    if (serving.every((value) => value === null)) reject(ctx, "model-serving tasks require at least one observed serving measurement");
  } else {
    if (row.elapsed_ms === null) reject(ctx, "workflow-task and judge tasks require elapsed_ms", ["elapsed_ms"]);
    if (serving.some((value) => value !== null)) reject(ctx, "only model-serving tasks can report serving measurements");
  }
});

export type TaskPerformanceRow = z.infer<typeof TaskPerformanceRowSchema>;
