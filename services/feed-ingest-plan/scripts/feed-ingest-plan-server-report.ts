/** Show observed server readiness and cleanup without treating diagnostic lines as execution proof. */
import type { ServerEvidence } from "../../typescript-api/src/server-evidence";

export function renderServerEvidence(evidence: readonly ServerEvidence[]): string {
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
    "</details>", "",
  ].join("\n");
}
