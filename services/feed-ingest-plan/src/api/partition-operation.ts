/** Which saved selection produces validated worker assignments without changing ranks? */
import { randomUUID } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import {
  ParsedFeedBatchSchema, SelectedFeedBatchSchema, PartitionedFeedBatchSchema,
  PartitionArticlesRequestSchema,
} from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { partitionArticles } from "../partition-article-shards/shard-packer";
import { resolvePartitionRequest } from "../partition-article-shards/partition-input";
import { PlanError } from "./plan-request";
import { requireStageConfiguration } from "./selection-operation";
import { readStageBatch, writeStageBatch } from "./stage-store";

export async function executePartition(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  const request = PartitionArticlesRequestSchema.parse(raw);
  let controls;
  try {
    controls = resolvePartitionRequest(inputs.harvest.config.partition, {
      ...(request.strategy === undefined ? {} : { strategy: request.strategy }),
      ...(request.shards === undefined ? {} : { shards: request.shards }),
    });
  } catch (error) {
    if (!(error instanceof Error)) throw error;
    throw new PlanError("INVALID_REQUEST", error.message, "shards");
  }
  const selected = await readStageBatch(inputs.outputRoot, "selected", request.batch_id, SelectedFeedBatchSchema);
  requireStageConfiguration(selected, inputs, runtime);
  const parsed = await readStageBatch(inputs.outputRoot, "parsed", selected.parsed_batch_id, ParsedFeedBatchSchema);
  requireStageConfiguration(parsed, inputs, runtime);
  if (!isDeepStrictEqual(parsed.context, selected.context)) {
    throw new PlanError("ARTIFACT_INVALID", "Saved selection context differs from its parsed batch", "batch_id");
  }
  const partition = partitionArticles({
    selections: selected.selections, candidates: parsed.candidates,
    context: selected.context, settings: inputs.harvest.config.partition,
    request: { strategy: controls.strategy, shards: controls.dispatch_count },
  });
  const batch = await writeStageBatch(inputs.outputRoot, "partitioned", PartitionedFeedBatchSchema, {
    batch_id: randomUUID(), selection_batch_id: selected.batch_id,
    config_sha256: selected.config_sha256, context: selected.context, ...partition,
  });
  return { batch, partition };
}
