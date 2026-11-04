/** Give the real persistence stage a declared captured selection, including an empty selection. */
import { createRootContext, SelectedArticleContentSchema, SelectedFeedBatchSchema } from "@idhazh/common-contracts";
import type { RejectedArticleRow } from "@idhazh/common-contracts";
import type { PlanInputs } from "../src/load-plan-inputs";
import type { PlanRuntime } from "../src/run-feed-plan";
import { resolveRunContext } from "../src/resolve-run-context";
import { operationMetadata, stageConfigFingerprint, stageContext } from "../src/api/operation-context";
import { stageStore } from "../src/api/stage-store";
import { readPlannerOutputRecording } from "./planner-output-recordings";

export async function recordedPersistenceBatch(inputs: PlanInputs, runtime: PlanRuntime,
  options: { empty?: boolean; rejected?: RejectedArticleRow[]; partition_enabled?: boolean } = {}) {
  const { response, health, artifact } = await readPlannerOutputRecording();
  inputs.harvest.config.partition.enabled = options.partition_enabled ?? false;
  const context = resolveRunContext(inputs.settings, runtime.git_sha, new Date(response.evaluated_at),
    response.run_id.slice(11), createRootContext(), undefined, response.attempt);
  const batch = stageStore(inputs).write("selected", SelectedFeedBatchSchema, {
    ...operationMetadata(context), context: stageContext(context),
    config_sha256: stageConfigFingerprint(inputs, runtime), evaluated_at: response.evaluated_at,
    selection_started_at_utc: response.selection_started_at_utc,
    articles: options.empty ? [] : SelectedArticleContentSchema.array().parse(artifact.articles.map(article => ({
      ...article, worker_assignment: null, run_id: context.run_id, attempt: context.writer.attempt, date: context.date,
    }))),
    health_rows: [], rejected_articles: options.rejected ?? [], exclusions: [], request_report: health.request_report,
  });
  return batch;
}
