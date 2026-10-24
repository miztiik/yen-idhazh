/** What do same-attempt task profiles and the separate RAM/copy proof actually measure? */
import { z } from "../../services/host-probes/node_modules/zod";
import { DateStampSchema, RequestIdSchema, RunIdSchema, SourceRunRecordSchema, WriterIdentitySchema } from "../../packages/common-contracts/src/index";
import type { TaskProfile } from "../../services/host-probes/src/task-profile/profile-schema";
import { probeBufferMib } from "../../services/host-fingerprints/src/inspect/copy-bandwidth";
import { ProfileProofIdentitySchema, ResourceProofSchema, StageProfileProofSchema } from "./feed-ingest-plan-profile-schema";
import type { ProfileProofIdentity, ResourceProof, StageProfileProof } from "./feed-ingest-plan-profile-schema";
import { escapeMarkdown, resourceNotice } from "./feed-ingest-plan-report-format";
import { formatPidCpuReport } from "./feed-ingest-plan-pid-report";
import { measurement } from "./feed-ingest-plan-resource-values";
import { formatCacheReport } from "./feed-ingest-plan-cache-report";

const ReportContextSchema = z.object({
  date: DateStampSchema, run_id: RunIdSchema, correlation_id: RequestIdSchema,
  planning_completion: z.object({
    run_id: RunIdSchema, attempt: WriterIdentitySchema.shape.attempt, correlation_id: RequestIdSchema,
  }),
  source_records: z.array(SourceRunRecordSchema),
});
type TaskRow = { work: string; profile: TaskProfile; replay: string };
export type ResourceReportControls = Readonly<{
  gitSha?: string; machineMemoryEnabled?: boolean; runNumber?: string; runAttempt?: string;
}>;

function requireIdentity(actual: ProfileProofIdentity, expected: ProfileProofIdentity): void {
  if (actual.git_sha !== expected.git_sha || actual.run_id !== expected.run_id
    || actual.attempt !== expected.attempt || actual.correlation_id !== expected.correlation_id) {
    throw new Error("Resource evidence differs from the completed planning attempt or executed revision");
  }
}

function readTaskRows(stage: StageProfileProof, identity: ProfileProofIdentity, sourceIds: Set<string>): TaskRow[] {
  requireIdentity(stage, identity);
  const rows: TaskRow[] = [];
  const requests = new Set<string>();
  const kinds = new Set<string>();
  for (const document of stage.documents) {
    requireIdentity({ ...document, attempt: stage.attempt }, identity);
    if (kinds.has(document.kind)) throw new Error("Repeated document resource evidence");
    kinds.add(document.kind);
    const profiling = document.profiling;
    if (profiling === undefined) continue;
    if ((profiling.actual_work_count !== null && profiling.actual_work_count !== profiling.profiles.length)
      || (profiling.after_checks_count !== null && (profiling.actual_work_count === null
        || profiling.after_checks_count !== profiling.actual_work_count))) {
      throw new Error("Resource profile counts differ from actual work or replay checks");
    }
    const replayVerified = document.status === "complete";
    if (replayVerified) {
      const journal = document.journal_records_sha256;
      if (profiling.actual_work_count !== 2 || profiling.after_checks_count !== 2
        || journal === null || journal.before_restart !== journal.after_checks) {
        throw new Error("Completed resource evidence lacks unchanged replay and journal proof");
      }
      for (const name of ["changed_input_conflict", "changed_operation_conflict", "changed_config_conflict"]) {
        const matches = document.calls.filter(call => call.stage === name);
        if (matches.length !== 1 || matches[0]?.http_status !== 409
          || matches[0].network.dns !== 0 || matches[0].network.http !== 0) {
          throw new Error("Completed resource evidence lacks offline conflict checks");
        }
      }
    }
    for (const profile of profiling.profiles) {
      const operation = profile.identity.task_name;
      const matches = document.calls.filter(call => call.stage === operation && call.endpoint === operation);
      const actual = matches[0];
      if (!["fetch", "parse"].includes(operation) || matches.length !== 1 || actual === undefined
        || profile.identity.pipeline_name !== "feed-ingest-plan"
        || profile.identity.run_id !== identity.run_id || profile.identity.correlation_id !== identity.correlation_id
        || profile.identity.request_id !== actual.request.request_id
        || actual.request.correlation_id !== identity.correlation_id
        || document.source_id === null || !sourceIds.has(document.source_id) || document.article_id === null
        || requests.has(profile.identity.request_id)
        || JSON.stringify(profile.config) !== JSON.stringify(stage.task_profile)) {
        throw new Error("Task profile identity, request or configuration differs from its document work");
      }
      requests.add(profile.identity.request_id);
      if (operation === "fetch" ? actual.request.source_id !== document.source_id || actual.request.kind !== document.kind
        : actual.request.article_id !== document.article_id
          || actual.request.fetch_request_id !== document.calls.find(call => call.stage === "fetch")?.request.request_id) {
        throw new Error("Task request refers to another document");
      }
      if (replayVerified) {
        const replays = document.calls.filter(call => call.stage === `${operation}_replay_after_restart`);
        const replay = replays[0];
        if (actual.http_status !== 200 || profile.outcome !== "success" || replays.length !== 1 || replay === undefined
          || replay.endpoint !== actual.endpoint || replay.http_status !== actual.http_status
          || replay.response_sha256 !== actual.response_sha256
          || JSON.stringify(replay.request) !== JSON.stringify(actual.request)
          || replay.network.dns !== 0 || replay.network.http !== 0) {
          throw new Error("Completed resource evidence lacks exact offline response replay");
        }
      }
      rows.push({ work: `${document.kind} / ${document.source_id} / ${operation} (${profile.outcome})`, profile,
        replay: replayVerified ? "Preserved; no new profile" : "Not verified" });
    }
  }
  if (stage.status === "complete" && (kinds.size !== 2 || stage.documents.some(document => document.status !== "complete"))) {
    throw new Error("Completed resource evidence requires both completed document checks");
  }
  return rows;
}

function processMemory(process: TaskProfile["processes"]["worker"]): string {
  const closing = process.closing;
  if (closing.unavailable["memory_kb.rss"] === "not_configured") return "Not configured";
  return `PID ${closing.pid ?? "unavailable"}; RSS ${measurement(closing.memory_kb.rss, "kB", closing.unavailable["memory_kb.rss"])}; sampled max ${measurement(process.sampled_rss_max_kb, "kB", process.unavailable.sampled_rss_max_kb)}`;
}

function machineMemory(profile: TaskProfile): string {
  if (!profile.config.machine_memory_enabled) return "Disabled; no task meminfo/vmstat reads";
  const closing = profile.samples.at(-1)!;
  return [...(["total", "free", "available"] as const).map(name =>
    `${name} ${measurement(closing.memory_kb[name], "kB", closing.unavailable[`memory_kb.${name}`])}`),
  `sampled min available ${measurement(profile.machine_available_min_kb, "kB", profile.unavailable.machine_available_min_kb)}`].join("; ");
}

function validateResourceProof(proof: ResourceProof, identity: ProfileProofIdentity): void {
  requireIdentity(proof, identity);
  const task = proof.task_profile;
  if (task !== null && (task.profile.identity.run_id !== identity.run_id
    || task.profile.identity.correlation_id !== identity.correlation_id)) {
    throw new Error("Controlled task CPU evidence differs from the completed planning attempt");
  }
  if (proof.status !== "complete") return;
  const memory = proof.sample?.memory_kb;
  const copy = proof.copy;
  if (proof.stage !== "complete" || proof.sample?.cpu == null || memory == null
    || memory.total === null || memory.total <= 0 || memory.free === null || memory.available === null
    || memory.free > memory.total || memory.available > memory.total
    || copy === null || copy.off === null || copy.on === null || copy.off.memcpy_probe_mib !== 0
    || copy.off.memcpy_gib_s !== null || copy.off_reason !== "configured_off"
    || copy.on.memcpy_gib_s === null || copy.on.memcpy_gib_s <= 0 || copy.on_reason !== null
    || copy.on.memcpy_probe_mib !== probeBufferMib(copy.floor_mib, copy.on.l3_cache_bytes, copy.cache_multiple)
    || copy.on.memcpy_probe_mib === null || copy.on.memcpy_probe_mib <= 0) {
    throw new Error("Completed standalone resource proof lacks actual RAM or separate copy OFF/ON measurements");
  }
}

export function formatResourceReport(input: ResourceReportControls & Readonly<{
  response: unknown; stageProof?: unknown; resourceProof?: unknown;
}>): Readonly<{ summary: string; annotations: readonly string[] }> {
  const context = ReportContextSchema.parse(input.response);
  if (context.planning_completion.run_id !== context.run_id
    || context.planning_completion.correlation_id !== context.correlation_id
    || (input.runNumber !== undefined && context.run_id !== `${context.date}-${input.runNumber}`)
    || (input.runAttempt !== undefined
      && context.planning_completion.attempt !== WriterIdentitySchema.shape.attempt.parse(Number(input.runAttempt)))
    || context.source_records.some(source => source.run_id !== context.run_id
      || source.attempt !== context.planning_completion.attempt || source.correlation_id !== context.correlation_id)) {
    throw new Error("Resource report requires one completed planning attempt");
  }
  const stage = input.stageProof == null ? null : StageProfileProofSchema.parse(input.stageProof);
  const resource = input.resourceProof == null ? null : ResourceProofSchema.parse(input.resourceProof);
  const identity = stage === null && resource === null ? null : ProfileProofIdentitySchema.parse({
    git_sha: input.gitSha, run_id: context.run_id, correlation_id: context.correlation_id,
    attempt: context.planning_completion.attempt,
  });
  if (stage !== null && input.machineMemoryEnabled !== undefined
    && stage.task_profile.machine_memory_enabled !== input.machineMemoryEnabled) {
    throw new Error("Task machine RAM evidence differs from the workflow input");
  }
  const rows = stage === null ? [] : readTaskRows(stage, identity!, new Set(context.source_records.map(source => source.source_id)));
  if (resource !== null) validateResourceProof(resource, identity!);
  const machineEnabled = stage?.task_profile.machine_memory_enabled ?? input.machineMemoryEnabled;
  const machineState = machineEnabled === false ? "Disabled" : machineEnabled === true ? "Enabled" : "Not recorded";
  const taskState = stage?.task_profile.enabled === false ? "Disabled" : "Not recorded";
  const annotations = rows.map(({ work, profile }) => resourceNotice(
    `${work}: ${measurement(profile.elapsed_ms, "ms")}; host CPU (not PID) ${profile.cpu.reason === null
      ? `${(profile.cpu.value.user + profile.cpu.value.system).toFixed(2)}% busy` : `unavailable (${profile.cpu.reason})`}; `
    + `${profile.periodic_sample_count} polls, ${profile.full_window_count} full windows; `
    + `process ${profile.config.memory_enabled ? processMemory(profile.processes.worker) : "RAM disabled"}; `
    + `machine RAM ${profile.config.machine_memory_enabled
      ? measurement(profile.machine_available_min_kb, "kB sampled min available", profile.unavailable.machine_available_min_kb) : "disabled"}.`,
  ));
  const sample = resource?.sample;
  const copy = resource?.copy;
  const copyHost = copy?.on ?? copy?.off;
  if (resource !== null) annotations.push(resourceNotice(
    `Standalone RAM HTTP/copy proof: ${resource.status}; L3 ${measurement(copyHost?.l3_cache_bytes ?? null, "bytes")}; `
    + `copy OFF ${copy?.off_reason === "configured_off" ? "configured off" : "not recorded"}; `
    + `copy ON ${measurement(copy?.on?.memcpy_gib_s ?? null, "GiB/s", copy?.on_reason ?? undefined)}. `
    + "This standalone RAM sample is not task machine-RAM profiling.",
  ));
  if (rows.length === 0) annotations.push(resourceNotice(
    `Task CPU and process RAM: ${taskState.toLowerCase()}; whole-machine task RAM: ${machineState.toLowerCase()}. No task measurements are inferred.`,
  ));
  const pidReport = formatPidCpuReport([
    ...rows,
    ...(resource?.task_profile == null ? [] : [{
      work: "Controlled CPU task / external PID", profile: resource.task_profile.profile,
    }]),
  ]);
  annotations.push(...pidReport.annotations);
  const cacheReport = resource === null ? { summary: "", annotations: [] as string[] } : formatCacheReport(resource);
  annotations.push(...cacheReport.annotations);
  const contextRows = resource === null ? ["| J1 | Standalone RAM and copy OFF/ON | Not recorded; resource-proof.json absent. |"] : [
    `| J1 | Standalone RAM HTTP sample (${resource.status}) | ${escapeMarkdown(sample == null ? "Not recorded" :
      `total ${measurement(sample.memory_kb.total, "kB", sample.unavailable["memory_kb.total"])}; free ${measurement(sample.memory_kb.free, "kB", sample.unavailable["memory_kb.free"])}; available ${measurement(sample.memory_kb.available, "kB", sample.unavailable["memory_kb.available"])}; interval ${measurement(sample.interval_ms, "ms")}; ${sample.sampled_at} UTC`)} |`,
    `| J2 | Standalone host | ${escapeMarkdown(`${resource.host.platform}; ${resource.host.arch}; kernel ${resource.host.release}; Bun ${resource.host.bun}`)} |`,
    `| J3 | ${copy?.on == null ? "Copy OFF" : "Copy ON"} CPU context | ${escapeMarkdown(copyHost == null ? "Not recorded" :
      `${copyHost.cpu_model ?? "Unavailable"}; logical ${copyHost.cpu_logical_processors ?? "unavailable"}; allowed ${copyHost.cpu_allowed_processors ?? "unavailable"}; quota ${copyHost.cpu_quota_state === "finite" ? measurement(copyHost.cpu_quota_cores, "cores") : copyHost.cpu_quota_state ?? "unavailable"}; fingerprint ${copyHost.fingerprint ?? "unavailable"}`)} |`,
    `| J4 | L3 cache | ${measurement(copyHost?.l3_cache_bytes ?? null, "bytes")} |`,
    `| J5 | Copy method and controls | ${copy == null ? "Not recorded" : `${copy.buffers} buffers; floor ${copy.floor_mib} MiB; cache multiple ${copy.cache_multiple}; ${copy.repeats} repeats; median read plus write`} |`,
    `| J6 | Copy OFF | ${escapeMarkdown(copy?.off == null ? "Not recorded" : `buffer ${measurement(copy.off.memcpy_probe_mib, "MiB")}; rate ${measurement(copy.off.memcpy_gib_s, "GiB/s", copy.off_reason ?? undefined)}`)} |`,
    `| J7 | Copy ON | ${escapeMarkdown(copy?.on == null ? "Not recorded" : `cache-derived buffer ${measurement(copy.on.memcpy_probe_mib, "MiB")}; rate ${measurement(copy.on.memcpy_gib_s, "GiB/s", copy.on_reason ?? undefined)}`)} |`,
  ];
  return { annotations, summary: [
    "## Resource measurements", "",
    `Whole-machine task RAM: **${machineState.toLowerCase()}**. CPU and process RAM have independent controls.`,
    `Document proof: ${stage?.status ?? "not recorded"}. Task rows come from the isolated HTTP check's stage-api-proof.json, not the full planner.`, "",
    "## Table H - Task CPU and sampling", "",
    "| Id | Work | Elapsed | Host CPU user / system / idle / wait / steal | CPU window / poll | Samples / full windows | Replay |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    ...rows.map(({ work, profile, replay }, index) => `| H${index + 1} | ${escapeMarkdown(work)} | ${measurement(profile.elapsed_ms, "ms")} | ${escapeMarkdown(profile.cpu.reason === null
      ? [profile.cpu.value.user, profile.cpu.value.system, profile.cpu.value.idle, profile.cpu.value.iowait, profile.cpu.value.steal].map(value => `${value.toFixed(2)}%`).join(" / ")
      : `Unavailable (${profile.cpu.reason.replaceAll("_", " ")})`)} | ${profile.config.cpu_window_ms} ms / ${profile.config.poll_interval_ms} ms | ${profile.sample_count} total; ${profile.periodic_sample_count} polls; ${profile.full_window_count} full windows; ${profile.full_window_count > 0 ? "full window recorded" : profile.elapsed_ms < profile.config.cpu_window_ms ? "partial window" : "no measured full window"} | ${replay} |`),
    ...(rows.length === 0 ? [`| H1 | Task profiles | ${taskState} | Unavailable | Not recorded | Not recorded | Not recorded |`] : []),
    "", "CPU percentages cover the whole host during actual work, not PID CPU or task-exclusive usage. The CPU window and polling cadence are independent; short work is never padded.", "",
    "## Table I - Task RAM", "",
    "| Id | Work | Process RAM | Whole-machine RAM |",
    "| --- | --- | --- | --- |",
    ...rows.map(({ work, profile }, index) => `| I${index + 1} | ${escapeMarkdown(work)} | ${escapeMarkdown(profile.config.memory_enabled
      ? `API ${processMemory(profile.processes.worker)}; server ${processMemory(profile.processes.server)}` : "Disabled")} | ${escapeMarkdown(machineMemory(profile))} |`),
    ...(rows.length === 0 ? [`| I1 | Task profiles | ${taskState} | ${machineState === "Disabled" ? "Disabled" : "Not recorded"} |`] : []),
    "", "RAM uses Linux kB (1024 bytes). RSS is resident process RAM, including other threads and collector overhead. Sampled maxima/minima are observations, not exact task peaks; lifetime high-water marks are not task peaks.", "",
    "## Table J - Separate RAM sample, cache and copy", "",
    "| Id | Observation | Recorded result |", "| --- | --- | --- |", ...contextRows, "",
    "The standalone probe writes resource-proof.json after document CPU windows close. Its one RAM HTTP sample still runs when task machine RAM is off. Copy OFF/ON is a separate bandwidth proof with two buffers, not L3 hit/miss counts or a task-RAM switch.", "",
    pidReport.summary,
    ...(cacheReport.summary ? ["", cacheReport.summary] : []),
  ].join("\n") };
}
