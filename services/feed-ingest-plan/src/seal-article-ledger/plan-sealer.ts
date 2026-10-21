/** How are verified current selections partitioned and persisted for workers? */
import type { CurationResult, persistPortfolio } from "../curate-article-portfolio/editorial-selection";
import type { FeedIngestCandidate } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { RunContext } from "../resolve-run-context";
import { readCurrentSelections } from "../partition-article-shards/read-editorial-selection";
import { partitionArticles, persistDispatches } from "../partition-article-shards/shard-packer";
import type { resolvePlanRequest } from "../api/plan-request";

export async function prepareDispatches(
  curation: CurationResult,
  persisted: Awaited<ReturnType<typeof persistPortfolio>>,
  candidates: readonly FeedIngestCandidate[],
  inputs: PlanInputs,
  context: RunContext,
  request: ReturnType<typeof resolvePlanRequest>,
) {
  const articles = await readCurrentSelections({
    curation, persisted: persisted.selections, candidates, writer: context.writer,
    outputRoot: inputs.outputRoot, context,
  });
  return partitionArticles({
    selections: articles.map(article => article.selection), candidates, context,
    settings: inputs.harvest.config.partition,
    request: { strategy: request.partition_strategy, shards: request.shards },
  });
}

export function sealDispatches(
  partition: ReturnType<typeof partitionArticles>, inputs: PlanInputs, context: RunContext,
) {
  return persistDispatches(partition, {
    outputRoot: inputs.outputRoot, writerContext: context.writer,
    ledgerSettings: inputs.ledgerSettings, registration: inputs.registrations.dispatches,
    date: context.date,
  });
}
