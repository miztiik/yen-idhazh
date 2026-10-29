/** Parse one saved response without network access and complete its server-owned article batch. */
import { randomUUID } from "node:crypto";
import {
  FEED_OUTCOME_PAYLOAD_VERSION, FeedIngestCandidateSchema, ParsedFeedBatchSchema, PlannerHarvestObservationSchema,
  deriveCandidateId,
} from "@idhazh/common-contracts";
import type { FeedIngestCandidate, PlannerOperation, PlannerHarvestObservation, PlannerFeedOffer } from "@idhazh/common-contracts";
import type { z } from "zod";
import { ParseRequestSchema } from "./operation-contracts";
import type { OperationStore } from "./operation-store";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { checkFetchedDocument, documentState } from "./document-state";
import { PlanError } from "./plan-request";
import { operationConfigFingerprint } from "./operation-context";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { documentWork, describeArticleParse, describeFeedParse } from "../harvest-feeds/document-work";
import { createIngestObservations } from "../ingest-observations";
import { ArticleParserPool } from "../harvest-feeds/article-parser-pool";
import { parseDocument } from "../harvest-feeds/parse-document";
import { fetchEvidence, recordRejection } from "../harvest-feeds/record-rejection";
import { resolveArticleTitle } from "../harvest-feeds/prepare-article";
import { stageStore } from "./stage-store";
import { createParsedFeedBatch, publicFeedOffers, updateFeedOffer } from "./feed-offers";
import { HarvestArticleResultSchema, utcTimestamp } from "../harvest-feeds/harvest-types";
import { readDiscoveredEvidence, rememberDiscoveries } from "../read-ledger-history/read-discovered-evidence";
import { requiredUtcDays } from "../utc-instant";
import { resolveArticleEvidence } from "../website-group";
import { DiscoveredArticleRowSchema } from "@idhazh/common-contracts";
import { plannerMemory } from "../planner-memory";
import { createStageLogger } from "../logging/structured-logger";
import { resolveArticleSourceOutcome } from "../article-source-outcome";
import { recordHarvestFailures } from "../record-harvest-failures";

export async function parseFetchedDocument(
  request: z.infer<typeof ParseRequestSchema>, record: PlannerOperation, fetched: PlannerOperation,
  inputs: PlanInputs, runtime: PlanRuntime, store: OperationStore, signal?: AbortSignal,
) {
  const artifact = checkFetchedDocument(fetched, inputs);
  if (fetched.config_sha256 !== record.config_sha256 || record.config_sha256 !== operationConfigFingerprint(inputs, runtime)) {
    throw new PlanError("REQUEST_CONFLICT", "Fetched configuration differs", "fetch_request_id");
  }
  if (artifact.article_id !== request.article_id || fetched.correlation_id !== request.correlation_id) {
    throw new PlanError("INVALID_REQUEST", "Parse identity differs from its fetched document", "article_id");
  }
  if (artifact.body === null || artifact.failure !== null) throw new PlanError("FETCH_UNAVAILABLE", "Fetch has no successful body", "fetch_request_id");
  const source = inputs.harvest.sources.find(source => source.id === artifact.feed_id);
  if (source === undefined) throw new PlanError("ARTIFACT_INVALID", "Fetched feed is no longer configured", "feed_id");
  const parent = artifact.parent_fetch_request_id === null ? undefined : store.get(artifact.parent_fetch_request_id);
  if (parent === null) throw new PlanError("ARTIFACT_NOT_FOUND", "Fetched offer has no parent response", "fetch_request_id");
  let offer: PlannerFeedOffer | undefined;
  if (artifact.parent_batch_id !== null) {
    const batch = stageStore(inputs).read("parsed", artifact.parent_batch_id, ParsedFeedBatchSchema);
    offer = batch.offers.find(offer => offer.entry.entry_ordinal === artifact.entry_ordinal);
    if (offer === undefined || offer.fetch_request_id !== fetched.request_id
      || batch.feed_fetch_request_id !== parent?.request_id) throw new PlanError("ARTIFACT_INVALID", "Fetched article does not match its current offer", "fetch_request_id");
  }
  const state = await documentState(fetched, inputs, runtime, store, parent);
  if (state.health_written) throw new PlanError("REQUEST_CONFLICT", "This execution finalized its health; parse in a new execution", "request_id");
  const emit = createStageLogger(state.context, runtime.log);
  const work = documentWork({
    document_activity: (operation, phase, details, url) => emit(operation, phase, details, ["feed_id", "publisher_id"], url),
    observations: createIngestObservations(state.work.observe), observation_clock: runtime.observation_clock ?? (() => new Date()),
  }, { run_id: fetched.run_id, correlation_id: fetched.correlation_id, article_id: artifact.article_id, feed_id: source.id },
  record.request_id, {
    document_kind: artifact.fetch_item_type, feed_id: source.id, publisher_id: source.publisher_id,
    observed_run_id: fetched.run_id, observed_attempt: state.context.writer.attempt, candidate_id: offer?.offer_id ?? null,
  });
  if (artifact.fetch_item_type === "feed") {
    const parsed = await work.parse(() => parseDocument("feed", artifact.body!, artifact.canonical_url),
      artifact.observation.event_id, describeFeedParse, artifact.canonical_url);
    const entries = parsed.parsed ?? [];
    state.work.feed({
      version: FEED_OUTCOME_PAYLOAD_VERSION, kind: "feed_outcome",
      source: sourceSnapshot(inputs.harvest, source), fetch_status: "success",
      parse_status: parsed.failure === null ? entries.length ? "success" : "empty" : "failure",
      parsed_count: entries.length, harvested_count: 0, fetch_duration_ms: null, parse_duration_ms: null,
      rejection_reason: parsed.failure === null ? entries.length ? null : "FEED_EMPTY" : "FEED_PARSE_FAILED",
      diagnostics: null, history: null,
    }, entries, parsed.observation.occurred_at, artifact);
    const batch = await createParsedFeedBatch({
      state, inputs, runtime, feed_id: source.id, entries, fetched_request_id: fetched.request_id, observed_at: parsed.observation.occurred_at,
    });
    return { artifact: null, response_json: JSON.stringify({
      batch_id: batch.batch_id, fetch_request_id: fetched.request_id, run_id: fetched.run_id, fetch_item_type: "feed",
      parsed_count: entries.length, failure: parsed.failure, offers: publicFeedOffers(batch),
    }) };
  }
  const pool = runtime.parser_pool ?? new ArticleParserPool(inputs.settings.listener.parser_concurrency);
  let parsed;
  try {
    parsed = await work.parse(() => parseDocument("article", artifact.body!, artifact.canonical_url, inputs.harvest.extraction, pool, {
      ...(signal === undefined ? {} : { signal }),
    }), artifact.observation.event_id, describeArticleParse, artifact.canonical_url);
  } finally { if (runtime.parser_pool === undefined) pool.close(); }
  const candidateId = offer?.offer_id ?? deriveCandidateId(state.context.run_id, source.id, 0);
  const observation = PlannerHarvestObservationSchema.parse({
    candidate_id: candidateId, http_status: artifact.http_status, robots: artifact.robots, fetch_failure: null,
    paywall: parsed.parsed?.paywall ?? null, paywall_evidence: parsed.parsed?.paywall_evidence ?? "not-observed",
    extraction: parsed.parsed === null ? "failed" : parsed.parsed.article_text ? "success" : "empty",
    observed_at: artifact.observation.occurred_at, diagnostics: null,
    ...(parsed.parsed?.content_evidence == null ? {} : { content_evidence: parsed.parsed.content_evidence }),
  });
  const title = resolveArticleTitle(offer?.entry.title ?? null, parsed.parsed?.page_title ?? null);
  let candidate: FeedIngestCandidate | null = null;
  const rejected = parsed.failure !== null || parsed.parsed?.quality?.rejected ? "EXTRACT_FAILED"
    : !parsed.parsed?.article_text ? "EXTRACT_EMPTY" : !title ? "MISSING_REQUIRED_FIELDS" : null;
  const rejection = rejected === null ? null : recordRejection({ feed_id: source.id, feed_url: source.url }, {
    writer: state.context.writer, correlation_id: state.context.correlation_id, max_future_hours: inputs.clock_config.collect.max_future_hours,
    observation_clock: runtime.observation_clock ?? (() => new Date()),
  }, rejected, fetchEvidence(artifact), {
    candidate_id: candidateId, canonical_url: artifact.canonical_url, url_key: artifact.article_id,
    title, categories: offer?.entry.categories ?? [],
  });
  if (rejection === null && parsed.parsed !== null) candidate = FeedIngestCandidateSchema.parse({
    date: artifact.observation.occurred_at.slice(0, 10), fetched_at: artifact.observation.occurred_at,
    correlation_id: state.context.correlation_id, run_id: state.context.run_id,
    candidate_id: candidateId, entry_ordinal: offer?.entry.entry_ordinal ?? 0, feed_id: source.id,
    source: sourceSnapshot(inputs.harvest, source), canonical_url: artifact.canonical_url, url_key: artifact.article_id,
    title, categories: offer?.entry.categories ?? [], article_text: parsed.parsed.article_text, word_count: parsed.parsed.word_count,
    author: parsed.parsed.author ?? offer?.entry.author ?? null, published_at: offer?.entry.published_at ?? null,
  });
  const result = HarvestArticleResultSchema.parse({ candidate, rejection, observation });
  const measuredOutcome = resolveArticleSourceOutcome(result, inputs.harvest.config.triage.min_words,
    inputs.harvest.config.triage.blocked_http_statuses, utcTimestamp(runtime.observation_clock));
  const sourceOutcome = fetched.source_outcome ?? (measuredOutcome === null ? null
    : store.settleSourceOutcome(fetched.request_id, measuredOutcome));
  state.work.article(result, fetched.request_id, sourceOutcome);
  if (rejection !== null) await recordHarvestFailures([rejection], state.context, inputs);
  let batch;
  if (offer !== undefined && artifact.parent_batch_id !== null) {
    batch = updateFeedOffer(inputs, state, artifact.parent_batch_id, offer.offer_id, candidate === null ? "rejected" : "parsed", fetched.request_id, result);
  } else {
    const discovered = await readDiscoveredEvidence({
      root: inputs.root, discovered_files: inputs.settings.inputs.discovered_files, discovered_days: inputs.settings.inputs.discovered_days,
      registration: inputs.registrations.discovered_articles, now: state.context.now,
      lookback_days: inputs.harvest.config.discovered_articles.lookback_days, concurrency: inputs.harvest.config.harvest.concurrency,
      own_rows: plannerMemory(inputs).discoveries(),
    });
    const instant = utcTimestamp(runtime.observation_clock);
    const saved = await rememberDiscoveries(discovered.rows, candidate === null ? [] : [DiscoveredArticleRowSchema.parse({
      url_key: candidate.url_key, first_seen_at: instant, date: instant.slice(0, 10),
    })], state.context, { outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.discovered_articles, ledgerSettings: inputs.ledgerSettings });
    plannerMemory(inputs).rememberDiscoveries(saved.rows, requiredUtcDays(
      state.context.now, inputs.harvest.config.discovered_articles.lookback_days,
    )[0]!);
    const observations: Record<string, PlannerHarvestObservation> = candidate === null ? {} : { [candidate.candidate_id]: observation };
    batch = stageStore(inputs).write("parsed", ParsedFeedBatchSchema, {
      batch_id: randomUUID(), context: state.context, config_sha256: record.config_sha256, request: {},
      candidates: candidate === null ? [] : [candidate], observations,
      evidence: candidate === null ? {} : { [candidate.candidate_id]: resolveArticleEvidence(
        candidate, undefined, inputs.harvest.config.curate_articles.website_grouping.include_private_suffixes,
      ) },
      discovered: { availability: "available", rows: saved.rows },
      history_rows: state.history.rows, history_days: state.history.days, work_rows: state.work.rows(), exclusions: state.work.exclusions(),
      article_fetch_request_id: fetched.request_id,
    });
  }
  return { artifact: null, response_json: JSON.stringify({
    batch_id: batch.batch_id, fetch_request_id: fetched.request_id, fetch_item_type: "article", run_id: fetched.run_id,
    parsed_count: candidate === null ? 0 : 1, failure: rejected,
    pending_offers: batch.offers.filter(offer => offer.state !== "parsed" && offer.state !== "rejected").length,
  }) };
}
