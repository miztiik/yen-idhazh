/** Route the operator health request without running a planner stage. */
import { Hono } from "hono";
import { PLANNER_API_PATHS } from "@idhazh/common-contracts";
import type { PlanInputs } from "../../load-plan-inputs";
import type { PlannerReady } from "../../config/planner-startup";

export function healthRoute(inputs: PlanInputs, identity?: PlannerReady) {
  return new Hono().get(PLANNER_API_PATHS.health, c => c.json({
    status: "available", planner_enabled: inputs.settings.enabled,
    ...(identity === undefined ? {} : { identity }),
  }));
}
