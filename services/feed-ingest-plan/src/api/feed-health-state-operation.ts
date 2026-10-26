/** Share bounded health reading and run/day recording with the API and the planner. */
import {
  FeedHealthStateRowContract, ParsedFeedBatchSchema, SelectedFeedBatchSchema, PartitionedFeedBatchSchema,
} from "@idhazh/common-contracts";
import type { FeedHealthStateRow } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import type { RunContext } from "../resolve-run-context";
import { readFeedHistory } from "../read-ledger-history/read-feed-history";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { summarizeHealth } from "../read-ledger-history/health-summary";
import { FeedHealthStateUpdateRequestSchema } from "./feed-health-state.schema";
import { stageStore } from "./stage-store";
import { requireStageConfiguration } from "./selection-operation";
import { utcTimestamp } from "../harvest-feeds/harvest-types";
import { readDocumentHealthBatch } from "./document-operations";

export function prepareFeedHealthState(inputs: PlanInputs, now: string) {
  return readFeedHistory({
    root: inputs.root, now, sources: inputs.harvest.sources.map(source => sourceSnapshot(inputs.harvest, source)),
    policy: inputs.clock_config.collect, ...inputs.harvest.config.feedback,
    concurrency: inputs.harvest.config.harvest.concurrency, health: inputs.registrations.feed_health_state,
    health_days: inputs.settings.inputs.feed_health_days,
  });
}
export async function recordFeedHealthState(
  rows: readonly FeedHealthStateRow[], context: RunContext, inputs: PlanInputs,
) {
  const result = await persistLedger({
    ledger: "feed-health-state", registryEntry: inputs.registrations.feed_health_state,
    rowContract: FeedHealthStateRowContract, rows, outputRoot: inputs.outputRoot, writerContext: context.writer,
    ledgerSettings: inputs.ledgerSettings, period: { tier: "raw", covers: context.date },
    updatedAt: new Date().toISOString(),
  });
  if (result.status === "skipped") throw new Error("Planner health write was refused");
  return result;
}
export async function executeFeedHealthState(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  const request = FeedHealthStateUpdateRequestSchema.parse(raw);
  if (!stageStore(inputs).has(request.batch_id)) {
    const document = await readDocumentHealthBatch(request.batch_id, inputs, runtime);
    const rows = document.work.rows();
    const summary = summarizeHealth({
      rows: [...document.history.rows, ...rows], days: document.history.days,
      now: utcTimestamp(runtime.selection_clock ?? runtime.clock),
      sources: inputs.harvest.sources.map(source => sourceSnapshot(inputs.harvest, source)),
      policy: inputs.clock_config.collect, ...inputs.harvest.config.feedback,
    });
    if (request.action === "record") await recordFeedHealthState(rows, document.context, inputs);
    return { batch_id: request.batch_id, status: request.action === "record" ? "recorded" as const : "summarized" as const,
      rows, request_report: summary.request_report };
  }
  const held = stageStore(inputs).inspect(request.batch_id);
  if (held.stage === "parsed") {
    const parsed = ParsedFeedBatchSchema.parse(held.value);
    requireStageConfiguration(parsed, inputs, runtime);
    const summary = summarizeHealth({
      rows: [...parsed.history_rows, ...parsed.work_rows], days: parsed.history_days,
      now: utcTimestamp(runtime.selection_clock ?? runtime.clock),
      sources: inputs.harvest.sources.map(source => sourceSnapshot(inputs.harvest, source)),
      policy: inputs.clock_config.collect, ...inputs.harvest.config.feedback,
    });
    if (request.action === "record") await recordFeedHealthState(parsed.work_rows, parsed.context, inputs);
    return { batch_id: request.batch_id, status: request.action === "record" ? "recorded" as const : "summarized" as const,
      rows: parsed.work_rows, request_report: summary.request_report };
  }
  const selected = held.stage === "selected" ? SelectedFeedBatchSchema.parse(held.value) : PartitionedFeedBatchSchema.parse(held.value);
  requireStageConfiguration(selected, inputs, runtime);
  if (request.action === "record") await recordFeedHealthState(selected.health_rows, selected.context, inputs);
  return { batch_id: request.batch_id, status: request.action === "record" ? "recorded" as const : "summarized" as const,
    rows: selected.health_rows, request_report: selected.request_report };
}
