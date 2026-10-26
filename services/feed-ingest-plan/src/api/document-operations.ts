/** Fetch and parse real permitted documents while returning only body-free stage references. */
import { randomUUID } from "node:crypto";
import {
  FeedIngestCandidateSchema, ParsedFeedBatchSchema, DiscoveredArticleRowSchema, PlannerHarvestObservationSchema, PlannerOperationSchema,
  FetchedDocumentSchema, deriveCandidateId,
} from "@idhazh/common-contracts";
import type { PlannerOperation } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { resolveRunContext } from "../resolve-run-context";
import { createPermittedFetcher } from "../harvest-feeds/robots-policy";
import { canonicalizeUrl } from "../harvest-feeds/url-cleaner";
import { validateTargetName } from "../harvest-feeds/safe-target";
import { parseDocument } from "../harvest-feeds/parse-document";
import { documentWork, describeArticleParse, describeFeedParse } from "../harvest-feeds/document-work";
import { observeDocument } from "../harvest-feeds/document-observation";
import { createIngestObservations } from "../ingest-observations";
import { createRunHealth } from "../run-health";
import { PlanError } from "./plan-request";
import { FetchRequestSchema, ParseRequestSchema } from "./operation-contracts";
import { openOperationStore, sha256 } from "./operation-store";
import type { PreparedOperation } from "./operation-store";
import { prepareFeedHealthState } from "./feed-health-state-operation";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { stageStore } from "./stage-store";
import { readSeenEvidence, rememberFirstSight, requiredSeenDays } from "../read-ledger-history/read-seen-evidence";
import { plannerMemory } from "../planner-memory";
import { utcTimestamp } from "../harvest-feeds/harvest-types";
import { ArticleParserPool } from "../harvest-feeds/article-parser-pool";
import { profileTask } from "../../../host-probes/src/task-profile/task-profiler";

export function operationConfigFingerprint(inputs: PlanInputs, runtime: PlanRuntime) {
  return sha256(JSON.stringify({
    harvest: inputs.harvest.config_sha256, settings: inputs.settings, clock: inputs.clock_config,
    ledger: inputs.ledgerSettings, registrations: inputs.registrations, git_sha: runtime.git_sha,
  }));
}
export function proposedOperation(
  operation: PlannerOperation["operation"], request_id: string, request: unknown, correlation_id: string,
  inputs: PlanInputs, runtime: PlanRuntime,
) {
  const now = runtime.clock?.() ?? new Date();
  const runNumber = operation === "plan" ? runtime.run_number
    : BigInt(`0x${request_id.replaceAll("-", "")}`).toString();
  const context = resolveRunContext(inputs.settings, runtime.git_sha, now, runNumber, correlation_id, runtime.captured_at);
  return PlannerOperationSchema.parse({
    request_id, operation, input_sha256: sha256(JSON.stringify(request)),
    config_sha256: operationConfigFingerprint(inputs, runtime), run_id: context.run_id, correlation_id,
    created_at: context.captured_at, state: "started", response_json: null, artifact: null,
  });
}
export function prepareOperation(
  operation: PlannerOperation["operation"], request_id: string, request: unknown, correlation_id: string,
  inputs: PlanInputs, runtime: PlanRuntime, runId?: string,
): PreparedOperation {
  return {
    request_id, operation, input_sha256: sha256(JSON.stringify(request)),
    config_sha256: operationConfigFingerprint(inputs, runtime),
    capture: () => {
      const record = proposedOperation(operation, request_id, request, correlation_id, inputs, runtime);
      return runId === undefined ? record : { ...record, run_id: runId };
    },
  };
}
type DocumentState = {
  context: ReturnType<typeof resolveRunContext>;
  history: Awaited<ReturnType<typeof prepareFeedHealthState>>;
  work: ReturnType<typeof createRunHealth>;
};
const documents = new WeakMap<PlanInputs, Map<string, DocumentState>>();
async function documentState(record: PlannerOperation, inputs: PlanInputs, runtime: PlanRuntime) {
  let states = documents.get(inputs);
  if (states === undefined) { states = new Map(); documents.set(inputs, states); }
  const existing = states.get(record.run_id);
  if (existing !== undefined) return existing;
  const context = resolveRunContext(inputs.settings, runtime.git_sha, new Date(record.created_at),
    record.run_id.slice(11), record.correlation_id, record.created_at);
  const history = await prepareFeedHealthState(inputs, context.now);
  const state = { context, history, work: createRunHealth(context,
    inputs.harvest.sources.map(source => sourceSnapshot(inputs.harvest, source)), history.sources) };
  while (states.size >= inputs.settings.listener.max_stage_batches) states.delete(states.keys().next().value!);
  states.set(record.run_id, state);
  return state;
}
export async function executeDocumentOperation(
  operation: "fetch" | "parse", raw: unknown, inputs: PlanInputs, runtime: PlanRuntime, signal?: AbortSignal,
) {
  const request = operation === "fetch" ? FetchRequestSchema.parse(raw) : ParseRequestSchema.parse(raw);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled", "enabled");
  const store = await openOperationStore(inputs.outputRoot);
  try {
    const fetchedRecord = "fetch_request_id" in request ? store.get(request.fetch_request_id) : null;
    const proposed = prepareOperation(operation, request.request_id, request, request.correlation_id, inputs, runtime, fetchedRecord?.run_id);
    const completed = await store.execute(proposed, async record => {
      if ("source_id" in request) {
        const source = inputs.harvest.sources.find(source => source.id === request.source_id);
        if (source === undefined || source.status !== "active") throw new PlanError("INVALID_REQUEST", "Fetch requires an active configured feed", "source_id");
        const url = request.kind === "feed" ? source.url : request.url!;
        try { validateTargetName(url); }
        catch { throw new PlanError("INVALID_REQUEST", "Fetch requires a public HTTP address without credentials", "url"); }
        const state = await documentState(record, inputs, runtime);
        const identity = canonicalizeUrl(url);
        const work = documentWork({
          observations: createIngestObservations(state.work.observe),
          observation_clock: runtime.observation_clock ?? (() => new Date()),
        }, { run_id: record.run_id, correlation_id: record.correlation_id, article_id: identity.url_key, source_id: source.id },
        record.request_id, {
          document_kind: request.kind, source_id: source.id, publisher_id: source.publisher_id,
          observed_run_id: record.run_id, observed_attempt: inputs.settings.run.attempt, candidate_id: null,
        });
        const result = await profileTask(runtime.task_profiling, {
          pipeline_name: "feed-ingest-plan", task_name: "fetch", run_id: record.run_id,
          correlation_id: record.correlation_id, request_id: record.request_id,
        }, () => work.fetch(createPermittedFetcher(inputs.harvest.config.harvest, inputs.harvest.extraction,
          runtime.boundary, runtime.observation_clock), url, request.caused_by_event_id ?? null),
        { ...(signal === undefined ? {} : { signal }), outcome: result => result.fetched.failure === null ? "success" : "error" });
        const { fetched, observation } = result;
        if (request.kind === "feed") state.work.pendingFeed(source.id, fetched, observation.occurred_at);
        const attempts = fetched.attempts ?? [];
        const artifact = FetchedDocumentSchema.parse({
          ...fetched, kind: request.kind, canonical_url: identity.canonical_url,
          article_id: identity.url_key, source_id: source.id,
          error_code: fetched.error_code ?? null, robots_failure: fetched.robots_failure ?? null,
          robots_http_status: fetched.robots_http_status ?? null,
          body_sha256: fetched.body === null ? null : sha256(fetched.body), attempts, observation,
          attempt_observations: attempts.map(attempt => observeDocument({
            run_id: record.run_id, correlation_id: record.correlation_id, article_id: identity.url_key, source_id: source.id,
          }, `${record.request_id}\n${attempt.sequence}`, "attempt", observation.event_id, observation.occurred_at)),
        });
        return { artifact, response_json: JSON.stringify({
          fetch_request_id: record.request_id, batch_id: record.request_id, run_id: record.run_id, correlation_id: record.correlation_id,
          kind: request.kind, source_id: source.id, article_id: identity.url_key,
          canonical_url: identity.canonical_url, http_status: fetched.http_status, failure: fetched.failure,
          body_sha256: artifact.body_sha256,
        }) };
      }
      if (fetchedRecord === null || fetchedRecord.state !== "complete" || fetchedRecord.operation !== "fetch") {
        throw new PlanError("ARTIFACT_NOT_FOUND", "No completed fetched document exists", "fetch_request_id");
      }
      if (fetchedRecord.config_sha256 !== record.config_sha256) throw new PlanError("REQUEST_CONFLICT", "Fetch configuration differs", "fetch_request_id");
      const artifact = FetchedDocumentSchema.parse(fetchedRecord.artifact);
      const identity = canonicalizeUrl(artifact.canonical_url);
      if (artifact.article_id !== identity.url_key || artifact.article_id !== request.article_id
        || fetchedRecord.correlation_id !== request.correlation_id || artifact.observation.run_id !== fetchedRecord.run_id) {
        throw new PlanError("INVALID_REQUEST", "Parse identity differs from the fetched document", "article_id");
      }
      if (artifact.body === null || artifact.failure !== null) throw new PlanError("FETCH_UNAVAILABLE", "Fetch has no successful body", "fetch_request_id");
      if (artifact.body_sha256 !== sha256(artifact.body) || Buffer.byteLength(artifact.body) > inputs.harvest.extraction.max_body_bytes) {
        throw new PlanError("ARTIFACT_INVALID", "Fetched body digest or byte bound differs", "fetch_request_id");
      }
      const source = inputs.harvest.sources.find(source => source.id === artifact.source_id);
      if (source === undefined) throw new PlanError("ARTIFACT_INVALID", "Fetched feed is no longer configured", "source_id");
      const state = await documentState(fetchedRecord, inputs, runtime);
      const work = documentWork({
        observations: createIngestObservations(state.work.observe), observation_clock: runtime.observation_clock ?? (() => new Date()),
      }, { run_id: fetchedRecord.run_id, correlation_id: fetchedRecord.correlation_id, article_id: artifact.article_id, source_id: source.id },
      record.request_id, {
        document_kind: artifact.kind, source_id: source.id, publisher_id: source.publisher_id,
        observed_run_id: fetchedRecord.run_id, observed_attempt: inputs.settings.run.attempt, candidate_id: null,
      });
      const candidates = [];
      const observations = {};
      const parser = new ArticleParserPool(inputs.settings.listener.parser_concurrency);
      let count = 0;
      let failure: string | null = null;
      try {
        if (artifact.kind === "feed") {
          const result = await work.parse(() => parseDocument("feed", artifact.body!, artifact.canonical_url),
            artifact.observation.event_id, describeFeedParse);
          failure = result.failure;
          count = result.parsed?.length ?? 0;
          state.work.feed({
            kind: "feed_outcome", source: sourceSnapshot(inputs.harvest, source), fetch_status: "success",
            parse_status: failure === null ? count > 0 ? "success" : "empty" : "failure",
            parsed_count: count, harvested_count: 0, fetch_duration_ms: null, parse_duration_ms: null,
            rejection_reason: failure === null ? null : "FEED_PARSE_FAILED", diagnostics: null, history: null,
          }, result.parsed ?? [], utcTimestamp(runtime.observation_clock), artifact);
        } else {
          const result = await work.parse(() => parseDocument("article", artifact.body!, artifact.canonical_url,
            inputs.harvest.extraction, source.form, parser), artifact.observation.event_id, describeArticleParse);
          failure = result.failure;
          if (result.parsed !== null && result.parsed.page_title && result.parsed.article_text && !result.parsed.quality?.rejected) {
            const candidateId = deriveCandidateId(state.context.run_id, source.id, 0);
            const candidate = FeedIngestCandidateSchema.parse({
              date: state.context.date, fetched_at: state.context.now, correlation_id: state.context.correlation_id,
              run_id: state.context.run_id, candidate_id: candidateId, entry_ordinal: 0,
              source_id: source.id, vertical: source.vertical, source: sourceSnapshot(inputs.harvest, source),
              canonical_url: artifact.canonical_url, url_key: artifact.article_id, title: result.parsed.page_title,
              categories: [], article_text: result.parsed.article_text, word_count: result.parsed.word_count,
              author: result.parsed.author, published_at: null,
            });
            candidates.push(candidate);
            Object.assign(observations, { [candidateId]: PlannerHarvestObservationSchema.parse({
              candidate_id: candidateId, http_status: artifact.http_status, robots: artifact.robots, fetch_failure: null,
              paywall: result.parsed.paywall, paywall_evidence: result.parsed.paywall_evidence,
              extraction: "success", observed_at: state.context.now, diagnostics: null,
            }) });
            count = 1;
          } else if (failure === null) failure = "ARTICLE_EXTRACTION_UNAVAILABLE";
        }
      } finally { parser.close(); }
      const seen = await readSeenEvidence({
        root: inputs.root, files: inputs.settings.inputs.seen_files, days: inputs.settings.inputs.seen_days,
        registration: inputs.registrations.discovered_articles, now: state.context.now,
        lookback_days: inputs.clock_config.collect.seen_window_days, concurrency: inputs.harvest.config.harvest.concurrency,
        own_rows: plannerMemory(inputs).discoveries(),
      });
      const sightings = candidates.map(candidate => DiscoveredArticleRowSchema.parse({
        url_key: candidate.url_key, first_seen_at: state.context.now, date: state.context.date,
      }));
      const saved = await rememberFirstSight(seen.rows, sightings, state.context, {
        outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.discovered_articles, ledgerSettings: inputs.ledgerSettings,
      });
      plannerMemory(inputs).rememberDiscoveries(saved.rows,
        requiredSeenDays(state.context.now, inputs.clock_config.collect.seen_window_days)[0]!);
      const batch = stageStore(inputs).write("parsed", ParsedFeedBatchSchema, {
        batch_id: randomUUID(), context: state.context, config_sha256: record.config_sha256, request: {},
        candidates, observations, evidence: {}, seen: { availability: "available", rows: saved.rows },
        history_rows: state.history.rows, history_days: state.history.days, work_rows: state.work.rows(), exclusions: state.work.exclusions(),
      });
      return { artifact: null, response_json: JSON.stringify({
        batch_id: batch.batch_id, fetch_request_id: request.fetch_request_id, kind: artifact.kind,
        parsed_count: count, failure, run_id: state.context.run_id,
      }) };
    });
    return completed.response_json!;
  } finally { store.close(); }
}

export async function readDocumentHealthBatch(batchId: string, inputs: PlanInputs, runtime: PlanRuntime) {
  const store = await openOperationStore(inputs.outputRoot);
  try {
    const record = store.get(batchId);
    if (record === null || record.operation !== "fetch" || record.state !== "complete") {
      throw new PlanError("ARTIFACT_NOT_FOUND", "No completed document work batch exists", "batch_id");
    }
    if (record.config_sha256 !== operationConfigFingerprint(inputs, runtime)) {
      throw new PlanError("REQUEST_CONFLICT", "Document work configuration differs", "batch_id");
    }
    const known = documents.get(inputs)?.has(record.run_id) === true;
    const state = await documentState(record, inputs, runtime);
    if (!known) state.work.unknownRequests(FetchedDocumentSchema.parse(record.artifact).source_id,
      utcTimestamp(runtime.observation_clock));
    return state;
  } finally { store.close(); }
}
