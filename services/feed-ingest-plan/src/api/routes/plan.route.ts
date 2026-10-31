/** Route a validated operator request to the real planner composition. */
import { Hono } from "hono";
import { PlanError, PlanRequestSchema } from "../plan-request";
import { summarizePlan } from "../../run-feed-plan";
import type { FeedPlanResult } from "../../run-feed-plan";
import type { PlanRequest } from "../plan-request";
import type { PlanInputs } from "../../load-plan-inputs";
import type { PlanRuntime } from "../../run-feed-plan";
import { executeKeyedPlan } from "../plan-operation";
import type { CapturedPlanIdentity } from "../plan-operation";
import { PlanResponseSchema } from "../plan-response.schema";

export type PlanningBindings = { beginPlanning?: () => void; stage_origin?: string };

export function planRoute(
  execute: (request: PlanRequest, captured?: CapturedPlanIdentity) => Promise<FeedPlanResult>,
  inputs: PlanInputs, runtime: () => PlanRuntime,
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
      const body = await executeKeyedPlan(key, request, inputs, runtime(), (request, captured) =>
        execute(request, { ...captured, signal: c.req.raw.signal,
          ...(c.env?.stage_origin === undefined ? {} : { stage_origin: c.env.stage_origin }) }));
      return c.body(body, JSON.parse(body).planning_complete === true ? 200 : 500, { "Content-Type": "application/json" });
    }
    const result = await execute(request, { signal: c.req.raw.signal,
      ...(c.env?.stage_origin === undefined ? {} : { stage_origin: c.env.stage_origin }) });
    const summary = PlanResponseSchema.parse(summarizePlan(result));
    return c.json(summary, summary.planning_complete ? 200 : 500);
  });
}
