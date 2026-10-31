/** Route independent validated requests without a listener-wide run queue. */
import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import { describePlanError } from "./plan-request";
import { healthRoute } from "./routes/health.route";
import { planRoute } from "./routes/plan.route";
import type { PlanningBindings } from "./routes/plan.route";
import { writeJsonLine } from "../logging/structured-logger";
import type { PlanInputs } from "../load-plan-inputs";
import { runFeedPlan } from "../run-feed-plan";
import type { PlanRuntime } from "../run-feed-plan";
import { documentRoute } from "./routes/document.route";
import { stagesRoute } from "./routes/stages.route";
import { feedHealthStateRoute } from "./routes/feed-health-state.route";
import { ArticleParserPool } from "../harvest-feeds/article-parser-pool";
import type { PlannerReady } from "../config/planner-startup";
import { collectionRoute } from "./routes/collection.route";
import { PLANNER_API_PREFIX } from "@idhazh/common-contracts";
import { finishRawDocumentFailures } from "../dump-raw-document-failure";
import { stageStore } from "./stage-store";

const apiPrefix = PLANNER_API_PREFIX;
const activeApps = new WeakMap<PlanInputs, number>();
export function createPlanApp(inputs: PlanInputs, runtime: PlanRuntime, identity?: PlannerReady) {
  const app = new Hono<{ Bindings: PlanningBindings }>();
  const parserPool = runtime.parser_pool ?? new ArticleParserPool(inputs.settings.listener.parser_concurrency);
  const requestRuntime = () => ({ ...runtime, parser_pool: parserPool });
  app.use(`${apiPrefix}/*`, bodyLimit({
    maxSize: inputs.settings.listener.max_body_bytes,
    onError: c => c.json({ code: "BODY_TOO_LARGE", issues: [{ field: "body", message: "Body exceeds configured max_body_bytes" }] }, 413),
  }));
  app.route(apiPrefix, healthRoute(inputs, identity));
  app.route(apiPrefix, planRoute((request, captured) => runFeedPlan(request, inputs, {
    ...requestRuntime(), ...captured,
    signal: AbortSignal.any([runtime.signal, captured?.signal].filter((signal): signal is AbortSignal => signal !== undefined)),
  })));
  app.route(apiPrefix, documentRoute(inputs, requestRuntime));
  app.route(apiPrefix, collectionRoute(inputs, requestRuntime));
  app.route(apiPrefix, stagesRoute(inputs, requestRuntime));
  app.route(apiPrefix, feedHealthStateRoute(inputs, requestRuntime));
  app.notFound(c => c.json({ code: "NOT_FOUND", issues: [{ field: "route", message: "Unknown API route" }] }, 404));
  app.onError((error, c) => {
    const failure = describePlanError(error, inputs.root);
    writeJsonLine({ event: "planner_error", code: failure.code });
    const status = failure.code === "PLANNER_DISABLED" ? 503
      : ["INVALID_INPUT", "INVALID_REQUEST"].includes(failure.code) ? 400
      : ["REQUEST_BUSY", "REQUEST_CONFLICT", "REQUEST_INCOMPLETE", "FETCH_UNAVAILABLE", "BATCH_INCOMPLETE", "ARTICLE_EXCLUDED"].includes(failure.code) ? 409
      : failure.code === "ARTIFACT_NOT_FOUND" ? 404 : 500;
    return c.json(failure, status);
  });
  activeApps.set(inputs, (activeApps.get(inputs) ?? 0) + 1);
  let closing: Promise<void> | undefined;
  return Object.assign(app, { close() {
    if (closing !== undefined) return closing;
    if (runtime.parser_pool === undefined) parserPool.close();
    const remaining = (activeApps.get(inputs) ?? 1) - 1;
    activeApps.set(inputs, remaining);
    closing = remaining > 0 ? Promise.resolve() : (async () => {
      try { await finishRawDocumentFailures(inputs); }
      finally {
        if (activeApps.get(inputs) === 0) { stageStore(inputs).releaseDocuments(); activeApps.delete(inputs); }
      }
    })();
    return closing;
  } });
}
export function servePlan(inputs: PlanInputs, runtime: PlanRuntime, identity?: PlannerReady) {
  const app = createPlanApp(inputs, runtime, identity);
  let server: ReturnType<typeof Bun.serve>;
  try { server = Bun.serve({
    hostname: inputs.settings.listener.hostname, port: inputs.settings.listener.port,
    idleTimeout: inputs.settings.listener.idle_timeout_seconds,
    fetch(request, server) {
      return app.fetch(request, { beginPlanning: () => server.timeout(request, 0),
        stage_origin: `http://${server.hostname}:${server.port}` });
    },
  }); } catch (error) {
    void app.close().catch(failure => writeJsonLine({
      event: "planner_close_failed", code: describePlanError(failure, inputs.root).code,
    }));
    throw error;
  }
  return {
    get port() { return server.port; },
    get hostname() { return server.hostname; },
    async stop(force = false) { try { await server.stop(force); } finally { await app.close(); } },
  };
}
