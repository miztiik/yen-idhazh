/** Which validated controls govern one host sampling service? */
import { z } from "zod";
import { constants as bufferConstants } from "node:buffer";

// Bun timers use a signed 32-bit millisecond delay; larger values overflow.
export const MAX_TIMER_DELAY_MS = 2 ** 31 - 1;

export const TaskProfileConfigSchema = z.strictObject({
  enabled: z.boolean().default(false).describe("Opt into transient whole-task profiles only; remove when this profiler is retired."),
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

export const ProbeConfigSchema = z.object({
  sample_interval_ms: z.number().int().positive().max(MAX_TIMER_DELAY_MS),
  task_profile: TaskProfileConfigSchema,
  listen_host: z.enum(["127.0.0.1", "::1"]),
  listen_port: z.number().int().min(1).max(65535),
  max_proc_bytes: z.number().int().positive().max(bufferConstants.MAX_LENGTH - 1),
  max_request_body_bytes: z.int().positive().max(bufferConstants.MAX_LENGTH - 1),
}).strict();

export type ProbeConfig = z.infer<typeof ProbeConfigSchema>;
export type TaskProfileConfig = z.infer<typeof TaskProfileConfigSchema>;

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
