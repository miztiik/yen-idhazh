/** Report the supported saved decision for each feed without another state store. */
import type { SourceHistoryEvidence } from "../read-ledger-history/read-feed-history";
import { projectLifecycleFields } from "../health-row";
import { resolveFeedEligibility } from "./feed-lifecycle";
import type { ConfiguredSource } from "../harvest-feeds/load-harvest-inputs";

export function summarizeFeedAvailability(sources: ReadonlyMap<string, SourceHistoryEvidence>, at: string,
  catalog: readonly Pick<ConfiguredSource, "id" | "status">[]) {
  const active = new Set(catalog.filter(source => source.status === "active").map(source => source.id));
  const feeds = [...sources].map(([feed_id, source]) => ({
    feed_id, endpoint_key: source.endpoint_key, ...projectLifecycleFields(source),
    availability: source.lifecycle === "retired" ? "retired" : resolveFeedEligibility(projectLifecycleFields(source), at),
  }));
  return { feeds, eligible_feed_ids: feeds.filter(feed => active.has(feed.feed_id)
    && (feed.availability === "eligible" || feed.availability === "unknown")).map(feed => feed.feed_id) };
}
