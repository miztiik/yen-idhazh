/** Which CPU time and one-core use belong to each explicitly identified PID? */
import type { TaskProfile } from "../../host-probes/src/task-profile/profile-schema";
import { escapeMarkdown, resourceNotice } from "./feed-ingest-plan-report-format";
import { measurement } from "./feed-ingest-plan-resource-values";

export function formatPidCpuReport(tasks: readonly Readonly<{ work: string; profile: TaskProfile }>[]) {
  const entries = tasks.flatMap(({ work, profile }) => (["worker", "server"] as const).flatMap(role => {
    const process = profile.processes[role];
    return process.closing.pid === null ? [] : [{ work, role: role === "worker" ? "Task" : "Server", process }];
  }));
  return {
    annotations: entries.map(({ work, role, process }) => resourceNotice(
      `PID CPU ${work}: ${role.toLowerCase()} PID ${process.closing.pid}; `
      + `${measurement(process.cpu.value?.cpu_time_ms ?? null, "ms CPU", process.cpu.reason ?? undefined)} over `
      + `${measurement(process.cpu_interval_ms, "ms observed")}; mean `
      + `${measurement(process.cpu.value?.percent_one_core ?? null, "% of one core", process.cpu.reason ?? undefined)}. `
      + "This is process-wide CPU, not host CPU or guaranteed growth capacity.",
    )),
    summary: [
      "## Table K - PID CPU", "",
      "| Id | Work | Process | Actual interval | CPU time | Mean CPU (% of one core) | Sampled min / max (% of one core) |",
      "| --- | --- | --- | --- | --- | --- | --- |",
      ...entries.map(({ work, role, process }, index) => {
        const reason = process.cpu.reason ?? undefined;
        return `| K${index + 1} | ${escapeMarkdown(work)} | ${role} PID ${process.closing.pid} | `
          + `${measurement(process.cpu_interval_ms, "ms")} | ${measurement(process.cpu.value?.cpu_time_ms ?? null, "ms", reason)} | `
          + `${measurement(process.cpu.value?.percent_one_core ?? null, "%", reason)} | `
          + `${escapeMarkdown(`${measurement(process.sampled_cpu_min_percent_one_core, "%", process.unavailable.sampled_cpu_min_percent_one_core)} / `
            + measurement(process.sampled_cpu_max_percent_one_core, "%", process.unavailable.sampled_cpu_max_percent_one_core))} |`;
      }),
      ...(entries.length === 0 ? ["| K1 | Task profiles | Not recorded | Unavailable | Unavailable | Unavailable | Unavailable |"] : []),
      "", "One fully used core is 100 percent; a multi-threaded PID can exceed 100 percent. CPU uses the process's own actual interval, not the configured poll delay. Values include other work and threads in that process, not task-exclusive CPU. Controlled CPU work is a separate fixture, not extended live fetch or parse.", "",
    ].join("\n"),
  };
}
