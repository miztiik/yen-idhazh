/** Route completed metadata to the existing safe-persist adapter without accepting its private controls. */
import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import { PLANNER_API_PREFIX } from "@idhazh/common-contracts";
import type { OperationMetadata } from "@idhazh/common-contracts";
import { z } from "zod";
import { describePlanError, PlanError } from "../src/api/plan-request";
import { writeJsonLine } from "../src/logging/structured-logger";
import { deliverWorkflowMetadata } from "./feed-ingest-plan-deliver";
import { SafePersistHttpRequestSchema } from "./feed-ingest-plan-delivery-result";
import { createDeliveryCompletionEvent, createDeliveryFailureEvent } from "./safe-persist-http-diagnostic";
import type { DeliveryEventOutput } from "./safe-persist-http-diagnostic";
import { DELIVERY_EVENT_SOURCE } from "../src/declare-event-source";
import type { SafePersistHttpReadySchema } from "./feed-ingest-plan-delivery-result";
import { withPlannerFailure } from "../src/api/plan-failure";
import type { FailureCaptureLimits } from "../src/config/service-settings";
import { captureRequestRuntime, commandContext } from "../src/api/operation-context";

export function createSafePersistApp(input: {
  root: string; directory: string; maxBodyBytes: number; gitSha: string;
  identity: z.infer<typeof SafePersistHttpReadySchema>; signal: AbortSignal;
  failureLimits?: FailureCaptureLimits;
  writeEvent?: DeliveryEventOutput;
}) {
  const writeEvent: DeliveryEventOutput = input.writeEvent ?? writeJsonLine;
  const app = new Hono<{
    Bindings: { beginDelivery?: () => void };
    Variables: { operation: OperationMetadata };
  }>();
  app.use("*", async (c, next) => {
    c.set("operation", commandContext(captureRequestRuntime({ git_sha: input.gitSha }, c.req.raw.headers)));
    await next();
  });
  app.use(`${PLANNER_API_PREFIX}/*`, bodyLimit({
    maxSize: input.maxBodyBytes,
    onError: c => {
      writeEvent(createDeliveryFailureEvent({ context: c.get("operation"), code: "BODY_TOO_LARGE" }));
      return c.json({ code: "BODY_TOO_LARGE", issues: [
        { field: "body", message: "Body exceeds configured max_body_bytes" },
      ] }, 413);
    },
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
    const context = c.get("operation");
    input.signal.throwIfAborted();
    c.req.raw.signal.throwIfAborted();
    c.env?.beginDelivery?.();
    let result;
    try { result = await deliverWorkflowMetadata({
      root: input.root, directory: input.directory, runNumber: request.runNumber,
      attempt: request.attempt, currentRunFiles: JSON.stringify(request.paths),
      gitSha: input.gitSha, context,
    }); } catch (error) {
      throw withPlannerFailure(error, {
        operation: "commit-ledgers", execution: {
          run_id: null, attempt: request.attempt, traceId: context.traceId, spanId: context.spanId, git_sha: input.gitSha,
        }, ...(input.failureLimits === undefined ? {} : { limits: input.failureLimits }),
      });
    }
    writeEvent(createDeliveryCompletionEvent({
      source: DELIVERY_EVENT_SOURCE, runNumber: request.runNumber, attempt: request.attempt,
      status: result.status, commit: result.commit, files: result.files, context,
    }));
    return c.json(result);
  });
  app.notFound(c => c.json({ code: "NOT_FOUND", issues: [{ field: "route", message: "Unknown API route" }] }, 404));
  app.onError((error, c) => {
    const failure = describePlanError(error, input.root, {
      operation: "commit-ledgers",
      ...(input.failureLimits === undefined ? {} : { limits: input.failureLimits }),
    });
    writeEvent(createDeliveryFailureEvent({ context: c.get("operation"), code: failure.code }));
    return c.json(failure, ["INVALID_INPUT", "INVALID_REQUEST"].includes(failure.code) ? 400 : 500);
  });
  return app;
}
