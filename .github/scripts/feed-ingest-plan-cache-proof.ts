/** Prove default-off cache probes and real unprivileged Linux instrument results without claiming L3 hits. */
import { createHash } from "node:crypto";
import { z } from "../../services/host-probes/node_modules/zod";
import type { ProbeConfig } from "../../services/host-probes/src/config";
import { CacheProbeConfigSchema } from "../../services/host-probes/src/cache-probe/cache-config";
import { CacheCountersSchema, CacheLatencySchema } from "../../services/host-probes/src/cache-probe/cache-schema";
import { startCacheCounters } from "../../services/host-probes/src/cache-probe/cache-counters";
import { measureWorkingSetLatency } from "../../services/host-probes/src/cache-probe/working-set-latency";
import { readProcessIdentity } from "../../services/host-probes/src/task-profile/process-memory";

export const CacheProofSchema = z.strictObject({
  scope: z.literal("unprivileged_linux_cache_instruments"),
  status: z.enum(["running", "complete", "failed"]),
  stage: z.enum(["counters", "latency", "complete"]),
  counters_measurement: z.enum(["pending", "measured", "pending_permitted_pmu_host"]),
  default_off: z.strictObject({ counters: CacheCountersSchema, latency: CacheLatencySchema }),
  counters: CacheCountersSchema.nullable(),
  latency: CacheLatencySchema.nullable(),
  beyond_recorded_llc: z.boolean().nullable(),
  tool_install: z.strictObject({
    source_revision: z.string().regex(/^[a-f0-9]{40}$/),
    install_seconds: z.int().nonnegative(), multichase_binary_bytes: z.int().positive(), perf_binary_bytes: z.int().positive(),
  }),
});
export async function verifyLiveCacheProfiling(
  config: ProbeConfig, hardware: { l3_cache_bytes: number | null }, installation: unknown,
  report: (proof: z.infer<typeof CacheProofSchema>) => Promise<void>,
) {
  if (process.platform !== "linux" || process.geteuid?.() === 0) {
    throw new Error("Cache proof requires an unprivileged Linux operator, not a permission change");
  }
  const identity = readProcessIdentity(process.pid, config.max_proc_bytes, {});
  if (identity.reason !== null) throw new Error("Cache proof cannot pin its own controlled Bun target");
  const target = { pid: identity.value.pid, start_ticks: identity.value.start_ticks };
  const off = CacheProbeConfigSchema.parse({
    ...config.cache_probe, counters: { ...config.cache_probe.counters, enabled: false },
    latency: { ...config.cache_probe.latency, enabled: false },
  });
  // An invalid proc root would fail a live read. Off must not inspect it or start a tool.
  const default_off = {
    counters: await (await startCacheCounters(off, target, config.max_proc_bytes, { procRoot: "cache-off-must-not-read" })).close(),
    latency: await measureWorkingSetLatency(off, config.max_proc_bytes, { procRoot: "cache-off-must-not-read" }),
  };
  if (default_off.counters.status !== "disabled" || default_off.latency.status !== "disabled") {
    throw new Error("Ordinary cache controls did not remain off");
  }
  const proof = CacheProofSchema.parse({
    scope: "unprivileged_linux_cache_instruments", status: "running", stage: "counters",
    counters_measurement: "pending", default_off, counters: null, latency: null,
    beyond_recorded_llc: null, tool_install: installation,
  });
  await report(proof);
  const enabled = CacheProbeConfigSchema.parse({
    ...config.cache_probe, counters: { ...config.cache_probe.counters, enabled: true },
    latency: { ...config.cache_probe.latency, enabled: true },
  });
  const capture = await startCacheCounters(enabled, target, config.max_proc_bytes);
  if (capture.initial === null) {
    const started = performance.now();
    while (performance.now() - started < config.sample_interval_ms) createHash("sha256").update("owned-cache-proof").digest();
  }
  const counters = await capture.close();
  proof.counters = counters;
  const permittedRefusal = ["permission_denied", "event_unsupported", "not_counted"].includes(counters.reason ?? "");
  proof.counters_measurement = counters.status === "measured" ? "measured" : permittedRefusal ? "pending_permitted_pmu_host" : "pending";
  await report(proof);
  if (counters.status !== "measured" && !permittedRefusal) {
    proof.status = "failed";
    await report(proof);
    throw new Error(`Cache counter capability failed explicitly: ${counters.reason}`);
  }
  proof.stage = "latency";
  await report(proof);
  const latency = await measureWorkingSetLatency(enabled, config.max_proc_bytes);
  proof.latency = latency;
  if (latency.status !== "measured" || latency.points.length !== enabled.latency.working_set_bytes.length) {
    proof.status = "failed";
    await report(proof);
    throw new Error(`Native cache-working-set latency was not measured: ${latency.reason}`);
  }
  proof.beyond_recorded_llc = hardware.l3_cache_bytes === null ? null
    : latency.points.at(-1)!.working_set_bytes > hardware.l3_cache_bytes;
  proof.status = "complete";
  proof.stage = "complete";
  await report(proof);
  return CacheProofSchema.parse(proof);
}
