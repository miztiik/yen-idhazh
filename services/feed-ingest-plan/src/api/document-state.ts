/** Keep one document chain's actual work and original clock isolated across concurrent requests. */
import { FetchedDocumentSchema } from "@idhazh/common-contracts";
import type { PlanApiTiming, CandidateRejectionRecord } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { createRunHealth } from "../run-health";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { createPermittedFetcher } from "../harvest-feeds/robots-policy";
import { preparePlanningHealth } from "./prepare-planning-health";
import { deriveArticleIdentity } from "../harvest-feeds/article-identity";
import { deriveFeedIdentity } from "../harvest-feeds/feed-identity";
import { PlanError } from "./plan-request";
import { hashText } from "../hash-text";
import { readExclusionEvidence } from "../read-ledger-history/read-exclusion-evidence";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { stageStore } from "./stage-store";
import type { RunContext } from "../resolve-run-context";
import type { recordPlanRun } from "../record-plan-run";
import { selectedArtifactPath } from "../selected-artifact-path";
import type { DocumentOperationContext } from "./operation-context";
import type { FetchedDocumentReference } from "./stage-store";
import type { PersistLedgerResult } from "@idhazh/ledger-file-writer";

type ExecutionStateBase = {
  context: RunContext; started: number | null; api_timings: PlanApiTiming[];
  health_written: boolean; health_fingerprint: string | null; owns_choice: boolean;
  run_result?: Promise<Awaited<ReturnType<typeof recordPlanRun>>>;
};
export type DocumentState = ExecutionStateBase & {
  plan_owned?: boolean;
  harvest_rejections?: CandidateRejectionRecord[];
  completed_files?: Partial<Record<"discovered_articles" | "rejected_articles", PersistLedgerResult[]>>;
  kind: "document"; history: Awaited<ReturnType<typeof preparePlanningHealth>>;
  work: ReturnType<typeof createRunHealth>; fetcher: ReturnType<typeof createPermittedFetcher>;
  config_sha256: string;
  fetch_request_ids: Set<string>;
  exclusions: Promise<Awaited<ReturnType<typeof readExclusionEvidence>>> | null;
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
    states.delete(expired);
    stageStore(inputs).forgetDocumentWork(expired);
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
export function executionHasArtifact(inputs: PlanInputs, context: RunContext) {
  // One trusted, deterministic artifact path is evidence of a prior result, not a history scan.
  return existsSync(resolve(inputs.root, ...selectedArtifactPath(inputs.settings.inputs.artifact_root, context).split("/")));
}
export function checkFetchedDocument(record: FetchedDocumentReference, inputs: PlanInputs) {
  const artifact = FetchedDocumentSchema.parse(record.document);
  const identity = artifact.fetch_item_type === "feed" ? deriveFeedIdentity(artifact.canonical_url)
    : deriveArticleIdentity(artifact.canonical_url, inputs.harvest.config.harvest);
  if (artifact.article_id !== identity.url_key || artifact.observation.run_id !== record.context.run_id
    || artifact.observation.correlation_id !== record.context.correlation_id
    || artifact.body_sha256 !== (artifact.body === null ? null : hashText(artifact.body))
    || (artifact.body !== null && Buffer.byteLength(artifact.body) > inputs.harvest.extraction.max_body_bytes)) {
    throw new PlanError("ARTIFACT_INVALID", "Fetched document identity, digest or byte bound differs", "fetch_request_id");
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
      const history = await preparePlanningHealth(inputs, context.now, { context, rows: [] });
      return {
        kind: "document", context, history, work: createRunHealth(context,
          inputs.harvest.sources.map(source => sourceSnapshot(inputs.harvest, source)), history.sources,
          { ...inputs.harvest.config.triage, tidy_urls: inputs.harvest.config.harvest.tidy_urls,
            clock: runtime.observation_clock ?? (() => new Date()) }),
        fetcher: createPermittedFetcher(inputs.harvest.config.harvest, inputs.harvest.extraction, runtime.boundary, runtime.observation_clock),
        config_sha256: record.config_sha256, fetch_request_ids: new Set<string>(), exclusions: null, started,
        api_timings: [{ operation: "feed-health-before-fetch", duration_ms: Math.round(performance.now() - historyStarted), status: "completed" }],
        health_written: false, health_fingerprint: null, owns_choice: false,
      };
    })();
    rememberExecution(inputs, record.context.run_id, pending);
  }
  const state = await pending;
  if (state.kind !== "document") throw new PlanError("ARTIFACT_INVALID", "Document work belongs to a different execution", "fetch_request_id");
  if (state.context.correlation_id !== record.context.correlation_id || state.config_sha256 !== record.config_sha256) {
    throw new PlanError("REQUEST_CONFLICT", "Document chain differs from its live execution", "fetch_request_id");
  }
  return state;
}
export async function readDocumentHealthBatch(batchId: string, inputs: PlanInputs) {
  const runId = stageStore(inputs).documentRun(batchId);
  const pending = runId === undefined ? undefined : statesFor(inputs).get(runId);
  if (pending === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "No current document work batch exists", "batch_id");
  const state = await pending;
  if (state.kind !== "document") throw new PlanError("ARTIFACT_INVALID", "Document work belongs to a different execution", "batch_id");
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
