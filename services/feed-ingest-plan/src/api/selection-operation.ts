/** Select from one complete current server batch without writing feed health as a side effect. */
import { randomUUID } from "node:crypto";
import { ParsedFeedBatchSchema, SelectedFeedBatchSchema, StageReferenceRequestSchema } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { operationConfigFingerprint } from "./document-operations";
import { PlanError } from "./plan-request";
import { stageStore } from "./stage-store";
import { selectArticles } from "../select-articles";
import { utcTimestamp } from "../harvest-feeds/harvest-types";

export function requireStageConfiguration(batch: { config_sha256: string }, inputs: PlanInputs, runtime: PlanRuntime) {
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  if (batch.config_sha256 !== operationConfigFingerprint(inputs, runtime)) {
    throw new PlanError("REQUEST_CONFLICT", "Batch configuration differs from the current planner", "batch_id");
  }
}
export async function executeSelection(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  const request = StageReferenceRequestSchema.parse(raw);
  const parsed = stageStore(inputs).read("parsed", request.batch_id, ParsedFeedBatchSchema);
  requireStageConfiguration(parsed, inputs, runtime);
  const selectionStartedAt = utcTimestamp(runtime.selection_clock ?? runtime.clock);
  const result = await selectArticles(parsed, inputs, selectionStartedAt);
  const batch = stageStore(inputs).write("selected", SelectedFeedBatchSchema, {
    batch_id: randomUUID(), parsed_batch_id: parsed.batch_id, config_sha256: parsed.config_sha256,
    context: parsed.context, selection_started_at_utc: selectionStartedAt, evaluated_at: parsed.context.now, ...result,
  });
  return { batch };
}
