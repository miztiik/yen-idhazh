/** Route a validated operator request to the real planner composition. */
import { Hono } from "hono";
import { PLANNER_API_PATHS } from "@idhazh/common-contracts";
import { PlanError, PlanRequestSchema } from "../plan-request";
import { summarizePlan } from "../../run-feed-plan";
import type { FeedPlanResult } from "../../run-feed-plan";
import type { PlanRequest } from "../plan-request";
import type { PlanRuntime } from "../../run-feed-plan";
import { PlanResponseSchema } from "../plan-response.schema";
import { captureRequestRuntime } from "../operation-context";

export type PlanningBindings = { beginPlanning?: () => void; stage_origin?: string };
export function planRoute(
  execute: (request: PlanRequest, runtime: PlanRuntime) => Promise<FeedPlanResult>,
  runtime: () => PlanRuntime,
) {
  return new Hono<{ Bindings: PlanningBindings }>().post(PLANNER_API_PATHS.plan, async c => {
    if (c.req.header("Idempotency-Key") !== undefined) {
      throw new PlanError("INVALID_REQUEST", "Idempotency-Key is unsupported; send a new live request", "Idempotency-Key");
    }
    let raw: unknown;
    try { raw = await c.req.json(); }
    catch (error) {
      if (error instanceof SyntaxError) throw new PlanError("INVALID_REQUEST", "body must contain valid JSON", "body");
      throw error;
    }
    const request = PlanRequestSchema.parse(raw);
    c.env?.beginPlanning?.();
    const result = await execute(request, captureRequestRuntime({ ...runtime(), signal: c.req.raw.signal,
      ...(c.env?.stage_origin === undefined ? {} : { stage_origin: c.env.stage_origin }) }, c.req.raw.headers));
    const summary = PlanResponseSchema.parse(summarizePlan(result));
    return c.json(summary, summary.planning_complete && summary.failure === null ? 200 : 500);
  });
}
