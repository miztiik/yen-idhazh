/** Consume one live fetched document without network access and complete its article batch. */
import {
  FEED_OUTCOME_PAYLOAD_VERSION, FeedIngestCandidateSchema, ParsedFeedBatchSchema, PlannerHarvestObservationSchema,
  HarvestDiagnosticsSchema,
} from "@idhazh/common-contracts";
import type { FeedIngestCandidate, PlannerHarvestObservation, PlannerFeedOffer, OperationLink, ParsedFeedBatch } from "@idhazh/common-contracts";
import type { FetchedDocumentReference } from "./stage-store";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { checkFetchedDocument, documentState } from "./document-state";
import { PlanError } from "./plan-request";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { documentWork, describeArticleParse, describeFeedParse } from "../harvest-feeds/document-work";
import { createIngestObservations } from "../ingest-observations";
import { ArticleParserPool } from "../harvest-feeds/article-parser-pool";
import { parseDocument } from "../harvest-feeds/parse-document";
import { fetchEvidence, recordRejection } from "../harvest-feeds/record-rejection";
import { fetchDiagnostics } from "../harvest-feeds/fetch-diagnostics";
import { resolveArticleTitle } from "../harvest-feeds/prepare-article";
import { stageStore } from "./stage-store";
import { createParsedFeedBatch, publicFeedOffers } from "./feed-offers";
import { readFeedOffer, updateFeedOffer } from "./feed-offer-state";
import { HarvestArticleResultSchema, utcTimestamp } from "../harvest-feeds/harvest-types";
import type { HarvestContext } from "../harvest-feeds/harvest-types";
import { foldDiscoveryHistory, rememberDiscoveries } from "../read-ledger-history/read-discovered-evidence";
import { requiredUtcDays } from "../utc-instant";
import { resolveArticleEvidence } from "../website-group";
import { DiscoveredArticleRowSchema } from "@idhazh/common-contracts";
import { plannerMemory } from "../planner-memory";
import { createStageLogger } from "../logging/structured-logger";
import { resolveArticleSourceOutcome } from "../article-source-outcome";
import { recordDocumentRejections } from "./record-document-rejections";
import { collectionForRun } from "./collection-operation";
import { recordArticleEntities } from "../record-article-entities";
import type { RunContext } from "../resolve-run-context";
import { operationKey, operationMetadata, stageContext } from "./operation-context";
import { retainCollectionParse } from "./collection-batch";
import { deriveArticleIdentity } from "../harvest-feeds/article-identity";
import { prepareArticleInput } from "./prepare-article-input";

export async function parseFetchedDocument(
  fetched: FetchedDocumentReference, context: RunContext,
  inputs: PlanInputs, runtime: PlanRuntime, signal?: AbortSignal,
) {
  const artifact = checkFetchedDocument(fetched, inputs);
  if (context.links.length !== 1 || operationKey(context.links[0]!) !== operationKey(fetched.context)) {
    throw new PlanError("INVALID_REQUEST", "Parse input differs from its fetched document", "links");
  }
  if (artifact.body === null || artifact.failure !== null) throw new PlanError("FETCH_UNAVAILABLE", "Fetch has no successful body", "links");
  const source = inputs.harvest.sources.find(source => source.id === artifact.feed_id);
  if (source === undefined) throw new PlanError("ARTIFACT_INVALID", "Fetched feed is no longer configured", "feed_id");
  const state = await documentState(fetched, inputs, runtime);
  if (!state.fetches.has(operationKey(fetched.context))) {
    throw new PlanError("ARTIFACT_NOT_FOUND", "Fetched document has no live captured work", "links");
  }
  let offer: PlannerFeedOffer | undefined;
  let feedParse: OperationLink | undefined;
  if (artifact.observation.links.length !== 0) {
    feedParse = artifact.observation.links[0];
    if (artifact.observation.links.length !== 1 || feedParse === undefined || artifact.entry_ordinal === null
      || artifact.candidate_id === null) {
      throw new PlanError("ARTIFACT_INVALID", "Fetched offer has no single producing feed parse or original ordinal", "links");
    }
    const reference = readFeedOffer(inputs, feedParse, artifact.candidate_id);
    const batch = reference.batch;
    offer = reference.offer;
    const feedFetch = batch.links[0];
    if (offer === undefined || offer.links.length !== 1 || operationKey(offer.links[0]!) !== operationKey(fetched.context)
      || offer.state !== "fetched" || offer.source.feed_id !== source.id || offer.entry.entry_ordinal !== artifact.entry_ordinal
      || batch.context.run_id !== context.run_id || batch.context.writer.attempt !== context.writer.attempt
      || feedFetch === undefined || !state.fetches.has(operationKey(feedFetch))) {
      throw new PlanError("ARTIFACT_INVALID", "Fetched article does not match its current offer and captured feed", "links");
    }
    const identity = offer.entry.link === null ? null : deriveArticleIdentity(offer.entry.link);
    if (identity?.canonical_url !== artifact.canonical_url || identity.url_key !== artifact.document_id) {
      throw new PlanError("ARTIFACT_INVALID", "Fetched article differs from its captured offer address", "links");
    }
  }
  if (state.health_written) throw new PlanError("REQUEST_CONFLICT", "This execution finalized its health; parse in a new execution", "links");
  const collection = collectionForRun(inputs, context.run_id);
  if (artifact.fetch_item_type === "feed" && collection !== undefined) {
    const feed = collection.feeds.get(source.id);
    if (feed === undefined || feed.state !== "fetching") {
      throw new PlanError("REQUEST_CONFLICT", "Feed is not awaiting parse in this collection", "links");
    }
    feed.state = "parsing";
  }
  const emit = createStageLogger(context, inputs.event_source, runtime.log);
  const document_activity: NonNullable<HarvestContext["document_activity"]> = (operation, phase, details, url, feedUrls, evidence, metadata) =>
    emit(operation, phase, details, ["feed_id", "publisher_id"], url, feedUrls, evidence, metadata);
  const work = documentWork({
    ...operationMetadata(context),
    document_activity,
    observations: createIngestObservations(state.work.observe), observation_clock: runtime.observation_clock ?? (() => new Date()),
  }, { run_id: fetched.context.run_id, document_id: artifact.document_id, feed_id: source.id, candidate_id: artifact.candidate_id },
  operationMetadata(fetched.context), {
    document_kind: artifact.fetch_item_type, feed_id: source.id, publisher_id: source.publisher_id,
    observed_run_id: fetched.context.run_id, observed_attempt: state.context.writer.attempt, candidate_id: artifact.candidate_id,
  }, artifact);
  if (artifact.fetch_item_type === "feed") {
    const parseSignal = signal ?? runtime.signal;
    const parseFeedDocument = () => work.parse(metadata => parseDocument("feed", artifact.body!, artifact.canonical_url, undefined,
      runtime.parser_pool, {
        context: metadata,
        timeout_ms: inputs.harvest.config.harvest.parse_timeout_ms,
        ...(parseSignal === undefined ? {} : { signal: parseSignal }),
      }), operationMetadata(context), describeFeedParse, artifact.canonical_url);
    let parsed: Awaited<ReturnType<typeof parseFeedDocument>>;
    try {
      parsed = await parseFeedDocument();
    } catch (error) {
      state.work.interruptFeed(source.id, fetched.context, utcTimestamp(runtime.observation_clock));
      throw error;
    }
    const entries = parsed.parsed ?? [];
    state.work.feed({
      version: FEED_OUTCOME_PAYLOAD_VERSION, kind: "feed_outcome",
      source: sourceSnapshot(source), fetch_status: "success",
      parse_status: parsed.failure === null ? entries.length ? "success" : "empty" : "failure",
      parsed_count: entries.length, harvested_count: 0, fetch_duration_ms: null, parse_duration_ms: null,
      rejection_reason: parsed.failure === null ? entries.length ? null : "FEED_EMPTY" : "FEED_PARSE_FAILED",
      diagnostics: parsed.failure === null ? null : HarvestDiagnosticsSchema.parse({
        ...fetchEvidence(artifact), stopped_stage: "parse", detail: parsed.failure, failure_code: "unknown",
      }), history: null,
    }, entries, parsed.observation.occurred_at, artifact, fetched.context);
    const batch = await createParsedFeedBatch({
      state, inputs, runtime, feed_id: source.id, entries, context, observed_at: parsed.observation.occurred_at,
    });
    return { response_json: JSON.stringify({
      ...operationMetadata(batch), run_id: fetched.context.run_id, fetch_item_type: "feed",
      feed_id: source.id, document_id: artifact.document_id,
      parsed_count: entries.length, failure: parsed.failure,
      offers: publicFeedOffers(batch, source.id, state.plan_owned === true),
    }) };
  }
  const pool = runtime.parser_pool ?? new ArticleParserPool(inputs.settings.listener.parser_concurrency);
  const candidateId = artifact.candidate_id;
  if (candidateId === null) throw new PlanError("ARTIFACT_INVALID", "Article document lacks its captured candidate", "candidate_id");
  const recordEntities = (title: string | null, article_text: string | null) =>
    recordArticleEntities(inputs, context, {
      article_id: artifact.document_id, candidate_id: candidateId, feed_id: source.id,
      title, article_text, observed_at: utcTimestamp(runtime.observation_clock),
    });
  let parsed;
  const parseStarted = performance.now();
  try {
    parsed = await work.parse(metadata => parseDocument("article", artifact.body!, artifact.canonical_url, inputs.harvest.extraction, pool, {
      context: metadata,
      timeout_ms: inputs.harvest.config.harvest.parse_timeout_ms,
      ...(signal === undefined ? {} : { signal }),
    }), operationMetadata(context), describeArticleParse, artifact.canonical_url);
  } catch (error) {
    await recordEntities(offer?.entry.title ?? null, null);
    throw error;
  } finally { if (runtime.parser_pool === undefined) pool.close(); }
  const extractionMs = Math.round(performance.now() - parseStarted);
  const prepared = parsed.parsed === null ? null
    : prepareArticleInput(parsed.parsed, inputs.harvest.config.harvest.max_input_words);
  const title = resolveArticleTitle(offer?.entry.title ?? null, parsed.parsed?.page_title ?? null);
  await recordEntities(title, prepared?.article_text ?? null);
  const extractionFailure = parsed.failure === "malformed-feed" ? null : parsed.failure
    ?? (parsed.parsed?.article_text ? title ? null : "missing-title" : "empty-content");
  const qualityFailure = parsed.parsed?.quality?.failure_code ?? null;
  const diagnostics = HarvestDiagnosticsSchema.parse({
    ...fetchDiagnostics(artifact, null), extract_ms: extractionMs,
    extraction_failure: extractionFailure,
    stopped_stage: extractionFailure !== null || parsed.parsed?.quality?.rejected ? "extract" : null,
    detail: parsed.failure ?? extractionFailure ?? (parsed.parsed?.quality?.rejected ? qualityFailure : null),
    failure_code: parsed.failure !== null ? "unknown" : extractionFailure === "empty-content" ? "no_text"
      : extractionFailure === "missing-title" ? "no_title" : qualityFailure,
    warnings: parsed.parsed?.warnings ?? [], quality: parsed.parsed?.quality ?? null,
  });
  const observation = PlannerHarvestObservationSchema.parse({
    candidate_id: candidateId, http_status: artifact.http_status, fetch_failure: null,
    paywall: parsed.parsed?.paywall ?? null, paywall_evidence: parsed.parsed?.paywall_evidence ?? "not-observed",
    extraction: parsed.parsed === null ? "failed" : parsed.parsed.article_text ? "success" : "empty",
    observed_at: artifact.observation.occurred_at, diagnostics,
    ...(parsed.parsed?.content_evidence == null ? {} : { content_evidence: parsed.parsed.content_evidence }),
  });
  let candidate: FeedIngestCandidate | null = null;
  const rejected = parsed.failure !== null || parsed.parsed?.quality?.rejected ? "EXTRACT_FAILED"
    : !parsed.parsed?.article_text ? "EXTRACT_EMPTY" : !title ? "MISSING_REQUIRED_FIELDS" : null;
  const rejection = rejected === null ? null : recordRejection({ feed_id: source.id, feed_url: source.url }, {
    ...operationMetadata(context), writer: state.context.writer, document_activity, max_future_hours: inputs.clock_config.collect.max_future_hours,
    observation_clock: runtime.observation_clock ?? (() => new Date()),
  }, rejected, { ...fetchEvidence(artifact), diagnostics }, {
    candidate_id: candidateId, canonical_url: artifact.canonical_url, url_key: artifact.document_id,
    title, categories: offer?.entry.categories ?? [],
  });
  if (rejection === null && parsed.parsed !== null && prepared !== null) candidate = FeedIngestCandidateSchema.parse({
    date: artifact.observation.occurred_at.slice(0, 10), fetched_at: artifact.observation.occurred_at,
    traceId: context.traceId, run_id: state.context.run_id,
    candidate_id: candidateId, entry_ordinal: artifact.entry_ordinal, feed_id: source.id,
    source: sourceSnapshot(source), canonical_url: artifact.canonical_url, url_key: artifact.document_id,
    title, categories: offer?.entry.categories ?? [], article_text: prepared.article_text, word_count: prepared.word_count,
    author: parsed.parsed.author ?? offer?.entry.author ?? null, published_at: offer?.entry.published_at ?? null,
  });
  const result = HarvestArticleResultSchema.parse({ candidate, rejection, observation });
  const measuredOutcome = resolveArticleSourceOutcome(result, inputs.harvest.config.triage.min_words,
    inputs.harvest.config.triage.blocked_http_statuses, utcTimestamp(runtime.observation_clock));
  state.work.article(result, candidateId, measuredOutcome);
  if (rejection !== null) {
    await recordDocumentRejections([rejection], state, inputs);
  }
  let pendingOffers = 0;
  let aggregate: Partial<ParsedFeedBatch> = {};
  if (offer !== undefined && feedParse !== undefined) {
    pendingOffers = updateFeedOffer(inputs, state, feedParse, offer.candidate_id,
      candidate === null ? "rejected" : "parsed", fetched.context, result).pending_offers;
    if (collection === undefined) aggregate = stageStore(inputs).read("parsed", feedParse, ParsedFeedBatchSchema);
  } else {
    const instant = utcTimestamp(runtime.observation_clock);
    state.discovered_rows = foldDiscoveryHistory([...state.discovered_rows, ...candidate === null ? [] : [
      DiscoveredArticleRowSchema.parse({
      url_key: candidate.url_key, first_seen_at: instant, date: instant.slice(0, 10),
      }),
    ]]);
    const saved = await rememberDiscoveries(state.baseline.discovered.rows, state.discovered_rows,
      state.context, { outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.discovered_articles, ledgerSettings: inputs.ledgerSettings });
    plannerMemory(inputs).rememberDiscoveries(saved.rows, requiredUtcDays(
      state.context.now, inputs.harvest.config.discovered_articles.lookback_days,
    )[0]!);
    if (collection !== undefined && candidate !== null) collection.results.set(candidateId, result);
    aggregate = { discovered: { availability: "available" as const, rows: saved.rows } };
  }
  const observations: Record<string, PlannerHarvestObservation> = candidate === null ? {} : { [candidate.candidate_id]: observation };
  const batch = collection === undefined ? stageStore(inputs).write("parsed", ParsedFeedBatchSchema, {
    candidates: candidate === null ? [] : [candidate], observations,
    evidence: candidate === null ? {} : { [candidate.candidate_id]: resolveArticleEvidence(
      candidate, undefined, inputs.harvest.config.curate_articles.website_grouping.include_private_suffixes,
    ) },
    discovered: { availability: "available", rows: [] },
    history_rows: [], history_days: state.history.days, work_rows: state.work.rows(), exclusions: state.work.exclusions(),
    ...aggregate, ...operationMetadata(context), context: stageContext(context),
    config_sha256: fetched.config_sha256, request: {},
    input_complete: collection === undefined && pendingOffers === 0,
  }) : retainCollectionParse(inputs, collection, context, {
    kind: "article", candidate: result.candidate, observation: result.observation,
    ...(aggregate.discovered === undefined ? {} : { discovered: aggregate.discovered }),
  });
  return { response_json: JSON.stringify({
    ...operationMetadata(batch), fetch_item_type: "article", run_id: fetched.context.run_id,
    article_id: artifact.document_id, candidate_id: candidateId,
    parsed_count: candidate === null ? 0 : 1, failure: rejected,
    warnings: diagnostics.warnings,
    word_limit: prepared?.word_limit ?? null,
    pending_offers: pendingOffers,
  }) };
}
