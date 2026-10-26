/** Keep one document chain's actual work and original clock isolated across concurrent requests. */
import { FetchedDocumentSchema } from "@idhazh/common-contracts";
import type { PlannerOperation, PlanApiTiming } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { resolveRunContext } from "../resolve-run-context";
import { createRunHealth } from "../run-health";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { createPermittedFetcher } from "../harvest-feeds/robots-policy";
import { prepareFeedHealthState } from "./feed-health-state-operation";
import { canonicalizeUrl } from "../harvest-feeds/url-cleaner";
import { PlanError } from "./plan-request";
import { sha256 } from "./operation-store";
import { readExclusionEvidence } from "../read-ledger-history/read-exclusion-evidence";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { stageStore } from "./stage-store";
import type { RunContext } from "../resolve-run-context";
import type { recordPlanRun } from "../record-plan-run";
import { selectedArtifactPath } from "../selected-artifact-path";

type ExecutionStateBase = {
  context: RunContext; started: number | null; api_timings: PlanApiTiming[];
  health_written: boolean; health_fingerprint: string | null; owns_choice: boolean;
  run_result?: Promise<Awaited<ReturnType<typeof recordPlanRun>>>;
};
export type DocumentState = ExecutionStateBase & {
  kind: "document"; history: Awaited<ReturnType<typeof prepareFeedHealthState>>;
  work: ReturnType<typeof createRunHealth>; fetcher: ReturnType<typeof createPermittedFetcher>;
  recovered: Set<string>;
  exclusions: Promise<Awaited<ReturnType<typeof readExclusionEvidence>>> | null;
};
export type ExecutionState = DocumentState | (ExecutionStateBase & { kind: "plan" | "selection" | "partition" });
const documents = new WeakMap<PlanInputs, Map<string, Promise<ExecutionState>>>();
function statesFor(inputs: PlanInputs) {
  let states = documents.get(inputs);
  if (states === undefined) { states = new Map(); documents.set(inputs, states); }
  return states;
}
function rememberExecution(inputs: PlanInputs, runId: string, state: Promise<ExecutionState>) {
  const states = statesFor(inputs);
  while (states.size >= inputs.settings.listener.max_stage_batches && !states.has(runId)) {
    states.delete(states.keys().next().value!);
  }
  states.set(runId, state);
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
export function executionHasArtifact(inputs: PlanInputs, context: RunContext) {
  // One trusted, deterministic artifact path is evidence of a prior result, not a history scan.
  return existsSync(resolve(inputs.root, ...selectedArtifactPath(inputs.settings.inputs.artifact_root, context).split("/")));
}
export function checkFetchedDocument(record: PlannerOperation, inputs: PlanInputs) {
  if (record.operation !== "fetch" || record.state !== "complete") throw new PlanError("ARTIFACT_NOT_FOUND", "No completed fetched document exists", "fetch_request_id");
  const artifact = FetchedDocumentSchema.parse(record.artifact);
  const identity = canonicalizeUrl(artifact.canonical_url);
  if (artifact.article_id !== identity.url_key || artifact.observation.run_id !== record.run_id
    || artifact.observation.correlation_id !== record.correlation_id
    || artifact.body_sha256 !== (artifact.body === null ? null : sha256(artifact.body))
    || (artifact.body !== null && Buffer.byteLength(artifact.body) > inputs.harvest.extraction.max_body_bytes)) {
    throw new PlanError("ARTIFACT_INVALID", "Fetched document identity, digest or byte bound differs", "fetch_request_id");
  }
  return artifact;
}
export async function documentState(record: PlannerOperation, inputs: PlanInputs, runtime: PlanRuntime, parent?: PlannerOperation) {
  const root = parent ?? record;
  if (root.run_id !== record.run_id || root.correlation_id !== record.correlation_id) throw new PlanError("ARTIFACT_INVALID", "Document chain belongs to another run", "fetch_request_id");
  const states = statesFor(inputs);
  let pending = states.get(root.run_id);
  if (pending === undefined) {
    pending = (async (): Promise<DocumentState> => {
      const started = root.state === "started" ? performance.now() : null;
      const context = resolveRunContext(inputs.settings, runtime.git_sha, new Date(root.created_at),
        root.run_id.slice(11), root.correlation_id, root.created_at);
      const historyStarted = performance.now();
      const history = await prepareFeedHealthState(inputs, context.now);
      return {
        kind: "document", context, history, work: createRunHealth(context, inputs.harvest.sources.map(source => sourceSnapshot(inputs.harvest, source)), history.sources),
        fetcher: createPermittedFetcher(inputs.harvest.config.harvest, inputs.harvest.extraction, runtime.boundary, runtime.observation_clock),
        recovered: new Set<string>(), exclusions: null, started,
        api_timings: [{ operation: "feed-health-before-fetch", duration_ms: Math.round(performance.now() - historyStarted), status: "completed" }],
        health_written: false, health_fingerprint: null, owns_choice: false,
      };
    })();
    rememberExecution(inputs, root.run_id, pending);
  }
  const state = await pending;
  if (state.kind !== "document") throw new PlanError("ARTIFACT_INVALID", "Document work belongs to a different execution", "fetch_request_id");
  for (const saved of parent === undefined ? [record] : [parent, record]) {
    if (saved.state !== "complete" || saved.operation !== "fetch" || state.recovered.has(saved.request_id)) continue;
    const artifact = checkFetchedDocument(saved, inputs);
    state.work.restoreRequests(artifact);
    if (artifact.kind === "feed") state.work.pendingFeed(artifact.source_id, artifact, artifact.observation.occurred_at);
    state.recovered.add(saved.request_id);
  }
  return state;
}
export function documentExclusions(state: DocumentState, inputs: PlanInputs) {
  state.exclusions ??= readExclusionEvidence({
    root: inputs.root, now: state.context.now, publishedWindowDays: inputs.clock_config.collect.published_window_days,
    settledFailureCodes: inputs.clock_config.collect.settled_failure_codes, publishedRegistration: inputs.registrations.published,
    itemHealthRegistration: inputs.registrations.item_health, publishedDays: inputs.settings.inputs.published_days,
    settledFailureDays: inputs.settings.inputs.settled_failure_days, concurrency: inputs.harvest.config.harvest.concurrency,
  });
  return state.exclusions;
}
export async function appendDocumentTiming(inputs: PlanInputs, runId: string, timing: PlanApiTiming) {
  const pending = documents.get(inputs)?.get(runId);
  if (pending !== undefined) (await pending).api_timings.push(timing);
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
