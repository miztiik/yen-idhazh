/** What CPU interval and closing memory observations are available now? */
import { z } from "zod";
import type { ProbeConfig } from "../config";
import { calculateCpuPercentages, parseCpuCounters } from "./cpu-sampler";
import { parseMemoryInfo, parseVmstat } from "./memory-probe";
import { readProcFile } from "./proc-reader";
import type { ProbeContext } from "./proc-reader";

const percentage = z.number().finite().min(0).max(100);
const counter = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);
export const HostSampleSchema = z.object({
  sampled_at: z.iso.datetime(),
  interval_ms: z.number().finite().nonnegative(),
  cpu: z.object({
    user: percentage, system: percentage, idle: percentage, iowait: percentage, steal: percentage,
  }).strict().nullable(),
  memory_kb: z.object({
    total: counter.nullable(), free: counter.nullable(), available: counter.nullable(),
  }).strict(),
  vmstat: z.object({
    pgfault: counter, pgmajfault: counter, pswpin: counter, pswpout: counter,
  }).strict().nullable(),
  unavailable: z.record(z.string(), z.enum([
    "unsupported_platform", "missing_file", "permission_denied", "too_large",
    "invalid_data", "missing_field", "counter_reset", "no_ticks",
  ])),
}).strict();
export type HostSample = z.infer<typeof HostSampleSchema>;

export async function sampleHost(config: ProbeConfig, context: ProbeContext = {}): Promise<HostSample> {
  const opening = readProcFile("stat", config.max_proc_bytes, context);
  const start = opening.reason === null ? parseCpuCounters(opening.value) : opening;
  const started = performance.now();
  if (start.reason === null) await Bun.sleep(config.sample_interval_ms);
  const closing = readProcFile("stat", config.max_proc_bytes, context);
  const interval_ms = performance.now() - started;
  const end = closing.reason === null ? parseCpuCounters(closing.value) : closing;
  const cpu = calculateCpuPercentages(start, end);
  const memoryText = readProcFile("meminfo", config.max_proc_bytes, context);
  const memory = parseMemoryInfo(memoryText.reason === null ? memoryText.value : "");
  const vmstatText = readProcFile("vmstat", config.max_proc_bytes, context);
  const vmstat = vmstatText.reason === null ? parseVmstat(vmstatText.value) : vmstatText;
  const unavailable: HostSample["unavailable"] = {};
  if (cpu.reason !== null) unavailable.cpu = cpu.reason;
  if (vmstat.reason !== null) unavailable.vmstat = vmstat.reason;
  for (const name of ["total", "free", "available"] as const) {
    const reason = memoryText.reason ?? memory.unavailable[name];
    if (reason !== undefined && reason !== null) unavailable[`memory_kb.${name}`] = reason;
  }
  return HostSampleSchema.parse({
    sampled_at: new Date().toISOString(), interval_ms, cpu: cpu.value,
    memory_kb: memory.value, vmstat: vmstat.value, unavailable,
  });
}
