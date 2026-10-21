/** Route configured sources and their original entries through the bounded harvest stages. */
import { WriterIdentitySchema, NonEmptySchema, PositiveCountSchema } from "@idhazh/common-contracts";
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
  const fetcher = createPermittedFetcher(inputs.config.harvest, inputs.extraction, boundary);
  const feeds = await mapPool(inputs.sources, inputs.config.harvest.concurrency, async configured => {
    const source = sourceSnapshot(inputs, configured);
    const policy = harvestPolicy(inputs, source.vertical, context.overrides);
    const result = await readFeed(source, fetcher, context, inputs.config.harvest.fetch_timeout_ms);
    const offered: OfferedArticle[] = result.entries.map(entry => ({ source, policy, entry }));
    return { offered, rejection: result.rejection };
  });
  const articles = await mapPool(feeds.flatMap(feed => feed.offered), inputs.config.harvest.concurrency,
    offered => harvestArticle(offered, inputs, fetcher, context));
  const rejections = [
    ...feeds.flatMap(feed => feed.rejection ? [feed.rejection] : []),
    ...articles.flatMap(article => article.rejection ? [article.rejection] : []),
  ];
  const rejection_files = await persistHarvestRejections(rejections, context, destination);
  return {
    inputs, config: inputs.config, articles, rejections, rejection_files,
    candidates: articles.flatMap(article => article.candidate ? [article.candidate] : []),
  };
}
