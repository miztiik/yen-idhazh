/** Assign workers to the saved selected articles without selecting or scoring them again. */
import { createRootContext, SelectedFeedBatchSchema, PartitionedFeedBatchSchema, PartitionArticlesRequestSchema } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { resolvePlanRequest, PlanError } from "./plan-request";
import { requireStageConfiguration } from "./selection-operation";
import { stageStore } from "./stage-store";
import { partitionArticles } from "../partition-article-shards/shard-packer";
import { appendDocumentTiming, executionHasArtifact, registerStageExecution } from "./document-state";
import { resolveRunContext } from "../resolve-run-context";
import { recordStandaloneRun, rememberCompletedSelection } from "./record-standalone-run";
import { retainFailureThroughCleanup } from "./retain-failure-through-cleanup";
import { commandContext, operationLink, operationMetadata, operationRunContext, stageContext } from "./operation-context";
import { collectionForRun } from "./collection-operation";

export async function executePartition(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  if (!inputs.harvest.config.partition.enabled) throw new PlanError("PARTITION_DISABLED", "Partitioning is disabled by the effective policy", "partition.enabled");
  const started = performance.now();
  const request = PartitionArticlesRequestSchema.parse(raw);
  const store = stageStore(inputs);
  let selected = store.read("selected", request.links[0], SelectedFeedBatchSchema);
  requireStageConfiguration(selected, inputs, runtime);
  const resolved = resolvePlanRequest({
    ...(request.strategy === undefined ? {} : { partition_strategy: request.strategy }),
    ...(request.shards === undefined ? {} : { shards: request.shards }),
  }, inputs.harvest.config);
  const controls = { strategy: resolved.partition_strategy, dispatch_count: resolved.shards };
  const keepOriginal = store.claimPartition(selected) && !executionHasArtifact(inputs, selected.context);
  const operation = keepOriginal ? commandContext(runtime, collectionForRun(inputs, selected.context.run_id)?.context, [selected])
    : createRootContext({ links: [operationLink(selected)] });
  let context = { ...selected.context, ...operation };
  if (!keepOriginal) {
    const captured = (runtime.selection_clock ?? runtime.clock)?.() ?? new Date();
    context = resolveRunContext(inputs.settings, runtime.git_sha, captured,
      undefined, operation, undefined, runtime.attempt, runtime.producer);
    registerStageExecution(inputs, context, "partition", started);
    selected = SelectedFeedBatchSchema.parse({
      ...selected, ...operationMetadata(context), context: stageContext(context), health_rows: [],
      articles: selected.articles.map(article => ({
        ...article, run_id: context.run_id, attempt: context.writer.attempt, date: context.date,
      })),
      rejected_articles: selected.rejected_articles.map(article => ({
        ...article, run_id: context.run_id, attempt: context.writer.attempt, date: context.date,
      })),
    });
  } else selected = SelectedFeedBatchSchema.parse({ ...selected, ...operationMetadata(context) });
  await rememberCompletedSelection(inputs, selected);
  try {
    const partition = partitionArticles(selected.articles, controls);
    const batch = store.write("partitioned", PartitionedFeedBatchSchema, {
      ...selected, ...partition,
    });
    await appendDocumentTiming(inputs, batch.context.run_id, { operation: "partition", duration_ms: Math.round(performance.now() - started), status: "completed" });
    return { batch };
  } catch (error) {
    throw await retainFailureThroughCleanup(error, {
      operation: "partition", execution: operationRunContext(selected), limits: inputs.settings.diagnostics.failure,
    }, [
      { operation: "record-run", execute: () => appendDocumentTiming(inputs, selected.context.run_id, {
        operation: "partition", duration_ms: Math.round(performance.now() - started), status: "failed",
      }) },
      { operation: "record-run", execute: () => recordStandaloneRun(inputs,
        { ...selected, strategy: controls.strategy, dispatch_count: 0 },
        null, error instanceof PlanError ? error.code : "PARTITION_FAILED", request.links[0]) },
    ]);
  }
}
