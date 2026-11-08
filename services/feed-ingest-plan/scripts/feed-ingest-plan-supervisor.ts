/** Keep one owned planner child alive through its HTTP calls and reap it on every exit path. */
import { randomUUID } from "node:crypto";
import { relative } from "node:path";
import { PLANNER_API_PREFIX } from "@idhazh/common-contracts";
import { PlannerStartupSchema } from "../src/config/planner-startup";
import type { PlannerStartup } from "../src/config/planner-startup";
import type { PlanInputs } from "../src/load-plan-inputs";
import type { PlanRequest } from "../src/api/plan-request";
import { requestPlannerHttp } from "./feed-ingest-plan-http-client";
import { superviseFeedApiTask } from "./supervise-feed-api-task";
import { loadHonoSettings } from "../../serve-pipeline-apis/src/load-settings";
import { runtimeFailureExecution } from "../src/api/plan-failure";
import { operationMetadata } from "../src/api/operation-context";

export function createPlannerStartup(inputs: PlanInputs, runtime: PlannerStartup["runtime"]) {
  return PlannerStartupSchema.parse({
    nonce: randomUUID(), settings: inputs.settings, planning: inputs.harvest.config,
    output_root: relative(inputs.root, inputs.outputRoot).replaceAll("\\", "/"), runtime,
  });
}

export async function invokePlannerHttp(
  inputs: PlanInputs, startup: PlannerStartup, request: PlanRequest, directory: string,
  options: {
    signal?: AbortSignal; serverEntry?: string;
  } = {},
) {
  return superviseFeedApiTask({
    root: inputs.root,
    startup: {
      group: "planning", server: await loadHonoSettings(inputs.root, "planning"),
      directory: relative(inputs.root, directory).replaceAll("\\", "/"),
      run: { run_id: startup.runtime.run_number, attempt: startup.runtime.attempt,
        started_at: startup.runtime.captured_at, context: operationMetadata(startup.runtime) },
      planner: PlannerStartupSchema.parse(startup),
    },
    capture: { operation: "workflow", execution: runtimeFailureExecution(startup.runtime),
      limits: inputs.settings.diagnostics.failure },
    ...(options.serverEntry === undefined ? {} : { serverEntry: options.serverEntry }),
    ...(options.signal === undefined ? {} : { signal: options.signal }),
    request: (origin, signal) => requestPlannerHttp(
      `${origin}${PLANNER_API_PREFIX}`, inputs, request, directory, signal, operationMetadata(startup.runtime),
    ),
  });
}
