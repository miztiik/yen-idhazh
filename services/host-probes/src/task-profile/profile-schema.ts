/** Which body-free transient measurements describe one actual task? */
import { z } from "zod";
import { MAX_TIMER_DELAY_MS, TaskProfileConfigSchema } from "../config";
import { UNAVAILABLE_REASONS } from "../probe/proc-reader";

const count = z.int().nonnegative().max(Number.MAX_SAFE_INTEGER);
const milliseconds = z.number().finite().nonnegative();
const percentage = z.number().finite().min(0).max(100);
export const UnavailableSchema = z.enum([
  ...UNAVAILABLE_REASONS, "configured_off", "not_configured", "process_exited", "pid_reused",
  "clock_ticks_unavailable", "no_interval",
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
export const ClockTicksSchema = z.discriminatedUnion("reason", [
  z.strictObject({ reason: z.null(), value: count.positive() }),
  z.strictObject({ reason: UnavailableSchema, value: z.null() }),
]);
export const ProcessCpuSchema = z.discriminatedUnion("reason", [
  z.strictObject({ reason: z.null(), value: z.strictObject({
    cpu_time_ms: milliseconds, percent_one_core: z.number().finite().nonnegative(),
  }) }),
  z.strictObject({ reason: UnavailableSchema, value: z.null() }),
]);
export const ProcessSampleSchema = z.strictObject({
  pid: count.positive().nullable(), start_ticks: z.string().regex(/^\d+$/).nullable(),
  cpu_window: z.strictObject({
    interval_ms: milliseconds, full_window: z.boolean(), cpu: ProcessCpuSchema,
  }),
  memory_kb: z.strictObject({
    rss: count.nullable(), hwm_lifetime: count.nullable(), anon: count.nullable(),
  }),
  major_faults: count.nullable(), unavailable: reasons,
});
const ProcessSummarySchema = z.strictObject({
  closing: ProcessSampleSchema, sampled_rss_max_kb: count.nullable(),
  major_faults_delta: count.nullable(), unavailable: reasons,
  cpu_interval_ms: milliseconds, cpu: ProcessCpuSchema,
  sampled_cpu_min_percent_one_core: z.number().finite().nonnegative().nullable(),
  sampled_cpu_max_percent_one_core: z.number().finite().nonnegative().nullable(),
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
export const TaskEndReasonSchema = z.enum([
  "task_settled", "explicit_stop", "owner_exited", "pid_reused", "expired", "service_stopped", "start_aborted",
]);
export const TaskProfileSchema = z.strictObject({
  identity: TaskIdentitySchema,
  collector: z.literal("worker_thread"),
  outcome: TaskOutcomeSchema,
  end_reason: TaskEndReasonSchema,
  started_at: z.iso.datetime(), finished_at: z.iso.datetime(), elapsed_ms: milliseconds,
  config: TaskProfileConfigSchema,
  process_clock_ticks_per_second: ClockTicksSchema,
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
  if (["owner_exited", "pid_reused", "expired", "service_stopped", "start_aborted"].includes(value.end_reason)
    && value.outcome !== "cancelled") {
    context.addIssue({ code: "custom", path: ["outcome"], message: "interrupted task profiles must be cancelled" });
  }
  if (!value.config.enabled || value.full_window_count >= value.sample_count
    || (value.samples.length === value.sample_count && value.full_window_count !== value.samples.filter(sample =>
      sample.phase !== "opening" && sample.cpu_window.full_window && sample.cpu_window.cpu.reason === null).length)) {
    context.addIssue({ code: "custom", path: ["full_window_count"], message: "must describe actual enabled CPU observations" });
  }
  if (!value.config.machine_memory_enabled && (value.machine_available_min_kb !== null
    || value.machine_major_faults_delta !== null || value.samples.some(sample =>
      Object.values(sample.memory_kb).some(reading => reading !== null) || sample.vmstat_major_faults !== null))) {
    context.addIssue({ code: "custom", path: ["machine_available_min_kb"], message: "disabled machine RAM must have no measurements" });
  }
  if (!value.config.memory_enabled && (Object.values(value.processes).some(process =>
    process.sampled_rss_max_kb !== null || process.major_faults_delta !== null)
    || value.samples.some(sample => Object.values(sample.processes).some(process =>
      Object.values(process.memory_kb).some(reading => reading !== null) || process.major_faults !== null)))) {
    context.addIssue({ code: "custom", path: ["processes"], message: "disabled PID RAM must have no measurements" });
  }
  if (["owner_exited", "pid_reused", "expired", "service_stopped", "start_aborted"].includes(value.end_reason)
    && value.outcome !== "cancelled") {
    context.addIssue({ code: "custom", path: ["outcome"], message: "interrupted task profiles must be cancelled" });
  }
});
export const CollectorInputSchema = z.strictObject({
  identity: TaskIdentitySchema, config: TaskProfileConfigSchema,
  max_proc_bytes: count.positive(), worker_pid: count.positive(),
  target: OwnedProcessSchema.nullable(), clock_ticks_per_second: ClockTicksSchema,
  expires_after_ms: z.int().positive().max(MAX_TIMER_DELAY_MS).nullable(),
  server: OwnedProcessSchema.nullable(),
  context: z.strictObject({ platform: z.string().optional(), procRoot: z.string().optional() }),
}).refine(value => value.target === null || value.target.pid === value.worker_pid, {
  path: ["target", "pid"], message: "must name the task worker PID",
});
export const CollectorCommandSchema = z.strictObject({ outcome: TaskOutcomeSchema, end_reason: TaskEndReasonSchema });
export const CollectorMessageSchema = z.discriminatedUnion("type", [
  z.strictObject({
    type: z.literal("ready"), target: OwnedProcessSchema.nullable(), expires_at: z.iso.datetime().nullable(),
  }),
  z.strictObject({ type: z.literal("rejected"), reason: UnavailableSchema }),
  z.strictObject({ type: z.literal("complete"), profile: TaskProfileSchema }),
]);
export type TaskIdentity = z.infer<typeof TaskIdentitySchema>;
export type OwnedProcess = z.infer<typeof OwnedProcessSchema>;
export type ClockTicks = z.infer<typeof ClockTicksSchema>;
export type ProcessCpu = z.infer<typeof ProcessCpuSchema>;
export type ProcessSample = z.infer<typeof ProcessSampleSchema>;
export type ProcessSummary = z.infer<typeof ProcessSummarySchema>;
export type TaskSample = z.infer<typeof TaskSampleSchema>;
export type TaskOutcome = z.infer<typeof TaskOutcomeSchema>;
export type TaskEndReason = z.infer<typeof TaskEndReasonSchema>;
export type TaskProfile = z.infer<typeof TaskProfileSchema>;
export type CollectorInput = z.infer<typeof CollectorInputSchema>;
