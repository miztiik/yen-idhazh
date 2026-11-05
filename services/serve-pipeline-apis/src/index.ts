/** Start exactly one explicit API group for the lifetime of its supervisor's private pipe. */
import { join, resolve } from "node:path";
import { runHttpChild } from "@idhazh/feed-ingest-plan/http-child-lifetime";
import { restorePlannerStartup } from "@idhazh/feed-ingest-plan/restore-startup";
import { PlannerReadySchema } from "@idhazh/feed-ingest-plan/startup";
import { SafePersistHttpReadySchema } from "@idhazh/feed-ingest-plan/delivery-contracts";
import { PlanError } from "@idhazh/feed-ingest-plan/plan-request";
import { runtimeFailureExecution } from "@idhazh/feed-ingest-plan/plan-failure";
import { loadConfig as loadFingerprintConfig, loadSettings as loadFingerprintSettings } from "@idhazh/host-fingerprints/config";
import { loadConfig as loadProbeConfig } from "@idhazh/host-probes/config";
import { ApiReadySchema, ApiStartupSchema, enabledModules, startupNonce, startupSupervision } from "./api-startup";
import { serveApiApp } from "./create-api-app";
import type { ApiModuleInputs } from "./create-api-app";

export async function runApiServer(options: { restorePlanner?: typeof restorePlannerStartup } = {}) {
  return runHttpChild("TYPESCRIPT_API", message => {
    const startup = ApiStartupSchema.parse(message);
    return {
      shutdownTimeoutMs: startupSupervision(startup).shutdown_timeout_ms,
      capture: {
        operation: "listener-start",
        ...(startup.group === "planning" ? {
          execution: runtimeFailureExecution(startup.planner.runtime),
          limits: startup.planner.settings.diagnostics.failure,
        } : startup.group === "delivery" ? {
          execution: { run_id: null, attempt: startup.run.attempt, traceId: startup.run.context.traceId,
            spanId: startup.run.context.spanId, git_sha: startup.delivery.git_sha },
          limits: startup.delivery.settings.diagnostics.failure,
        } : {}),
      },
      start: async signal => {
        const modules: ApiModuleInputs = {
          identity: ApiReadySchema.parse({
            event: "typescript_api_ready", nonce: startupNonce(startup), pid: process.pid,
            port: startup.server.port, group: startup.group, modules: enabledModules(startup.group),
            enabled: startup.group !== "planning" || startup.planner.settings.enabled,
          }),
        };
        if (startup.group === "planning") {
          const restored = await (options.restorePlanner ?? restorePlannerStartup)(startup.planner);
          modules.identity = { ...modules.identity, nonce: startupNonce(startup), enabled: restored.inputs.settings.enabled };
          modules.planner = { ...restored, runtime: { ...restored.runtime, signal },
            identity: PlannerReadySchema.parse({
              event: "planner_ready", nonce: startup.planner.nonce, pid: process.pid,
              port: startup.server.port, runtime: startup.planner.runtime,
            }) };
        }
        if (startup.group === "planning" || startup.group === "machine") {
          const root = process.cwd();
          const [config, settings, probes] = await Promise.all([
            loadFingerprintConfig(join(root, "config", "host-fingerprints.json")),
            loadFingerprintSettings(join(root, "config", "idhazh.json")),
            loadProbeConfig(join(root, "config", "host-probes.json")),
          ]);
          modules.fingerprint = { config, settings, options: {
            outputRoot: resolve(root, startup.group === "planning" ? startup.planner.output_root : startup.state_root),
            registryPath: join(root, startup.group === "planning" ? startup.planner.settings.inputs.registrations : "config/ledgers.json"),
          } };
          modules.probes = { config: probes };
        }
        if (startup.group === "delivery") {
          modules.delivery = {
            root: process.cwd(), directory: resolve(process.cwd(), startup.delivery.output_root),
            identity: SafePersistHttpReadySchema.parse({
              event: "safe_persist_ready", nonce: startup.delivery.nonce, pid: process.pid, port: startup.server.port,
            }),
            gitSha: startup.delivery.git_sha, signal,
            maxBodyBytes: startup.delivery.settings.listener.max_body_bytes,
            failureLimits: startup.delivery.settings.diagnostics.failure,
          };
        }
        signal.throwIfAborted();
        try {
          const server = await serveApiApp(startup.server, modules);
          return { server, ready: { ...modules.identity, port: server.port } };
        } catch (error) {
          const kind = startup.group === "delivery" ? "SAFE_PERSIST" : startup.group === "planning" ? "PLANNER" : "TYPESCRIPT_API";
          throw new PlanError(`${kind}_BIND_FAILED`, "Pipeline API loopback listener could not start", null, { cause: error });
        }
      },
    };
  });
}

if (import.meta.main) {
  try { await runApiServer(); }
  catch { process.exitCode = 2; }
}
