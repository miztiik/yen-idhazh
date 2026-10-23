/** Route a validated operator request to the real planner composition. */
import { Hono } from "hono";
import { PlanError, PlanRequestSchema } from "../plan-request";
import { summarizePlan } from "../../run-feed-plan";
import type { RecordedFeedPlanResult } from "../../run-feed-plan";
import type { PlanRequest } from "../plan-request";
import type { PlanInputs } from "../../load-plan-inputs";
import type { PlanRuntime } from "../../run-feed-plan";
import { executeKeyedPlan } from "../plan-operation";
import type { CapturedPlanIdentity } from "../plan-operation";

export type PlanningBindings = { beginPlanning?: () => void };

export function planRoute(
  execute: (request: PlanRequest, captured?: CapturedPlanIdentity) => Promise<RecordedFeedPlanResult>,
  inputs: PlanInputs, runtime: PlanRuntime,
) {
  return new Hono<{ Bindings: PlanningBindings }>().post("/plan", async c => {
    let raw: unknown;
    try { raw = await c.req.json(); }
    catch (error) {
      if (error instanceof SyntaxError) throw new PlanError("INVALID_REQUEST", "body must contain valid JSON", "body");
      throw error;
    }
    const request = PlanRequestSchema.parse(raw);
    c.env?.beginPlanning?.();
    const key = c.req.header("Idempotency-Key");
    if (key !== undefined) {
      const body = await executeKeyedPlan(key, request, inputs, runtime, execute);
      return c.body(body, JSON.parse(body).planning_complete === true ? 200 : 409, { "Content-Type": "application/json" });
    }
    const result = await execute(request);
    const summary = summarizePlan(result);
    return c.json(summary, summary.planning_complete ? 200 : 409);
  });
}
