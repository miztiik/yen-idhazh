/** Route the versioned operator API and apply configured request limits. */
import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import { describePlanError } from "./plan-request";
import { healthRoute } from "./routes/health.route";
import { planRoute } from "./routes/plan.route";
import { writeJsonLine } from "../logging/structured-logger";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";

// Calendar-versioned HTTP protocol paths are not runtime planning controls.
const apiPrefix = "/api/2026-10-20";

export function createPlanApp(inputs: PlanInputs, runtime: PlanRuntime) {
  const app = new Hono();
  app.use(`${apiPrefix}/plan`, bodyLimit({
    maxSize: inputs.settings.listener.max_body_bytes,
    onError: c => c.json({
      code: "BODY_TOO_LARGE", issues: [{ field: "body", message: "body exceeds configured max_body_bytes" }],
    }, 413),
  }));
  app.route(apiPrefix, healthRoute(inputs));
  app.route(apiPrefix, planRoute(inputs, runtime));
  app.notFound(c => c.json({ code: "NOT_FOUND", issues: [{ field: "route", message: "Unknown API route" }] }, 404));
  app.onError((error, c) => {
    const failure = describePlanError(error, inputs.root);
    writeJsonLine({ event: "planner_error", ...failure });
    const status = failure.code === "PLANNER_DISABLED" ? 503
      : failure.code === "INVALID_INPUT" || failure.code === "INVALID_REQUEST" ? 400 : 500;
    return c.json(failure, status);
  });
  return app;
}

export function servePlan(inputs: PlanInputs, runtime: PlanRuntime) {
  const app = createPlanApp(inputs, runtime);
  return Bun.serve({
    hostname: inputs.settings.listener.hostname,
    port: inputs.settings.listener.port,
    idleTimeout: inputs.settings.listener.idle_timeout_seconds,
    fetch: app.fetch,
  });
}
