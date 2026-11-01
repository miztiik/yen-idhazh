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

export function createSafePersistApp(input: {
  root: string; directory: string; maxBodyBytes: number; gitSha: string;
  identity: z.infer<typeof SafePersistHttpReadySchema>; signal: AbortSignal;
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
    const result = await deliverWorkflowMetadata({
      root: input.root, directory: input.directory, runNumber: request.runNumber,
      attempt: request.attempt, currentRunFiles: JSON.stringify(request.paths),
      gitSha: input.gitSha,
    });
    writeJsonLine({
      event: "safe_persist_http_completed", run_number: request.runNumber, attempt: request.attempt,
      status: result.status, commit: result.commit, files: result.files,
    });
    return c.json(result);
  });
  app.notFound(c => c.json({ code: "NOT_FOUND", issues: [{ field: "route", message: "Unknown API route" }] }, 404));
  app.onError((error, c) => {
    const failure = describePlanError(error, input.root);
    const code = "code" in error && typeof error.code === "string" ? error.code : failure.code;
    writeJsonLine({ event: "safe_persist_http_failed", code });
    return c.json({
      ...failure, code,
      issues: failure.issues.map(issue => ({
        ...issue, message: issue.message.replaceAll(input.directory, "feed-ingest-plan").replaceAll("\\", "/"),
      })),
    }, ["INVALID_INPUT", "INVALID_REQUEST"].includes(code) ? 400 : 500);
  });
  return app;
}
