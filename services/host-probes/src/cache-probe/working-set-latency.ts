/** What dependent-load latency does the installed native tool measure at each configured working set? */
import { arch, release } from "node:os";
import { readProcFile } from "../probe/proc-reader";
import type { ProbeContext } from "../probe/proc-reader";
import { readProcessIdentity } from "../task-profile/process-stat";
import type { CacheProbeConfig } from "./cache-config";
import { CACHE_API_VERSION, CacheLatencySchema } from "./cache-schema";
import type { CacheLatency, CacheReason } from "./cache-schema";
import { startBoundedTool } from "./bounded-tool";
import { parseMultichaseOutput } from "./latency-output";

export function refuseCacheLatency(reason: CacheReason): CacheLatency {
  return CacheLatencySchema.parse({
    version: CACHE_API_VERSION, kind: "cache_working_set_latency",
    status: reason === "configured_off" ? "disabled" : "unavailable", reason,
    measurement_obtained: false, host: null, interval: null, tool: "multichase",
    method: "single_dependent_random_pointer_chain", prefault: "chain_construction",
    warmup_samples_discarded: 1, sample_period_ms: 500, statistic: "mean_of_tool_samples",
    interpretation: "working_set_curve_not_direct_l3_hit_latency", points: [],
  });
}
export async function measureWorkingSetLatency(
  config: CacheProbeConfig, maxProcBytes: number, context: ProbeContext = {}, signal?: AbortSignal,
): Promise<CacheLatency> {
  const result = refuseCacheLatency("configured_off");
  const unavailable = (reason: CacheReason): CacheLatency => CacheLatencySchema.parse({
    ...result, status: reason === "configured_off" ? "disabled" : "unavailable", reason,
    measurement_obtained: false, points: [],
  });
  if (!config.latency.enabled) return unavailable("configured_off");
  if ((context.platform ?? process.platform) !== "linux") return unavailable("unsupported_platform");
  if (signal?.aborted) return unavailable("cancelled");
  const status = readProcFile(`${process.pid}/status`, maxProcBytes, context);
  const firstAllowed = status.reason === null ? /^Cpus_allowed_list:\s*(\d+)(?:[-,]\d+)*\s*$/m.exec(status.value)?.[1] : undefined;
  const allowed_cpu = Number(firstAllowed);
  if (!Number.isSafeInteger(allowed_cpu) || allowed_cpu < 0) return unavailable("affinity_unavailable");
  result.host = { platform: "linux", arch: arch(), release: release() };
  const started_at = new Date().toISOString(), started = performance.now();
  for (const working_set_bytes of config.latency.working_set_bytes) {
    const remaining = config.latency.timeout_ms - (performance.now() - started);
    if (remaining <= 0) return unavailable("timeout");
    if (signal?.aborted) return unavailable("cancelled");
    const tlb_locality_bytes = Math.min(config.latency.tlb_locality_bytes, working_set_bytes);
    const pointStartedAt = new Date().toISOString(), pointStarted = performance.now();
    const tool = startBoundedTool("multichase", [
      "-c", "simple", "-t", "1", "-m", String(working_set_bytes),
      "-s", String(config.latency.stride_bytes), "-T", String(tlb_locality_bytes),
      "-n", String(config.latency.samples), "-F", "0", "-a", "-v",
    ], { max_output_bytes: config.max_output_bytes, timeout_ms: remaining }, signal);
    const pid = await tool.ready;
    let identity: ReturnType<typeof readProcessIdentity> | null;
    try { identity = pid === null ? null : readProcessIdentity(pid, maxProcBytes, context); }
    catch (error) {
      tool.cancel("invalid_target");
      await tool.finished;
      throw error;
    }
    if (!identity || identity.reason !== null) {
      if (tool.running) tool.cancel("invalid_target");
      const output = await tool.finished;
      return unavailable(output.reason ?? "invalid_target");
    }
    const output = await tool.finished;
    if (output.reason) return unavailable(output.reason);
    if (output.code !== 0 || output.stderr.trim() !== "") return unavailable("tool_failed");
    try {
      const reading = parseMultichaseOutput(output.stdout, {
        working_set_bytes, stride_bytes: config.latency.stride_bytes, tlb_locality_bytes, samples: config.latency.samples,
      });
      result.points.push({
        ...reading, working_set_bytes, stride_bytes: config.latency.stride_bytes, tlb_locality_bytes,
        benchmark: { pid: identity.value.pid, start_ticks: identity.value.start_ticks }, allowed_cpu,
        interval: { started_at: pointStartedAt, finished_at: new Date().toISOString(), elapsed_ms: performance.now() - pointStarted },
      });
    } catch { return unavailable("invalid_output"); }
  }
  result.interval = { started_at, finished_at: new Date().toISOString(), elapsed_ms: performance.now() - started };
  return CacheLatencySchema.parse({ ...result, status: "measured", reason: null, measurement_obtained: true });
}
