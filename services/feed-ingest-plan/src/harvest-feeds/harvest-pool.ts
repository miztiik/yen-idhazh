/** Overlap independent feed reads and article work within the configured request bound. */
import { FeedOutcomePayloadSchema, PositiveCountSchema, WriterIdentitySchema } from "@idhazh/common-contracts";
import type { HarvestContext, HarvestResult, OfferedArticle } from "./harvest-types";
import { utcTimestamp } from "./harvest-types";
import type { HarvestInputs } from "./load-harvest-inputs";
import { sourceSnapshot } from "./load-harvest-inputs";
import { feedDocumentWork, readFeed } from "./feed-client";
import { harvestArticle } from "./harvest-article";
import { createPermittedFetcher } from "./robots-policy";
import type { HarvestTransport } from "./transport";
import type { ResolveAddresses } from "./safe-target";
import { ArticleParserPool } from "./article-parser-pool";

export { loadHarvestInputs, readHarvestInputs } from "./load-harvest-inputs";
export type { HarvestInputs } from "./load-harvest-inputs";
export type { HarvestResult, HarvestArticleResult, HarvestObservation, HarvestContext } from "./harvest-types";
export { HarvestObservationSchema, HarvestArticleResultSchema } from "./harvest-types";

export async function mapPool<T, R>(items: readonly T[], concurrency: number, execute: (item: T) => Promise<R>): Promise<R[]> {
  PositiveCountSchema.parse(concurrency);
  const output: R[] = new Array(items.length);
  let next = 0;
  const workers = await Promise.allSettled(Array.from({ length: Math.min(concurrency, items.length) }, async () => {
    for (;;) {
      const index = next++;
      if (index >= items.length) return;
      const item = items[index];
      if (item === undefined) throw new Error("Pool received a sparse input");
      output[index] = await execute(item);
    }
  }));
  const failures = workers.flatMap(worker => worker.status === "rejected" ? [worker.reason] : []);
  if (failures.length) throw new AggregateError(failures, "Work pool failed; completed work is retained");
  return output;
}

export function workPool(concurrency: number) {
  PositiveCountSchema.parse(concurrency);
  let active = 0;
  const waiting: (() => void)[] = [];
  return async <T>(execute: () => Promise<T>): Promise<T> => {
    if (active >= concurrency) await new Promise<void>(resolve => waiting.push(resolve));
    else active++;
    try { return await execute(); }
    finally {
      const next = waiting.shift();
      if (next === undefined) active--;
      else next();
    }
  };
}

export async function harvestFeeds(
  inputs: HarvestInputs, context: HarvestContext,
  boundary: { transport?: HarvestTransport; resolve?: ResolveAddresses } = {},
): Promise<HarvestResult> {
  WriterIdentitySchema.parse(context.writer);
  const fetcher = createPermittedFetcher(inputs.config.harvest, inputs.extraction, boundary, context.observation_clock);
  const permit = workPool(inputs.config.harvest.concurrency);
  const boundedFetcher: Pick<typeof fetcher, "fetch"> = {
    fetch: (url, emit) => permit(() => fetcher.fetch(url, emit)),
  };
  const ownedPool = context.parser_pool ?? new ArticleParserPool(inputs.config.harvest.concurrency);
  const runContext = { ...context, parser_pool: ownedPool };
  try {
    const feeds = await mapPool(inputs.sources, inputs.config.harvest.concurrency, async configured => {
      const source = sourceSnapshot(inputs, configured);
      const history = context.feed_history?.get(source.feed_id);
      if (source.status === "active" && history?.lifecycle === "resting") {
        await feedDocumentWork(source, runContext).skip();
        const outcome = FeedOutcomePayloadSchema.parse({
          kind: "feed_outcome", source, fetch_status: "not_requested", parse_status: "not_attempted",
          parsed_count: null, harvested_count: null, fetch_duration_ms: null, parse_duration_ms: null, rejection_reason: null,
        });
        context.on_feed?.(outcome, [], utcTimestamp(context.observation_clock));
        return { outcome, articles: [], rejection: null };
      }
      context.progress?.("FEED_FETCH_STARTED", { feed_id: source.feed_id });
      const feed = await readFeed(source, boundedFetcher, runContext, inputs.config.harvest.fetch_timeout_ms);
      context.on_feed?.(feed.outcome, feed.entries, utcTimestamp(context.observation_clock));
      context.progress?.("FEED_FETCH_COMPLETED", { feed_id: source.feed_id, output_count: feed.entries.length });
      const articles = await mapPool(feed.entries, inputs.config.harvest.concurrency, async entry => {
        const offered: OfferedArticle = { source, entry };
        context.progress?.("ARTICLE_HARVEST_STARTED", { feed_id: source.feed_id });
        const result = await harvestArticle(offered, inputs, boundedFetcher, runContext);
        context.on_article?.(result);
        context.progress?.("ARTICLE_HARVEST_COMPLETED", {
          feed_id: source.feed_id, output_count: result.candidate === null ? 0 : 1,
        });
        return result;
      });
      const outcome = FeedOutcomePayloadSchema.parse({
        ...feed.outcome, harvested_count: feed.outcome.parse_status === "success"
          ? articles.filter(article => article.candidate !== null).length : feed.outcome.harvested_count,
      });
      return { outcome, articles, rejection: feed.rejection };
    });
    const articles = feeds.flatMap(feed => feed.articles);
    const rejections = [
      ...feeds.flatMap(feed => feed.rejection ? [feed.rejection] : []),
      ...articles.flatMap(article => article.rejection ? [article.rejection] : []),
    ];
    return {
      inputs, config: inputs.config, articles, feed_outcomes: feeds.map(feed => feed.outcome),
      rejections, salience: [],
      discovered_candidates: articles.flatMap(article => {
        if (article.rejection?.drop_reason === "BLOCKED_URL_MARKER") return [];
        const key = (article.candidate ?? article.rejection)?.url_key;
        return key === null || key === undefined ? [] : [{ url_key: key }];
      }),
      candidates: articles.flatMap(article => article.candidate ? [article.candidate] : []),
    };
  } finally { if (context.parser_pool === undefined) ownedPool.close(); }
}
