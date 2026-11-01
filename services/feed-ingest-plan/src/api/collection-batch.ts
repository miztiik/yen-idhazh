/** Assemble one validated collection payload at an explicit stage boundary. */
import { ParsedFeedBatchSchema } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { Collection } from "./collection-operation";
import { stageStore } from "./stage-store";
import { foldDiscoveryHistory } from "../read-ledger-history/read-discovered-evidence";
import { resolveArticleEvidence } from "../website-group";

export function snapshotCollectionBatch(inputs: PlanInputs, collection: Collection, complete: boolean) {
  const current = stageStore(inputs).read("parsed", collection.parsed_batch_id, ParsedFeedBatchSchema);
  const articles = [...collection.results.values()].flatMap(result => result.candidate === null ? []
    : [{ candidate: result.candidate, observation: result.observation }]);
  const candidates = articles.map(article => article.candidate)
    .sort((a, b) => a.entry_ordinal - b.entry_ordinal);
  return stageStore(inputs).replace("parsed", ParsedFeedBatchSchema, {
    ...current, candidates, offers: [...collection.offers.values()],
    observations: Object.fromEntries(articles.map(article => [article.candidate.candidate_id, article.observation])),
    evidence: Object.fromEntries(candidates.map(candidate => [candidate.candidate_id, resolveArticleEvidence(
      candidate, undefined, inputs.harvest.config.curate_articles.website_grouping.include_private_suffixes,
    )])),
    discovered: { availability: "available", rows: foldDiscoveryHistory([
      ...collection.state.baseline.discovered.rows, ...collection.state.discovered_rows,
    ]) },
    input_complete: complete && collection.pending_offers === 0, history_rows: [], history_days: collection.state.history.days,
    work_rows: collection.state.work.rows(), exclusions: collection.state.work.exclusions(),
  });
}
