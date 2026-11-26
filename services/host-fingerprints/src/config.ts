/** Which authored controls and selected observability settings govern collection? */
import { z } from "zod";
import { constants } from "node:buffer";
import { HOST_FINGERPRINT_PRODUCER, JobNameSchema, WriterIdentitySchema } from "@idhazh/common-contracts";

export const SERVICE_ROOT = new URL("../", import.meta.url);
export const REPOSITORY_ROOT = new URL("../../../", import.meta.url);
export const ServiceConfigSchema = z.strictObject({
  listen_host: z.string().min(1), listen_port: z.int().min(1).max(65535),
  max_input_bytes: z.int().positive().max(constants.MAX_LENGTH - 1),
  max_online_processors: z.int().positive(),
  cache_indices: z.array(z.int().nonnegative()).min(1).refine((ids) => new Set(ids).size === ids.length),
  max_cgroup_depth: z.int().positive(),
  metadata_url: z.url().refine((url) => new URL(url).hostname === "169.254.169.254", "metadata must use the host link-local address").nullable(),
  metadata_timeout_ms: z.int().positive().max(2 ** 31 - 1),
  copy_repeats: z.int().positive(),
});
export const SelectedSettingsSchema = z.object({
  observability: z.object({
    host_telemetry_enabled: z.boolean(),
    host_fingerprint: z.boolean(),
    host_fingerprint_frequency_enabled: z.boolean(),
    host_fingerprint_placement_enabled: z.boolean(),
    host_fingerprint_bandwidth_jobs: z.array(z.string()),
    host_fingerprint_bandwidth_floor_mib: z.int().nonnegative(),
    host_fingerprint_bandwidth_cache_multiple: z.int().positive(),
  }),
  ledger: z.object({
    format: z.literal("parquet"),
    compression_raw: z.enum(["snappy", "zstd", "none"]),
    compression_compact: z.enum(["snappy", "zstd", "none"]),
  }),
});
export const FingerprintTargetSchema = z.strictObject({
  pid: z.int().positive(), start_ticks: z.string().regex(/^\d{1,20}$/),
});
export type FingerprintTarget = z.infer<typeof FingerprintTargetSchema>;

export const FingerprintRequestSchema = z.strictObject({
  date: z.iso.date(),
  writer: WriterIdentitySchema.safeExtend({
    pipeline_name: JobNameSchema, task_name: JobNameSchema, producer: z.literal(HOST_FINGERPRINT_PRODUCER),
  }),
  target: FingerprintTargetSchema.nullable().optional(),
  ask_placement: z.literal(false).optional(),
});
export const CaptureContextSchema = FingerprintRequestSchema;
export type ServiceConfig = z.infer<typeof ServiceConfigSchema>;
export type SelectedSettings = z.infer<typeof SelectedSettingsSchema>;
export type CaptureContext = z.infer<typeof CaptureContextSchema>;

export async function loadConfig(path: string | URL = new URL("config/host-fingerprints.json", REPOSITORY_ROOT)): Promise<ServiceConfig> {
  return ServiceConfigSchema.parse(await Bun.file(path).json());
}
export async function loadSettings(path: string | URL = new URL("config/idhazh.json", REPOSITORY_ROOT)): Promise<SelectedSettings> {
  return SelectedSettingsSchema.parse(await Bun.file(path).json());
}
