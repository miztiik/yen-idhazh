/** Route distinct fetch and parse controls without accepting filesystem paths. */
import { Hono } from "hono";
import { PLANNER_API_PATHS } from "@idhazh/common-contracts";
import type { PlanInputs } from "../../load-plan-inputs";
import type { PlanRuntime } from "../../run-feed-plan";
import type { PlanningBindings } from "./plan.route";
import { executeDocumentOperation } from "../document-operations";
import { FetchRequestSchema, ParseRequestSchema } from "../operation-contracts";
import { PlanError } from "../plan-request";
import { captureRequestRuntime } from "../operation-context";

export function documentRoute(inputs: PlanInputs, runtime: () => PlanRuntime) {
  const app = new Hono<{ Bindings: PlanningBindings }>();
  for (const operation of ["fetch", "parse"] as const) app.post(PLANNER_API_PATHS[operation], async c => {
    if (c.req.header("Idempotency-Key") !== undefined) {
      throw new PlanError("INVALID_REQUEST", "Idempotency-Key is unsupported; send a new live request", "Idempotency-Key");
    }
    let raw: unknown;
    try { raw = await c.req.json(); }
    catch (error) {
      if (error instanceof SyntaxError) throw new PlanError("INVALID_REQUEST", "body must contain valid JSON", "body");
      throw error;
    }
    const request = operation === "fetch" ? FetchRequestSchema.parse(raw) : ParseRequestSchema.parse(raw);
    c.env?.beginPlanning?.();
    return c.body(await executeDocumentOperation(operation, request, inputs,
      captureRequestRuntime(runtime(), c.req.raw.headers), c.req.raw.signal), 200, {
      "Content-Type": "application/json",
    });
  });
  return app;
}
