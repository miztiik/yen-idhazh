/** Which optional cache measurements may run within authored resource bounds? */
import { z } from "zod";
import { constants } from "node:buffer";

// Node/Bun timers and pointer alignment are runtime and native-tool protocol limits.
const MAX_TIMER_MS = 2 ** 31 - 1;
const POINTER_BYTES = 8;
export const MULTICHASE_SAMPLE_MS = 500;
export const CacheEventSchema = z.enum(["LLC-loads:u", "LLC-load-misses:u"]);
export const CacheProbeConfigSchema = z.strictObject({
  max_output_bytes: z.int().positive().max(constants.MAX_LENGTH - 1),
  lifecycle_timeout_ms: z.int().positive().max(MAX_TIMER_MS),
  max_concurrent: z.int().positive(),
  counters: z.strictObject({
    enabled: z.boolean().default(false).describe("Opt into Linux perf counters; remove when cache counters are retired."),
    events: z.array(CacheEventSchema).min(1).max(CacheEventSchema.options.length)
      .refine(events => new Set(events).size === events.length, "counter events must be unique"),
    max_duration_ms: z.int().min(10).max(MAX_TIMER_MS),
  }),
  latency: z.strictObject({
    enabled: z.boolean().default(false).describe("Opt into the separate multichase benchmark; remove when cache latency is retired."),
    max_working_set_bytes: z.int().positive().max(constants.MAX_LENGTH),
    max_points: z.int().positive(),
    working_set_bytes: z.array(z.int().positive()).min(2),
    stride_bytes: z.int().min(POINTER_BYTES),
    tlb_locality_bytes: z.int().positive(),
    samples: z.int().positive(),
    timeout_ms: z.int().positive().max(MAX_TIMER_MS),
  }).superRefine((value, context) => {
    if (value.stride_bytes % POINTER_BYTES !== 0 || value.tlb_locality_bytes % value.stride_bytes !== 0) {
      context.addIssue({ code: "custom", path: ["stride_bytes"], message: "stride and locality must preserve native pointer alignment" });
    }
    if (value.working_set_bytes.length > value.max_points) {
      context.addIssue({ code: "custom", path: ["working_set_bytes"], message: "working sets exceed max_points" });
    }
    if (value.working_set_bytes.some((bytes, index, sets) => bytes > value.max_working_set_bytes
      || bytes % value.stride_bytes !== 0 || (index > 0 && bytes <= sets[index - 1]!))) {
      context.addIssue({ code: "custom", path: ["working_set_bytes"], message: "working sets must increase, align with stride and fit the byte bound" });
    }
    if ((value.samples + 1) * MULTICHASE_SAMPLE_MS * value.working_set_bytes.length >= value.timeout_ms) {
      context.addIssue({ code: "custom", path: ["timeout_ms"], message: "timeout must allow measured samples and each tool warm-up" });
    }
  }),
});
export type CacheProbeConfig = z.infer<typeof CacheProbeConfigSchema>;
