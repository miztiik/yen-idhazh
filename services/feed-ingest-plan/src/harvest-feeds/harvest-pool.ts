/** Route configured sources and their original entries through the bounded harvest stages. */
import { FeedOutcomePayloadSchema, WriterIdentitySchema, NonEmptySchema, PositiveCountSchema, NonNegativeSchema } from "@idhazh/common-contracts";
import type { HarvestContext, HarvestResult, OfferedArticle, RejectionDestination } from "./harvest-types";
import type { HarvestInputs } from "./load-harvest-inputs";
import { harvestPolicy, sourceSnapshot } from "./load-harvest-inputs";
import { readFeed } from "./feed-client";
import { harvestArticle } from "./harvest-article";
import { persistHarvestRejections } from "./record-rejection";
import { createPermittedFetcher } from "./robots-policy";
import type { HarvestTransport } from "./transport";
import type { ResolveAddresses } from "./safe-target";

export { loadHarvestInputs, readHarvestInputs } from "./load-harvest-inputs";
export type { HarvestInputs } from "./load-harvest-inputs";
export type { HarvestResult, HarvestArticleResult, HarvestObservation, HarvestContext } from "./harvest-types";
export { HarvestObservationSchema, HarvestArticleResultSchema } from "./harvest-types";

export async function mapPool<T, R>(items: readonly T[], concurrency: number, execute: (item: T) => Promise<R>): Promise<R[]> {
  PositiveCountSchema.parse(concurrency);
  const output: R[] = new Array(items.length);
  let next = 0;
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, async () => {
    for (;;) {
      const index = next++;
      if (index >= items.length) return;
      const item = items[index];
      if (item === undefined) throw new Error("pool received a sparse input");
      output[index] = await execute(item);
    }
  }));
  return output;
}

export async function harvestFeeds(
  inputs: HarvestInputs, context: HarvestContext, destination: RejectionDestination,
  boundary: { transport?: HarvestTransport; resolve?: ResolveAddresses } = {},
): Promise<HarvestResult> {
  WriterIdentitySchema.parse(context.writer);
  NonEmptySchema.parse(context.correlation_id);
  NonNegativeSchema.parse(context.max_future_hours);
  context.progress?.("FEED_DISCOVERY_STARTED", { input_count: inputs.sources.length });
  const fetcher = createPermittedFetcher(inputs.config.harvest, inputs.extraction, boundary);
  const feeds = await mapPool(inputs.sources, inputs.config.harvest.concurrency, async configured => {
    const source = sourceSnapshot(inputs, configured);
    context.progress?.("FEED_FETCH_STARTED", { source_id: source.source_id });
    const result = await readFeed(source, fetcher, context, inputs.config.harvest.fetch_timeout_ms);
    context.progress?.("FEED_FETCH_COMPLETED", {
      source_id: source.source_id, fetch_status: result.outcome.fetch_status,
      parse_status: result.outcome.parse_status, output_count: result.entries.length,
      drop_reason: result.outcome.rejection_reason,
    });
    const offered: OfferedArticle[] = [];
    if (result.entries.length) {
      const policy = harvestPolicy(inputs, source.vertical, context.overrides);
      offered.push(...result.entries.map(entry => ({ source, policy, entry })));
    }
    return { offered, rejection: result.rejection, outcome: result.outcome };
  });
  const articles = await mapPool(feeds.flatMap(feed => feed.offered), inputs.config.harvest.concurrency,
    async offered => {
      context.progress?.("ARTICLE_EXTRACTION_STARTED", { source_id: offered.source.source_id });
      const result = await harvestArticle(offered, inputs, fetcher, context);
      context.progress?.("ARTICLE_EXTRACTION_COMPLETED", {
        source_id: offered.source.source_id, candidate_id: result.observation.candidate_id,
        output_count: result.candidate === null ? 0 : 1, drop_reason: result.rejection?.drop_reason ?? null,
      });
      return result;
    });
  const rejections = [
    ...feeds.flatMap(feed => feed.rejection ? [feed.rejection] : []),
    ...articles.flatMap(article => article.rejection ? [article.rejection] : []),
  ];
  const rejection_files = await persistHarvestRejections(rejections, context, destination);
  const harvestedCounts = new Map<string, number>();
  for (const article of articles) {
    if (article.candidate) harvestedCounts.set(article.candidate.source_id, (harvestedCounts.get(article.candidate.source_id) ?? 0) + 1);
  }
  const feed_outcomes = feeds.map(({ outcome }) => FeedOutcomePayloadSchema.parse({
    ...outcome,
    harvested_count: outcome.parse_status === "success" ? harvestedCounts.get(outcome.source.source_id) ?? 0 : outcome.harvested_count,
  }));
  return {
    inputs, config: inputs.config, articles, feed_outcomes, rejections, rejection_files,
    candidates: articles.flatMap(article => article.candidate ? [article.candidate] : []),
  };
}
