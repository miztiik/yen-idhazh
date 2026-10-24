/** Which transient cache results distinguish real measurements from unavailable instruments? */
import { z } from "zod";
import { OwnedProcessSchema } from "../task-profile/profile-schema";
import { CacheEventSchema } from "./cache-config";
export { CacheEventSchema } from "./cache-config";

// Calendar versions, event aliases and units identify external protocols, not tuning controls.
export const CACHE_API_VERSION = "2026-10-24";
export const CacheReasonSchema = z.enum([
  "configured_off", "unsupported_platform", "tool_missing", "permission_denied",
  "event_unsupported", "not_counted", "invalid_output", "output_limit", "timeout",
  "cancelled", "process_exited", "pid_reused", "target_not_owned", "invalid_target",
  "tool_failed", "affinity_unavailable", "concurrency_limit",
]);
export type CacheReason = z.infer<typeof CacheReasonSchema>;
export type CacheEvent = z.infer<typeof CacheEventSchema>;
const number = z.number().finite().nonnegative();
const count = z.int().nonnegative().max(Number.MAX_SAFE_INTEGER);
export const CacheIntervalSchema = z.strictObject({
  started_at: z.iso.datetime(), finished_at: z.iso.datetime(), elapsed_ms: number,
});
export const CacheHostSchema = z.strictObject({
  platform: z.literal("linux"), arch: z.string().min(1), release: z.string().min(1),
});
export const CacheCounterSchema = z.strictObject({
  event: CacheEventSchema,
  support: z.enum(["measured", "unsupported", "unavailable", "not_counted"]),
  reason: CacheReasonSchema.nullable(),
  count: count.nullable(),
  time_running_ns: count.nullable(),
  time_enabled_ns_estimate: number.nullable(),
  running_percent: z.number().finite().min(0).max(100).nullable(),
  multiplexing: z.enum(["reported", "not_reported", "unknown"]),
}).superRefine((value, context) => {
  const measured = value.support === "measured";
  if (measured !== (value.reason === null)
    || measured !== (value.count !== null && value.time_running_ns !== null
      && value.time_enabled_ns_estimate !== null && value.running_percent !== null)) {
    context.addIssue({ code: "custom", message: "counter values require a measured event and its timing" });
  }
  if (measured && (value.time_running_ns === 0 || value.running_percent === 0)) {
    context.addIssue({ code: "custom", message: "a measured event must have running time" });
  }
  if (!measured && [value.count, value.time_running_ns, value.time_enabled_ns_estimate, value.running_percent].some(cell => cell !== null)) {
    context.addIssue({ code: "custom", message: "an unavailable event has no measurement values" });
  }
  if (measured && value.time_running_ns !== null && value.running_percent !== null) {
    const enabled = value.time_running_ns / (value.running_percent / 100);
    if (value.time_enabled_ns_estimate !== enabled
      || value.multiplexing !== (value.running_percent < 100 ? "reported" : "not_reported")) {
      context.addIssue({ code: "custom", message: "counter scheduling metadata must agree with perf's reported percentage" });
    }
  } else if (value.multiplexing !== "unknown") {
    context.addIssue({ code: "custom", message: "unavailable counters have unknown scheduling" });
  }
});
export type CacheCounter = z.infer<typeof CacheCounterSchema>;
export const CacheCountersSchema = z.strictObject({
  version: z.literal(CACHE_API_VERSION),
  kind: z.literal("last_level_cache_counters"),
  status: z.enum(["disabled", "unavailable", "measured"]),
  reason: CacheReasonSchema.nullable(),
  measurement_obtained: z.boolean(),
  target: OwnedProcessSchema,
  host: CacheHostSchema.nullable(),
  interval: CacheIntervalSchema.nullable(),
  completion: z.enum(["stopped", "duration_limit", "cancelled"]).nullable(),
  scope: z.literal("existing_pid_threads_user_space_without_descendants"),
  scaled: z.literal(false),
  enabled_time_precision: z.literal("derived_from_running_percent_rounded_to_0.01_percent"),
  events: z.array(CacheCounterSchema).min(1).max(CacheEventSchema.options.length),
}).superRefine((value, context) => {
  const measured = value.events.some(event => event.support === "measured");
  if (value.measurement_obtained !== measured || (value.status === "measured") !== measured
    || (value.status === "measured") !== (value.reason === null)
    || (measured && (!value.interval || !value.host))
    || (value.status === "disabled") !== (value.reason === "configured_off")
    || new Set(value.events.map(event => event.event)).size !== value.events.length) {
    context.addIssue({ code: "custom", message: "cache status must describe actual counter evidence" });
  }
});
export type CacheCounters = z.infer<typeof CacheCountersSchema>;
export const CacheCountersStartSchema = z.union([
  CacheCountersSchema,
  z.strictObject({
    version: z.literal(CACHE_API_VERSION), kind: z.literal("last_level_cache_counters"),
    status: z.literal("started"), measurement_obtained: z.literal(false),
    target: OwnedProcessSchema, events: z.array(CacheEventSchema).min(1).max(CacheEventSchema.options.length),
  }),
]);
export const CacheLatencyPointSchema = z.strictObject({
  working_set_bytes: count.positive(),
  stride_bytes: count.positive(),
  tlb_locality_bytes: count.positive(),
  page_size_bytes: count.positive(),
  nanoseconds_per_load: z.number().finite().positive(),
  sample_nanoseconds_per_load: z.array(z.number().finite().positive()).min(1),
  benchmark: OwnedProcessSchema,
  allowed_cpu: count,
  interval: CacheIntervalSchema,
});
export const CacheLatencySchema = z.strictObject({
  version: z.literal(CACHE_API_VERSION),
  kind: z.literal("cache_working_set_latency"),
  status: z.enum(["disabled", "unavailable", "measured"]),
  reason: CacheReasonSchema.nullable(),
  measurement_obtained: z.boolean(),
  host: CacheHostSchema.nullable(),
  interval: CacheIntervalSchema.nullable(),
  tool: z.literal("multichase"),
  method: z.literal("single_dependent_random_pointer_chain"),
  prefault: z.literal("chain_construction"),
  warmup_samples_discarded: z.literal(1),
  sample_period_ms: z.literal(500),
  statistic: z.literal("mean_of_tool_samples"),
  interpretation: z.literal("working_set_curve_not_direct_l3_hit_latency"),
  points: z.array(CacheLatencyPointSchema),
}).superRefine((value, context) => {
  const measured = value.status === "measured";
  if (measured !== value.measurement_obtained || measured !== (value.reason === null)
    || measured !== (value.points.length > 0) || (measured && (!value.interval || !value.host))
    || (value.status === "disabled") !== (value.reason === "configured_off")
    || value.points.some((point, index, points) => index > 0 && point.working_set_bytes <= points[index - 1]!.working_set_bytes)) {
    context.addIssue({ code: "custom", message: "latency requires actual finite tool readings" });
  }
});
export type CacheLatency = z.infer<typeof CacheLatencySchema>;
