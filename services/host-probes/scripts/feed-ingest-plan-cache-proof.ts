/** Prove default-off cache probes and real unprivileged Linux instrument results without claiming L3 hits. */
import { z } from "zod";
import { ProbeConfigSchema } from "../src/config";
import type { ProbeConfig } from "../src/config";
import { CacheProbeConfigSchema } from "../src/cache-probe/cache-config";
import { CacheCountersSchema, CacheCountersStartSchema, CacheLatencySchema } from "../src/cache-probe/cache-schema";
import { startCacheCounters } from "../src/cache-probe/cache-counters";
import { measureWorkingSetLatency } from "../src/cache-probe/working-set-latency";
import { readProcessIdentity } from "../src/task-profile/process-stat";
import { OwnedProcessSchema } from "../src/task-profile/profile-schema";
import { startBoundedTool } from "../src/cache-probe/bounded-tool";
import { CACHE_LATENCY_PATH, serveSamples } from "../src/api/server";
import type { TaskProfileProof } from "./feed-ingest-plan-profile-schema";
import { CacheAffinityProofSchema, verifyCacheAffinity } from "./host-cache-affinity-proof";

export const CacheProofSchema = z.strictObject({
  scope: z.literal("unprivileged_linux_cache_instruments"),
  status: z.enum(["running", "complete", "failed"]),
  stage: z.enum(["counters", "cancellation", "latency", "affinity", "complete"]),
  counters_measurement: z.enum(["pending", "measured", "partial_pending_supported_events", "pending_permitted_pmu_host"]),
  default_off: z.strictObject({ counters: CacheCountersSchema, latency: CacheLatencySchema }),
  counters: CacheCountersSchema.nullable(),
  task_api: z.strictObject({
    target: OwnedProcessSchema, handle: z.uuid(), expires_at: z.iso.datetime(),
    initial: CacheCountersStartSchema, target_alive_at_stop: z.literal(true), repeat_stop_identical: z.literal(true),
  }).nullable().default(null),
  latency: CacheLatencySchema.nullable(),
  affinity: CacheAffinityProofSchema.nullable().default(null),
  cancellation: z.strictObject({
    owned_benchmark: OwnedProcessSchema, reason: z.literal("cancelled"),
    benchmark_exited: z.literal(true), target_preserved: z.literal(true),
  }).nullable(),
  beyond_recorded_llc: z.boolean().nullable(),
  tool_install: z.strictObject({
    source_revision: z.string().regex(/^[a-f0-9]{40}$/),
    perf_source_revision: z.string().regex(/^[a-f0-9]{40}$/),
    perf_version: z.string().regex(/^perf version [0-9a-zA-Z.+_-]+$/),
    perf_fetch_seconds: z.int().nonnegative(), perf_build_seconds: z.int().nonnegative(),
    multichase_build_seconds: z.int().nonnegative(), python_execution_count: z.literal(0),
    perf_elf_libraries: z.array(z.string().regex(/^[a-zA-Z0-9_.+-]+$/))
      .refine(libraries => libraries.every(name => !/python/i.test(name))),
    perf_runtime_libraries: z.array(z.string().regex(/^[a-zA-Z0-9_.+-]+$/))
      .refine(libraries => libraries.every(name => !/python/i.test(name))),
    added_os_packages: z.array(z.strictObject({
      name: z.string().regex(/^[a-z0-9.+:-]+$/), version: z.string().min(1), installed_kib: z.int().nonnegative(),
    })).refine(packages => packages.every(pkg => !/^(python[0-9]|libpython)/.test(pkg.name))),
    install_seconds: z.int().nonnegative(), multichase_binary_bytes: z.int().positive(), perf_binary_bytes: z.int().positive(),
  }),
});
export async function verifyLiveCacheProfiling(
  identity: { run_id: string; correlation_id: string },
  config: ProbeConfig, hardware: { l3_cache_bytes: number | null }, installation: unknown,
  task: TaskProfileProof,
  report: (proof: z.infer<typeof CacheProofSchema>) => Promise<void>,
) {
  if (process.platform !== "linux" || process.geteuid?.() === 0) {
    throw new Error("Cache proof requires an unprivileged Linux operator, not a permission change");
  }
  const operator = readProcessIdentity(process.pid, config.max_proc_bytes, {});
  if (operator.reason !== null) throw new Error("Cache proof cannot pin its own controlled Bun operator");
  const target = { pid: operator.value.pid, start_ticks: operator.value.start_ticks };
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
    counters_measurement: "pending", default_off, counters: null, task_api: null, latency: null, affinity: null, cancellation: null,
    beyond_recorded_llc: null, tool_install: installation,
  });
  await report(proof);
  const enabled = CacheProbeConfigSchema.parse({
    ...config.cache_probe, counters: { ...config.cache_probe.counters, enabled: true },
    latency: { ...config.cache_probe.latency, enabled: true },
  });
  const counters = task.cache_counters;
  if (counters === null || task.cache_counters_start === null
    || counters.target.pid !== task.target.pid || counters.target.start_ticks !== task.target.start_ticks
    || task.profile.identity.run_id !== identity.run_id || task.profile.identity.correlation_id !== identity.correlation_id
    || !task.repeat_stop_identical) {
    throw new Error("Task HTTP cache counters did not retain the actual controlled PID");
  }
  proof.task_api = {
    target: task.target, handle: task.handle, expires_at: task.expires_at, initial: task.cache_counters_start,
    target_alive_at_stop: task.target_alive_at_stop, repeat_stop_identical: task.repeat_stop_identical,
  };
  proof.counters = counters;
  const permittedRefusal = ["permission_denied", "event_unsupported", "not_counted"].includes(counters.reason ?? "");
  proof.counters_measurement = counters.status === "measured"
    ? counters.events.every(event => event.support === "measured") ? "measured" : "partial_pending_supported_events"
    : permittedRefusal ? "pending_permitted_pmu_host" : "pending";
  await report(proof);
  if (counters.status !== "measured" && !permittedRefusal) {
    proof.status = "failed";
    await report(proof);
    throw new Error(`Cache counter capability failed explicitly: ${counters.reason}`);
  }
  proof.stage = "cancellation";
  await report(proof);
  const cancellation = new AbortController();
  const benchmark = startBoundedTool("multichase", [
    "-c", "simple", "-t", "1", "-m", String(enabled.latency.working_set_bytes[0]),
    "-s", String(enabled.latency.stride_bytes), "-n", String(enabled.latency.samples), "-F", "0",
  ], { max_output_bytes: enabled.max_output_bytes, timeout_ms: enabled.latency.timeout_ms }, cancellation.signal);
  const benchmarkPid = await benchmark.ready;
  let owned: ReturnType<typeof readProcessIdentity> | null;
  try { owned = benchmarkPid === null ? null : readProcessIdentity(benchmarkPid, config.max_proc_bytes, {}); }
  finally {
    cancellation.abort();
    await benchmark.finished;
  }
  const cancelled = await benchmark.finished;
  if (!owned || owned.reason !== null || cancelled.reason !== "cancelled"
    || readProcessIdentity(owned.value.pid, config.max_proc_bytes, {}).reason !== "process_exited"
    || readProcessIdentity(target.pid, config.max_proc_bytes, {}).value?.start_ticks !== target.start_ticks) {
    proof.status = "failed";
    await report(proof);
    throw new Error("Cache benchmark cancellation did not prove owned cleanup and target survival");
  }
  proof.cancellation = {
    owned_benchmark: { pid: owned.value.pid, start_ticks: owned.value.start_ticks },
    reason: "cancelled", benchmark_exited: true, target_preserved: true,
  };
  proof.stage = "latency";
  await report(proof);
  let listener: ReturnType<typeof serveSamples> | undefined;
  let latency: z.infer<typeof CacheLatencySchema>;
  try {
    listener = serveSamples(ProbeConfigSchema.parse({
      ...config, task_profile: { ...config.task_profile, enabled: false }, cache_probe: {
        ...enabled, counters: { ...enabled.counters, enabled: false },
      },
    }));
    const response = await fetch(new URL(CACHE_LATENCY_PATH, listener.url), {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      signal: AbortSignal.timeout(enabled.latency.timeout_ms), timeout: false,
    });
    if (response.status !== 200 || response.headers.get("cache-control") !== "no-store") {
      throw new Error("Cache latency HTTP endpoint did not return an uncached result");
    }
    latency = CacheLatencySchema.parse(await response.json());
  } finally { await listener?.stop(true); }
  proof.latency = latency;
  if (latency.status !== "measured" || latency.points.length !== enabled.latency.working_set_bytes.length) {
    proof.status = "failed";
    await report(proof);
    throw new Error(`Native cache-working-set latency was not measured: ${latency.reason}`);
  }
  proof.beyond_recorded_llc = hardware.l3_cache_bytes === null ? null
    : latency.points.at(-1)!.working_set_bytes > hardware.l3_cache_bytes;
  proof.stage = "affinity";
  await report(proof);
  proof.affinity = await verifyCacheAffinity(config);
  await report(proof);
  proof.status = "complete";
  proof.stage = "complete";
  await report(proof);
  return CacheProofSchema.parse(proof);
}
