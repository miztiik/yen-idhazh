/** How are native planning, machine and delivery routes assembled for one feed task? */
import { join, resolve } from "node:path";
import { Hono } from "hono";
import { createApiApp, serveApiApp } from "@idhazh/serve-pipeline-apis/app";
import type { ApiBindings } from "@idhazh/serve-pipeline-apis/app";
import type { ApiReady } from "@idhazh/serve-pipeline-apis/startup";
import { createMachineApp, loadMachineApiInputs } from "@idhazh/host-probes/machine-app";
import type { MachineApiInputs } from "@idhazh/host-probes/machine-app";
import { createPlanApp } from "../src/api/server";
import { PlanError } from "../src/api/plan-request";
import { PlannerReadySchema } from "../src/config/planner-startup";
import { restorePlannerStartup } from "./restore-planner-startup";
import { createSafePersistApp } from "./safe-persist-http-api";
import { SafePersistHttpReadySchema } from "./feed-ingest-plan-delivery-result";
import { readFeedApiIdentity } from "./read-feed-api-startup";
import type { FeedApiStartup } from "./read-feed-api-startup";

export type FeedApiInputs = {
  identity: ApiReady;
  planner?: {
    inputs: Parameters<typeof createPlanApp>[0];
    runtime: Parameters<typeof createPlanApp>[1];
    identity: Parameters<typeof createPlanApp>[2];
  };
  machine?: MachineApiInputs;
  delivery?: Parameters<typeof createSafePersistApp>[0];
  writeEvent?: Parameters<typeof createApiApp>[0]["writeEvent"];
};

export function createFeedApiApp(input: FeedApiInputs) {
  const enabled = new Set(input.identity.modules);
  if (enabled.has("planning") !== (input.planner !== undefined)
    || enabled.has("delivery") !== (input.delivery !== undefined)
    || enabled.has("machine") !== (input.machine !== undefined)) {
    throw new Error("Readiness must identify exactly the actual enabled API modules");
  }
  return createApiApp({ identity: input.identity,
    ...(input.writeEvent === undefined ? {} : { writeEvent: input.writeEvent }), create: signal => {
    const app = new Hono<{ Bindings: ApiBindings }>();
    const planner = input.planner === undefined ? undefined : createPlanApp(input.planner.inputs, {
      ...input.planner.runtime,
      signal: AbortSignal.any([signal, ...(input.planner.runtime.signal === undefined ? [] : [input.planner.runtime.signal])]),
    }, input.planner.identity);
    const machine = input.machine === undefined ? undefined : createMachineApp(input.machine);
    if (planner !== undefined) app.route("/", planner);
    if (input.delivery !== undefined) app.route("/", createSafePersistApp({
      ...input.delivery, signal: AbortSignal.any([input.delivery.signal, signal]),
    }));
    if (machine !== undefined) app.all("*", c => machine.fetch(c.req.raw, c.env));
    app.notFound(c => c.json({ code: "NOT_FOUND" }, 404));
    app.onError(error => { throw error; });
    return {
      maxRequestBodyBytes: Math.max(
        input.planner?.inputs.settings.listener.max_body_bytes ?? 0,
        machine?.maxRequestBodyBytes ?? 0, input.delivery?.maxBodyBytes ?? 0,
      ),
      fetch: (request, bindings) => app.fetch(request, bindings),
      async close() {
        const results = await Promise.allSettled([planner?.close(), machine?.close()]);
        const failures = results.filter(result => result.status === "rejected").map(result => result.reason);
        if (failures.length) throw new AggregateError(failures, "Pipeline API module cleanup failed");
      },
    };
  } });
}

export async function startFeedApiApp(
  startup: FeedApiStartup, signal: AbortSignal, restore = restorePlannerStartup,
) {
  const root = process.cwd();
  const modules: FeedApiInputs = { identity: readFeedApiIdentity(startup, process.pid) };
  if (startup.group === "planning") {
    const restored = await restore(startup.planner);
    modules.identity = readFeedApiIdentity(startup, process.pid);
    modules.identity.enabled = restored.inputs.settings.enabled;
    modules.planner = { ...restored, runtime: { ...restored.runtime, signal },
      identity: PlannerReadySchema.parse({
        event: "planner_ready", nonce: startup.planner.nonce, pid: process.pid,
        port: startup.server.port, runtime: startup.planner.runtime,
      }) };
    modules.machine = await loadMachineApiInputs(root, startup.planner.output_root,
      join(root, startup.planner.settings.inputs.registrations));
  } else {
    modules.delivery = {
      root, directory: resolve(root, startup.delivery.output_root),
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
    const server = await serveApiApp(startup.server, createFeedApiApp(modules));
    return { server, ready: { ...modules.identity, port: server.port } };
  } catch (error) {
    const kind = startup.group === "delivery" ? "SAFE_PERSIST" : "PLANNER";
    throw new PlanError(`${kind}_BIND_FAILED`, "Pipeline API loopback listener could not start", null, { cause: error });
  }
}
