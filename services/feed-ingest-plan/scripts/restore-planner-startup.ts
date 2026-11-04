/** Reconstruct one planner's captured settings without starting another listener. */
import { resolve } from "node:path";
import type { PlannerStartup } from "../src/config/planner-startup";
import { loadPlanInputs } from "../src/load-plan-inputs";
import type { PlanRuntime } from "../src/run-feed-plan";

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
