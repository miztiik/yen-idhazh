/** Which same-task cache results and native-tool costs can the operator safely read? */
import { CacheProofSchema } from "./feed-ingest-plan-cache-proof";
import type { ResourceProof } from "./feed-ingest-plan-profile-schema";
import { escapeMarkdown, resourceNotice } from "./feed-ingest-plan-report-format";
import { measurement } from "./feed-ingest-plan-resource-values";

function workingSet(bytes: number): string {
  // Binary memory units are display protocol constants, not measurement controls.
  if (bytes % 1024 ** 3 === 0) return `${bytes / 1024 ** 3} GiB`;
  if (bytes % 1024 ** 2 === 0) return `${bytes / 1024 ** 2} MiB`;
  if (bytes % 1024 === 0) return `${bytes / 1024} KiB`;
  return `${bytes} bytes`;
}

export function formatCacheReport(resource: ResourceProof) {
  if (resource.cache === null) return { summary: "", annotations: [] as string[] };
  const cache = CacheProofSchema.parse(resource.cache);
  const task = resource.task_profile;
  const api = cache.task_api;
  const counters = cache.counters;
  if (api !== null || counters !== null || cache.status === "complete") {
    if (task === null || api === null || counters === null
      || api.handle !== task.handle || api.expires_at !== task.expires_at
      || api.target.pid !== task.target.pid || api.target.start_ticks !== task.target.start_ticks
      || counters.target.pid !== task.target.pid || counters.target.start_ticks !== task.target.start_ticks
      || api.target_alive_at_stop !== task.target_alive_at_stop || api.repeat_stop_identical !== task.repeat_stop_identical
      || JSON.stringify(api.initial) !== JSON.stringify(task.cache_counters_start)
      || JSON.stringify(counters) !== JSON.stringify(task.cache_counters)) {
      throw new Error("Cache evidence differs from the controlled task target, handle or cache result");
    }
  }
  const latency = cache.latency;
  for (const host of [counters?.host, latency?.host]) {
    if (host != null && (host.platform !== resource.host.platform
      || host.arch !== resource.host.arch || host.release !== resource.host.release)) {
      throw new Error("Cache evidence belongs to another host");
    }
  }
  const counterText = counters === null ? "Not recorded" : counters.events.map(event =>
    `${event.event}: ${event.support}${event.reason === null ? "" : ` (${event.reason.replaceAll("_", " ")})`}; `
    + (event.count === null ? "count null, not zero; event timing null" :
      `count ${event.count}; running ${measurement(event.time_running_ns, "ns")}; `
      + `running share ${measurement(event.running_percent, "%")}; multiplexing ${event.multiplexing}`)).join("; ");
  const curve = latency === null ? "Not recorded" : latency.status !== "measured"
    ? `${latency.status} (${latency.reason?.replaceAll("_", " ")}); no latency reading`
    : latency.points.map(point => `${workingSet(point.working_set_bytes)}: ${measurement(point.nanoseconds_per_load, "ns/load")}`).join("; ");
  const hardware = resource.copy?.on ?? resource.copy?.off;
  const observed = latency?.points.map(point => point.allowed_cpu) ?? [];
  const affinity = cache.affinity;
  if (affinity?.status === "verified" && (affinity.restricted_allowed_cpus === null
    || affinity.measured_cpu === null || !affinity.restricted_allowed_cpus.includes(affinity.measured_cpu)
    || affinity.measured_cpu === 0
    || (affinity.discontiguous_tested && !affinity.restricted_allowed_cpus.some((cpu, index, list) =>
      index > 0 && cpu - list[index - 1]! > 1)))) {
    throw new Error("Cache affinity evidence does not prove its reported CPU");
  }
  const tools = cache.tool_install;
  const coverage = counters?.measurement_obtained
    ? "Read the individual event support and interval; no L3 hit rate is inferred."
    : "Actual hardware counters were not measured.";
  const rows: readonly (readonly [string, string, string])[] = [
    ["L1", "Exact LLC events", `${counterText}${counters === null ? "" : `; target PID ${counters.target.pid}, start ticks ${counters.target.start_ticks}`}`],
    ["L2", "Native working-set curve", curve],
    ["L3", "Observed CPU and host",
      `${hardware?.cpu_model ?? "CPU model unavailable"}; L3 ${measurement(hardware?.l3_cache_bytes ?? null, "bytes")}; `
      + `logical/allowed ${hardware?.cpu_logical_processors ?? "unavailable"}/${hardware?.cpu_allowed_processors ?? "unavailable"}; `
      + `kernel ${resource.host.release}; observed benchmark CPUs ${[...new Set(observed)].join(",") || "unavailable"}; `
      + (affinity?.status === "verified"
        ? `restricted [${affinity.restricted_allowed_cpus?.join(",")}], verified CPU ${affinity.measured_cpu}`
        : `restricted affinity ${affinity?.reason?.replaceAll("_", " ") ?? "not recorded"}`)],
    ["L4", "Compliant native tools",
      `${tools.perf_version}; perf build ${tools.perf_build_seconds} seconds; total setup ${tools.install_seconds} seconds; `
      + `perf ${tools.perf_binary_bytes} bytes; multichase ${tools.multichase_binary_bytes} bytes; `
      + `perf-build Python executions ${tools.python_execution_count}; direct/resolved libraries exclude libpython`],
    ["L5", "Added OS dependencies", tools.added_os_packages.length === 0 ? "None; declared native tools already present" :
      tools.added_os_packages.map(pkg => `${pkg.name} ${pkg.version}: ${pkg.installed_kib} KiB installed`).join("; ")],
  ];
  return {
    summary: [
      "## Table L - Separate optional cache measurements", "",
      "| Id | Measurement | Observed result |", "| --- | --- | --- |",
      ...rows.map(([id, name, value]) => `| ${id} | ${escapeMarkdown(name)} | ${escapeMarkdown(value)} |`),
      "", `${coverage} The curve is NOT direct L3-hit latency, a hit rate, memory-copy throughput or caller task CPU. `
      + "The Python execution count covers the native perf build, not unrelated CI jobs.", "",
    ].join("\n"),
    annotations: [resourceNotice(
      `Cache instruments: ${counterText}. Working-set curve: ${curve}. ${coverage} NOT direct L3-hit latency. `
      + `Observed benchmark CPUs ${[...new Set(observed)].join(",") || "unavailable"}; ${hardware?.cpu_model ?? "host unavailable"}. `
      + `Perf build ${tools.perf_build_seconds} seconds; native perf/multichase ${tools.perf_binary_bytes}/${tools.multichase_binary_bytes} bytes; `
      + `perf-build Python executions ${tools.python_execution_count}.`,
    )],
  };
}
