/** Retain the complete current feed offer batch without exporting or archiving article bodies. */
import { randomUUID } from "node:crypto";
import { DiscoveredArticleRowSchema, ParsedFeedBatchSchema, PlannerFeedOfferSchema } from "@idhazh/common-contracts";
import type { ParsedFeedBatch, PlannerFeedOffer } from "@idhazh/common-contracts";
import type { FeedEntry } from "../harvest-feeds/harvest-types";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import type { DocumentState } from "./document-state";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { deriveArticleIdentity } from "../harvest-feeds/article-identity";
import type { ArticleUrlPolicy } from "../harvest-feeds/article-url";
import { matchUrlExclusion } from "../harvest-feeds/url-exclusions";
import { prepareArticle } from "../harvest-feeds/prepare-article";
import { foldDiscoveryHistory, readDiscoveredEvidence, rememberDiscoveries } from "../read-ledger-history/read-discovered-evidence";
import { requiredUtcDays } from "../utc-instant";
import { plannerMemory } from "../planner-memory";
import { stageStore } from "./stage-store";
import { operationConfigFingerprint } from "./operation-context";
import { collectionForRun } from "./collection-operation";
import { recordDocumentRejections } from "./record-document-rejections";
import { createStageLogger } from "../logging/structured-logger";
import { documentExclusions } from "./document-state";
import { PlanError } from "./plan-request";

export async function createParsedFeedBatch(input: {
  state: DocumentState; inputs: PlanInputs; runtime: PlanRuntime;
  feed_id: string; entries: readonly FeedEntry[]; fetched_request_id: string; observed_at: string;
}) {
  const { state, inputs, runtime } = input;
  const configured = inputs.harvest.sources.find(source => source.id === input.feed_id);
  if (configured === undefined) throw new Error("Parsed feed is not configured");
  const source = sourceSnapshot(inputs.harvest, configured);
  const collection = collectionForRun(inputs, state.context.run_id);
  const offers: PlannerFeedOffer[] = [];
  const rejections = [];
  const exclusions = collection === undefined ? undefined : await documentExclusions(state, inputs);
  for (const entry of input.entries) {
    const prepared = prepareArticle({ source, entry }, inputs.harvest, {
      writer: state.context.writer, correlation_id: state.context.correlation_id, max_future_hours: inputs.clock_config.collect.max_future_hours,
      clock: () => new Date(state.context.now), observation_clock: runtime.observation_clock ?? (() => new Date()),
      ...(exclusions === undefined ? {} : {
        exclusions: { ...exclusions, published_window_days: inputs.clock_config.collect.published_window_days },
      }),
    });
    if (prepared.status === "rejected" && (collection !== undefined || prepared.identity === null)) {
      state.work.article(prepared.result);
      if (prepared.result.rejection !== null) rejections.push(prepared.result.rejection);
      if (prepared.identity === null) continue;
    }
    offers.push(PlannerFeedOfferSchema.parse({ offer_id: prepared.candidate_id,
      source, entry, state: collection !== undefined && prepared.status === "rejected" ? "rejected" : "pending",
      fetch_request_id: null }));
  }
  if (rejections.length) await recordDocumentRejections(rejections, state, inputs);
  const readDiscovery = () => readDiscoveredEvidence({
    root: inputs.root, discovered_files: inputs.settings.inputs.discovered_files, discovered_days: inputs.settings.inputs.discovered_days,
    registration: inputs.registrations.discovered_articles, now: state.context.now,
    lookback_days: inputs.harvest.config.discovered_articles.lookback_days, concurrency: inputs.harvest.config.harvest.concurrency,
    own_rows: plannerMemory(inputs).discoveries(), log: createStageLogger(state.context, runtime.log),
  });
  const fromDay = requiredUtcDays(state.context.now, inputs.harvest.config.discovered_articles.lookback_days)[0]!;
  const discoveredRows = collection === undefined ? (await readDiscovery()).rows
    : await (collection.discovery_baseline ??= readDiscovery().then(value => {
      plannerMemory(inputs).rememberDiscoveries(value.rows, fromDay);
      return value.rows;
    }));
  const sightings = offers.flatMap(offer => {
    const identity = deriveArticleIdentity(offer.entry.link!, inputs.harvest.config.harvest);
    if (matchUrlExclusion(identity.canonical_url, inputs.harvest.config.harvest.url_exclusions) !== undefined) return [];
    return [DiscoveredArticleRowSchema.parse({
      url_key: identity.url_key, first_seen_at: input.observed_at, date: input.observed_at.slice(0, 10),
    })];
  });
  if (collection !== undefined) {
    collection.feed_requests.set(input.feed_id, input.fetched_request_id);
    plannerMemory(inputs).rememberDiscoveries(sightings, fromDay);
    for (const offer of offers) {
      if (collection.offers.has(offer.offer_id)) throw new PlanError("ARTIFACT_INVALID", "Collection offer identity already exists", "offer_id");
      collection.offers.set(offer.offer_id, offer);
      if (offer.state === "pending") collection.pending_offers++;
    }
    return { batch_id: collection.parsed_batch_id, offers };
  }
  const saved = await rememberDiscoveries(discoveredRows, foldDiscoveryHistory([...discoveredRows, ...sightings]), state.context, {
    outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.discovered_articles, ledgerSettings: inputs.ledgerSettings,
  });
  if (state.plan_owned) {
    state.completed_files ??= {};
    (state.completed_files.discovered_articles ??= []).push(saved.result);
  }
  plannerMemory(inputs).rememberDiscoveries(saved.rows, requiredUtcDays(
    state.context.now, inputs.harvest.config.discovered_articles.lookback_days,
  )[0]!);
  return stageStore(inputs).write("parsed", ParsedFeedBatchSchema, {
    batch_id: randomUUID(), context: state.context, config_sha256: operationConfigFingerprint(inputs, runtime), request: {},
    candidates: [], observations: {}, evidence: {}, discovered: { availability: "available", rows: saved.rows },
    history_rows: [], history_days: state.history.days, work_rows: state.work.rows(), exclusions: state.work.exclusions(),
    offers, feed_fetch_request_id: input.fetched_request_id, input_complete: offers.length === 0,
  });
}
export function publicFeedOffers(batch: Pick<ParsedFeedBatch, "offers">, policy: ArticleUrlPolicy, feedId: string,
  pendingOnly = false) {
  return batch.offers.filter(offer => offer.source.feed_id === feedId && (!pendingOnly || offer.state === "pending")).map(offer => ({
    offer_id: offer.offer_id, feed_id: offer.source.feed_id, canonical_url: deriveArticleIdentity(offer.entry.link!, policy).canonical_url,
    title: offer.entry.title, categories: offer.entry.categories, published_at: offer.entry.published_at,
  }));
}
