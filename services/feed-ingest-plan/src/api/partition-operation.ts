/** Assign workers to the saved selected articles without selecting or scoring them again. */
import { randomUUID } from "node:crypto";
import { SelectedFeedBatchSchema, PartitionedFeedBatchSchema, PartitionArticlesRequestSchema } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { resolvePartitionRequest } from "../partition-article-shards/partition-input";
import { requireStageConfiguration } from "./selection-operation";
import { stageStore } from "./stage-store";
import { partitionArticles } from "../partition-article-shards/shard-packer";

export async function executePartition(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  const request = PartitionArticlesRequestSchema.parse(raw);
  const selected = stageStore(inputs).read("selected", request.batch_id, SelectedFeedBatchSchema);
  requireStageConfiguration(selected, inputs, runtime);
  const controls = resolvePartitionRequest(inputs.harvest.config.partition, {
    ...(request.strategy === undefined ? {} : { strategy: request.strategy }),
    ...(request.shards === undefined ? {} : { shards: request.shards }),
  });
  const partition = partitionArticles(selected.articles, controls);
  const batch = stageStore(inputs).write("partitioned", PartitionedFeedBatchSchema, {
    ...selected, batch_id: randomUUID(), selection_batch_id: selected.batch_id, ...partition,
  });
  return { batch };
}
