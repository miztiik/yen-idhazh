/** Retain the complete current feed offer batch without exporting or archiving article bodies. */
import { randomUUID } from "node:crypto";
import { DiscoveredArticleRowSchema, ParsedFeedBatchSchema, PlannerFeedEntrySchema, deriveCandidateId } from "@idhazh/common-contracts";
import type { ParsedFeedBatch, PlannerFeedOffer } from "@idhazh/common-contracts";
import type { FeedEntry, HarvestArticleResult } from "../harvest-feeds/harvest-types";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import type { DocumentState } from "./document-state";
import { documentIdentities } from "./document-state";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { deriveArticleIdentity, InvalidArticleUrlError } from "../harvest-feeds/article-identity";
import { UnsafeTargetError } from "../harvest-feeds/safe-target";
import type { ArticleUrlPolicy } from "../harvest-feeds/article-url";
import { matchUrlExclusion } from "../harvest-feeds/url-exclusions";
import { prepareArticle } from "../harvest-feeds/prepare-article";
import { readDiscoveredEvidence, rememberDiscoveries } from "../read-ledger-history/read-discovered-evidence";
import { requiredUtcDays } from "../utc-instant";
import { resolveArticleEvidence } from "../website-group";
import { plannerMemory } from "../planner-memory";
import { stageStore } from "./stage-store";
import { operationConfigFingerprint } from "./operation-context";

export async function createParsedFeedBatch(input: {
  state: DocumentState; inputs: PlanInputs; runtime: PlanRuntime;
  feed_id: string; entries: readonly FeedEntry[]; fetched_request_id: string; observed_at: string;
}) {
  const { state, inputs, runtime } = input;
  const configured = inputs.harvest.sources.find(source => source.id === input.feed_id);
  if (configured === undefined) throw new Error("Parsed feed is not configured");
  const source = sourceSnapshot(inputs.harvest, configured);
  const offers: PlannerFeedOffer[] = [];
  for (const entry of input.entries) {
    let valid = false;
    if (entry.link !== null) {
      try { deriveArticleIdentity(entry.link, inputs.harvest.config.harvest); valid = true; }
      catch (error) {
        if (!(error instanceof InvalidArticleUrlError || error instanceof UnsafeTargetError)) throw error;
      }
    }
    if (!valid) {
      const prepared = prepareArticle({ source, entry }, inputs.harvest, {
        writer: state.context.writer, correlation_id: state.context.correlation_id, max_future_hours: inputs.clock_config.collect.max_future_hours,
        clock: () => new Date(state.context.now), observation_clock: runtime.observation_clock ?? (() => new Date()),
      });
      if (prepared.status !== "rejected") throw new Error("Invalid feed offer passed article preparation");
      state.work.article(prepared.result);
      continue;
    }
    offers.push({ offer_id: deriveCandidateId(state.context.run_id, source.feed_id, entry.entry_ordinal),
      source, entry: PlannerFeedEntrySchema.parse(entry), state: "pending", fetch_request_id: null });
  }
  const discovered = await readDiscoveredEvidence({
    root: inputs.root, discovered_files: inputs.settings.inputs.discovered_files, discovered_days: inputs.settings.inputs.discovered_days,
    registration: inputs.registrations.discovered_articles, now: state.context.now,
    lookback_days: inputs.harvest.config.discovered_articles.lookback_days, concurrency: inputs.harvest.config.harvest.concurrency,
    own_rows: plannerMemory(inputs).discoveries(),
  });
  const identities = await documentIdentities(state, inputs);
  const sightings = offers.flatMap(offer => {
    const identity = identities.remember(offer.entry.link!);
    if (matchUrlExclusion(identity.canonical_url, inputs.harvest.config.harvest.url_exclusions) !== undefined) return [];
    return [DiscoveredArticleRowSchema.parse({
      url_key: identity.url_key, first_seen_at: input.observed_at, date: input.observed_at.slice(0, 10),
    })];
  });
  const saved = await rememberDiscoveries(discovered.rows, identities.discoveries([...discovered.rows, ...sightings]), state.context, {
    outputRoot: inputs.outputRoot, registryEntry: inputs.registrations.discovered_articles, ledgerSettings: inputs.ledgerSettings,
  });
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
export function updateFeedOffer(
  inputs: PlanInputs, state: DocumentState, batchId: string, offerId: string, status: PlannerFeedOffer["state"],
  fetchRequestId?: string, result?: HarvestArticleResult,
) {
  return stageStore(inputs).update("parsed", batchId, ParsedFeedBatchSchema, current => {
    const offers = current.offers.map(offer => offer.offer_id === offerId ? {
      ...offer, state: status, fetch_request_id: fetchRequestId ?? offer.fetch_request_id,
    } : offer);
    const retained = current.candidates.filter(candidate => candidate.candidate_id !== offerId);
    const candidates = result?.candidate ? [...retained, result.candidate] : status === "fetched" || status === "rejected" ? retained : current.candidates;
    const observations = Object.fromEntries(Object.entries(current.observations).filter(([id]) => id !== offerId));
    const evidence = { ...current.evidence };
    if (result?.candidate) evidence[offerId] = resolveArticleEvidence(
      result.candidate, evidence[offerId], inputs.harvest.config.curate_articles.website_grouping.include_private_suffixes,
    );
    else if (status === "fetched" || status === "rejected") delete evidence[offerId];
    if (result?.candidate) observations[offerId] = result.observation;
    return {
      ...current, offers, candidates: candidates.sort((a, b) => a.entry_ordinal - b.entry_ordinal), observations, evidence,
      input_complete: offers.every(offer => offer.state === "parsed" || offer.state === "rejected"),
      work_rows: state.work.rows(), exclusions: state.work.exclusions(),
    };
  });
}
export function publicFeedOffers(batch: ParsedFeedBatch, policy: ArticleUrlPolicy) {
  return batch.offers.map(offer => ({
    offer_id: offer.offer_id, feed_id: offer.source.feed_id, canonical_url: deriveArticleIdentity(offer.entry.link!, policy).canonical_url,
    title: offer.entry.title, categories: offer.entry.categories, published_at: offer.entry.published_at,
  }));
}
