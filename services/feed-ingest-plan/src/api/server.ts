/** Route the versioned operator API and apply configured request limits. */
import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import { join, relative } from "node:path";
import { describePlanError, PlanError } from "./plan-request";
import { healthRoute } from "./routes/health.route";
import { planRoute } from "./routes/plan.route";
import { writeJsonLine } from "../logging/structured-logger";
import type { PlanInputs } from "../load-plan-inputs";
import { runFeedPlan } from "../run-feed-plan";
import type { PlanRuntime } from "../run-feed-plan";
import type { PlanRequest } from "./plan-request";
import { parseSeenDays, requiredSeenDays } from "../read-ledger-history/read-seen-evidence";
import { RelativePathSchema } from "../config/service-settings";
import { recordFeedPlan } from "../record-feed-plan";

// Calendar-versioned HTTP protocol paths are not runtime planning controls.
const apiPrefix = "/api/2026-10-20";

export function createPlanApp(inputs: PlanInputs, runtime: PlanRuntime) {
  const app = new Hono();
  const ownFiles = new Map<string, Set<string>>();
  for (const receipt of runtime.seen_receipts ?? []) {
    if (ownFiles.has(receipt.day) || new Set(receipt.files).size !== receipt.files.length) {
      throw new PlanError("INVALID_INPUT", "own seen receipts must have distinct days and files", "seen_receipts");
    }
    ownFiles.set(receipt.day, new Set(receipt.files.map(file => RelativePathSchema.parse(file))));
  }
  const acceptedDays = new Map<string, string>();
  let lastRunAt: number | undefined;
  let ready = Promise.resolve();
  const execute = (request: PlanRequest) => {
    const result = ready.then(async () => {
      const now = runtime.clock?.() ?? new Date();
      if (!Number.isFinite(now.getTime())) {
        throw new PlanError("INVALID_RUN_CONTEXT", "listener run clock must be a valid UTC instant", "now");
      }
      if (lastRunAt !== undefined && now.getTime() < lastRunAt) {
        throw new PlanError("INVALID_RUN_CONTEXT", "listener run clock moved backwards", "now");
      }
      lastRunAt = now.getTime();
      const required = new Set(requiredSeenDays(
        now.toISOString().replace(/\.\d{3}Z$/, "Z"), inputs.clock_config.collect.seen_window_days,
      ));
      for (const day of ownFiles.keys()) if (!required.has(day)) ownFiles.delete(day);
      const authoredDays = parseSeenDays(inputs.settings.inputs.seen_days);
      const firstRequired = required.values().next().value!;
      const seenDays = authoredDays.filter(day =>
        day.day >= firstRequired || acceptedDays.get(day.day) !== JSON.stringify(day));
      const result = await runFeedPlan(request, {
        ...inputs, settings: {
          ...inputs.settings, inputs: { ...inputs.settings.inputs, seen_days: seenDays },
        },
      }, {
        ...runtime, clock: () => now,
        seen_receipts: [...ownFiles].map(([day, files]) => ({ day, files: [...files] })),
        on_seen_persisted: receipt => {
          const paths = ownFiles.get(receipt.day) ?? new Set<string>();
          for (const file of receipt.files) paths.add(RelativePathSchema.parse(
            relative(inputs.root, join(inputs.outputRoot, file.path)).replaceAll("\\", "/"),
          ));
          ownFiles.set(receipt.day, paths);
          runtime.on_seen_persisted?.(receipt);
        },
      });
      const configured = new Set(authoredDays.map(day => day.day));
      for (const day of acceptedDays.keys()) if (!configured.has(day)) acceptedDays.delete(day);
      for (const day of seenDays) acceptedDays.set(day.day, JSON.stringify(day));
      return recordFeedPlan(result, inputs, runtime);
    });
    // The caller still receives the failure; only the listener queue is released.
    ready = result.then(() => undefined, () => undefined);
    return result;
  };
  app.use(`${apiPrefix}/plan`, bodyLimit({
    maxSize: inputs.settings.listener.max_body_bytes,
    onError: c => c.json({
      code: "BODY_TOO_LARGE", issues: [{ field: "body", message: "body exceeds configured max_body_bytes" }],
    }, 413),
  }));
  app.route(apiPrefix, healthRoute(inputs, runtime.observe_publication !== undefined));
  app.route(apiPrefix, planRoute(execute));
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
