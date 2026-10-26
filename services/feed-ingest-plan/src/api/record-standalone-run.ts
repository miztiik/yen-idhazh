/** Finalize a public stage chain after selected persistence without inventing missing timing evidence. */
import type { PartitionedFeedBatch } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import { currentDocumentState } from "./document-state";
import { recordPlanRun } from "../record-plan-run";

export async function recordStandaloneRun(inputs: PlanInputs, batch: PartitionedFeedBatch, artifact: string) {
  const pending = currentDocumentState(inputs, batch.context.run_id);
  if (pending === undefined) return undefined;
  const state = await pending;
  return recordPlanRun(inputs, batch.context, {
    duration_ms: state.started === null ? null : Math.round(performance.now() - state.started),
    status: state.health_written ? "completed" : "partial",
    failure_code: state.health_written ? null : "FEED_HEALTH_NOT_RECORDED",
    selected_count: batch.articles.length, strategy: batch.strategy, dispatch_count: batch.dispatch_count,
    selected_articles_artifact: artifact, api_timings: [...state.api_timings],
    evaluated_at: batch.evaluated_at, selection_started_at_utc: batch.selection_started_at_utc,
  });
}
