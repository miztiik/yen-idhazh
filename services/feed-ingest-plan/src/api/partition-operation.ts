/** Assign workers to the saved selected articles without selecting or scoring them again. */
import { randomUUID } from "node:crypto";
import { SelectedFeedBatchSchema, PartitionedFeedBatchSchema, PartitionArticlesRequestSchema } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { resolvePlanRequest } from "./plan-request";
import { requireStageConfiguration } from "./selection-operation";
import { stageStore } from "./stage-store";
import { partitionArticles } from "../partition-article-shards/shard-packer";
import { appendDocumentTiming, executionHasArtifact, registerStageExecution } from "./document-state";
import { resolveRunContext } from "../resolve-run-context";

export async function executePartition(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  const started = performance.now();
  const request = PartitionArticlesRequestSchema.parse(raw);
  const store = stageStore(inputs);
  let selected = store.read("selected", request.batch_id, SelectedFeedBatchSchema);
  requireStageConfiguration(selected, inputs, runtime);
  const resolved = resolvePlanRequest({
    ...(request.strategy === undefined ? {} : { partition_strategy: request.strategy }),
    ...(request.shards === undefined ? {} : { shards: request.shards }),
  }, inputs.harvest.config);
  const controls = { strategy: resolved.partition_strategy, dispatch_count: resolved.shards };
  const keepOriginal = store.claimPartition(selected.batch_id) && !executionHasArtifact(inputs, selected.context);
  if (!keepOriginal) {
    const captured = (runtime.selection_clock ?? runtime.clock)?.() ?? new Date();
    const context = resolveRunContext(inputs.settings, runtime.git_sha, captured);
    registerStageExecution(inputs, context, "partition", started);
    selected = SelectedFeedBatchSchema.parse({
      ...selected, context, health_rows: [],
      articles: selected.articles.map(article => ({
        ...article, run_id: context.run_id, attempt: context.writer.attempt, date: context.date,
      })),
      rejected_articles: selected.rejected_articles.map(article => ({
        ...article, run_id: context.run_id, attempt: context.writer.attempt, date: context.date,
      })),
    });
  }
  const partition = partitionArticles(selected.articles, controls);
  const batch = store.write("partitioned", PartitionedFeedBatchSchema, {
    ...selected, batch_id: randomUUID(), selection_batch_id: selected.batch_id, ...partition,
  });
  await appendDocumentTiming(inputs, batch.context.run_id, { operation: "partition", duration_ms: Math.round(performance.now() - started), status: "completed" });
  return { batch };
}
