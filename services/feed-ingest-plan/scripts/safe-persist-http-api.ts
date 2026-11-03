/** Route completed metadata to the existing safe-persist adapter without accepting its private controls. */
import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import { PLANNER_API_PREFIX } from "@idhazh/common-contracts";
import { z } from "zod";
import { describePlanError, PlanError } from "../src/api/plan-request";
import { writeJsonLine } from "../src/logging/structured-logger";
import { deliverWorkflowMetadata } from "./feed-ingest-plan-deliver";
import { SafePersistHttpRequestSchema } from "./feed-ingest-plan-delivery-result";
import type { SafePersistHttpReadySchema } from "./feed-ingest-plan-delivery-result";
import { withPlannerFailure } from "../src/api/plan-failure";
import type { FailureCaptureLimits } from "../src/config/service-settings";

export function createSafePersistApp(input: {
  root: string; directory: string; maxBodyBytes: number; gitSha: string;
  identity: z.infer<typeof SafePersistHttpReadySchema>; signal: AbortSignal;
  failureLimits?: FailureCaptureLimits;
}) {
  const app = new Hono<{ Bindings: { beginDelivery?: () => void } }>();
  app.use(`${PLANNER_API_PREFIX}/*`, bodyLimit({
    maxSize: input.maxBodyBytes,
    onError: c => c.json({ code: "BODY_TOO_LARGE", issues: [
      { field: "body", message: "Body exceeds configured max_body_bytes" },
    ] }, 413),
  }));
  app.get(`${PLANNER_API_PREFIX}/health`, c => c.json({ identity: input.identity }));
  app.post(`${PLANNER_API_PREFIX}/safe-persist-data`, async c => {
    let raw: unknown;
    try { raw = await c.req.json(); }
    catch (error) {
      if (error instanceof SyntaxError) throw new PlanError("INVALID_REQUEST", "body must contain valid JSON", "body");
      throw error;
    }
    const request = SafePersistHttpRequestSchema.parse(raw);
    input.signal.throwIfAborted();
    c.req.raw.signal.throwIfAborted();
    c.env?.beginDelivery?.();
    let result;
    try { result = await deliverWorkflowMetadata({
      root: input.root, directory: input.directory, runNumber: request.runNumber,
      attempt: request.attempt, currentRunFiles: JSON.stringify(request.paths),
      gitSha: input.gitSha,
    }); } catch (error) {
      throw withPlannerFailure(error, {
        operation: "commit-ledgers", execution: {
          run_id: null, attempt: request.attempt, correlation_id: null, git_sha: input.gitSha,
        }, ...(input.failureLimits === undefined ? {} : { limits: input.failureLimits }),
      });
    }
    writeJsonLine({
      event: "safe_persist_http_completed", run_number: request.runNumber, attempt: request.attempt,
      status: result.status, commit: result.commit, files: result.files,
    });
    return c.json(result);
  });
  app.notFound(c => c.json({ code: "NOT_FOUND", issues: [{ field: "route", message: "Unknown API route" }] }, 404));
  app.onError((error, c) => {
    const failure = describePlanError(error, input.root, {
      operation: "commit-ledgers",
      ...(input.failureLimits === undefined ? {} : { limits: input.failureLimits }),
    });
    writeJsonLine({ event: "safe_persist_http_failed", code: failure.code, failure: failure.failure });
    return c.json(failure, ["INVALID_INPUT", "INVALID_REQUEST"].includes(failure.code) ? 400 : 500);
  });
  return app;
}
