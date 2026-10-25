/** Which configured optional feeds voted for an already offered canonical identity? */
import type { PlanningObservations } from "@idhazh/common-contracts";
import type { HarvestInputs } from "./load-harvest-inputs";
import type { PermittedFetcher } from "./robots-policy";
import { parseDocument } from "./parse-document";
import { FeedParseError } from "./parse-feed";
import { canonicalizeUrl, InvalidArticleUrlError } from "./url-cleaner";
import { documentWork, describeFeedParse } from "./document-work";
import type { HarvestContext } from "./harvest-types";

export type SalienceReading = Readonly<{
  feed_id: string; url_keys: ReadonlySet<string> | null; unavailable_reason: string | null;
}>;
export async function readSalienceFeed(
  feed: NonNullable<HarvestInputs["salience"]>[number], fetcher: PermittedFetcher,
  context?: HarvestContext,
): Promise<SalienceReading> {
  if (feed.status !== "active") return { feed_id: feed.id, url_keys: null, unavailable_reason: "source-inactive" };
  const work = context === undefined ? undefined : documentWork(context, {
    run_id: context.writer.run_id, correlation_id: context.correlation_id,
    article_id: canonicalizeUrl(feed.url).url_key, source_id: null,
  }, `${context.writer.run_id}\nsalience\n${feed.id}`, {
    document_kind: "feed", source_id: null, publisher_id: null, candidate_id: null,
    observed_run_id: context.writer.run_id, observed_attempt: context.writer.attempt,
  });
  const captured = work === undefined ? null : await work.fetch(fetcher, feed.url);
  const result = captured?.fetched ?? await fetcher.fetch(feed.url);
  context?.observations?.assertSaved();
  if (result.body === null) return {
    feed_id: feed.id, url_keys: null, unavailable_reason: result.failure ?? "fetch-unavailable",
  };
  let entries;
  try {
    const body = result.body;
    if (work !== undefined && captured !== null) {
      const parsed = await work.parse(() => parseDocument("feed", body, feed.url), captured.observation.event_id, describeFeedParse);
      context?.observations?.assertSaved();
      if (parsed.parsed === null) return { feed_id: feed.id, url_keys: null, unavailable_reason: "feed-parse-failed" };
      entries = parsed.parsed;
    } else entries = await parseDocument("feed", body, feed.url);
  }
  catch (error) {
    if (!(error instanceof FeedParseError)) throw error;
    return { feed_id: feed.id, url_keys: null, unavailable_reason: "feed-parse-failed" };
  }
  const url_keys = new Set<string>();
  let unavailable_reason: string | null = null;
  for (const entry of entries) {
    if (entry.link === null) continue;
    try { url_keys.add(canonicalizeUrl(entry.link).url_key); }
    catch (error) {
      if (!(error instanceof InvalidArticleUrlError)) throw error;
      unavailable_reason = "invalid-vote-address";
    }
  }
  return { feed_id: feed.id, url_keys, unavailable_reason };
}

export function observeSalience(
  urlKey: string, configured: HarvestInputs["salience"], readings: readonly SalienceReading[],
): Pick<PlanningObservations, "salience" | "salience_available" | "on_front_page" | "salience_unavailable_reason"> {
  const salience = readings.map(reading => {
    const available = reading.url_keys !== null && reading.unavailable_reason === null;
    return {
      feed_id: reading.feed_id, available,
      voted: reading.url_keys?.has(urlKey) ? true : available ? false : null,
      unavailable_reason: reading.unavailable_reason,
    };
  });
  const reason = configured === null ? "salience-not-configured"
    : !configured.length ? "no-salience-feeds"
    : readings.length !== configured.length ? "salience-not-observed"
    : salience.some(feed => !feed.available) ? "salience-feed-unavailable" : null;
  return {
    salience, salience_available: reason === null,
    on_front_page: salience.some(feed => feed.voted === true) ? true : reason === null ? false : null,
    salience_unavailable_reason: reason,
  };
}
