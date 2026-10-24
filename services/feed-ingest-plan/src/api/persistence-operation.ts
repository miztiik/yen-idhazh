/** Which validated saved assignments are written to the registered dispatch ledger? */
import { isDeepStrictEqual } from "node:util";
import {
  ParsedFeedBatchSchema, SelectedFeedBatchSchema, PartitionedFeedBatchSchema, StageReferenceRequestSchema,
  readParsedFeedBatch, readSelectedFeedBatch, readPartitionedFeedBatch,
} from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { partitionArticles, persistDispatches } from "../partition-article-shards/shard-packer";
import { requireStageConfiguration } from "./selection-operation";
import { readStageBatch } from "./stage-store";

export async function executePersistence(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  const request = StageReferenceRequestSchema.parse(raw);
  const batch = await readStageBatch(inputs.outputRoot, "partitioned", request.batch_id, PartitionedFeedBatchSchema, readPartitionedFeedBatch);
  requireStageConfiguration(batch, inputs, runtime);
  const selected = await readStageBatch(inputs.outputRoot, "selected", batch.selection_batch_id, SelectedFeedBatchSchema, readSelectedFeedBatch);
  requireStageConfiguration(selected, inputs, runtime);
  const parsed = await readStageBatch(inputs.outputRoot, "parsed", selected.parsed_batch_id, ParsedFeedBatchSchema, readParsedFeedBatch);
  requireStageConfiguration(parsed, inputs, runtime);
  const expected = partitionArticles({
    selections: selected.selections, candidates: parsed.candidates,
    context: selected.context, settings: inputs.harvest.config.partition,
    request: { strategy: batch.strategy, shards: batch.dispatch_count },
  });
  if (!isDeepStrictEqual(expected.dispatches, batch.dispatches) || !isDeepStrictEqual(expected.work, batch.work)
    || !isDeepStrictEqual(batch.context, selected.context) || !isDeepStrictEqual(parsed.context, selected.context)) {
    throw new Error("Saved partition does not preserve its original selection, content and worker assignments");
  }
  return persistDispatches(expected, {
    outputRoot: inputs.outputRoot, writerContext: batch.context.writer,
    ledgerSettings: inputs.ledgerSettings, registration: inputs.registrations.dispatches,
    date: batch.context.date, correlation_id: batch.context.correlation_id,
  });
}
