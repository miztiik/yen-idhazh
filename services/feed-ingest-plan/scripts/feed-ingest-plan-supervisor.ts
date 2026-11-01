/** Keep one owned planner child alive through its HTTP calls and reap it on every exit path. */
import { randomUUID } from "node:crypto";
import { relative } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { PlannerReadySchema, PlannerStartupSchema, PlannerStartupFailureSchema } from "../src/config/planner-startup";
import type { PlannerStartup } from "../src/config/planner-startup";
import type { PlanInputs } from "../src/load-plan-inputs";
import { PlanError } from "../src/api/plan-request";
import type { PlanRequest } from "../src/api/plan-request";
import { requestPlannerHttp } from "./feed-ingest-plan-http-client";
import { superviseHttpChild } from "./http-child-lifetime";

export function createPlannerStartup(inputs: PlanInputs, runtime: PlannerStartup["runtime"]) {
  return PlannerStartupSchema.parse({
    nonce: randomUUID(), settings: inputs.settings, planning: inputs.harvest.config,
    output_root: relative(inputs.root, inputs.outputRoot).replaceAll("\\", "/"), runtime,
  });
}

export async function invokePlannerHttp(
  inputs: PlanInputs, startup: PlannerStartup, request: PlanRequest, directory: string,
  options: { signal?: AbortSignal; serverEntry?: string } = {},
) {
  return superviseHttpChild({
    root: inputs.root, kind: "PLANNER", settings: inputs.settings,
    startup: PlannerStartupSchema.parse(startup),
    serverEntry: options.serverEntry ?? fileURLToPath(new URL("./feed-ingest-plan-server.ts", import.meta.url)),
    ...(options.signal === undefined ? {} : { signal: options.signal }),
    ready: async (message, pid, signal) => {
      const ready = z.union([PlannerReadySchema, PlannerStartupFailureSchema]).parse(message);
      if (ready.event === "planner_startup_failed") throw new PlanError(ready.code, ready.message);
      if (ready.pid !== pid || ready.nonce !== startup.nonce
        || JSON.stringify(ready.runtime) !== JSON.stringify(startup.runtime)
        || ready.port !== inputs.settings.listener.port) {
        throw new PlanError("PLANNER_READY_IDENTITY", "Readiness does not match the owned child and invocation");
      }
      const hostname = inputs.settings.listener.hostname;
      const base = `http://${hostname === "::1" ? "[::1]" : hostname}:${ready.port}/api/2026-10-31`;
      await fetch(`${base}/health`, { signal }).then(async response => {
        const body = z.object({ identity: PlannerReadySchema, planner_enabled: z.boolean() }).parse(await response.json());
        if (response.status !== 200 || body.planner_enabled !== true
          || JSON.stringify(PlannerReadySchema.parse(body.identity)) !== JSON.stringify(ready)) {
          throw new PlanError("PLANNER_READY_IDENTITY", "HTTP readiness does not match the owned child");
        }
      });
      return base;
    },
    request: (base, signal) => requestPlannerHttp(base, inputs, request, directory, signal),
  });
}
