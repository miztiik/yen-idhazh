/** Read or settle one article offer without copying its owning collection. */
import { ParsedFeedBatchSchema, PlannerFeedOfferSchema } from "@idhazh/common-contracts";
import type { OperationLink, PlannerFeedOffer } from "@idhazh/common-contracts";
import type { HarvestArticleResult } from "../harvest-feeds/harvest-types";
import type { PlanInputs } from "../load-plan-inputs";
import type { DocumentState } from "./document-state";
import { stageStore } from "./stage-store";
import { collectionForRun } from "./collection-operation";
import { resolveArticleEvidence } from "../website-group";
import { PlanError } from "./plan-request";
import { operationKey, operationLink } from "./operation-context";

export function readFeedOffer(inputs: PlanInputs, reference: OperationLink, offerId: string) {
  const batch = stageStore(inputs).read("parsed", reference, ParsedFeedBatchSchema);
  const fetch = batch.links[0];
  if (batch.links.length !== 1 || fetch === undefined || stageStore(inputs).documentKind(fetch) !== "feed"
    || stageStore(inputs).documentRun(fetch) !== batch.context.run_id) {
    throw new PlanError("ARTIFACT_INVALID", "Article offers require their live producing feed parse", "links");
  }
  const member = batch.offers.find(offer => offer.offer_id === offerId);
  const collection = collectionForRun(inputs, batch.context.run_id);
  if (collection !== undefined) {
    const offer = member === undefined ? undefined : collection.offers.get(offerId);
    const feedParse = member === undefined ? undefined : collection.feeds.get(member.source.feed_id)?.parse;
    if (member !== undefined && (feedParse == null || operationKey(feedParse) !== operationKey(batch))) {
      throw new PlanError("ARTIFACT_INVALID", "Feed parse is not the collection's producing result", "links");
    }
    return { batch, offer: offer === undefined ? undefined : structuredClone(offer) };
  }
  return { batch, offer: member };
}

export function updateFeedOffer(
  inputs: PlanInputs, state: DocumentState, reference: OperationLink, offerId: string, status: PlannerFeedOffer["state"],
  fetch?: OperationLink, result?: HarvestArticleResult,
) {
  const { batch: original, offer: currentOffer } = readFeedOffer(inputs, reference, offerId);
  if (original.context.run_id !== state.context.run_id || original.context.writer.attempt !== state.context.writer.attempt) {
    throw new PlanError("ARTIFACT_INVALID", "Article offer belongs to another run attempt", "links");
  }
  if (currentOffer === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "Article offer is not a member of this feed parse", "offer_id");
  if (status === "fetched" && currentOffer.state === "fetched"
    && (fetch === undefined || currentOffer.links.length !== 1
      || operationKey(currentOffer.links[0]!) !== operationKey(fetch))) {
    throw new PlanError("REQUEST_CONFLICT", "Article offer already has a claimed fetch", "offer_id");
  }
  const links = fetch === undefined ? currentOffer.links : [operationLink(fetch)];
  const collection = collectionForRun(inputs, original.context.run_id);
  if (collection !== undefined) {
    const offer = collection.offers.get(offerId);
    if (offer === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "Article offer does not belong to this collection", "offer_id");
    const updated = PlannerFeedOfferSchema.parse({ ...offer, state: status, links });
    const terminal = (value: PlannerFeedOffer["state"]) => value === "parsed" || value === "rejected";
    collection.pending_offers += Number(terminal(offer.state)) - Number(terminal(status));
    collection.offers.set(offerId, updated);
    if (result?.candidate) collection.results.set(offerId, result);
    else if (status === "fetched" || status === "rejected") collection.results.delete(offerId);
    return { pending_offers: collection.pending_offers };
  }
  const batch = stageStore(inputs).update("parsed", reference, ParsedFeedBatchSchema, current => {
    const offers = current.offers.map(offer => offer.offer_id === offerId ? {
      ...offer, state: status, links,
    } : offer);
    const retained = current.candidates.filter(candidate => candidate.candidate_id !== offerId);
    const candidates = result?.candidate ? [...retained, result.candidate]
      : status === "fetched" || status === "rejected" ? retained : current.candidates;
    const observations = Object.fromEntries(Object.entries(current.observations).filter(([id]) => id !== offerId));
    const evidence = { ...current.evidence };
    if (result?.candidate) {
      evidence[offerId] = resolveArticleEvidence(
        result.candidate, evidence[offerId], inputs.harvest.config.curate_articles.website_grouping.include_private_suffixes,
      );
      observations[offerId] = result.observation;
    } else if (status === "fetched" || status === "rejected") delete evidence[offerId];
    return {
      ...current, offers, candidates: candidates.sort((a, b) => a.entry_ordinal - b.entry_ordinal), observations, evidence,
      input_complete: collectionForRun(inputs, state.context.run_id) === undefined
        && offers.every(offer => offer.state === "parsed" || offer.state === "rejected"),
      work_rows: state.work.rows(), exclusions: state.work.exclusions(),
    };
  });
  return { pending_offers: batch.offers.filter(offer => offer.state !== "parsed" && offer.state !== "rejected").length };
}
