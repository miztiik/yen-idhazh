/** Which validated controls govern one host sampling service? */
import { z } from "zod";
import { constants as bufferConstants } from "node:buffer";
import { CompressionSchema, JobNameSchema, TaskPerformanceRowSchema, WriterIdentitySchema } from "@idhazh/common-contracts";
import { CacheProbeConfigSchema } from "./cache-probe/cache-config";

// Bun timers use a signed 32-bit millisecond delay; larger values overflow.
export const MAX_TIMER_DELAY_MS = 2 ** 31 - 1;

export const TaskProfileConfigSchema = z.strictObject({
  enabled: z.boolean().default(false).describe("Opt into transient task and item profiles; remove when this profiler is retired."),
  memory_enabled: z.boolean().default(false).describe("Opt into PID RAM in enabled task profiles; remove when process RAM collection is retired."),
  machine_memory_enabled: z.boolean().default(false).describe("Opt into whole-machine RAM and vmstat in enabled task profiles independently of PID RAM; remove when machine RAM collection is retired."),
  cpu_window_ms: z.int().positive().max(MAX_TIMER_DELAY_MS),
  poll_interval_ms: z.int().positive().max(MAX_TIMER_DELAY_MS),
  max_retained_samples: z.int().positive(),
  lifecycle_timeout_ms: z.int().positive().max(MAX_TIMER_DELAY_MS),
  max_profile_handles: z.int().positive().max(Number.MAX_SAFE_INTEGER),
  profile_handle_ttl_ms: z.int().positive().max(MAX_TIMER_DELAY_MS)
    .describe("Explicit HTTP task safety expiry and completed-handle retention, not a CPU sampling window."),
}).refine(value => Math.ceil(value.cpu_window_ms / value.poll_interval_ms) + 2 <= value.max_retained_samples, {
  path: ["max_retained_samples"], message: "must hold the CPU window plus its two endpoints",
});

const ShardMemoryConfigSchema = z.strictObject({
  poll_interval_ms: z.int().positive().max(MAX_TIMER_DELAY_MS),
  max_proc_entries: z.int().positive(),
  max_artifact_bytes: z.int().positive(),
});

export const ProbeConfigSchema = z.object({
  sample_interval_ms: z.number().int().positive().max(MAX_TIMER_DELAY_MS),
  task_profile: TaskProfileConfigSchema,
  shard_memory: ShardMemoryConfigSchema.default({
    poll_interval_ms: 15_000, max_proc_entries: 8_192, max_artifact_bytes: 16_777_216,
  }),
  cache_probe: CacheProbeConfigSchema,
  listen_host: z.enum(["127.0.0.1", "::1"]),
  listen_port: z.number().int().min(1).max(65535),
  max_proc_bytes: z.number().int().positive().max(bufferConstants.MAX_LENGTH - 1),
  max_request_body_bytes: z.int().positive().max(bufferConstants.MAX_LENGTH - 1),
}).strict();

export type ProbeConfig = z.infer<typeof ProbeConfigSchema>;
export type TaskProfileConfig = z.infer<typeof TaskProfileConfigSchema>;

export const TaskPerformanceExecutionSchema = z.strictObject({
  run_id: WriterIdentitySchema.shape.run_id,
  attempt: WriterIdentitySchema.shape.attempt,
  pipeline_name: TaskPerformanceRowSchema.shape.pipeline_name,
  shard: WriterIdentitySchema.shape.shard,
  git_sha: WriterIdentitySchema.shape.git_sha,
  accounting_days: z.array(TaskPerformanceRowSchema.shape.date).min(1)
    .refine(days => new Set(days).size === days.length, "accounting days must be distinct"),
  runner_job: JobNameSchema.optional(),
});
export type TaskPerformanceExecution = z.infer<typeof TaskPerformanceExecutionSchema>;

const TaskPerformanceSettingsSchema = z.object({
  observability: z.object({ host_telemetry_enabled: z.boolean(), memory_profiling_enabled: z.boolean() }),
  ledger: z.object({
    format: z.literal("parquet"), compression_raw: CompressionSchema, compression_compact: CompressionSchema,
  }),
});
export type TaskPerformanceSettings = z.infer<typeof TaskPerformanceSettingsSchema>;

export async function loadTaskPerformanceSettings(
  path: string | URL = new URL("../../../config/idhazh.json", import.meta.url),
): Promise<TaskPerformanceSettings> {
  return TaskPerformanceSettingsSchema.parse(await Bun.file(path).json());
}

export function configureJobProfiles(config: ProbeConfig, settings: TaskPerformanceSettings): ProbeConfig {
  const enabled = settings.observability.host_telemetry_enabled;
  const memory = enabled && settings.observability.memory_profiling_enabled;
  return { ...config, task_profile: {
    ...config.task_profile, enabled, memory_enabled: memory, machine_memory_enabled: memory,
  } };
}

export async function loadConfig(
  path: string | URL = new URL("../../../config/host-probes.json", import.meta.url),
): Promise<ProbeConfig> {
  let input: unknown;
  try {
    input = await Bun.file(path).json();
  } catch (error) {
    throw new Error("Cannot read config/host-probes.json as JSON", { cause: error });
  }
  return ProbeConfigSchema.parse(input);
}
