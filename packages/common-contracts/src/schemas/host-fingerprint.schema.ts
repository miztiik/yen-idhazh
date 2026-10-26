/** Which complete hardware and task measurements may an existing host row retain? */
import { createHash } from "node:crypto";
import { z } from "zod";
import { JobNameSchema, RunIdSchema, reject } from "./primitives";

export const HOST_FINGERPRINT_VERSION = "2026-10-26";
export const WATCHED_FLAGS = [
  "amx_bf16", "amx_int8", "amx_tile", "avx2", "avx512_bf16",
  "avx512_fp16", "avx512_vnni", "avx512f", "avx_vnni", "f16c", "fma", "sse4_2",
] as const;
const integer = z.int();
const count = integer.nonnegative();
const positiveCount = integer.positive();
const number = z.number().finite();
const text = z.string().nullable().default(null);
const instant = z.iso.datetime({ precision: 0 }).nullable().default(null);

// Algorithm 2's keys and ASCII JSON spelling are a persisted identity protocol.
const HARDWARE_KEYS = [
  "cpu_family", "cpu_model", "cpu_model_number", "cpu_stepping",
  "cpu_vendor", "flags", "l3_cache_bytes",
] as const;
type Hardware = {
  cpu_family: number | null; cpu_model: string | null;
  cpu_model_number: number | null; cpu_stepping: number | null;
  cpu_vendor: string | null; flags: string; l3_cache_bytes: number | null;
};

export function fingerprintV2(row: Hardware): string | null {
  const flags = row.flags.split(/\s+/).filter(Boolean);
  if (row.flags !== [...new Set(flags)].sort().join(" ") ||
      flags.some((flag) => !(WATCHED_FLAGS as readonly string[]).includes(flag))) {
    throw new Error("fingerprint flags must be watched, sorted and space-joined");
  }
  const numbers = [row.cpu_family, row.cpu_model_number, row.cpu_stepping];
  if (numbers.some((value) => value !== null && (!Number.isSafeInteger(value) || value < 0))) {
    throw new Error("algorithm 2 CPU identifiers must be nonnegative safe integers");
  }
  if (![row.cpu_vendor, row.cpu_model].some((value) => value?.trim()) &&
      !numbers.some((value) => value !== null) && !(row.l3_cache_bytes !== null && row.l3_cache_bytes > 0) &&
      !flags.length) return null;
  const json = JSON.stringify(Object.fromEntries(HARDWARE_KEYS.map((key) => [key, row[key]])))
    .replace(/[\u007f-\uffff]/g, (character) =>
      `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`);
  return createHash("sha256").update(json, "ascii").digest("hex").slice(0, 16);
}

export const HostFingerprintRowSchema = z.strictObject({
  version: z.enum(["2026-10-10", "2026-10-12", "2026-10-14", HOST_FINGERPRINT_VERSION]).default(HOST_FINGERPRINT_VERSION),
  date: z.iso.date(), run_id: RunIdSchema,
  job: JobNameSchema.nullable().default("work"),
  pipeline_name: JobNameSchema.nullable().default(null),
  task_name: JobNameSchema.nullable().default(null), shard: count,
  fingerprint: z.string().regex(/^[0-9a-f]{16}$/).nullable().default(null),
  fingerprint_version: z.union([z.literal(1), z.literal(2)]).nullable().default(null),
  cpu_model: text, cpu_vendor: text,
  cpu_family: integer.nullable().default(null),
  cpu_model_number: integer.nullable().default(null),
  cpu_stepping: integer.nullable().default(null), microcode: text,
  cpu_physical_cores: positiveCount.nullable().default(null),
  cpu_logical_processors: positiveCount.nullable().default(null),
  cpu_allowed_processors: positiveCount.nullable().default(null),
  cpu_quota_cores: number.positive().nullable().default(null),
  cpu_quota_state: z.enum(["finite", "unlimited", "unavailable"]).nullable().default(null),
  cpu_target_measured_at: instant,
  l3_cache_bytes: count.nullable().default(null),
  machine_memory_total_mib: number.positive().nullable().default(null),
  cpu_observed_mhz: number.positive().nullable().default(null),
  cpu_reported_max_mhz: number.positive().nullable().default(null),
  flags: z.string().default(""), boot_seconds: number.nonnegative().nullable().default(null),
  memcpy_gib_s: number.positive().nullable().default(null),
  memcpy_probe_mib: count.nullable().default(null),
  vm_size: text, vm_location: text, vm_zone: text, vm_fault_domain: text,
  runner_name: text, measured_at: instant,
  model_load_ms: number.nonnegative().nullable().default(null),
  job_seconds: count.nullable().default(null),
  server_prompt_tokens: count.nullable().default(null),
  server_prompt_seconds: number.nonnegative().nullable().default(null),
}).superRefine((row, ctx) => {
  if ((row.pipeline_name === null) !== (row.task_name === null)) reject(ctx, "requires both pipeline_name and task_name");
  if (row.task_name === null && row.job === null) reject(ctx, "requires a legacy job or pipeline and task");
  if (row.task_name !== null && row.job !== null && row.job !== row.task_name) reject(ctx, "generic job must be null or match task_name");
  if ((row.fingerprint === null) !== (row.fingerprint_version === null)) reject(ctx, "fingerprint and version must be present together");
  if (row.fingerprint_version === 2) {
    try {
      if (row.fingerprint !== fingerprintV2(row)) reject(ctx, "fingerprint does not match algorithm 2");
    } catch (error) {
      reject(ctx, error instanceof Error ? error.message : "invalid hardware identity");
    }
  }
  if ((row.cpu_quota_cores !== null) !== (row.cpu_quota_state === "finite")) reject(ctx, "finite quota requires cpu_quota_cores and vice versa");
  const target = row.cpu_target_measured_at !== null;
  if (target !== (row.cpu_quota_state !== null)) reject(ctx, "target time and quota state must be present together");
  if (row.cpu_allowed_processors !== null && (!target || row.cpu_logical_processors === null)) reject(ctx, "allowed count requires target capture and logical count");
  for (const name of ["cpu_physical_cores", "cpu_allowed_processors"] as const) {
    if (row[name] !== null && row.cpu_logical_processors !== null && row[name] > row.cpu_logical_processors) reject(ctx, `${name} cannot exceed logical count`);
  }
  if (row.measured_at !== null && row.cpu_target_measured_at !== null && row.cpu_target_measured_at < row.measured_at) reject(ctx, "target capture cannot precede machine probe");
});
export type HostFingerprintRow = z.infer<typeof HostFingerprintRowSchema>;
