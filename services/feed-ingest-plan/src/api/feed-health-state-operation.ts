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
import { readRequestHistory } from "../read-ledger-history/read-request-history";
import { createPlannerHistoryCache } from "../read-ledger-history/read-planner-history";
import { healthHistoryInput, preparePlanningHealth } from "./prepare-planning-health";
import type { CurrentHealthWork } from "./prepare-planning-health";
import type { RunHistory } from "../read-ledger-history/read-run-history";
import { captureHealthRows } from "../read-ledger-history/health-summary";
import { FeedHealthStateUpdateRequestSchema } from "./feed-health-state.schema";
import { stageStore } from "./stage-store";
import { requireStageConfiguration } from "./selection-operation";
import { utcTimestamp } from "../harvest-feeds/harvest-types";
import { PlanError } from "./plan-request";
import { currentExecutionState, readDocumentHealthBatch, rememberDocumentHealth, requireDocumentState } from "./document-state";
import { plannerMemory } from "../planner-memory";
import { summarizeFeedAvailability } from "../availability/feed-availability-view";
import { projectLifecycleFields } from "../health-row";
import { summarizeRequestReport } from "../read-ledger-history/request-summary";
import { collectionForBatch } from "./collection-operation";
import { snapshotCollectionBatch } from "./collection-batch";
import { projectFeedHealthFields } from "../read-ledger-history/read-feed-health-fields";

export async function prepareExecutionHealth(inputs: PlanInputs, now: string, current?: CurrentHealthWork, baseline?: RunHistory) {
  const captured = baseline ?? (current === undefined ? undefined : (await requireDocumentState(inputs, current.context)).baseline);
  const planning = await preparePlanningHealth(inputs, now, current, captured?.health);
  const requestFields = captured === undefined ? planning.uses.request_totals : currentRequestFields(captured, current);
  return { ...planning, request_report: summarizeRequestReport({
    ...healthHistoryInput(inputs, now, current), ...requestFields,
    days: captured?.requests.request_days ?? planning.request_days,
    input_complete: !inputs.settings.inputs.feed_health_input_gap,
  }) };
}

function currentRequestFields(baseline: RunHistory, current?: CurrentHealthWork) {
  const fields = structuredClone(baseline.requests.uses.request_totals);
  const rows = current?.rows ?? [];
  for (const day of new Set(rows.map(row => row.date))) {
    const work = projectFeedHealthFields(day, rows.filter(row => row.date === day)).request_totals;
    fields.rows.push(...work.rows);
    fields.partial_rows.push(...work.partial_rows);
    fields.gaps.push(...work.gaps);
  }
  return fields;
}

export async function prepareRequestReport(inputs: PlanInputs, now: string, current?: CurrentHealthWork,
  cache = createPlannerHistoryCache<Record<string, unknown>>()) {
  if (current !== undefined) {
    const baseline = (await requireDocumentState(inputs, current.context)).baseline;
    return summarizeRequestReport({
      ...healthHistoryInput(inputs, now, current), ...currentRequestFields(baseline, current),
      days: baseline.requests.request_days, input_complete: !inputs.settings.inputs.feed_health_input_gap,
    });
  }
  const { request_report } = await readRequestHistory({
    ...healthHistoryInput(inputs, now, current), input_complete: !inputs.settings.inputs.feed_health_input_gap,
  }, cache);
  return request_report;
}
export async function prepareFeedHealthState(inputs: PlanInputs, now: string, current?: CurrentHealthWork) {
  if (current !== undefined) return prepareExecutionHealth(inputs, now, current);
  const cache = createPlannerHistoryCache<Record<string, unknown>>();
  const [planning, request_report] = await Promise.all([
    preparePlanningHealth(inputs, now), prepareRequestReport(inputs, now, undefined, cache),
  ]);
  return { ...planning, request_report };
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
    plannerMemory(inputs).rememberHealth(rows);
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
    const document = await readDocumentHealthBatch(request.batch_id, inputs);
    requireStageConfiguration(document, inputs, runtime);
    const prepare = request.action === "record" ? prepareExecutionHealth : prepareFeedHealthState;
    const summary = await prepare(inputs, utcTimestamp(runtime.selection_clock ?? runtime.clock),
      { context: document.context, rows: document.work.rows() });
    const rows = captureHealthRows(document.work.rows(), summary.sources);
    const files = request.action === "record" ? await recordFeedHealthState(rows, document.context, inputs) : null;
    return { batch_id: request.batch_id, status: request.action === "record" ? "recorded" as const : "summarized" as const,
      rows, request_report: summary.request_report, reliability, availability: summary.availability, ...(files === null ? {} : { files }) };
  }
  const held = stageStore(inputs).inspect(request.batch_id);
  if (held.stage === "parsed") {
    let parsed = ParsedFeedBatchSchema.parse(held.value);
    requireStageConfiguration(parsed, inputs, runtime);
    const collection = collectionForBatch(inputs, request.batch_id);
    if (collection !== undefined && collection.status === "collecting") {
      parsed = snapshotCollectionBatch(inputs, collection, false);
    }
    const live = await currentExecutionState(inputs, parsed.context.run_id);
    if (live?.kind === "document" && stageStore(inputs).ownership(parsed.batch_id).health_fingerprint === null) {
      parsed = stageStore(inputs).replace("parsed", ParsedFeedBatchSchema, {
        ...parsed, work_rows: live.work.rows(), exclusions: live.work.exclusions(),
      });
    }
    const prepare = request.action === "record" ? prepareExecutionHealth : prepareFeedHealthState;
    const summary = await prepare(inputs, utcTimestamp(runtime.selection_clock ?? runtime.clock),
      { context: parsed.context, rows: parsed.work_rows });
    const rows = captureHealthRows(parsed.work_rows, summary.sources);
    const files = request.action === "record" ? await recordFeedHealthState(rows, parsed.context, inputs) : null;
    return { batch_id: request.batch_id, status: request.action === "record" ? "recorded" as const : "summarized" as const,
      rows, request_report: summary.request_report, reliability, availability: summary.availability, ...(files === null ? {} : { files }) };
  }
  const selected = held.stage === "selected" ? SelectedFeedBatchSchema.parse(held.value) : PartitionedFeedBatchSchema.parse(held.value);
  requireStageConfiguration(selected, inputs, runtime);
  const sources = new Map(selected.health_rows.map(row => [row.feed_id, {
    ...projectLifecycleFields({ ...row, lifecycle: row.availability }),
    lifecycle: row.availability, endpoint_key: row.endpoint_key, reliability: row.reliability,
  }]));
  const availability = summarizeFeedAvailability(sources, utcTimestamp(runtime.observation_clock), inputs.harvest.sources);
  const files = request.action === "record" ? await recordFeedHealthState(selected.health_rows, selected.context, inputs) : null;
  return { batch_id: request.batch_id, status: request.action === "record" ? "recorded" as const : "summarized" as const,
    rows: selected.health_rows, request_report: selected.request_report, reliability, availability, ...(files === null ? {} : { files }) };
}

const healthWrites = new WeakMap<PlanInputs, Map<string, { fingerprint: string; result: Promise<PersistLedgerResult> }>>();
export function healthFingerprint(rows: readonly FeedHealthStateRow[]) {
  return createHash("sha256").update(JSON.stringify([...rows].sort((a, b) => a.date.localeCompare(b.date) || a.feed_id.localeCompare(b.feed_id)))).digest("hex");
}
