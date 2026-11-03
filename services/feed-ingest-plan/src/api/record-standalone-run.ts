/** Save a standalone selection outcome without inventing missing completion or timing evidence. */
import type { SelectedFeedBatch } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import { currentExecutionState, executionHasArtifact, registerStageExecution } from "./document-state";
import type { DocumentState, ExecutionState } from "./document-state";
import { recordPlanRun } from "../record-plan-run";
import { stageStore } from "./stage-store";
import { summarizeSelectionMetrics } from "../summarize-selection-metrics";
import type { RunContext } from "../resolve-run-context";
import { finishArticleEntities } from "../record-article-entities";
import { finishRawDocumentFailures } from "../dump-raw-document-failure";
import { withPlannerFailure } from "./plan-failure";

async function saveOutcome(inputs: PlanInputs, state: ExecutionState, values: Parameters<typeof recordPlanRun>[2]) {
  if (state.run_result !== undefined) return state.run_result;
  const result = (async () => {
    const outputs = await Promise.allSettled([
      finishArticleEntities(inputs, state.context), finishRawDocumentFailures(inputs, state.context),
    ]);
    const failures = outputs.flatMap(result => result.status === "rejected" ? [result.reason] : []);
    if (failures.length) throw withPlannerFailure(new AggregateError(failures, "Standalone diagnostics could not be closed"), {
      operation: "persist", execution: state.context, limits: inputs.settings.diagnostics.failure,
    });
    return recordPlanRun(inputs, state.context, values);
  })();
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
    status: "completed", failure_code: null, selected_count: 0, selection_metrics: null, strategy: "none", dispatch_count: 0,
    selected_articles_artifact: null, api_timings: [...state.api_timings],
    evaluated_at: state.context.now, selection_started_at_utc: null,
  });
}

export async function recordStandaloneRun(inputs: PlanInputs,
  batch: SelectedFeedBatch & { strategy: "bin-pack" | "round-robin" | "none"; dispatch_count: number },
  artifact: string | null, failureCode: string | null = null) {
  const claim = stageStore(inputs).ownership(batch.batch_id);
  if (claim.scope === "plan") return undefined;
  const pending = currentExecutionState(inputs, batch.context.run_id);
  const state = pending === undefined
    ? registerStageExecution(inputs, batch.context, "partition", null) : await pending;
  const selection = await rememberCompletedSelection(inputs, batch);
  const healthRecorded = batch.health_rows.length === 0 || state.health_written || claim.health_fingerprint !== null;
  return saveOutcome(inputs, state, {
    duration_ms: state.started === null ? null : Math.round(performance.now() - state.started),
    status: failureCode !== null ? "failed" : healthRecorded ? "completed" : "partial",
    failure_code: failureCode ?? (healthRecorded ? null : "FEED_HEALTH_NOT_RECORDED"),
    ...selection,
    strategy: batch.strategy, dispatch_count: batch.dispatch_count,
    selected_articles_artifact: artifact, api_timings: [...state.api_timings],
  });
}

export async function rememberCompletedSelection(inputs: PlanInputs, batch: SelectedFeedBatch) {
  const state = await currentExecutionState(inputs, batch.context.run_id)
    ?? registerStageExecution(inputs, batch.context, "selection", null);
  state.completed_selection ??= {
    selected_count: batch.articles.length,
    selection_metrics: summarizeSelectionMetrics(batch.articles,
      inputs.harvest.config.curate_articles.website_grouping.include_private_suffixes),
    evaluated_at: batch.evaluated_at, selection_started_at_utc: batch.selection_started_at_utc,
  };
  return state.completed_selection;
}

export async function recordSelectionFailure(
  inputs: PlanInputs, context: RunContext, evaluatedAt: string, selectionStartedAt: string, failureCode: string,
) {
  const state = await currentExecutionState(inputs, context.run_id);
  if (state === undefined || state.kind === "plan" || (state.kind === "document" && state.plan_owned)) return;
  return saveOutcome(inputs, state, {
    duration_ms: state.started === null ? null : Math.round(performance.now() - state.started),
    status: "failed", failure_code: failureCode, selected_count: 0, selection_metrics: null,
    strategy: "none", dispatch_count: 0, selected_articles_artifact: null, api_timings: [...state.api_timings],
    evaluated_at: evaluatedAt, selection_started_at_utc: selectionStartedAt,
  });
}
