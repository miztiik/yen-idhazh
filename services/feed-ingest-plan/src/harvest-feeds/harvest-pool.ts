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
import { readSalienceFeed } from "./salience-votes";

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
  const responses = new Map<string, ReturnType<typeof fetcher.fetch>>();
  const feedFetcher = { fetch: (url: string) => {
    let result = responses.get(url);
    if (result === undefined) { result = fetcher.fetch(url); responses.set(url, result); }
    return result;
  } };
  const feeds = await mapPool(inputs.sources, inputs.config.harvest.concurrency, async configured => {
    const source = sourceSnapshot(inputs, configured);
    context.progress?.("FEED_FETCH_STARTED", { source_id: source.source_id });
    const started = performance.now();
    const result = await readFeed(source, feedFetcher, context, inputs.config.harvest.fetch_timeout_ms);
    context.progress?.("FEED_FETCH_COMPLETED", {
      source_id: source.source_id, fetch_status: result.outcome.fetch_status,
      parse_status: result.outcome.parse_status, output_count: result.entries.length,
      drop_reason: result.outcome.rejection_reason,
      diagnostics: result.outcome.diagnostics,
      duration_ms: Math.round(performance.now() - started),
    });
    const offered: OfferedArticle[] = [];
    if (result.entries.length) {
      const policy = harvestPolicy(inputs, source.vertical, context.overrides);
      offered.push(...result.entries.map(entry => ({ source, policy, entry })));
    }
    return { offered, rejection: result.rejection, outcome: result.outcome };
  });
  const salience = await mapPool(inputs.salience ?? [], inputs.config.harvest.concurrency,
    feed => readSalienceFeed(feed, feedFetcher));
  const articles = await mapPool(feeds.flatMap(feed => feed.offered), inputs.config.harvest.concurrency,
    async offered => {
      context.progress?.("ARTICLE_HARVEST_STARTED", { source_id: offered.source.source_id });
      const started = performance.now();
      const result = await harvestArticle(offered, inputs, fetcher, context, salience);
      context.progress?.("ARTICLE_HARVEST_COMPLETED", {
        source_id: offered.source.source_id, candidate_id: result.observation.candidate_id,
        output_count: result.candidate === null ? 0 : 1, drop_reason: result.rejection?.drop_reason ?? null,
        extraction_outcome: result.observation.extraction,
        diagnostics: result.observation.diagnostics,
        duration_ms: Math.round(performance.now() - started),
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
    salience: salience.map(reading => ({
      feed_id: reading.feed_id, available: reading.url_keys !== null && reading.unavailable_reason === null,
      unavailable_reason: reading.unavailable_reason,
    })),
    first_sight_candidates: articles.flatMap(article => {
      if (article.rejection?.drop_reason === "BLOCKED_URL_MARKER") return [];
      const url_key = article.candidate?.url_key ?? article.rejection?.url_key;
      return url_key === null || url_key === undefined ? [] : [{ url_key }];
    }),
    candidates: articles.flatMap(article => article.candidate ? [article.candidate] : []),
  };
}
