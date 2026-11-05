/** Fetch one configured feed or authorized server-owned article offer without parsing it. */
import { FetchedDocumentSchema } from "@idhazh/common-contracts";
import type { z } from "zod";
import { FetchRequestSchema } from "./operation-contracts";
import type { DocumentOperationContext } from "./operation-context";
import { hashText } from "../hash-text";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { PlanError } from "./plan-request";
import { requireStageConfiguration } from "./selection-operation";
import { documentExclusions, documentState } from "./document-state";
import { deriveArticleIdentity, InvalidArticleUrlError } from "../harvest-feeds/article-identity";
import { deriveFeedIdentity } from "../harvest-feeds/feed-identity";
import { validateTargetName, UnsafeTargetError } from "../harvest-feeds/safe-target";
import { documentWork } from "../harvest-feeds/document-work";
import type { observeDocument } from "../harvest-feeds/document-observation";
import { createIngestObservations } from "../ingest-observations";
import { prepareArticle } from "../harvest-feeds/prepare-article";
import { readFeedOffer, updateFeedOffer } from "./feed-offer-state";
import { workPool } from "../harvest-feeds/harvest-pool";
import { fetchRejection, recordRejection } from "../harvest-feeds/record-rejection";
import { fetchDiagnostics } from "../harvest-feeds/fetch-diagnostics";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { HarvestArticleResultSchema, utcTimestamp } from "../harvest-feeds/harvest-types";
import { resolveArticleSourceOutcome } from "../article-source-outcome";
import type { SourceArticleOutcome } from "@idhazh/common-contracts";
import { createStageLogger } from "../logging/structured-logger";
import { recordDocumentRejections } from "./record-document-rejections";
import { resolveFeedEligibility } from "../availability/feed-lifecycle";
import { projectLifecycleFields } from "../health-row";
import { stageStore } from "./stage-store";
import { operationKey, operationMetadata } from "./operation-context";

type FetchRequest = z.infer<typeof FetchRequestSchema>;
const requestPools = new WeakMap<PlanInputs, ReturnType<typeof workPool>>();
export function resolveFetchParent(request: FetchRequest, inputs: PlanInputs, runtime: PlanRuntime) {
  if (!("candidate_id" in request)) return null;
  const { batch, offer } = readFeedOffer(inputs, request.links[0], request.candidate_id);
  requireStageConfiguration(batch, inputs, runtime);
  if (offer === undefined) throw new PlanError("INVALID_REQUEST", "Article candidate is not a member of this feed parse", "candidate_id");
  const fetch = batch.links[0];
  if (fetch === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "Feed parse has no captured input fetch", "links");
  return { batch, offer, fetch };
}
export async function fetchDocument(
  request: FetchRequest, record: DocumentOperationContext, inputs: PlanInputs, runtime: PlanRuntime,
  parent: ReturnType<typeof resolveFetchParent>,
) {
  const feedId = parent?.offer.source.feed_id ?? ("feed_id" in request ? request.feed_id : undefined);
  const source = inputs.harvest.sources.find(source => source.id === feedId);
  if (source === undefined || source.status !== "active") throw new PlanError("INVALID_REQUEST", "Fetch requires an active configured feed", "feed_id");
  const url = request.fetch_item_type === "feed" ? source.url : parent?.offer.entry.link ?? ("url" in request ? request.url : undefined);
  if (url == null) throw new PlanError("INVALID_REQUEST", "Article fetch requires its authorized address", "url");
  const candidateId = record.candidate_id;
  if (request.fetch_item_type === "article" && candidateId === null) {
    throw new PlanError("ARTIFACT_INVALID", "Article admission lacks its captured candidate", "candidate_id");
  }
  if (parent === null) {
    try { validateTargetName(url); }
    catch (error) {
      if (!(error instanceof UnsafeTargetError)) throw error;
      throw new PlanError("INVALID_REQUEST", "Fetch requires a public HTTP address without credentials", "url");
    }
  }
  const state = await documentState(record, inputs, runtime);
  if (state.health_written) throw new PlanError("REQUEST_CONFLICT", "This execution finalized its health; start a new feed fetch for new work", "links");
  const key = operationKey(record.context);
  if (state.fetches.has(key)) throw new PlanError("REQUEST_CONFLICT", "Fetch operation already belongs to this live execution", "spanId");
  if (parent !== null && !state.fetches.has(operationKey(parent.fetch))) {
    throw new PlanError("ARTIFACT_NOT_FOUND", "Feed parse has no live captured work", "links");
  }
  state.fetches.add(key);
  let identity: ReturnType<typeof deriveArticleIdentity>;
  try {
    identity = request.fetch_item_type === "feed" ? deriveFeedIdentity(url)
      : deriveArticleIdentity(url);
  } catch (error) {
    if (!(error instanceof InvalidArticleUrlError || error instanceof UnsafeTargetError)) throw error;
    throw new PlanError("INVALID_REQUEST", "Normalized fetch address is invalid or unsafe", "url");
  }
  const attemptObservations: ReturnType<typeof observeDocument>[] = [];
  const emit = createStageLogger(record.context, inputs.event_source, runtime.log);
  const work = documentWork({
    ...operationMetadata(record.context),
    document_activity: (operation, phase, details, url, feedUrls, evidence, context) =>
      emit(operation, phase, details, ["feed_id", "publisher_id"], url, feedUrls, evidence, context),
    observations: createIngestObservations(state.work.observe), observation_clock: runtime.observation_clock ?? (() => new Date()),
    on_attempt: observation => { attemptObservations.push(observation); },
  }, { run_id: record.context.run_id, document_id: identity.url_key, feed_id: source.id, candidate_id: candidateId },
  operationMetadata(record.context), {
    document_kind: request.fetch_item_type, feed_id: source.id, publisher_id: source.publisher_id,
    observed_run_id: record.context.run_id, observed_attempt: state.context.writer.attempt, candidate_id: candidateId,
  });
  if (request.fetch_item_type === "feed") {
    const status = resolveFeedEligibility(projectLifecycleFields(state.history.sources.get(source.id)), utcTimestamp(runtime.observation_clock));
    if (status === "retired") throw new PlanError("FEED_RETIRED", "Supported evidence retires this feed", "feed_id");
    if (status === "resting") throw new PlanError("FEED_RESTING", "Feed is resting until its supported UTC recovery deadline", "feed_id");
  }
  if (request.fetch_item_type === "article" && candidateId !== null) {
    const exclusions = documentExclusions(state);
    const offered = parent?.offer ?? { candidate_id: candidateId, source: sourceSnapshot(source), entry: {
      entry_ordinal: null, title: null, link: url, categories: [], author: null, published_at: null, media_types: [],
    } };
    const prepared = prepareArticle(offered, inputs.harvest, {
      ...operationMetadata(record.context), writer: state.context.writer,
      max_future_hours: inputs.clock_config.collect.max_future_hours, clock: () => new Date(state.context.now),
      observation_clock: runtime.observation_clock ?? (() => new Date()),
      exclusions: { ...exclusions, published_window_days: inputs.clock_config.collect.published_window_days },
    });
    if (prepared.status === "rejected") {
      await work.skip();
      work.rejectFetch(url, "ARTICLE_EXCLUDED");
      state.work.article(prepared.result);
      if (prepared.result.rejection !== null) await recordDocumentRejections([prepared.result.rejection], state, inputs);
      if (parent !== null) updateFeedOffer(inputs, state, parent.batch, parent.offer.candidate_id, "rejected");
      throw new PlanError("ARTICLE_EXCLUDED", prepared.result.rejection!.drop_reason, parent === null ? "url" : "candidate_id");
    }
    if (parent !== null) updateFeedOffer(inputs, state, parent.batch, parent.offer.candidate_id, "fetched", record.context);
  }
  let permit = requestPools.get(inputs);
  if (permit === undefined) { permit = workPool(inputs.harvest.config.harvest.concurrency); requestPools.set(inputs, permit); }
  const bounded = permit;
  let result: Awaited<ReturnType<typeof work.fetch>>;
  try {
    result = await bounded(() => {
      runtime.signal?.throwIfAborted();
      return work.fetch(state.fetcher, identity.canonical_url, runtime.signal);
    });
  } catch (error) {
    if (request.fetch_item_type === "feed") {
      state.work.interruptFeed(source.id, record.context, utcTimestamp(runtime.observation_clock));
    }
    throw error;
  }
  const { fetched, observation } = result;
  const fetchedDocument = fetched;
  const artifact = FetchedDocumentSchema.parse({
    ...fetchedDocument, fetch_item_type: request.fetch_item_type, canonical_url: identity.canonical_url, document_id: identity.url_key, feed_id: source.id,
    error_code: fetched.error_code ?? null,
    body_sha256: fetched.body === null ? null : hashText(fetched.body), attempts: fetched.attempts ?? [],
    observation, attempt_observations: attemptObservations,
    candidate_id: candidateId,
    entry_ordinal: parent?.offer.entry.entry_ordinal ?? null,
  });
  stageStore(inputs).rememberFetchedDocument(record.context, artifact);
  stageStore(inputs).rememberDocumentWork(record.context, record.context.run_id, request.fetch_item_type);
  if (request.fetch_item_type === "feed") {
    state.work.pendingFeed(source.id, fetched, observation.occurred_at, record.context);
  }
  let sourceOutcome: SourceArticleOutcome | null = null;
  if (request.fetch_item_type === "article" && candidateId !== null && fetched.body === null) {
    const refusal = fetchRejection(fetched, inputs.harvest.config.harvest.fetch_timeout_ms, fetchDiagnostics(fetched, null));
    const rejection = recordRejection({ feed_id: source.id, feed_url: source.url }, {
      ...operationMetadata(record.context), writer: state.context.writer,
      max_future_hours: inputs.clock_config.collect.max_future_hours,
      observation_clock: runtime.observation_clock ?? (() => new Date()),
    }, refusal.reason, refusal.details, {
      candidate_id: candidateId,
      canonical_url: identity.canonical_url, url_key: identity.url_key,
      title: parent?.offer.entry.title ?? null, categories: parent?.offer.entry.categories ?? [],
    });
    const result = HarvestArticleResultSchema.parse({
      candidate: null, rejection, observation: {
        candidate_id: rejection.candidate_id, http_status: fetched.http_status,
        fetch_failure: fetched.failure, paywall: null, paywall_evidence: "not-observed",
        extraction: "not-attempted", observed_at: observation.occurred_at, diagnostics: refusal.details.diagnostics ?? null,
      },
    });
    sourceOutcome = resolveArticleSourceOutcome(result, inputs.harvest.config.triage.min_words,
      inputs.harvest.config.triage.blocked_http_statuses, utcTimestamp(runtime.observation_clock));
    state.work.article(result, candidateId, sourceOutcome);
    await recordDocumentRejections([rejection], state, inputs);
  }
  if (request.fetch_item_type === "article" && candidateId !== null) {
    state.work.captureArticle(candidateId, source.id, observation.occurred_at, sourceOutcome);
  }
  if (parent !== null) updateFeedOffer(inputs, state, parent.batch, parent.offer.candidate_id,
    fetched.failure === null && fetched.body !== null ? "fetched" : "rejected", record.context);
  return { artifact, response_json: JSON.stringify({
    ...operationMetadata(record.context),
    run_id: record.context.run_id, fetch_item_type: request.fetch_item_type, feed_id: source.id,
    canonical_url: identity.canonical_url, http_status: fetched.http_status,
    failure: fetched.failure, body_sha256: artifact.body_sha256,
    ...(request.fetch_item_type === "article"
      ? { article_id: identity.url_key, candidate_id: candidateId } : { document_id: identity.url_key }),
  }) };
}
