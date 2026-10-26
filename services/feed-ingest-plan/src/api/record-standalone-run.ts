/** Finalize a public stage chain after selected persistence without inventing missing timing evidence. */
import type { PartitionedFeedBatch } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import { currentExecutionState, executionHasArtifact, registerStageExecution } from "./document-state";
import type { DocumentState, ExecutionState } from "./document-state";
import { recordPlanRun } from "../record-plan-run";
import { stageStore } from "./stage-store";

async function saveOutcome(inputs: PlanInputs, state: ExecutionState, values: Parameters<typeof recordPlanRun>[2]) {
  if (state.run_result !== undefined) return state.run_result;
  const result = recordPlanRun(inputs, state.context, values);
  state.run_result = result;
  try { return await result; }
  catch (error) {
    if (state.run_result === result) delete state.run_result;
    throw error;
  }
}
export async function recordFinalizedDocumentWork(inputs: PlanInputs, state: DocumentState) {
  if (!state.health_written || state.owns_choice || executionHasArtifact(inputs, state.context)) return;
  return saveOutcome(inputs, state, {
    duration_ms: state.started === null ? null : Math.round(performance.now() - state.started),
    status: "completed", failure_code: null, selected_count: 0, strategy: "none", dispatch_count: 0,
    selected_articles_artifact: null, api_timings: [...state.api_timings],
    evaluated_at: state.context.now, selection_started_at_utc: null,
  });
}

export async function recordStandaloneRun(inputs: PlanInputs, batch: PartitionedFeedBatch, artifact: string) {
  const claim = stageStore(inputs).ownership(batch.batch_id);
  if (claim.scope === "plan") return undefined;
  const pending = currentExecutionState(inputs, batch.context.run_id);
  const state = pending === undefined
    ? registerStageExecution(inputs, batch.context, "partition", null) : await pending;
  const healthRecorded = batch.health_rows.length === 0 || state.health_written || claim.health_fingerprint !== null;
  return saveOutcome(inputs, state, {
    duration_ms: state.started === null ? null : Math.round(performance.now() - state.started),
    status: healthRecorded ? "completed" : "partial",
    failure_code: healthRecorded ? null : "FEED_HEALTH_NOT_RECORDED",
    selected_count: batch.articles.length, strategy: batch.strategy, dispatch_count: batch.dispatch_count,
    selected_articles_artifact: artifact, api_timings: [...state.api_timings],
    evaluated_at: batch.evaluated_at, selection_started_at_utc: batch.selection_started_at_utc,
  });
}
