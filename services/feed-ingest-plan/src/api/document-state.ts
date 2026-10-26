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

export type DocumentState = {
  context: ReturnType<typeof resolveRunContext>; history: Awaited<ReturnType<typeof prepareFeedHealthState>>;
  work: ReturnType<typeof createRunHealth>; fetcher: ReturnType<typeof createPermittedFetcher>;
  recovered: Set<string>;
  exclusions: Promise<Awaited<ReturnType<typeof readExclusionEvidence>>> | null;
  started: number | null; api_timings: PlanApiTiming[]; health_written: boolean;
  health_fingerprint: string | null;
};
const documents = new WeakMap<PlanInputs, Map<string, Promise<DocumentState>>>();
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
  let states = documents.get(inputs);
  if (states === undefined) { states = new Map(); documents.set(inputs, states); }
  let pending = states.get(root.run_id);
  if (pending === undefined) {
    pending = (async (): Promise<DocumentState> => {
      const started = root.state === "started" ? performance.now() : null;
      const context = resolveRunContext(inputs.settings, runtime.git_sha, new Date(root.created_at),
        root.run_id.slice(11), root.correlation_id, root.created_at);
      const history = await prepareFeedHealthState(inputs, context.now);
      return {
        context, history, work: createRunHealth(context, inputs.harvest.sources.map(source => sourceSnapshot(inputs.harvest, source)), history.sources),
        fetcher: createPermittedFetcher(inputs.harvest.config.harvest, inputs.harvest.extraction, runtime.boundary, runtime.observation_clock),
        recovered: new Set<string>(), exclusions: null, started, api_timings: [], health_written: false, health_fingerprint: null,
      };
    })();
    while (states.size >= inputs.settings.listener.max_stage_batches) states.delete(states.keys().next().value!);
    states.set(root.run_id, pending);
  }
  const state = await pending;
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
  const pending = documents.get(inputs)?.get(runId);
  if (pending !== undefined) {
    const state = await pending;
    state.health_written = true;
    state.health_fingerprint = fingerprint;
  }
}
export function currentDocumentState(inputs: PlanInputs, runId: string) { return documents.get(inputs)?.get(runId); }
