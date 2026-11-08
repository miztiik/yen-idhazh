/** Show observed server readiness and cleanup without treating diagnostic lines as execution proof. */
import type { MachineServerEvidence } from "@idhazh/host-probes/machine-evidence";
import { formatDuration } from "../src/reporting/aggregate-feed-results";
import { escapeMarkdown } from "../src/reporting/markdown-format";

export function renderServerEvidence(evidence: readonly MachineServerEvidence[]): string {
  const profiles = evidence.flatMap(server => server.reported_profiles.map(profile => ({ group: server.group, profile })));
  return [
    "<details>", "<summary>API servers</summary>", "",
    "## Table L - API servers", "",
    "| Id | Server | Listener | API process / instance | Startup | Observed startup | Shutdown | Log file | Failure |",
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ...evidence.map((server, index) => {
      const duration = server.startup_ms === null ? "Unavailable" : `${server.startup_ms.toFixed(0)} ms`;
      const log = `\`${server.log_filename}\`${server.log_available ? "" : " (mirror unavailable)"}`;
      const errors = [server.error_code, server.cleanup_error_code].filter(code => code !== null).join("; ") || "None recorded";
      const shutdown = `${server.shutdown}${server.exit_code === null ? "" : ` (exit ${server.exit_code})`}`;
      const listener = server.version === "2026-11-07"
        ? `${server.listener.hostname}:${server.listener.port}` : "Not recorded";
      const process = server.pid === null ? "Not recorded" : `PID ${server.pid}`;
      const identity = server.version === "2026-11-07" && server.identity !== null
        ? ` / ${server.identity.nonce}` : " / instance not recorded";
      return `| L${index + 1} | ${server.group} | ${listener} | ${process}${identity} | ${server.startup} | ${duration} | ${shutdown} | ${log} | ${errors} |`;
    }),
    ...(evidence.length ? [] : ["| L1 | Server | Unavailable | Unavailable | Unavailable | Unavailable | Unavailable | Unavailable | No server outcome recorded |"]),
    "", "Ready means the owned child's enabled routes passed HTTP readiness. Startup time includes preparation. API results and actual exits, not log lines, establish task completion.", "",
    ...(profiles.length === 0 ? ["No native task-profile reports were captured. This does not prove no profiles ran.", ""] : [
      "## Table M - Captured task measurements", "",
      "| Id | Recorder / task | Measured process | Outcome | Closed by | Measured time | Target CPU time | Sampled target RAM maximum | Native operation |",
      "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
      ...profiles.map(({ group, profile }, index) => {
        const cpu = profile.processes.worker.cpu;
        const memory = profile.processes.worker.sampled_rss_max_kb;
        const outcome = profile.outcome === "cancelled" ? "Interrupted" : profile.outcome === "success" ? "Completed" : "Failed";
        const target = profile.processes.worker.closing;
        const process = target.pid === null ? "Unavailable"
          : `PID ${target.pid}; start ticks ${target.start_ticks ?? "unavailable"}`;
        return `| M${index + 1} | ${escapeMarkdown(`${group}: ${profile.identity.task_name}`)} | ${process} | ${outcome} | ${escapeMarkdown(profile.end_reason)} | ${formatDuration(profile.elapsed_ms)} | ${cpu.reason === null ? formatDuration(cpu.value.cpu_time_ms) : "Unavailable"} | ${memory === null ? "Unavailable" : `${memory} KiB`} | \`${profile.traceId}\` / \`${profile.spanId}\` |`;
      }),
      "", "The API process records the measurement; the target process is the work being measured. A shutdown-only profile is interrupted, not a completed task. Full native samples, unavailable reasons and identities remain in the server evidence artifact.", "",
    ]),
    "</details>", "",
  ].join("\n");
}
