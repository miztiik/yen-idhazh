/** Route a validated operator request to the real planner composition. */
import { Hono } from "hono";
import { PlanError, PlanRequestSchema } from "../plan-request";
import { summarizePlan } from "../../run-feed-plan";
import type { FeedPlanResult } from "../../run-feed-plan";
import type { PlanRequest } from "../plan-request";

export function planRoute(execute: (request: PlanRequest) => Promise<FeedPlanResult>) {
  return new Hono().post("/plan", async c => {
    let raw: unknown;
    try { raw = await c.req.json(); }
    catch (error) {
      if (error instanceof SyntaxError) throw new PlanError("INVALID_REQUEST", "body must contain valid JSON", "body");
      throw error;
    }
    const request = PlanRequestSchema.parse(raw);
    const result = await execute(request);
    return c.json(summarizePlan(result), 409);
  });
}
