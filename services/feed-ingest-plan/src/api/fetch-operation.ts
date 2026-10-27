/** Fetch one configured feed or authorized server-owned article offer without parsing it. */
import { FetchedDocumentSchema, ParsedFeedBatchSchema } from "@idhazh/common-contracts";
import type { PlannerOperation } from "@idhazh/common-contracts";
import type { z } from "zod";
import { FetchRequestSchema } from "./operation-contracts";
import type { OperationStore } from "./operation-store";
import { sha256 } from "./operation-store";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { PlanError } from "./plan-request";
import { stageStore } from "./stage-store";
import { requireStageConfiguration } from "./selection-operation";
import { checkFetchedDocument, documentExclusions, documentState } from "./document-state";
import { canonicalizeUrl } from "../harvest-feeds/url-cleaner";
import { validateTargetName } from "../harvest-feeds/safe-target";
import { documentWork } from "../harvest-feeds/document-work";
import type { observeDocument } from "../harvest-feeds/document-observation";
import { createIngestObservations } from "../ingest-observations";
import { prepareArticle } from "../harvest-feeds/prepare-article";
import { updateFeedOffer } from "./feed-offers";
import { workPool } from "../harvest-feeds/harvest-pool";
import { profileTask } from "../../../host-probes/src/task-profile/task-profiler";
import { fetchRejection, recordRejection } from "../harvest-feeds/record-rejection";
import { deriveCandidateId } from "@idhazh/common-contracts";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";

type FetchRequest = z.infer<typeof FetchRequestSchema>;
const requestPools = new WeakMap<PlanInputs, ReturnType<typeof workPool>>();
export function resolveFetchParent(request: FetchRequest, inputs: PlanInputs, runtime: PlanRuntime, store: OperationStore) {
  if (request.batch_id === undefined || request.offer_id === undefined) return null;
  const batch = stageStore(inputs).read("parsed", request.batch_id, ParsedFeedBatchSchema);
  requireStageConfiguration(batch, inputs, runtime);
  const offer = batch.offers.find(offer => offer.offer_id === request.offer_id);
  if (offer === undefined || offer.source.source_id !== request.feed_id || request.correlation_id !== batch.context.correlation_id
    || batch.feed_fetch_request_id === null) throw new PlanError("INVALID_REQUEST", "Article reference does not belong to this feed batch", "offer_id");
  const root = store.get(batch.feed_fetch_request_id);
  if (root === null || checkFetchedDocument(root, inputs).fetch_item_type !== "feed") throw new PlanError("ARTIFACT_NOT_FOUND", "Feed batch has no completed fetched input", "batch_id");
  return { batch, offer, root };
}
export async function fetchDocument(
  request: FetchRequest, record: PlannerOperation, inputs: PlanInputs, runtime: PlanRuntime,
  parent: ReturnType<typeof resolveFetchParent>, signal?: AbortSignal,
) {
  const source = inputs.harvest.sources.find(source => source.id === request.feed_id);
  if (source === undefined || source.status !== "active") throw new PlanError("INVALID_REQUEST", "Fetch requires an active configured feed", "feed_id");
  const url = request.fetch_item_type === "feed" ? source.url : parent?.offer.entry.link ?? request.url;
  if (url == null) throw new PlanError("INVALID_REQUEST", "Article fetch requires its authorized address", "url");
  if (parent === null) {
    try { validateTargetName(url); }
    catch { throw new PlanError("INVALID_REQUEST", "Fetch requires a public HTTP address without credentials", "url"); }
  }
  const state = await documentState(record, inputs, runtime, parent?.root);
  if (state.health_written) throw new PlanError("REQUEST_CONFLICT", "This execution finalized its health; start a new feed fetch for new work", "request_id");
  const identity = canonicalizeUrl(url);
  const attemptObservations: ReturnType<typeof observeDocument>[] = [];
  const work = documentWork({
    observations: createIngestObservations(state.work.observe), observation_clock: runtime.observation_clock ?? (() => new Date()),
    on_attempt: observation => { attemptObservations.push(observation); },
  }, { run_id: record.run_id, correlation_id: record.correlation_id, article_id: identity.url_key, source_id: source.id },
  record.request_id, {
    document_kind: request.fetch_item_type, source_id: source.id, publisher_id: source.publisher_id,
    observed_run_id: record.run_id, observed_attempt: inputs.settings.run.attempt, candidate_id: parent?.offer.offer_id ?? null,
  });
  if (request.fetch_item_type === "article") {
    const exclusions = await documentExclusions(state, inputs);
    const offered = parent?.offer ?? { source: sourceSnapshot(inputs.harvest, source), entry: {
      entry_ordinal: 0, title: null, link: url, categories: [], author: null, published_at: null, media_types: [],
    } };
    const prepared = prepareArticle(offered, inputs.harvest, {
      writer: state.context.writer, correlation_id: state.context.correlation_id,
      max_future_hours: inputs.clock_config.collect.max_future_hours, clock: () => new Date(state.context.now),
      observation_clock: runtime.observation_clock ?? (() => new Date()),
      exclusions: { ...exclusions, published_window_days: inputs.clock_config.collect.published_window_days },
    });
    if (prepared.status === "rejected") {
      await work.skip();
      state.work.article(prepared.result);
      if (parent !== null) updateFeedOffer(inputs, state, parent.batch.batch_id, parent.offer.offer_id, "rejected");
      throw new PlanError("ARTICLE_EXCLUDED", prepared.result.rejection!.drop_reason, parent === null ? "url" : "offer_id");
    }
    if (parent !== null) updateFeedOffer(inputs, state, parent.batch.batch_id, parent.offer.offer_id, "fetched", record.request_id);
  }
  let permit = requestPools.get(inputs);
  if (permit === undefined) { permit = workPool(inputs.harvest.config.harvest.concurrency); requestPools.set(inputs, permit); }
  const bounded = permit;
  const result = await profileTask(runtime.task_profiling, {
    pipeline_name: "feed-ingest-plan", task_name: "fetch", run_id: record.run_id,
    correlation_id: record.correlation_id, request_id: record.request_id,
  }, () => bounded(() => work.fetch(state.fetcher, url, request.caused_by_event_id ?? null)),
  { ...(signal === undefined ? {} : { signal }), outcome: result => result.fetched.failure === null ? "success" : "error" });
  const { fetched, observation } = result;
  state.recovered.add(record.request_id);
  if (request.fetch_item_type === "feed") state.work.pendingFeed(source.id, fetched, observation.occurred_at);
  if (request.fetch_item_type === "article" && fetched.body === null) {
    const refusal = fetchRejection(fetched, inputs.harvest.config.harvest.fetch_timeout_ms, null);
    state.work.reject(recordRejection({ source_id: source.id, feed_url: source.url }, {
      writer: state.context.writer, correlation_id: state.context.correlation_id,
      max_future_hours: inputs.clock_config.collect.max_future_hours,
      observation_clock: runtime.observation_clock ?? (() => new Date()),
    }, refusal.reason, refusal.details, {
      candidate_id: parent?.offer.offer_id ?? deriveCandidateId(record.run_id, source.id, 0),
      canonical_url: identity.canonical_url, url_key: identity.url_key,
      title: parent?.offer.entry.title ?? null, categories: parent?.offer.entry.categories ?? [],
    }));
  }
  if (parent !== null) updateFeedOffer(inputs, state, parent.batch.batch_id, parent.offer.offer_id,
    fetched.failure === null && fetched.body !== null ? "fetched" : "rejected", record.request_id);
  const artifact = FetchedDocumentSchema.parse({
    ...fetched, fetch_item_type: request.fetch_item_type, canonical_url: identity.canonical_url, article_id: identity.url_key, source_id: source.id,
    error_code: fetched.error_code ?? null, robots_failure: fetched.robots_failure ?? null, robots_http_status: fetched.robots_http_status ?? null,
    body_sha256: fetched.body === null ? null : sha256(fetched.body), attempts: fetched.attempts ?? [],
    observation, attempt_observations: attemptObservations,
    parent_fetch_request_id: parent?.root.request_id ?? null, parent_batch_id: parent?.batch.batch_id ?? null,
    entry_ordinal: parent?.offer.entry.entry_ordinal ?? null,
  });
  return { artifact, response_json: JSON.stringify({
    fetch_request_id: record.request_id, batch_id: parent?.batch.batch_id ?? record.request_id,
    run_id: record.run_id, correlation_id: record.correlation_id, fetch_item_type: request.fetch_item_type, feed_id: source.id,
    article_id: identity.url_key, canonical_url: identity.canonical_url, http_status: fetched.http_status,
    failure: fetched.failure, body_sha256: artifact.body_sha256,
  }) };
}
