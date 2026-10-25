/** Which saved batch references drive selection, partitioning and dispatch persistence? */
import { Hono } from "hono";
import {
  PartitionArticlesRequestSchema, StageReferenceRequestSchema,
} from "@idhazh/common-contracts";
import type { PlanInputs } from "../../load-plan-inputs";
import type { PlanRuntime } from "../../run-feed-plan";
import type { PlanningBindings } from "./plan.route";
import { executeSelection } from "../selection-operation";
import { executePartition } from "../partition-operation";
import { executePersistence } from "../persistence-operation";
import { PlanError } from "../plan-request";
import {
  SelectionResponseSchema, PartitionResponseSchema, PersistenceResponseSchema,
} from "../stage-response.schema";

export function stagesRoute(inputs: PlanInputs, runtime: PlanRuntime) {
  const app = new Hono<{ Bindings: PlanningBindings }>();
  for (const operation of ["select-articles", "partition-articles", "persist-dispatches"] as const) {
    app.post(`/${operation}`, async c => {
      let raw: unknown;
      try { raw = await c.req.json(); }
      catch (error) {
        if (error instanceof SyntaxError) throw new PlanError("INVALID_REQUEST", "body must contain valid JSON", "body");
        throw error;
      }
      const request = operation === "partition-articles"
        ? PartitionArticlesRequestSchema.parse(raw) : StageReferenceRequestSchema.parse(raw);
      if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled by service settings", "enabled");
      c.env?.beginPlanning?.();
      if (operation === "select-articles") {
        const result = await executeSelection(request, inputs, runtime);
        return c.json(SelectionResponseSchema.parse({
          batch_id: result.batch.batch_id, parsed_batch_id: result.batch.parsed_batch_id,
          run_id: result.batch.context.run_id, correlation_id: result.batch.context.correlation_id,
          selections: result.batch.selections, exclusions: result.batch.rejections,
          publisher_history: {
            day: result.publisher_publication.day, availability: result.publisher_publication.availability,
            gaps: result.publisher_publication.gaps,
          },
          files: { screening_rejections: result.screening.sealing, ...result.portfolio },
        }));
      }
      if (operation === "partition-articles") {
        const result = await executePartition(request, inputs, runtime);
        return c.json(PartitionResponseSchema.parse({
          batch_id: result.batch.batch_id, selection_batch_id: result.batch.selection_batch_id,
          run_id: result.batch.context.run_id, correlation_id: result.batch.context.correlation_id,
          ...result.partition,
        }));
      }
      return c.json(PersistenceResponseSchema.parse({
        batch_id: request.batch_id, files: await executePersistence(request, inputs, runtime),
      }));
    });
  }
  return app;
}
