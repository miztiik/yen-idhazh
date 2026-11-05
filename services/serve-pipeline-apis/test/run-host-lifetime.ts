/** Run a real shared-only child with observable request cancellation and awaited close. */
import { join } from "node:path";
import { z } from "zod";
import { ApiHostStartupSchema, ApiReadySchema, enabledModules } from "../src/api-startup";
import { createApiApp, serveApiApp } from "../src/create-api-app";
import type { HttpChildFailurePolicy } from "../src/http-child-failure";
import { runHttpChild } from "../src/run-http-child";

export class HostFailure extends Error {
  constructor(readonly code: string, message: string, cause?: unknown) {
    super(message, { cause });
  }
}

function capture(error: unknown, cancelled = false): HostFailure {
  return error instanceof HostFailure ? error
    : new HostFailure(cancelled ? "HOST_CANCELLED" : "HOST_FAILED", "Test host failed", error);
}

export const hostFailure: HttpChildFailurePolicy<HostFailure> = {
  create: (code, message, cause) => new HostFailure(code, message, cause),
  capture,
  async retainCleanup(original, close) {
    try { await close(); return original; }
    catch (cleanup) {
      return new HostFailure(original.code, original.message, new AggregateError([original, cleanup]));
    }
  },
  startup(error, kind) {
    const failure = capture(error);
    return { error: failure, packet: { event: `${kind.toLowerCase()}_startup_failed`, code: failure.code } };
  },
  describe: error => ({ code: capture(error).code }),
};

export const HostStartupSchema = ApiHostStartupSchema.extend({
  group: z.literal("machine"),
  nonce: z.uuid(),
  shutdown_timeout_ms: z.int().positive(),
  startup_delay_ms: z.int().nonnegative(),
  close_delay_ms: z.int().nonnegative(),
  max_request_body_bytes: z.int().positive(),
});
export type HostStartup = z.infer<typeof HostStartupSchema>;
export const HOST_CLOSED_FILENAME = "closed.json";
export const HostClosedSchema = z.strictObject({
  pid: z.int().positive(),
  parent_cancelled: z.boolean(),
  application_cancelled: z.boolean(),
  request_cancelled: z.boolean(),
  close_calls: z.int().positive(),
});

if (import.meta.main) {
  try {
    await runHttpChild("TYPESCRIPT_API", hostFailure, message => {
      const startup = HostStartupSchema.parse(message);
      return {
        shutdownTimeoutMs: startup.shutdown_timeout_ms,
        async start(parentSignal) {
          await Bun.sleep(startup.startup_delay_ms);
          if (parentSignal.aborted) throw hostFailure.create("HOST_STARTUP_CANCELLED", "Parent closed during startup");
          const identity = ApiReadySchema.parse({
            event: "typescript_api_ready", nonce: startup.nonce, pid: process.pid,
            port: startup.server.port, group: startup.group, modules: enabledModules(startup.group), enabled: true,
          });
          const entered = Promise.withResolvers<void>();
          let pendingSignal: AbortSignal | undefined;
          let closeCalls = 0;
          const app = createApiApp({ identity, create: applicationSignal => ({
            maxRequestBodyBytes: startup.max_request_body_bytes,
            async fetch(request, bindings) {
              const path = new URL(request.url).pathname;
              if (path === "/wait") {
                pendingSignal = request.signal;
                entered.resolve();
                if (!request.signal.aborted) await new Promise<void>(resolve => {
                  request.signal.addEventListener("abort", () => resolve(), { once: true });
                });
                return Response.json({ cancelled: request.signal.aborted });
              }
              if (path === "/entered") { await entered.promise; return new Response(null, { status: 204 }); }
              if (path === "/fail") throw new Error("PRIVATE_OPERATION_FAILURE");
              return Response.json({ body: await request.text(), origin: bindings?.stage_origin });
            },
            async close() {
              closeCalls += 1;
              console.error(JSON.stringify({ phase: "stopping", severity: "info", code: "HOST_CLOSE_STARTED" }));
              await Bun.sleep(startup.close_delay_ms);
              const closed = HostClosedSchema.parse({
                pid: process.pid, parent_cancelled: parentSignal.aborted,
                application_cancelled: applicationSignal.aborted,
                request_cancelled: pendingSignal?.aborted ?? false, close_calls: closeCalls,
              });
              await Bun.write(join(startup.directory, HOST_CLOSED_FILENAME), JSON.stringify(closed));
              process.stderr.write(JSON.stringify({ phase: "operation_completed", severity: "info", code: "HOST_CLOSED" }));
            },
          }) });
          const server = await serveApiApp(startup.server, app);
          return { server, ready: identity };
        },
      };
    });
  } catch (error) {
    console.error(JSON.stringify({ event: "host_failed", ...hostFailure.describe(error) }));
    process.exitCode = 1;
  }
}
