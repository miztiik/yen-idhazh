/** Route the operator health request without running a planner stage. */
import { Hono } from "hono";
import type { PlanInputs } from "../../load-plan-inputs";

export function healthRoute(inputs: PlanInputs) {
  return new Hono().get("/health", c => c.json({
    status: "available", planner_enabled: inputs.settings.enabled, audited_completion_available: false,
  }));
}
