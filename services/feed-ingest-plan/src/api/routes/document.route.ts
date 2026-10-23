/** Route distinct fetch and parse controls without accepting filesystem paths. */
import { Hono } from "hono";
import type { PlanInputs } from "../../load-plan-inputs";
import type { PlanRuntime } from "../../run-feed-plan";
import type { PlanningBindings } from "./plan.route";
import { executeDocumentOperation } from "../document-operations";
import { FetchRequestSchema, ParseRequestSchema } from "../operation-contracts";
import { PlanError } from "../plan-request";

export function documentRoute(inputs: PlanInputs, runtime: PlanRuntime) {
  const app = new Hono<{ Bindings: PlanningBindings }>();
  for (const operation of ["fetch", "parse"] as const) app.post(`/${operation}`, async c => {
    let raw: unknown;
    try { raw = await c.req.json(); }
    catch (error) {
      if (error instanceof SyntaxError) throw new PlanError("INVALID_REQUEST", "body must contain valid JSON", "body");
      throw error;
    }
    const request = operation === "fetch" ? FetchRequestSchema.parse(raw) : ParseRequestSchema.parse(raw);
    c.env?.beginPlanning?.();
    return c.body(await executeDocumentOperation(operation, request, inputs, runtime), 200, {
      "Content-Type": "application/json",
    });
  });
  return app;
}
