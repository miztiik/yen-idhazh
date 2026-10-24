/** Which body-free transient measurements describe one actual task? */
import { z } from "zod";
import { TaskProfileConfigSchema } from "../config";
import { UNAVAILABLE_REASONS } from "../probe/proc-reader";

const count = z.int().nonnegative().max(Number.MAX_SAFE_INTEGER);
const milliseconds = z.number().finite().nonnegative();
const percentage = z.number().finite().min(0).max(100);
export const UnavailableSchema = z.enum([
  ...UNAVAILABLE_REASONS, "configured_off", "not_configured", "process_exited", "pid_reused",
]);
export type TaskUnavailableReason = z.infer<typeof UnavailableSchema>;
const reasons = z.record(z.string(), UnavailableSchema);
export const CpuObservationSchema = z.discriminatedUnion("reason", [
  z.strictObject({ reason: z.null(), value: z.strictObject({
    user: percentage, system: percentage, idle: percentage, iowait: percentage, steal: percentage,
  }) }),
  z.strictObject({ reason: UnavailableSchema, value: z.null() }),
]);
export const TaskIdentitySchema = z.strictObject({
  pipeline_name: z.string().min(1), task_name: z.string().min(1),
  run_id: z.string().min(1), correlation_id: z.uuid(), request_id: z.uuid(),
});
export const OwnedProcessSchema = z.strictObject({
  pid: count.positive(), start_ticks: z.string().regex(/^\d+$/),
});
export const ProcessSampleSchema = z.strictObject({
  pid: count.positive().nullable(), start_ticks: z.string().regex(/^\d+$/).nullable(),
  memory_kb: z.strictObject({
    rss: count.nullable(), hwm_lifetime: count.nullable(), anon: count.nullable(),
  }),
  major_faults: count.nullable(), unavailable: reasons,
});
const ProcessSummarySchema = z.strictObject({
  closing: ProcessSampleSchema, sampled_rss_max_kb: count.nullable(),
  major_faults_delta: count.nullable(), unavailable: reasons,
});
export const TaskSampleSchema = z.strictObject({
  phase: z.enum(["opening", "poll", "closing"]),
  observed_at: z.iso.datetime(), elapsed_ms: milliseconds,
  cpu_window: z.strictObject({
    interval_ms: milliseconds, full_window: z.boolean(), cpu: CpuObservationSchema,
  }),
  memory_kb: z.strictObject({
    total: count.nullable(), free: count.nullable(), available: count.nullable(),
  }),
  vmstat_major_faults: count.nullable(),
  processes: z.strictObject({ worker: ProcessSampleSchema, server: ProcessSampleSchema }),
  unavailable: reasons,
});
export const TaskOutcomeSchema = z.enum(["success", "error", "cancelled"]);
export const TaskProfileSchema = z.strictObject({
  identity: TaskIdentitySchema,
  collector: z.literal("worker_thread"),
  outcome: TaskOutcomeSchema,
  started_at: z.iso.datetime(), finished_at: z.iso.datetime(), elapsed_ms: milliseconds,
  config: TaskProfileConfigSchema,
  sample_count: count.positive(), periodic_sample_count: count, full_window_count: count,
  cpu: CpuObservationSchema,
  sampled_busy_min_percent: percentage.nullable(), sampled_busy_max_percent: percentage.nullable(),
  machine_available_min_kb: count.nullable(), machine_major_faults_delta: count.nullable(),
  processes: z.strictObject({ worker: ProcessSummarySchema, server: ProcessSummarySchema }),
  unavailable: reasons,
  samples: z.array(TaskSampleSchema).min(2),
}).superRefine((value, context) => {
  if (value.samples.length > value.config.max_retained_samples || value.samples.length > value.sample_count) {
    context.addIssue({ code: "custom", path: ["samples"], message: "retained samples exceed their bound" });
  }
  if (value.sample_count !== value.periodic_sample_count + 2
    || value.samples.at(-1)?.phase !== "closing"
    || value.samples.at(-1)?.elapsed_ms !== value.elapsed_ms) {
    context.addIssue({ code: "custom", path: ["samples"], message: "must retain the actual closing observation and whole-task count" });
  }
});
export const CollectorInputSchema = z.strictObject({
  identity: TaskIdentitySchema, config: TaskProfileConfigSchema,
  max_proc_bytes: count.positive(), worker_pid: count.positive(),
  server: OwnedProcessSchema.nullable(),
  context: z.strictObject({ platform: z.string().optional(), procRoot: z.string().optional() }),
});
export const CollectorCommandSchema = z.strictObject({ outcome: TaskOutcomeSchema });
export const CollectorMessageSchema = z.discriminatedUnion("type", [
  z.strictObject({ type: z.literal("ready") }),
  z.strictObject({ type: z.literal("complete"), profile: TaskProfileSchema }),
]);
export type TaskIdentity = z.infer<typeof TaskIdentitySchema>;
export type OwnedProcess = z.infer<typeof OwnedProcessSchema>;
export type ProcessSample = z.infer<typeof ProcessSampleSchema>;
export type TaskSample = z.infer<typeof TaskSampleSchema>;
export type TaskOutcome = z.infer<typeof TaskOutcomeSchema>;
export type TaskProfile = z.infer<typeof TaskProfileSchema>;
export type CollectorInput = z.infer<typeof CollectorInputSchema>;
