/** How does a native-built application acquire one listener, cancellation and awaited cleanup? */
import { Hono } from "hono";
import { createChildContext, createRootContext, readTraceContext } from "@idhazh/common-contracts";
import { createRequestFailureEvent } from "./create-request-failure-event";
import type { RequestFailureEvent } from "./create-request-failure-event";
import { API_HEALTH_PATH } from "./api-startup";
import type { ApiReady } from "./api-startup";
import { apiOrigin } from "./load-settings";
import type { HonoServerSettings } from "./load-settings";

export type ApiBindings = {
  beginPlanning?: () => void;
  beginDelivery?: () => void;
  stage_origin?: string;
};
export type ApiApplication = {
  maxRequestBodyBytes: number;
  fetch: (request: Request, bindings?: ApiBindings) => Response | Promise<Response>;
  close: () => Promise<void>;
};

export function createApiApp(input: {
  identity: ApiReady; create: (signal: AbortSignal) => ApiApplication;
  writeEvent?: (event: RequestFailureEvent) => void;
}): ApiApplication {
  const writeEvent = input.writeEvent ?? ((event: RequestFailureEvent) => { console.error(JSON.stringify(event)); });
  const app = new Hono<{ Bindings: ApiBindings }>();
  const cancellation = new AbortController();
  const pending = new Set<Promise<Response>>();
  const native = input.create(cancellation.signal);
  app.get(API_HEALTH_PATH, c => c.json({ identity: input.identity }, 200, { "Cache-Control": "no-store" }));
  app.all("*", c => native.fetch(c.req.raw, c.env));
  app.onError((_error, c) => {
    const parent = readTraceContext({
      traceparent: c.req.header("traceparent"), tracestate: c.req.header("tracestate"),
    });
    const context = parent === undefined ? createRootContext() : createChildContext(parent);
    writeEvent(createRequestFailureEvent({ context }));
    return c.json({ code: "API_OPERATION_FAILED" }, 500);
  });
  let closed = false;
  let closing: Promise<void> | undefined;
  return {
    maxRequestBodyBytes: native.maxRequestBodyBytes,
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
      cancellation.abort(new Error("Pipeline API task stopped"));
      closing = (async () => {
        const results = await Promise.allSettled([
          native.close(), ...pending,
        ]);
        const failures = results.filter(result => result.status === "rejected").map(result => result.reason);
        if (failures.length) throw new AggregateError(failures, "Pipeline API module cleanup failed");
      })();
      return closing;
    },
  };
}

export async function serveApiApp(settings: HonoServerSettings, app: ApiApplication) {
  let server: ReturnType<typeof Bun.serve>;
  try {
    server = Bun.serve({
      hostname: settings.hostname, port: settings.port, idleTimeout: settings.idle_timeout_seconds,
      maxRequestBodySize: app.maxRequestBodyBytes,
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
        if (failures.length) throw new AggregateError(failures, "Pipeline API shutdown failed");
      })();
      return stopping;
    },
  };
}
