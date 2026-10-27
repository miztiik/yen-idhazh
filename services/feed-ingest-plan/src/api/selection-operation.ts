/** Select from one complete current server batch without writing feed health as a side effect. */
import { randomUUID } from "node:crypto";
import { ParsedFeedBatchSchema, SelectedFeedBatchSchema, StageReferenceRequestSchema } from "@idhazh/common-contracts";
import type { PlanApiTiming } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { operationConfigFingerprint } from "./document-operations";
import { PlanError } from "./plan-request";
import { stageStore } from "./stage-store";
import { selectArticles } from "../select-articles";
import { utcTimestamp } from "../harvest-feeds/harvest-types";
import { prepareFeedHealthState } from "./feed-health-state-operation";
import { appendDocumentTiming, currentExecutionState, executionHasArtifact, registerStageExecution } from "./document-state";
import { resolveRunContext } from "../resolve-run-context";
import { recordFinalizedDocumentWork } from "./record-standalone-run";
import { restoreSourceHealth } from "./restore-source-health";

export function requireStageConfiguration(batch: { config_sha256: string }, inputs: PlanInputs, runtime: PlanRuntime) {
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  if (batch.config_sha256 !== operationConfigFingerprint(inputs, runtime)) {
    throw new PlanError("REQUEST_CONFLICT", "Batch configuration differs from the current planner", "batch_id");
  }
}
export async function executeSelection(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime,
  recordHealthTiming?: (timing: PlanApiTiming) => void) {
  const started = performance.now();
  const request = StageReferenceRequestSchema.parse(raw);
  const store = stageStore(inputs);
  let parsed = store.read("parsed", request.batch_id, ParsedFeedBatchSchema);
  requireStageConfiguration(parsed, inputs, runtime);
  if (store.ownership(parsed.batch_id).health_fingerprint === null) {
    parsed = store.replace("parsed", ParsedFeedBatchSchema, await restoreSourceHealth(parsed, inputs));
  }
  if (!parsed.input_complete) throw new PlanError("BATCH_INCOMPLETE", "Every offered article needs a terminal fetch/parse result before selection", "batch_id");
  const originalClaim = store.claimSelection(parsed.batch_id);
  const captured = (runtime.selection_clock ?? runtime.clock)?.() ?? new Date();
  const selectionStartedAt = utcTimestamp(() => captured);
  const pending = currentExecutionState(inputs, parsed.context.run_id);
  const original = pending === undefined ? undefined : await pending;
  const claim = store.ownership(parsed.batch_id);
  claim.scope = original?.kind === "plan" ? "plan" : claim.scope;
  if (original?.health_fingerprint !== null && original?.health_fingerprint !== undefined) {
    claim.health_fingerprint = original.health_fingerprint;
  }
  const hasArtifact = executionHasArtifact(inputs, parsed.context);
  const keepOriginal = originalClaim && !hasArtifact && !original?.owns_choice
    && !original?.health_written && claim.health_fingerprint === null;
  const context = keepOriginal ? parsed.context : resolveRunContext(inputs.settings, runtime.git_sha, captured);
  if (keepOriginal) {
    if (original !== undefined) original.owns_choice = true;
  } else {
    registerStageExecution(inputs, context, "selection", started);
    if (original?.kind === "document" && !hasArtifact) await recordFinalizedDocumentWork(inputs, original);
  }
  const healthStarted = performance.now();
  let health;
  let healthDuration: number;
  let healthStatus: PlanApiTiming["status"] = "failed";
  try {
    health = await prepareFeedHealthState(inputs, selectionStartedAt, { context: parsed.context, rows: parsed.work_rows });
    healthStatus = "completed";
  } finally {
    healthDuration = Math.round(performance.now() - healthStarted);
    const timing: PlanApiTiming = { operation: "feed-health-for-selection", duration_ms: healthDuration, status: healthStatus };
    recordHealthTiming?.(timing);
    await appendDocumentTiming(inputs, context.run_id, timing);
  }
  const result = await selectArticles(parsed, inputs, selectionStartedAt, health, context);
  const batch = store.write("selected", SelectedFeedBatchSchema, {
    batch_id: randomUUID(), parsed_batch_id: parsed.batch_id, config_sha256: parsed.config_sha256,
    context, selection_started_at_utc: selectionStartedAt, evaluated_at: parsed.context.now, ...result,
  });
  store.ownership(batch.batch_id).scope = keepOriginal ? claim.scope : "standalone";
  await appendDocumentTiming(inputs, batch.context.run_id, { operation: "select", duration_ms: Math.round(performance.now() - started), status: "completed" });
  return { batch, health_summary_duration_ms: healthDuration };
}
