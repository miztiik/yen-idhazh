/** Which versioned command samples, profiles or records a completed task? */
import { createChildContext, createRootContext, OperationMetadataSchema, readTraceContext } from "@idhazh/common-contracts";
import type { OperationMetadata } from "@idhazh/common-contracts";
import type { ProbeConfig } from "../config";
import { configureJobProfiles } from "../config";
import { createTaskPerformanceRecorder } from "../persist-task-performance";
import type { TaskPerformanceRecordingOptions } from "../persist-task-performance";
import { sampleHost } from "../probe/sample-host";
import type { ProbeContext } from "../probe/proc-reader";
import type { TaskProfiling } from "../task-profile/task-profiler";
import { CacheProbeController } from "../cache-probe/cache-controller";
import { TaskProfileManager } from "./task-profile-manager";
import { postTaskProfile, probeErrorResponse } from "./task-profile-route";
import { postCacheLatency } from "./cache-latency-route";
import { createProbeCompletionEvent, createProbeFailureEvent } from "./create-probe-event";
import type { ProbeEventOutput } from "./create-probe-event";
import { postRecordTaskPerformance, RECORD_TASK_PERFORMANCE_PATH } from "./record-task-performance-route";
import { ITEM_WINDOW_VERSION } from "../task-profile/item-window-schema";
export { RECORD_TASK_PERFORMANCE_PATH, RecordTaskPerformanceRequestSchema, RecordTaskPerformanceResponseSchema } from "./record-task-performance-route";

export type ProbeDiagnosticOptions = { writeEvent?: ProbeEventOutput; lifetimeContext?: OperationMetadata };

// The calendar-versioned route is an API protocol identifier.
export const SAMPLE_PATH = "/api/2026-11-05/sample-host";
export const START_TASK_PROFILE_PATH = "/api/2026-11-05/start-task-profile";
export const STOP_TASK_PROFILE_PATH = "/api/2026-11-05/stop-task-profile";
export const START_ITEM_WINDOW_PATH = `/api/${ITEM_WINDOW_VERSION}/start-item-profile`;
export const STOP_ITEM_WINDOW_PATH = `/api/${ITEM_WINDOW_VERSION}/stop-item-profile`;
export const CACHE_LATENCY_PATH = "/api/2026-11-05/measure-cache-latency";
// Bun's zero disables its idle timer; only the configured sampling delay applies.
const DISABLED_IDLE_TIMEOUT = 0;

export function createSampleHandler(
  config: ProbeConfig, context: ProbeContext = {},
  report: TaskProfiling["report"] = profile => { console.error(JSON.stringify({ event: "task_profile", profile })); },
  diagnostics: ProbeDiagnosticOptions = {},
  recording?: TaskPerformanceRecordingOptions,
) {
  const lifetime = OperationMetadataSchema.parse(diagnostics.lifetimeContext ?? createRootContext());
  const writeEvent: ProbeEventOutput = diagnostics.writeEvent ?? (event => { console.error(JSON.stringify(event)); });
  const cache = new CacheProbeController(config.cache_probe, config.max_proc_bytes, context);
  const recorder = recording === undefined ? undefined : createTaskPerformanceRecorder(recording);
  const profileConfig = recording === undefined ? config : configureJobProfiles(config, recording.settings);
  const profiles = new TaskProfileManager({ config: profileConfig, context, report, cache, writeEvent });
  const handler = async (request: Request): Promise<Response> => {
    const parent = readTraceContext({
      traceparent: request.headers.get("traceparent") ?? undefined,
      tracestate: request.headers.get("tracestate") ?? undefined,
    });
    const operation = parent === undefined ? createRootContext() : createChildContext(parent);
    const requestDiagnostics = { context: operation, writeEvent };
    try {
      const path = new URL(request.url).pathname;
      const method = path === SAMPLE_PATH ? "GET"
        : [START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH, START_ITEM_WINDOW_PATH, STOP_ITEM_WINDOW_PATH,
          CACHE_LATENCY_PATH, RECORD_TASK_PERFORMANCE_PATH].includes(path) ? "POST" : null;
      if (method === null) return Response.json({ error: "Not found" }, { status: 404, headers: { "Cache-Control": "no-store" } });
      if (request.method !== method) {
        return Response.json({ error: "Method not allowed" }, { status: 405, headers: { Allow: method, "Cache-Control": "no-store" } });
      }
      if (path === SAMPLE_PATH) {
        const result = await sampleHost(config, context);
        writeEvent(createProbeCompletionEvent({ context: operation, operation: "sample", outcome: "handled" }));
        return Response.json(result, { headers: { "Cache-Control": "no-store" } });
      }
      if (path === CACHE_LATENCY_PATH) {
        return await postCacheLatency(request, cache, config.max_request_body_bytes,
          config.cache_probe.lifecycle_timeout_ms, requestDiagnostics);
      }
      if (path === RECORD_TASK_PERFORMANCE_PATH) {
        return await postRecordTaskPerformance(request, recorder, config.max_request_body_bytes, requestDiagnostics);
      }
      return await postTaskProfile(path === START_TASK_PROFILE_PATH || path === START_ITEM_WINDOW_PATH ? "start" : "stop",
        request, profiles, config.max_request_body_bytes, requestDiagnostics,
        path === START_ITEM_WINDOW_PATH || path === STOP_ITEM_WINDOW_PATH ? "item" : "task",
        config.cache_probe.counters.enabled ? config.cache_probe.lifecycle_timeout_ms : undefined);
    } catch (error) {
      writeEvent(createProbeFailureEvent({ context: operation, type: "host_probe_failed" }));
      return probeErrorResponse(error);
    }
  };
  let closing: Promise<void> | undefined;
  handler.close = (): Promise<void> => {
    closing ??= (async () => {
      const results = await Promise.allSettled([profiles.shutdown(), cache.shutdown(), recorder?.close()]);
      const errors = results.filter(result => result.status === "rejected").map(result => result.reason);
      if (errors.length) {
        writeEvent(createProbeFailureEvent({ context: lifetime, type: "host_probe_cleanup_failed" }));
        throw new AggregateError(errors, "Host probe service cleanup failed");
      }
    })();
    return closing;
  };
  return handler;
}

export function serveSamples(
  config: ProbeConfig, diagnostics: ProbeDiagnosticOptions = {}, recording?: TaskPerformanceRecordingOptions,
) {
  const lifetime = OperationMetadataSchema.parse(diagnostics.lifetimeContext ?? createRootContext());
  const writeEvent: ProbeEventOutput = diagnostics.writeEvent ?? (event => { console.error(JSON.stringify(event)); });
  const handler = createSampleHandler(config, {}, undefined, { lifetimeContext: lifetime, writeEvent }, recording);
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
        const errors: unknown[] = [];
        let moduleClosed = false;
        try { await handler.close(); moduleClosed = true; }
        catch (error) { errors.push(error); }
        try { await server.stop(closeActiveConnections); }
        catch (error) {
          if (moduleClosed) writeEvent(createProbeFailureEvent({ context: lifetime, type: "host_probe_cleanup_failed" }));
          errors.push(error);
        }
        if (errors.length === 1) throw errors[0];
        if (errors.length > 1) throw new AggregateError(errors, "Host probe and listener cleanup failed");
      })();
      return stopping;
    },
  };
}
