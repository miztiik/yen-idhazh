/** Rebuild source counters from the receipt membership of one named captured batch. */
import { ParsedFeedBatchSchema } from "@idhazh/common-contracts";
import type { ParsedFeedBatch } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import { createRunHealth } from "../run-health";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { openOperationStore } from "./operation-store";
import { checkFetchedDocument } from "./document-state";
import { PlanError } from "./plan-request";

export async function restoreSourceHealth(batch: ParsedFeedBatch, inputs: PlanInputs) {
  const rootId = batch.feed_fetch_request_id ?? batch.article_fetch_request_id;
  if (rootId === null) return batch;
  const store = await openOperationStore(inputs.outputRoot);
  try {
    const root = store.get(rootId);
    if (root?.state !== "complete" || root.operation !== "fetch" || root.run_id !== batch.context.run_id
      || root.correlation_id !== batch.context.correlation_id || root.config_sha256 !== batch.config_sha256) {
      throw new PlanError("ARTIFACT_INVALID", "Parsed batch lacks its original captured receipt", "batch_id");
    }
    const original = checkFetchedDocument(root, inputs);
    const ids = original.fetch_item_type === "article" ? [rootId] : root.article_capture_request_ids;
    const work = createRunHealth(batch.context, inputs.harvest.sources.map(source => sourceSnapshot(inputs.harvest, source)),
      new Map(), inputs.harvest.config.triage, batch.work_rows);
    for (const id of ids) {
      const capture = store.get(id);
      if (capture?.state !== "complete" || capture.operation !== "fetch" || capture.run_id !== root.run_id
        || capture.correlation_id !== root.correlation_id || capture.config_sha256 !== root.config_sha256) {
        throw new PlanError("ARTIFACT_INVALID", "Source receipt membership is incomplete or unrelated", "batch_id");
      }
      const artifact = checkFetchedDocument(capture, inputs);
      if (artifact.fetch_item_type !== "article" || (id !== rootId && artifact.parent_fetch_request_id !== rootId)) {
        throw new PlanError("ARTIFACT_INVALID", "Source receipt does not belong to this original capture", "batch_id");
      }
      work.captureArticle(id, artifact.source_id, artifact.observation.occurred_at, capture.source_outcome);
    }
    return ParsedFeedBatchSchema.parse({ ...batch, work_rows: work.rows(), exclusions: work.exclusions() });
  } finally { store.close(); }
}
