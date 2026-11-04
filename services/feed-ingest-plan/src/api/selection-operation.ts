/** Select from one complete current server batch without writing feed health as a side effect. */
import { createRootContext, ParsedFeedBatchSchema, SelectedFeedBatchSchema, StageReferenceRequestSchema } from "@idhazh/common-contracts";
import type { PlanApiTiming } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import {
  commandContext, operationKey, operationLink, operationMetadata, operationRunContext, stageConfigFingerprint, stageContext,
} from "./operation-context";
import { PlanError } from "./plan-request";
import { stageStore } from "./stage-store";
import { selectArticles } from "../select-articles";
import { utcTimestamp } from "../harvest-feeds/harvest-types";
import { prepareExecutionHealth } from "./feed-health-state-operation";
import { appendDocumentTiming, currentExecutionState, executionHasArtifact, registerStageExecution } from "./document-state";
import { resolveRunContext } from "../resolve-run-context";
import { recordFinalizedDocumentWork, recordSelectionFailure, rememberCompletedSelection } from "./record-standalone-run";
import { collectionForRun } from "./collection-operation";
import { retainFailureThroughCleanup } from "./retain-failure-through-cleanup";

export function requireStageConfiguration(
  batch: { config_sha256: string; context?: { run_id: string } }, inputs: PlanInputs, runtime: PlanRuntime,
  allowFinalizedSummary = false,
) {
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  if (batch.config_sha256 !== stageConfigFingerprint(inputs, runtime)) {
    throw new PlanError("REQUEST_CONFLICT", "Result configuration differs from the current planner", "links");
  }
  const collection = batch.context === undefined ? undefined : collectionForRun(inputs, batch.context.run_id);
  if (collection?.finalizing || (collection?.finalization !== undefined && !allowFinalizedSummary)) {
    throw new PlanError("REQUEST_CONFLICT", "Collection outcome is already finalized", "links");
  }
}
export async function executeSelection(raw: unknown, inputs: PlanInputs, runtime: PlanRuntime,
  recordHealthTiming?: (timing: PlanApiTiming) => void) {
  const started = performance.now();
  const request = StageReferenceRequestSchema.parse(raw);
  const store = stageStore(inputs);
  let parsed = store.read("parsed", request.links[0], ParsedFeedBatchSchema);
  requireStageConfiguration(parsed, inputs, runtime);
  const collection = collectionForRun(inputs, parsed.context.run_id);
  if (collection !== undefined && (collection.status !== "complete" || collection.finalizing
    || collection.finalization !== undefined || collection.completed === undefined
    || operationKey(collection.completed) !== operationKey(parsed))) {
    throw new PlanError("BATCH_INCOMPLETE", "Selection requires the completed global collection, not one feed's result", "links");
  }
  const original = await currentExecutionState(inputs, parsed.context.run_id);
  if (original?.kind !== "document") {
    throw new PlanError("ARTIFACT_NOT_FOUND", "Selection requires its live captured input", "links");
  }
  if (original.kind === "document" && (store.ownership(parsed).health_fingerprint === null || store.isCollectionResult(parsed))) {
    const updated = {
      ...parsed, work_rows: original.work.rows(), exclusions: original.work.exclusions(),
    };
    parsed = store.isCollectionResult(parsed) ? ParsedFeedBatchSchema.parse(updated)
      : store.replace("parsed", ParsedFeedBatchSchema, updated);
  }
  if (!parsed.input_complete) throw new PlanError("BATCH_INCOMPLETE", "Every offered article needs a terminal fetch/parse result before selection", "links");
  const originalClaim = store.claimSelection(parsed);
  const captured = (runtime.selection_clock ?? runtime.clock)?.() ?? new Date();
  const selectionStartedAt = utcTimestamp(() => captured);
  const claim = store.ownership(parsed);
  claim.scope = original.plan_owned ? "plan" : claim.scope;
  if (original?.health_fingerprint !== null && original?.health_fingerprint !== undefined) {
    claim.health_fingerprint = original.health_fingerprint;
  }
  const hasArtifact = executionHasArtifact(inputs, parsed.context);
  const keepOriginal = originalClaim && !hasArtifact && !original?.owns_choice
    && !original?.health_written && claim.health_fingerprint === null;
  const operation = keepOriginal ? commandContext(runtime, collection?.context, [parsed])
    : createRootContext({ links: [operationLink(parsed)] });
  const context = keepOriginal ? { ...parsed.context, ...operation } : resolveRunContext(inputs.settings, runtime.git_sha, captured,
    undefined, operation, undefined, runtime.attempt, runtime.producer);
  if (keepOriginal) {
    if (original !== undefined) original.owns_choice = true;
  } else {
    registerStageExecution(inputs, context, "selection", started);
    if (original?.kind === "document" && !hasArtifact) await recordFinalizedDocumentWork(inputs, original);
  }
  const healthStarted = performance.now();
  try {
    let health;
    let healthDuration: number;
    let healthStatus: PlanApiTiming["status"] = "failed";
    try {
      health = await prepareExecutionHealth(inputs, selectionStartedAt,
        { context: operationRunContext(parsed), rows: parsed.work_rows }, original.baseline);
      healthStatus = "completed";
    } finally {
      healthDuration = Math.round(performance.now() - healthStarted);
      const timing: PlanApiTiming = { operation: "feed-health-for-selection", duration_ms: healthDuration, status: healthStatus };
      recordHealthTiming?.(timing);
      await appendDocumentTiming(inputs, context.run_id, timing);
    }
    const result = await selectArticles(parsed, inputs, selectionStartedAt, health, context, original.baseline);
    const batch = store.write("selected", SelectedFeedBatchSchema, {
      ...operationMetadata(context), config_sha256: parsed.config_sha256,
      context: stageContext(context), selection_started_at_utc: selectionStartedAt, evaluated_at: parsed.context.now, ...result,
    });
    store.ownership(batch).scope = keepOriginal ? claim.scope : "standalone";
    await rememberCompletedSelection(inputs, batch);
    await appendDocumentTiming(inputs, batch.context.run_id, { operation: "select", duration_ms: Math.round(performance.now() - started), status: "completed" });
    return { batch, health_summary_duration_ms: healthDuration };
  } catch (error) {
    throw await retainFailureThroughCleanup(error, {
      operation: "select", execution: context, limits: inputs.settings.diagnostics.failure,
    }, [
      { operation: "record-run", execute: () => appendDocumentTiming(inputs, context.run_id, {
        operation: "select", duration_ms: Math.round(performance.now() - started), status: "failed",
      }) },
      { operation: "record-run", execute: () => recordSelectionFailure(inputs, context, parsed.context.now,
        selectionStartedAt, error instanceof PlanError ? error.code : "SELECTION_FAILED") },
    ]);
  }
}
