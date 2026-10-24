/** Which versioned command exposes a host sample or owns a task profile? */
import type { ProbeConfig } from "../config";
import { sampleHost } from "../probe/sample-host";
import type { ProbeContext } from "../probe/proc-reader";
import type { TaskProfiling } from "../task-profile/task-profiler";
import { TaskProfileManager } from "./task-profile-manager";
import { postTaskProfile, probeErrorResponse } from "./task-profile-route";

// The calendar-versioned route is an API protocol identifier.
export const SAMPLE_PATH = "/api/2026-10-20/sample";
export const START_TASK_PROFILE_PATH = "/api/2026-10-24/start-task-profile";
export const STOP_TASK_PROFILE_PATH = "/api/2026-10-24/stop-task-profile";
// Bun's zero disables its idle timer; only the configured sampling delay applies.
const DISABLED_IDLE_TIMEOUT = 0;

export function createSampleHandler(
  config: ProbeConfig, context: ProbeContext = {},
  report: TaskProfiling["report"] = profile => { console.error(JSON.stringify({ event: "task_profile", profile })); },
) {
  const profiles = new TaskProfileManager({ config, context, report });
  const handler = async (request: Request): Promise<Response> => {
    try {
      const path = new URL(request.url).pathname;
      const method = path === SAMPLE_PATH ? "GET"
        : path === START_TASK_PROFILE_PATH || path === STOP_TASK_PROFILE_PATH ? "POST" : null;
      if (method === null) return Response.json({ error: "Not found" }, { status: 404, headers: { "Cache-Control": "no-store" } });
      if (request.method !== method) {
        return Response.json({ error: "Method not allowed" }, { status: 405, headers: { Allow: method, "Cache-Control": "no-store" } });
      }
      if (path === SAMPLE_PATH) return Response.json(await sampleHost(config, context), { headers: { "Cache-Control": "no-store" } });
      return await postTaskProfile(path === START_TASK_PROFILE_PATH ? "start" : "stop", request, profiles, config.max_request_body_bytes);
    } catch (error) { return probeErrorResponse(error); }
  };
  handler.close = () => profiles.shutdown();
  return handler;
}

export function serveSamples(config: ProbeConfig) {
  const handler = createSampleHandler(config);
  const server = Bun.serve({
    hostname: config.listen_host,
    port: config.listen_port,
    idleTimeout: DISABLED_IDLE_TIMEOUT,
    maxRequestBodySize: config.max_request_body_bytes,
    fetch: handler, error: probeErrorResponse,
  });
  let stopping: Promise<void> | undefined;
  return {
    url: server.url,
    stop(closeActiveConnections = false): Promise<void> {
      stopping ??= (async () => {
        try { await handler.close(); }
        finally { await server.stop(closeActiveConnections); }
      })();
      return stopping;
    },
  };
}
