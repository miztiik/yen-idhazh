/** How do recorded hardware capacity and task samples read without claiming unobserved minima? */
import type { TaskProfile } from "../../host-probes/src/task-profile/profile-schema";
import { ResourceProofSchema } from "../../host-probes/scripts/feed-ingest-plan-profile-schema";
import { WorkflowResourcesSchema } from "./feed-ingest-plan-workflow-resources";
import { escapeMarkdown } from "./feed-ingest-plan-report-format";
import { measurement } from "./feed-ingest-plan-resource-values";

// Linux proc "kB" is KiB; the displayed GB unit is exactly one billion bytes.
const BYTES_PER_PROC_KB = 1024;
const BYTES_PER_GB = 1_000_000_000;
const BYTES_PER_GIB = 2 ** 30;
const BYTES_PER_MIB = 2 ** 20;

export function formatRam(valueKb: number | null, totalKb?: number | null,
  quantity: "free" | "available" = "available", reason?: string): string {
  if (valueKb === null) return measurement(null, "GB", reason);
  const value = `${(valueKb * BYTES_PER_PROC_KB / BYTES_PER_GB).toFixed(2)} GB`;
  if (totalKb === undefined) return value;
  if (totalKb === null || totalKb <= 0 || valueKb > totalKb) {
    return `${value}; total or ${quantity} percentage unavailable`;
  }
  return `${value} / ${(totalKb * BYTES_PER_PROC_KB / BYTES_PER_GB).toFixed(2)} GB total (${(valueKb / totalKb * 100).toFixed(2)}% ${quantity})`;
}

function observedMinimum(profile: TaskProfile): string {
  const minimum = profile.machine_available_min_kb;
  const minimumTotals = profile.samples.filter(sample => sample.memory_kb.available === minimum)
    .map(sample => sample.memory_kb.total);
  const minimumTotal = minimumTotals.length > 0 && minimumTotals.every(total => total === minimumTotals[0])
    ? minimumTotals[0] : null;
  return formatRam(minimum, minimumTotal, "available", profile.unavailable.machine_available_min_kb);
}

function profileRows(profile: TaskProfile, planner: boolean): string[][] {
  const closing = profile.samples.at(-1)!;
  const worker = profile.processes.worker;
  return [
    ["Process scope", planner ? "The HTTP listener and planner share one Bun PID; there is no separate server PID to measure or count twice"
      : "Separate controlled CPU work and its own server; not the live planner"],
    ["Profile interval", `${profile.elapsed_ms.toFixed(0)} milliseconds; ${profile.sample_count} observations; ${profile.config.poll_interval_ms} milliseconds poll interval; outcome ${profile.outcome}`],
    ["Process RAM at close", formatRam(worker.closing.memory_kb.rss, undefined, "available", worker.closing.unavailable["memory_kb.rss"])],
    ["Highest observed process RAM", formatRam(worker.sampled_rss_max_kb, undefined, "available", worker.unavailable.sampled_rss_max_kb)],
    ["Process CPU", `${measurement(worker.cpu.value?.cpu_time_ms ?? null, "milliseconds CPU", worker.cpu.reason ?? undefined)}; ${measurement(worker.cpu.value?.percent_one_core ?? null, "percent of one core", worker.cpu.reason ?? undefined)}; process-wide, not article-exclusive`],
    ["Machine free RAM at close", formatRam(closing.memory_kb.free, closing.memory_kb.total, "free", closing.unavailable["memory_kb.free"])],
    ["Machine available RAM at close", formatRam(closing.memory_kb.available, closing.memory_kb.total, "available", closing.unavailable["memory_kb.available"])],
    ["Lowest observed available RAM", `${observedMinimum(profile)}; sampled observations only, not an assured whole-run minimum`],
  ];
}

export function formatResourceSummary(input: unknown, independent: unknown, requested: boolean | undefined) {
  const resources = input === undefined ? undefined : WorkflowResourcesSchema.parse(input);
  const proof = independent === undefined ? undefined : ResourceProofSchema.parse(independent);
  const rows: { scope: string; fact: string; value: string }[] = [];
  const add = (scope: string, entries: string[][]) => {
    for (const [fact, value] of entries) rows.push({ scope, fact: fact!, value: value! });
  };
  const profileRequested = resources?.profile_requested ?? requested;
  let hostNotice = "Actual host: unavailable (host evidence was not saved)";
  if (resources?.host.status === "recorded") {
    const { row, unavailable } = resources.host;
    const reason = (field: string) => unavailable[field] ?? unavailable.platform ?? "not observed";
    const cpu = row.cpu_model ?? `Unavailable (${unavailable.cpu_model ?? unavailable.platform ?? "not observed"})`;
    const cache = row.l3_cache_bytes === null ? `Unavailable (${unavailable.l3_cache_bytes ?? unavailable.platform ?? "not observed"})`
      : `${(row.l3_cache_bytes / BYTES_PER_MIB).toFixed(2)} MiB`;
    const capacity = measurement(row.machine_memory_total_mib, "MiB", reason("machine_memory_total_mib"));
    add("Actual host", [
      ["CPU", cpu], ["Logical / allowed processors", `${measurement(row.cpu_logical_processors, "processors", reason("cpu_logical_processors"))} / ${measurement(row.cpu_allowed_processors, "processors", reason("cpu_allowed_processors"))}`],
      ["CPU quota", row.cpu_quota_state === "unlimited" ? "No quota" : measurement(row.cpu_quota_cores, "cores", reason("cpu_quota_cores"))],
      ["L3 cache", cache], ["Total machine RAM capacity", capacity],
      ["Completed host files", `${resources.host.files.length} raw Parquet file; publication is recorded separately`],
      ["Hardware fingerprint", row.fingerprint ?? `Unavailable (${unavailable.platform ?? "not observed"})`],
      ["Observation clock", row.measured_at === null ? "Unavailable" : `${row.measured_at} UTC`],
    ]);
    hostNotice = `Actual host: ${cpu}; ${measurement(row.cpu_allowed_processors, "allowed processors", reason("cpu_allowed_processors"))}; L3 ${cache}; total RAM ${capacity}`;
  } else {
    add("Actual host", [["Collection", resources?.host.reason ?? "Unavailable; host evidence was not saved"]]);
    if (resources !== undefined) hostNotice = `Actual host: ${resources.host.status} (${resources.host.reason})`;
  }
  let profileNotice: string;
  if (resources?.profile.status === "recorded") {
    const profile = resources.profile.value;
    add("Live planner process", profileRows(profile, true));
    const closing = profile.samples.at(-1)!;
    profileNotice = `Planner process RAM ${formatRam(profile.processes.worker.closing.memory_kb.rss, undefined,
      "available", profile.processes.worker.closing.unavailable["memory_kb.rss"])}; `
      + `machine free ${formatRam(closing.memory_kb.free, closing.memory_kb.total, "free", closing.unavailable["memory_kb.free"])}; `
      + `machine available ${formatRam(closing.memory_kb.available, closing.memory_kb.total, "available", closing.unavailable["memory_kb.available"])}; `
      + `lowest observed available ${observedMinimum(profile)} (samples only). `
      + "Planner and HTTP listener share one PID";
  } else {
    const reason = resources?.profile.reason ?? (profileRequested === false
      ? "profile_machine_memory=false" : "The whole-planner process profile was not saved");
    add("Live planner process", [["CPU and RAM profiling", `${resources?.profile.status ?? "Unavailable"} (${reason})`],
      ["Process scope", "The HTTP listener and planner share one Bun PID; no separate server PID is required"]]);
    profileNotice = `Planner CPU/RAM profiling: ${resources?.profile.status ?? "unavailable"} (${reason})`;
  }
  let independentNotice: string;
  if (proof === undefined) {
    independentNotice = profileRequested === false ? "Independent CPU/copy/cache proof: not requested"
      : "Independent CPU/copy/cache proof: unavailable (no result saved)";
    add("Independent controlled proof", [["Result", independentNotice]]);
  } else {
    independentNotice = `Independent CPU/copy/cache proof: ${proof.status} at ${proof.stage}; not live planner measurements`;
    add("Independent controlled proof", [["Result", `${proof.status} at ${proof.stage}${proof.error === null ? "" : `; ${proof.error}`}`]]);
    if (proof.sample !== null) add("Independent host sample", [
      ["Free RAM", formatRam(proof.sample.memory_kb.free, proof.sample.memory_kb.total, "free", proof.sample.unavailable["memory_kb.free"])],
      ["Available RAM", formatRam(proof.sample.memory_kb.available, proof.sample.memory_kb.total, "available", proof.sample.unavailable["memory_kb.available"])],
    ]);
    if (proof.task_profile !== null) add("Independent controlled process", profileRows(proof.task_profile.profile, false));
    if (proof.copy !== null) add("Independent copy proof", [
      ["Copy rate", proof.copy.on?.memcpy_gib_s == null ? measurement(null, "GB/second", proof.copy.on_reason ?? "not measured")
        : `${(proof.copy.on.memcpy_gib_s * BYTES_PER_GIB / BYTES_PER_GB).toFixed(2)} GB/second; median read plus write`],
      ["Copy buffers", proof.copy.on?.memcpy_probe_mib == null ? measurement(null, "GB", proof.copy.on_reason ?? "not measured")
        : `${proof.copy.buffers} buffers of ${(proof.copy.on.memcpy_probe_mib * BYTES_PER_MIB / BYTES_PER_GB).toFixed(2)} GB each`],
    ]);
    if (proof.cache !== null) add("Independent cache proof", [
      ["Counters", `${proof.cache.counters_measurement.replaceAll("_", " ")}; ${proof.cache.counters?.reason?.replaceAll("_", " ") ?? "no refusal reported"}`],
      ["Latency", proof.cache.latency?.measurement_obtained ? "Measured by the separate pointer-chase tool"
        : `Unavailable (${proof.cache.latency?.reason?.replaceAll("_", " ") ?? "no measurement obtained"})`],
      ["Python execution", `${proof.cache.tool_install.python_execution_count} executions; native tools only`],
    ]);
  }
  return {
    notice: `${hostNotice}. ${profileNotice}. ${independentNotice}. Free RAM excludes reclaimable cache; available RAM includes it.`,
    summary: [
      "## Table G - Resources", "",
      "| Id | Scope | Measurement | Recorded value |", "| --- | --- | --- | --- |",
      ...rows.map((row, index) => `| G${index + 1} | ${escapeMarkdown(row.scope)} | ${escapeMarkdown(row.fact)} | ${escapeMarkdown(row.value)} |`),
      "", "MiB means 1,048,576 bytes; L3 cache and total machine RAM capacity use MiB. Task RAM uses GB (1,000,000,000 bytes). Linux proc kB values are KiB (1,024 bytes). Free RAM excludes reclaimable cache; available RAM includes it. Unavailable readings are not zero.", "",
    ].join("\n"),
  };
}
