/** Assemble one validated collection payload at an explicit stage boundary. */
import { ParsedFeedBatchSchema } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { Collection } from "./collection-operation";
import { stageStore } from "./stage-store";
import { foldDiscoveryHistory } from "../read-ledger-history/read-discovered-evidence";
import { resolveArticleEvidence } from "../website-group";
import type {
  FeedIngestCandidate, OperationMetadata, OperationLink, ParsedFeedBatch, PlannerHarvestObservation,
} from "@idhazh/common-contracts";
import { operationMetadata, stageContext } from "./operation-context";

export function snapshotCollectionBatch(inputs: PlanInputs, collection: Collection, operation: OperationMetadata, complete: boolean) {
  return retainCollectionBatch(inputs, collection, {
    ...operationMetadata(operation),
    links: [...collection.parses.values()].filter((value): value is OperationLink => value !== undefined),
  }, {
    articles: [...collection.results.values()].flatMap(result => result.candidate === null ? []
      : [{ candidate: result.candidate, observation: result.observation }]),
    offers: [...collection.offers.values()],
    discovered: { availability: "available", rows: foldDiscoveryHistory([
      ...collection.state.baseline.discovered.rows, ...collection.state.discovered_rows,
    ]) },
    input_complete: complete && collection.pending_offers === 0,
  });
}

export function retainCollectionParse(inputs: PlanInputs, collection: Collection, operation: OperationMetadata, result:
  { kind: "feed"; feed_id: string } | {
    kind: "article"; candidate: FeedIngestCandidate | null; observation: PlannerHarvestObservation;
    discovered?: ParsedFeedBatch["discovered"];
  }) {
  return retainCollectionBatch(inputs, collection, operation, {
    articles: result.kind === "article" && result.candidate !== null
      ? [{ candidate: result.candidate, observation: result.observation }] : [],
    offers: result.kind === "feed" ? [...collection.offers.values()].filter(offer => offer.source.feed_id === result.feed_id) : [],
    discovered: result.kind === "article" && result.discovered !== undefined ? result.discovered
      : { availability: "available", rows: [] },
    input_complete: false,
  });
}

type CollectionContent = {
  articles: readonly { candidate: FeedIngestCandidate; observation: PlannerHarvestObservation }[];
  offers: ParsedFeedBatch["offers"]; discovered: ParsedFeedBatch["discovered"]; input_complete: boolean;
};
type CapturedBatch = OperationMetadata & Pick<ParsedFeedBatch,
  "context" | "config_sha256" | "request" | "history_rows" | "history_days" | "work_rows" | "exclusions">;

function retainCollectionBatch(inputs: PlanInputs, collection: Collection, operation: OperationMetadata, content: CollectionContent) {
  const captured: CapturedBatch = {
    ...operationMetadata(operation), context: stageContext(collection.context), config_sha256: collection.config_sha256,
    request: structuredClone(collection.request), history_rows: [], history_days: structuredClone(collection.state.history.days),
    work_rows: collection.state.work.rows(), exclusions: structuredClone(collection.state.work.exclusions()),
  };
  return stageStore(inputs).writeCollectionResult(ParsedFeedBatchSchema, capturedBatchReader(
    captured, { ...content, discovered: structuredClone(content.discovered) },
    inputs.harvest.config.curate_articles.website_grouping.include_private_suffixes,
  ));
}

function capturedBatchReader(captured: CapturedBatch, content: CollectionContent, includePrivateSuffixes: boolean) {
  // Retain captured schema data, not the live collection or a downloaded document.
  return () => collectionBatch(captured, content, includePrivateSuffixes);
}

function collectionBatch(captured: CapturedBatch, content: CollectionContent, includePrivateSuffixes: boolean) {
  const candidates = content.articles.map(article => article.candidate).sort((a, b) => a.entry_ordinal - b.entry_ordinal);
  return {
    ...captured, candidates, offers: content.offers,
    observations: Object.fromEntries(content.articles.map(article => [article.candidate.candidate_id, article.observation])),
    evidence: Object.fromEntries(candidates.map(candidate => [candidate.candidate_id, resolveArticleEvidence(
      candidate, undefined, includePrivateSuffixes,
    )])),
    discovered: content.discovered, input_complete: content.input_complete,
  };
}
