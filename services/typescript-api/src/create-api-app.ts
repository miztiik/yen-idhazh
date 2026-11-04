/** How do enabled native API handlers share one listener and one awaited cleanup? */
import { Hono } from "hono";
import { createPlanApp } from "@idhazh/feed-ingest-plan/api";
import { createSafePersistApp } from "@idhazh/feed-ingest-plan/delivery-api";
import { createFingerprintHandler, FINGERPRINT_PATH, HEALTH_PATH } from "@idhazh/host-fingerprints/api";
import {
  CACHE_LATENCY_PATH, createSampleHandler, SAMPLE_PATH, START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH,
} from "@idhazh/host-probes/api";
import { API_HEALTH_PATH } from "./api-startup";
import type { ApiReady } from "./api-startup";
import { apiOrigin } from "./load-settings";
import type { HonoServerSettings } from "./load-settings";

type FingerprintOptions = Parameters<typeof createFingerprintHandler>;
type ProbeOptions = Parameters<typeof createSampleHandler>;
export type ApiModuleInputs = {
  identity: ApiReady;
  planner?: {
    inputs: Parameters<typeof createPlanApp>[0];
    runtime: Parameters<typeof createPlanApp>[1];
    identity: Parameters<typeof createPlanApp>[2];
  };
  fingerprint?: { config: FingerprintOptions[0]; settings: FingerprintOptions[1]; options: FingerprintOptions[2] };
  probes?: { config: ProbeOptions[0]; context?: ProbeOptions[1]; report?: ProbeOptions[2] };
  delivery?: Parameters<typeof createSafePersistApp>[0];
};
export type ApiBindings = {
  beginPlanning?: () => void;
  beginDelivery?: () => void;
  stage_origin?: string;
};

export function createApiApp(input: ApiModuleInputs) {
  const enabled = new Set(input.identity.modules);
  if (enabled.has("planning") !== (input.planner !== undefined)
    || enabled.has("delivery") !== (input.delivery !== undefined)
    || enabled.has("machine") !== (input.fingerprint !== undefined && input.probes !== undefined)
    || (input.fingerprint === undefined) !== (input.probes === undefined)) {
    throw new Error("Readiness must identify exactly the actual enabled API modules");
  }
  const app = new Hono<{ Bindings: ApiBindings }>();
  const cancellation = new AbortController();
  const pending = new Set<Promise<Response>>();
  const planner = input.planner === undefined ? undefined : createPlanApp(input.planner.inputs, {
    ...input.planner.runtime,
    signal: AbortSignal.any([cancellation.signal, ...(
      input.planner.runtime.signal === undefined ? [] : [input.planner.runtime.signal]
    )]),
  }, input.planner.identity);
  const probe = input.probes === undefined ? undefined
    : createSampleHandler(input.probes.config, input.probes.context, input.probes.report);
  if (planner !== undefined) app.route("/", planner);
  if (input.delivery !== undefined) app.route("/", createSafePersistApp({
    ...input.delivery, signal: AbortSignal.any([input.delivery.signal, cancellation.signal]),
  }));
  if (input.fingerprint !== undefined) {
    const handler = createFingerprintHandler(input.fingerprint.config, input.fingerprint.settings, input.fingerprint.options);
    app.all(FINGERPRINT_PATH, c => handler(c.req.raw));
    app.all(HEALTH_PATH, c => handler(c.req.raw));
  }
  if (probe !== undefined) {
    for (const path of [SAMPLE_PATH, START_TASK_PROFILE_PATH, STOP_TASK_PROFILE_PATH, CACHE_LATENCY_PATH]) {
      app.all(path, c => probe(c.req.raw));
    }
  }
  app.get(API_HEALTH_PATH, c => c.json({ identity: input.identity }, 200, { "Cache-Control": "no-store" }));
  app.notFound(c => c.json({ code: "NOT_FOUND" }, 404));
  app.onError((_error, c) => {
    console.error(JSON.stringify({ event: "typescript_api_request_failed", code: "API_OPERATION_FAILED" }));
    return c.json({ code: "API_OPERATION_FAILED" }, 500);
  });
  let closed = false;
  let closing: Promise<void> | undefined;
  return {
    fetch(request: Request, bindings?: ApiBindings): Promise<Response> {
      if (closed) return Promise.resolve(Response.json({ code: "SERVER_CLOSING" }, { status: 503 }));
      const current = new Request(request, { signal: AbortSignal.any([request.signal, cancellation.signal]) });
      const response = Promise.resolve(app.fetch(current, bindings));
      pending.add(response);
      void response.finally(() => pending.delete(response)).catch(() => {});
      return response;
    },
    close(): Promise<void> {
      if (closing !== undefined) return closing;
      closed = true;
      cancellation.abort(new Error("TypeScript API task stopped"));
      closing = (async () => {
        const results = await Promise.allSettled([
          planner?.close(), probe?.close(), ...pending,
        ]);
        const failures = results.filter(result => result.status === "rejected").map(result => result.reason);
        if (failures.length) throw new AggregateError(failures, "TypeScript API module cleanup failed");
      })();
      return closing;
    },
  };
}

export async function serveApiApp(settings: HonoServerSettings, input: ApiModuleInputs) {
  const app = createApiApp(input);
  let server: ReturnType<typeof Bun.serve>;
  try {
    server = Bun.serve({
      hostname: settings.hostname, port: settings.port, idleTimeout: settings.idle_timeout_seconds,
      maxRequestBodySize: Math.max(
        input.planner?.inputs.settings.listener.max_body_bytes ?? 0,
        input.fingerprint?.config.max_input_bytes ?? 0,
        input.probes?.config.max_request_body_bytes ?? 0,
        input.delivery?.maxBodyBytes ?? 0,
      ),
      fetch(request, listener) {
        return app.fetch(request, {
          beginPlanning: () => listener.timeout(request, 0),
          beginDelivery: () => listener.timeout(request, 0),
          stage_origin: apiOrigin({ hostname: settings.hostname, port: listener.port! }),
        });
      },
    });
  } catch (original) {
    try { await app.close(); }
    catch (cleanup) { throw new AggregateError([original, cleanup], "Listener startup and module cleanup failed"); }
    throw original;
  }
  let stopping: Promise<void> | undefined;
  return {
    port: server.port,
    hostname: server.hostname,
    stop(force = false): Promise<void> {
      if (force && stopping !== undefined) {
        return Promise.all([stopping, server.stop(true)]).then(() => undefined);
      }
      stopping ??= (async () => {
        const results = await Promise.allSettled([app.close(), server.stop(force)]);
        const failures = results.filter(result => result.status === "rejected").map(result => result.reason);
        if (failures.length) throw new AggregateError(failures, "TypeScript API shutdown failed");
      })();
      return stopping;
    },
  };
}
