/** Which bounded records are kept only with the shard's diagnostic artifacts? */
import { z } from "zod";

export const SHARD_MEMORY_VERSION = "2026-11-26";
const count = z.int().nonnegative();
const reading = count.nullable();
const version = z.literal(SHARD_MEMORY_VERSION);
const stamp = { version, ts: z.iso.datetime() };
const contract = {
  version: SHARD_MEMORY_VERSION,
  readCompatibility: "Legacy private artifacts lack a version; the native CLI reads only its own run receipt.",
  changelog: [{ version: SHARD_MEMORY_VERSION, change: "Bound the private shard diagnostics and omit executable paths and arguments." }],
};
export const ShardSampleSchema = z.strictObject({
  ...stamp, llama_vmrss_kb: reading, llama_vmhwm_kb: reading,
  python_vmrss_kb: reading, python_vmhwm_kb: reading, python_procs: reading,
  mem_total_kb: reading, mem_available_kb: reading, committed_as_kb: reading, cgroup_current_bytes: reading,
}).meta(contract);
export const PythonProcessSampleSchema = z.strictObject({
  ...stamp, pid: count.positive(), comm: z.string().startsWith("python"), vmrss_kb: count, vmhwm_kb: reading,
}).meta(contract);
export const ShardMemoryReceiptSchema = z.strictObject({
  version, status: z.enum(["closed", "server_exited", "expired", "artifact_limit"]),
  samples: count, llama_peak_hwm_kb: reading, python_peak_hwm_kb: reading, combined_peak_rss_kb: reading,
}).meta(contract);

export type PythonProcessSample = z.infer<typeof PythonProcessSampleSchema>;
export type ShardMemoryReceipt = z.infer<typeof ShardMemoryReceiptSchema>;
