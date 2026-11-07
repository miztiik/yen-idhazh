/** Route the explicit current-batch feed-health operation without HTTP loopback. */
import { Hono } from "hono";
import { PLANNER_API_PATHS } from "@idhazh/common-contracts";
import type { PlanInputs } from "../../load-plan-inputs";
import type { PlanRuntime } from "../../run-feed-plan";
import { executeFeedHealthState } from "../feed-health-state-operation";
import { FeedHealthStateUpdateRequestSchema, FeedHealthStateUpdateResponseSchema } from "../feed-health-state.schema";
import { readRequestBody } from "./stages.route";
import { captureRequestRuntime } from "../operation-context";

export function feedHealthStateRoute(inputs: PlanInputs, runtime: () => PlanRuntime) {
  return new Hono().post(PLANNER_API_PATHS.updateFeedHealth, async c => {
    const request = FeedHealthStateUpdateRequestSchema.parse(await readRequestBody(c.req.raw));
    return c.json(FeedHealthStateUpdateResponseSchema.parse(await executeFeedHealthState(request, inputs,
      captureRequestRuntime({ ...runtime(), signal: c.req.raw.signal }, c.req.raw.headers))));
  });
}
