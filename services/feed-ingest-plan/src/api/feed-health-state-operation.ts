/** Share bounded health reading and run/day recording with the API and the planner. */
import {
  FeedHealthStateRowContract, ParsedFeedBatchSchema, SelectedFeedBatchSchema, PartitionedFeedBatchSchema,
} from "@idhazh/common-contracts";
import type { FeedHealthStateRow } from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { PersistLedgerResult } from "@idhazh/ledger-file-writer";
import { createHash } from "node:crypto";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import type { RunContext } from "../resolve-run-context";
import { readFeedHistory } from "../read-ledger-history/read-feed-history";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { captureHealthRows } from "../read-ledger-history/health-summary";
import { FeedHealthStateUpdateRequestSchema } from "./feed-health-state.schema";
import { stageStore } from "./stage-store";
import { requireStageConfiguration } from "./selection-operation";
import { utcTimestamp } from "../harvest-feeds/harvest-types";
import { readDocumentHealthBatch } from "./document-operations";
import { plannerMemory } from "../planner-memory";
import { PlanError } from "./plan-request";
import { rememberDocumentHealth } from "./document-state";
import { restoreSourceHealth } from "./restore-source-health";

export async function prepareFeedHealthState(inputs: PlanInputs, now: string, current?: {
  context: RunContext; rows: readonly FeedHealthStateRow[];
}) {
  const result = await readFeedHistory({
    root: inputs.root, now, sources: inputs.harvest.sources.map(source => sourceSnapshot(inputs.harvest, source)),
    policy: inputs.clock_config.collect, ...inputs.harvest.config.feedback,
    concurrency: inputs.harvest.config.harvest.concurrency, health: inputs.registrations.feed_health_state,
    health_days: inputs.settings.inputs.feed_health_days,
    own_rows: plannerMemory(inputs).health(),
    ...(current === undefined ? {} : {
      current_rows: current.rows, exclude_execution: { run_id: current.context.run_id, attempt: current.context.writer.attempt },
    }),
  });
  if (inputs.settings.inputs.feed_health_input_gap) {
    for (const [id, source] of result.sources) result.sources.set(id, {
      ...source, article_pass_rate: null,
      reliability: source.reliability === null ? null : { ...source.reliability, complete: false },
    });
    result.request_report.complete = false;
    for (const source of result.request_report.feeds) {
      source.feed_requests = null;
      source.article_requests = null;
      source.robots_requests = null;
      source.counts_complete = false;
    }
  }
  return result;
}
export async function recordFeedHealthState(
  rows: readonly FeedHealthStateRow[], context: RunContext, inputs: PlanInputs,
) {
  if (rows.some(row => row.run_id !== context.run_id || row.attempt !== context.writer.attempt)) throw new PlanError("ARTIFACT_INVALID", "Health work belongs to another execution", "batch_id");
  const fingerprint = healthFingerprint(rows);
  let finished = healthWrites.get(inputs);
  if (finished === undefined) { finished = new Map(); healthWrites.set(inputs, finished); }
  const key = `${context.run_id}:${context.writer.attempt}`;
  const previous = finished.get(key);
  if (previous !== undefined) {
    if (previous.fingerprint !== fingerprint) throw new PlanError("REQUEST_CONFLICT", "This execution already finalized different health work", "batch_id");
    return previous.result;
  }
  const result = (async () => {
    const saved = await persistLedger({
      ledger: "feed-health-state", registryEntry: inputs.registrations.feed_health_state,
      rowContract: FeedHealthStateRowContract, rows, outputRoot: inputs.outputRoot, writerContext: context.writer,
      ledgerSettings: inputs.ledgerSettings, period: { tier: "raw", covers: context.date }, updatedAt: new Date().toISOString(),
    });
    if (saved.status === "skipped") throw new Error("Planner health write was refused");
    await rememberDocumentHealth(inputs, context.run_id, fingerprint);
    return saved;
  })();
  while (finished.size >= inputs.settings.listener.max_stage_batches) finished.delete(finished.keys().next().value!);
  finished.set(key, { fingerprint, result });
  try { return await result; }
  catch (error) { finished.delete(key); throw error; }
}
export async function executeFeedHealthState(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime) {
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  const request = FeedHealthStateUpdateRequestSchema.parse(raw);
  const reliability = { window_days: inputs.clock_config.collect.reliability_window_days };
  if (!stageStore(inputs).has(request.batch_id)) {
    const document = await readDocumentHealthBatch(request.batch_id, inputs, runtime);
    const summary = await prepareFeedHealthState(inputs, utcTimestamp(runtime.selection_clock ?? runtime.clock),
      { context: document.context, rows: document.work.rows() });
    const rows = captureHealthRows(document.work.rows(), summary.sources);
    const files = request.action === "record" ? await recordFeedHealthState(rows, document.context, inputs) : null;
    return { batch_id: request.batch_id, status: request.action === "record" ? "recorded" as const : "summarized" as const,
      rows, request_report: summary.request_report, reliability, ...(files === null ? {} : { files }) };
  }
  const held = stageStore(inputs).inspect(request.batch_id);
  if (held.stage === "parsed") {
    let parsed = ParsedFeedBatchSchema.parse(held.value);
    requireStageConfiguration(parsed, inputs, runtime);
    if (stageStore(inputs).ownership(parsed.batch_id).health_fingerprint === null) {
      parsed = stageStore(inputs).replace("parsed", ParsedFeedBatchSchema, await restoreSourceHealth(parsed, inputs));
    }
    const summary = await prepareFeedHealthState(inputs, utcTimestamp(runtime.selection_clock ?? runtime.clock),
      { context: parsed.context, rows: parsed.work_rows });
    const rows = captureHealthRows(parsed.work_rows, summary.sources);
    const files = request.action === "record" ? await recordFeedHealthState(rows, parsed.context, inputs) : null;
    return { batch_id: request.batch_id, status: request.action === "record" ? "recorded" as const : "summarized" as const,
      rows, request_report: summary.request_report, reliability, ...(files === null ? {} : { files }) };
  }
  const selected = held.stage === "selected" ? SelectedFeedBatchSchema.parse(held.value) : PartitionedFeedBatchSchema.parse(held.value);
  requireStageConfiguration(selected, inputs, runtime);
  const files = request.action === "record" ? await recordFeedHealthState(selected.health_rows, selected.context, inputs) : null;
  return { batch_id: request.batch_id, status: request.action === "record" ? "recorded" as const : "summarized" as const,
    rows: selected.health_rows, request_report: selected.request_report, reliability, ...(files === null ? {} : { files }) };
}

const healthWrites = new WeakMap<PlanInputs, Map<string, { fingerprint: string; result: Promise<PersistLedgerResult> }>>();
export function healthFingerprint(rows: readonly FeedHealthStateRow[]) {
  return createHash("sha256").update(JSON.stringify([...rows].sort((a, b) => a.date.localeCompare(b.date) || a.feed_id.localeCompare(b.feed_id)))).digest("hex");
}
