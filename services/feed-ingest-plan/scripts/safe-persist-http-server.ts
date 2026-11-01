/** Serve safe-persist HTTP only for the lifetime of its finalizer's private startup pipe. */
import { resolve } from "node:path";
import { PlanError } from "../src/api/plan-request";
import { writeJsonLine } from "../src/logging/structured-logger";
import { SafePersistHttpReadySchema, SafePersistHttpStartupSchema } from "./feed-ingest-plan-delivery-result";
import { createSafePersistApp } from "./safe-persist-http-api";
import { runHttpChild } from "./http-child-lifetime";

export function runSafePersistServer(root = process.cwd()) {
  return runHttpChild("SAFE_PERSIST", message => {
    const startup = SafePersistHttpStartupSchema.parse(message);
    return {
      shutdownTimeoutMs: startup.settings.supervision.shutdown_timeout_ms,
      start: async signal => {
        signal.throwIfAborted();
        const identity = SafePersistHttpReadySchema.parse({
          event: "safe_persist_ready", nonce: startup.nonce, pid: process.pid,
          port: startup.settings.listener.port,
        });
        const app = createSafePersistApp({
          root, directory: resolve(root, startup.output_root), identity, signal,
          gitSha: startup.git_sha,
          maxBodyBytes: startup.settings.listener.max_body_bytes,
        });
        let server: ReturnType<typeof Bun.serve>;
        try {
          server = Bun.serve({
            hostname: startup.settings.listener.hostname, port: startup.settings.listener.port,
            idleTimeout: startup.settings.listener.idle_timeout_seconds,
            fetch(request, listener) {
              return app.fetch(request, { beginDelivery: () => listener.timeout(request, 0) });
            },
          });
        } catch (error) {
          const code = error instanceof Error && "code" in error ? String(error.code) : "LISTEN_FAILED";
          throw new PlanError("SAFE_PERSIST_BIND_FAILED", `Safe-persist loopback listener could not bind: ${code}`);
        }
        return { server, ready: { ...identity, port: server.port } };
      },
    };
  });
}

if (import.meta.main) {
  try { await runSafePersistServer(); }
  catch (error) {
    writeJsonLine({
      event: "safe_persist_server_failed",
      code: error instanceof PlanError ? error.code : "SAFE_PERSIST_STARTUP_FAILED",
    });
    process.exitCode = 2;
  }
}
