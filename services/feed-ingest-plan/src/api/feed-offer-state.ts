/** Read or settle one article offer without copying its owning collection. */
import { ParsedFeedBatchSchema, PlannerFeedOfferSchema } from "@idhazh/common-contracts";
import type { PlannerFeedOffer } from "@idhazh/common-contracts";
import type { HarvestArticleResult } from "../harvest-feeds/harvest-types";
import type { PlanInputs } from "../load-plan-inputs";
import type { DocumentState } from "./document-state";
import { stageStore } from "./stage-store";
import { collectionForBatch, collectionForRun } from "./collection-operation";
import { resolveArticleEvidence } from "../website-group";
import { PlanError } from "./plan-request";

export function readFeedOffer(inputs: PlanInputs, batchId: string, offerId: string) {
  const collection = collectionForBatch(inputs, batchId);
  if (collection !== undefined) {
    if (!stageStore(inputs).has(batchId)) throw new PlanError("ARTIFACT_NOT_FOUND", "Current collection batch has expired", "batch_id");
    const offer = collection.offers.get(offerId);
    return {
      batch: { batch_id: batchId, context: collection.context, config_sha256: collection.config_sha256,
        feed_fetch_request_id: null },
      offer: offer === undefined ? undefined : structuredClone(offer),
    };
  }
  const batch = stageStore(inputs).read("parsed", batchId, ParsedFeedBatchSchema);
  return { batch, offer: batch.offers.find(offer => offer.offer_id === offerId) };
}

export function updateFeedOffer(
  inputs: PlanInputs, state: DocumentState, batchId: string, offerId: string, status: PlannerFeedOffer["state"],
  fetchRequestId?: string, result?: HarvestArticleResult,
) {
  const collection = collectionForBatch(inputs, batchId);
  if (collection !== undefined) {
    const offer = collection.offers.get(offerId);
    if (offer === undefined) throw new PlanError("ARTIFACT_NOT_FOUND", "Article offer does not belong to this collection", "offer_id");
    const updated = PlannerFeedOfferSchema.parse({ ...offer, state: status,
      fetch_request_id: fetchRequestId ?? offer.fetch_request_id });
    const terminal = (value: PlannerFeedOffer["state"]) => value === "parsed" || value === "rejected";
    collection.pending_offers += Number(terminal(offer.state)) - Number(terminal(status));
    collection.offers.set(offerId, updated);
    if (result?.candidate) collection.results.set(offerId, result);
    else if (status === "fetched" || status === "rejected") collection.results.delete(offerId);
    return { batch_id: batchId, pending_offers: collection.pending_offers };
  }
  const batch = stageStore(inputs).update("parsed", batchId, ParsedFeedBatchSchema, current => {
    const offers = current.offers.map(offer => offer.offer_id === offerId ? {
      ...offer, state: status, fetch_request_id: fetchRequestId ?? offer.fetch_request_id,
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
  return { batch_id: batch.batch_id,
    pending_offers: batch.offers.filter(offer => offer.state !== "parsed" && offer.state !== "rejected").length };
}
