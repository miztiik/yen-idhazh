/** Keep one document chain's actual work and original clock isolated across concurrent requests. */
import { FetchedDocumentSchema } from "@idhazh/common-contracts";
import type { PlanApiTiming, PlanRunRow, CandidateRejectionRecord, DiscoveredArticleRow, OperationLink } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { createRunHealth } from "../run-health";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { createSourceFetcher } from "../harvest-feeds/fetch-source";
import { preparePlanningHealth } from "./prepare-planning-health";
import { deriveArticleIdentity } from "../harvest-feeds/article-identity";
import { deriveFeedIdentity } from "../harvest-feeds/feed-identity";
import { PlanError } from "./plan-request";
import { hashText } from "../hash-text";
import { readRunHistory } from "../read-ledger-history/read-run-history";
import type { RunHistory } from "../read-ledger-history/read-run-history";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { stageStore } from "./stage-store";
import type { RunContext } from "../resolve-run-context";
import type { recordPlanRun } from "../record-plan-run";
import { selectedArtifactPath } from "../selected-artifact-path";
import type { DocumentOperationContext } from "./operation-context";
import { operationKey } from "./operation-context";
import type { FetchedDocumentReference } from "./stage-store";
import { finishArticleEntities } from "../record-article-entities";
import { writeJsonLine } from "../logging/structured-logger";
import { describePlanError } from "./plan-request";

type ExecutionStateBase = {
  context: RunContext; started: number | null; api_timings: PlanApiTiming[];
  health_written: boolean; health_fingerprint: string | null; owns_choice: boolean;
  run_result?: Promise<Awaited<ReturnType<typeof recordPlanRun>>>;
  completed_selection?: Pick<PlanRunRow, "selected_count" | "selection_metrics" | "evaluated_at" | "selection_started_at_utc">;
};
export type DocumentState = ExecutionStateBase & {
  plan_owned?: boolean;
  harvest_rejections?: CandidateRejectionRecord[];
  kind: "document"; history: Awaited<ReturnType<typeof preparePlanningHealth>>;
  work: ReturnType<typeof createRunHealth>; fetcher: ReturnType<typeof createSourceFetcher>;
  config_sha256: string;
  fetches: Set<string>;
  baseline: RunHistory;
  discovered_rows: DiscoveredArticleRow[];
};
export type ExecutionState = DocumentState | (ExecutionStateBase & { kind: "plan" | "selection" | "partition" });
const documents = new WeakMap<PlanInputs, Map<string, Promise<ExecutionState>>>();
function statesFor(inputs: PlanInputs) {
  let states = documents.get(inputs);
  if (states === undefined) { states = new Map(); documents.set(inputs, states); }
  return states;
}
function statesForExecution(inputs: PlanInputs, runId: string) {
  const states = statesFor(inputs);
  while (states.size >= inputs.settings.listener.max_stage_batches && !states.has(runId)) {
    const expired = [...states.keys()].find(id => !stageStore(inputs).isRunActive(id));
    if (expired === undefined) throw new PlanError("REQUEST_BUSY", "Run capacity is occupied by active work");
    const state = states.get(expired);
    if (state !== undefined) void state.then(value => finishArticleEntities(inputs, value.context)).catch(error => {
      writeJsonLine({ event: "planner_expired_entity_output_failed",
        ...describePlanError(error, inputs.root, { operation: "write-entities", limits: inputs.settings.diagnostics.failure }) });
    });
    stageStore(inputs).forgetRun(expired);
    states.delete(expired);
  }
  return states;
}
function rememberExecution(inputs: PlanInputs, runId: string, state: Promise<ExecutionState>) {
  statesForExecution(inputs, runId).set(runId, state);
}
export function registerStageExecution(
  inputs: PlanInputs, context: RunContext, kind: "plan" | "selection" | "partition", started: number | null,
) {
  const state: ExecutionState = {
    kind, context, started, api_timings: [], health_written: false, health_fingerprint: null,
    owns_choice: kind !== "plan",
  };
  rememberExecution(inputs, context.run_id, Promise.resolve(state));
  return state;
}
export function executionHasArtifact(inputs: PlanInputs, context: Pick<RunContext, "run_id" | "writer">) {
  // One trusted, deterministic artifact path is evidence of a prior result, not a history scan.
  return existsSync(resolve(inputs.root, ...selectedArtifactPath(inputs.settings.inputs.artifact_root, context).split("/")));
}
export function checkFetchedDocument(record: FetchedDocumentReference, inputs: PlanInputs) {
  const artifact = FetchedDocumentSchema.parse(record.document);
  const identity = artifact.fetch_item_type === "feed" ? deriveFeedIdentity(artifact.canonical_url)
    : deriveArticleIdentity(artifact.canonical_url);
  if (artifact.document_id !== identity.url_key || artifact.candidate_id !== record.candidate_id
    || artifact.observation.run_id !== record.context.run_id
    || operationKey(artifact.observation) !== operationKey(record.context)
    || artifact.body_sha256 !== (artifact.body === null ? null : hashText(artifact.body))
    || (artifact.body !== null && Buffer.byteLength(artifact.body) > inputs.harvest.extraction.max_body_bytes)) {
    throw new PlanError("ARTIFACT_INVALID", "Fetched document identity, digest or byte bound differs", "links");
  }
  return artifact;
}
export async function documentState(record: DocumentOperationContext, inputs: PlanInputs, runtime: PlanRuntime) {
  const states = statesForExecution(inputs, record.context.run_id);
  let pending = states.get(record.context.run_id);
  if (pending === undefined) {
    pending = (async (): Promise<DocumentState> => {
      const started = performance.now();
      const context = record.context;
      const historyStarted = performance.now();
      const baseline = await readRunHistory(inputs, context);
      const history = await preparePlanningHealth(inputs, context.now, { context, rows: [] }, baseline.health);
      return {
        kind: "document", context, history, work: createRunHealth(context,
          inputs.harvest.sources.map(source => sourceSnapshot(source)), history.sources,
          { ...inputs.harvest.config.triage,
            clock: runtime.observation_clock ?? (() => new Date()) }),
        fetcher: createSourceFetcher(inputs.harvest.config.harvest, inputs.harvest.extraction, runtime.boundary, runtime.observation_clock),
        config_sha256: record.config_sha256, fetches: new Set<string>(), baseline, discovered_rows: [], started,
        api_timings: [{ operation: "feed-health-before-fetch", duration_ms: Math.round(performance.now() - historyStarted), status: "completed" }],
        health_written: false, health_fingerprint: null, owns_choice: false,
      };
    })();
    rememberExecution(inputs, record.context.run_id, pending);
  }
  const state = await pending;
  if (state.kind !== "document") throw new PlanError("ARTIFACT_INVALID", "Document work belongs to a different execution", "links");
  if (state.context.writer.attempt !== record.context.writer.attempt || state.config_sha256 !== record.config_sha256) {
    throw new PlanError("REQUEST_CONFLICT", "Document work differs from its live run attempt or configuration", "links");
  }
  return state;
}
export async function readDocumentHealthBatch(reference: OperationLink, inputs: PlanInputs) {
  const runId = stageStore(inputs).documentRun(reference);
  const pending = runId === undefined ? undefined : statesFor(inputs).get(runId);
  if (pending === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "No current document work exists", "links");
  const state = await pending;
  if (state.kind !== "document") throw new PlanError("ARTIFACT_INVALID", "Document work belongs to a different execution", "links");
  return state;
}
export function documentExclusions(state: DocumentState) {
  return capturedExclusions(state.baseline, state.context.now);
}
export function capturedExclusions(baseline: RunHistory, now: string) {
  const held = baseline.exclusions.get(now.slice(0, 10));
  if (held === undefined) throw new PlanError("HISTORY_WINDOW_UNAVAILABLE", "Exclusions lie outside the captured UTC days", "links");
  return held;
}
export async function requireDocumentState(inputs: PlanInputs, context: RunContext) {
  const state = await currentExecutionState(inputs, context.run_id);
  if (state?.kind !== "document" || state.context.writer.attempt !== context.writer.attempt) {
    throw new PlanError("ARTIFACT_NOT_FOUND", "Stage has no live captured input", "links");
  }
  return state;
}
export async function appendDocumentTiming(inputs: PlanInputs, runId: string, timing: PlanApiTiming, scope: "document" | "plan" = "document") {
  const pending = documents.get(inputs)?.get(runId);
  if (pending === undefined) return;
  const state = await pending;
  if (scope === "document" && state.kind === "document" && state.plan_owned
    && (timing.operation === "fetch" || timing.operation === "parse")) return;
  state.api_timings.push(timing);
}
export async function rememberDocumentHealth(inputs: PlanInputs, runId: string, fingerprint: string) {
  stageStore(inputs).rememberHealth(runId, fingerprint);
  const pending = documents.get(inputs)?.get(runId);
  if (pending !== undefined) {
    const state = await pending;
    state.health_written = true;
    state.health_fingerprint = fingerprint;
  }
}
export function currentExecutionState(inputs: PlanInputs, runId: string) { return documents.get(inputs)?.get(runId); }
