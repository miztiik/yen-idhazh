/** Show observed server readiness and cleanup without treating diagnostic lines as execution proof. */
import type { ServerEvidence } from "../../serve-pipeline-apis/src/server-evidence";
import { formatDuration } from "../src/reporting/aggregate-feed-results";
import { escapeMarkdown } from "../src/reporting/markdown-format";

export function renderServerEvidence(evidence: readonly ServerEvidence[]): string {
  const profiles = evidence.flatMap(server => server.reported_profiles.map(profile => ({ group: server.group, profile })));
  return [
    "<details>", "<summary>API servers</summary>", "",
    "## Table L - API servers", "",
    "| Id | Task | Startup | Observed startup | Shutdown | Log file | Failure |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    ...evidence.map((server, index) => {
      const duration = server.startup_ms === null ? "Unavailable" : `${server.startup_ms.toFixed(0)} ms`;
      const log = `\`${server.log_filename}\`${server.log_available ? "" : " (mirror unavailable)"}`;
      const errors = [server.error_code, server.cleanup_error_code].filter(code => code !== null).join("; ") || "None recorded";
      const shutdown = `${server.shutdown}${server.exit_code === null ? "" : ` (exit ${server.exit_code})`}`;
      return `| L${index + 1} | ${server.group} | ${server.startup} | ${duration} | ${shutdown} | ${log} | ${errors} |`;
    }),
    ...(evidence.length ? [] : ["| L1 | Server | Unavailable | Unavailable | Unavailable | Unavailable | No server outcome recorded |"]),
    "", "Ready means the owned child's enabled routes passed HTTP readiness. Startup time includes preparation. API results and actual exits, not log lines, establish task completion.", "",
    ...(profiles.length === 0 ? ["No native task-profile reports were captured. This does not prove no profiles ran.", ""] : [
      "## Table M - Captured task measurements", "",
      "| Id | Task | Outcome | Closed by | Measured time | Worker CPU time | Sampled worker RAM maximum | Native operation |",
      "| --- | --- | --- | --- | --- | --- | --- | --- |",
      ...profiles.map(({ group, profile }, index) => {
        const cpu = profile.processes.worker.cpu;
        const memory = profile.processes.worker.sampled_rss_max_kb;
        const outcome = profile.outcome === "cancelled" ? "Interrupted" : profile.outcome === "success" ? "Completed" : "Failed";
        return `| M${index + 1} | ${escapeMarkdown(`${group}: ${profile.identity.task_name}`)} | ${outcome} | ${escapeMarkdown(profile.end_reason)} | ${formatDuration(profile.elapsed_ms)} | ${cpu.reason === null ? formatDuration(cpu.value.cpu_time_ms) : "Unavailable"} | ${memory === null ? "Unavailable" : `${memory} KiB`} | \`${profile.traceId}\` / \`${profile.spanId}\` |`;
      }),
      "", "A shutdown-only profile is interrupted, not a completed task. Full native samples, unavailable reasons and identities remain in the server evidence artifact.", "",
    ]),
    "</details>", "",
  ].join("\n");
}
