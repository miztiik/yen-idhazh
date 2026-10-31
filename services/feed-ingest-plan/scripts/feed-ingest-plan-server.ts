/** Reconstruct one planner child from private startup data and close it when its supervisor leaves. */
import { resolve } from "node:path";
import { PlannerReadySchema, PlannerStartupSchema } from "../src/config/planner-startup";
import type { PlannerStartup } from "../src/config/planner-startup";
import { loadPlanInputs } from "../src/load-plan-inputs";
import type { PlanInputs } from "../src/load-plan-inputs";
import type { PlanRuntime } from "../src/run-feed-plan";
import { servePlan } from "../src/api/server";
import { PlanError } from "../src/api/plan-request";
import { runHttpChild } from "./http-child-lifetime";
import { writeJsonLine } from "../src/logging/structured-logger";

export async function restorePlannerStartup(startup: PlannerStartup, root = process.cwd()) {
  const inputs = await loadPlanInputs(root, undefined, startup.settings);
  inputs.harvest = { ...inputs.harvest, config: startup.planning };
  inputs.outputRoot = resolve(root, startup.output_root);
  const runtime: PlanRuntime = {
    ...startup.runtime, clock: () => new Date(startup.runtime.captured_at),
    selection_clock: () => new Date(),
  };
  return { inputs, runtime };
}

export async function runPlannerServer(
  restore: (startup: PlannerStartup) => Promise<{ inputs: PlanInputs; runtime: PlanRuntime }> = restorePlannerStartup,
) {
  return runHttpChild("PLANNER", message => {
    const startup = PlannerStartupSchema.parse(message);
    return {
      shutdownTimeoutMs: startup.settings.supervision.shutdown_timeout_ms,
      start: async signal => {
        const { inputs, runtime } = await restore(startup);
        signal.throwIfAborted();
        const identity = PlannerReadySchema.parse({
          event: "planner_ready", nonce: startup.nonce, pid: process.pid,
          port: inputs.settings.listener.port, runtime: startup.runtime,
        });
        let server: ReturnType<typeof servePlan>;
        try { server = servePlan(inputs, { ...runtime, signal }, identity); }
        catch (error) {
          const code = error instanceof Error && "code" in error ? String(error.code) : "LISTEN_FAILED";
          throw new PlanError("PLANNER_BIND_FAILED", `Planner loopback listener could not bind: ${code}`);
        }
        return { server, ready: { ...identity, port: server.port } };
      },
    };
  });
}

if (import.meta.main) {
  try { await runPlannerServer(); }
  catch (error) {
    writeJsonLine({
      event: "planner_server_failed",
      code: error instanceof PlanError ? error.code : "PLANNER_STARTUP_FAILED",
      ...(error instanceof PlanError ? { message: error.message } : {}),
    });
    process.exitCode = 2;
  }
}
