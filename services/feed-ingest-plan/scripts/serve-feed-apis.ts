/** Dispatch validated feed startup to native assembly under the shared child lifetime. */
import { runHttpChild } from "@idhazh/serve-pipeline-apis/child";
import { runtimeFailureExecution } from "../src/api/plan-failure";
import { restorePlannerStartup } from "./restore-planner-startup";
import { captureFeedApiFailure } from "./capture-feed-api-failure";
import { FeedApiStartupSchema } from "./read-feed-api-startup";
import { startFeedApiApp } from "./create-feed-api-app";

export function runFeedApiServer(options: { restorePlanner?: typeof restorePlannerStartup } = {}) {
  return runHttpChild("TYPESCRIPT_API", captureFeedApiFailure({ operation: "listener-start" }), message => {
    const startup = FeedApiStartupSchema.parse(message);
    const capture = {
      operation: "listener-start" as const,
      ...(startup.group === "planning" ? {
        execution: runtimeFailureExecution(startup.planner.runtime),
        limits: startup.planner.settings.diagnostics.failure,
      } : {
        execution: { run_id: null, attempt: startup.run.attempt, traceId: startup.run.context.traceId,
          spanId: startup.run.context.spanId, git_sha: startup.delivery.git_sha },
        limits: startup.delivery.settings.diagnostics.failure,
      }),
    };
    return {
      shutdownTimeoutMs: startup.server.supervision.shutdown_timeout_ms,
      failure: captureFeedApiFailure(capture),
      start: signal => startFeedApiApp(startup, signal, options.restorePlanner),
    };
  });
}

if (import.meta.main) {
  try { await runFeedApiServer(); }
  catch { process.exitCode = 2; }
}
