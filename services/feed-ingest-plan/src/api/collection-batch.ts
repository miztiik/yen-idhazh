/** Assemble one validated collection payload at an explicit stage boundary. */
import { ParsedFeedBatchSchema } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { Collection } from "./collection-operation";
import { stageStore } from "./stage-store";
import { foldDiscoveryHistory } from "../read-ledger-history/read-discovered-evidence";
import { resolveArticleEvidence } from "../website-group";
import type { OperationMetadata, OperationLink } from "@idhazh/common-contracts";
import { operationMetadata, stageContext } from "./operation-context";

export function snapshotCollectionBatch(inputs: PlanInputs, collection: Collection, operation: OperationMetadata, complete: boolean) {
  const articles = [...collection.results.values()].flatMap(result => result.candidate === null ? []
    : [{ candidate: result.candidate, observation: result.observation }]);
  const candidates = articles.map(article => article.candidate)
    .sort((a, b) => a.entry_ordinal - b.entry_ordinal);
  return stageStore(inputs).write("parsed", ParsedFeedBatchSchema, {
    ...operationMetadata(operation),
    links: [...collection.parses.values()].filter((value): value is OperationLink => value !== undefined),
    context: stageContext(collection.context), config_sha256: collection.config_sha256,
    request: collection.request, candidates, offers: [...collection.offers.values()],
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
