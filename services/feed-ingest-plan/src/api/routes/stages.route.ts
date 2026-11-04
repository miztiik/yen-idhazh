/** Route current batch references without exposing parsed or rejected article populations. */
import { Hono } from "hono";
import { PartitionArticlesRequestSchema, StageReferenceRequestSchema, selectedArticleMetadata } from "@idhazh/common-contracts";
import type { PlanInputs } from "../../load-plan-inputs";
import type { PlanRuntime } from "../../run-feed-plan";
import type { PlanningBindings } from "./plan.route";
import { executeSelection } from "../selection-operation";
import { executePartition } from "../partition-operation";
import { executePersistence } from "../persistence-operation";
import { PlanError } from "../plan-request";
import { SelectionResponseSchema, PartitionResponseSchema, PersistenceResponseSchema } from "../stage-response.schema";
import { captureRequestRuntime, operationMetadata } from "../operation-context";

export async function readRequestBody(request: Request): Promise<unknown> {
  try { return await request.json(); }
  catch (error) {
    if (error instanceof SyntaxError) throw new PlanError("INVALID_REQUEST", "Body must contain valid JSON", "body");
    throw error;
  }
}
export function stagesRoute(inputs: PlanInputs, runtime: () => PlanRuntime) {
  const app = new Hono<{ Bindings: PlanningBindings }>();
  app.post("/select-articles", async c => {
    const request = StageReferenceRequestSchema.parse(await readRequestBody(c.req.raw));
    c.env?.beginPlanning?.();
    const { batch } = await executeSelection(request, inputs, captureRequestRuntime(runtime(), c.req.raw.headers));
    return c.json(SelectionResponseSchema.parse({
      ...operationMetadata(batch), run_id: batch.context.run_id,
      selection_started_at_utc: batch.selection_started_at_utc, evaluated_at: batch.evaluated_at,
      articles: batch.articles.map(article => ({ ...selectedArticleMetadata(article),
        run_id: batch.context.run_id, attempt: batch.context.writer.attempt, date: batch.context.date })),
      exclusions: batch.exclusions, request_report: batch.request_report,
    }));
  });
  app.post("/partition-articles", async c => {
    const request = PartitionArticlesRequestSchema.parse(await readRequestBody(c.req.raw));
    c.env?.beginPlanning?.();
    const { batch } = await executePartition(request, inputs, captureRequestRuntime(runtime(), c.req.raw.headers));
    return c.json(PartitionResponseSchema.parse({
      ...operationMetadata(batch), run_id: batch.context.run_id,
      strategy: batch.strategy, dispatch_count: batch.dispatch_count, work: batch.work,
      articles: batch.articles.map(article => ({ ...selectedArticleMetadata(article),
        run_id: batch.context.run_id, attempt: batch.context.writer.attempt, date: batch.context.date })),
    }));
  });
  app.post("/persist-selected-articles", async c => {
    const request = StageReferenceRequestSchema.parse(await readRequestBody(c.req.raw));
    c.env?.beginPlanning?.();
    return c.json(PersistenceResponseSchema.parse(
      await executePersistence(request, inputs, captureRequestRuntime(runtime(), c.req.raw.headers)),
    ));
  });
  return app;
}
