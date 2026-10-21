/** Route a validated operator request to the real planner composition. */
import { Hono } from "hono";
import { PlanError, PlanRequestSchema } from "../plan-request";
import { runFeedPlan, summarizePlan } from "../../run-feed-plan";
import type { PlanRuntime } from "../../run-feed-plan";
import type { PlanInputs } from "../../load-plan-inputs";

export function planRoute(inputs: PlanInputs, runtime: PlanRuntime) {
  return new Hono().post("/plan", async c => {
    let raw: unknown;
    try { raw = await c.req.json(); }
    catch (error) {
      if (error instanceof SyntaxError) throw new PlanError("INVALID_REQUEST", "body must contain valid JSON", "body");
      throw error;
    }
    const request = PlanRequestSchema.parse(raw);
    const result = await runFeedPlan(request, inputs, runtime);
    return c.json(summarizePlan(result), 409);
  });
}
