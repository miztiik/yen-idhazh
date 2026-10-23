/** Which configured optional feeds voted for an already offered canonical identity? */
import type { PlanningObservations } from "@idhazh/common-contracts";
import type { HarvestInputs } from "./load-harvest-inputs";
import type { PermittedFetcher } from "./robots-policy";
import { parseDocument } from "./parse-document";
import { canonicalizeUrl } from "./url-cleaner";

export type SalienceReading = Readonly<{
  feed_id: string; url_keys: ReadonlySet<string> | null; unavailable_reason: string | null;
}>;
export async function readSalienceFeed(
  feed: NonNullable<HarvestInputs["salience"]>[number], fetcher: PermittedFetcher,
): Promise<SalienceReading> {
  if (feed.status !== "active") return { feed_id: feed.id, url_keys: null, unavailable_reason: "source-inactive" };
  const result = await fetcher.fetch(feed.url);
  if (result.body === null) return {
    feed_id: feed.id, url_keys: null, unavailable_reason: result.failure ?? "fetch-unavailable",
  };
  let entries;
  try { entries = await parseDocument("feed", result.body, feed.url); }
  catch { return { feed_id: feed.id, url_keys: null, unavailable_reason: "feed-parse-failed" }; }
  const url_keys = new Set<string>();
  for (const entry of entries) {
    if (entry.link === null) continue;
    try { url_keys.add(canonicalizeUrl(entry.link).url_key); }
    catch { return { feed_id: feed.id, url_keys: null, unavailable_reason: "invalid-vote-address" }; }
  }
  return { feed_id: feed.id, url_keys, unavailable_reason: null };
}

export function observeSalience(
  urlKey: string, configured: HarvestInputs["salience"], readings: readonly SalienceReading[],
): Pick<PlanningObservations, "salience" | "salience_available" | "on_front_page" | "salience_unavailable_reason"> {
  const salience = readings.map(reading => ({
    feed_id: reading.feed_id, available: reading.url_keys !== null,
    voted: reading.url_keys === null ? null : reading.url_keys.has(urlKey),
    unavailable_reason: reading.unavailable_reason,
  }));
  const reason = configured === null ? "salience-not-configured"
    : !configured.length ? "no-salience-feeds"
    : readings.length !== configured.length ? "salience-not-observed"
    : salience.some(feed => !feed.available) ? "salience-feed-unavailable" : null;
  return {
    salience, salience_available: reason === null,
    on_front_page: reason === null ? salience.some(feed => feed.voted) : null,
    salience_unavailable_reason: reason,
  };
}
