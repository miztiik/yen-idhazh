/** Which configured enclosure type or structured address identifies a media offer? */
import type { FeedIngestConfig, RejectionDetails } from "@idhazh/common-contracts";
import { matchUrlExclusion, urlExclusionMarker } from "./url-exclusions";

export function matchMediaOffer(
  canonicalUrl: string, mediaTypes: readonly string[], config: FeedIngestConfig["content_filters"]["media"],
): Partial<RejectionDetails> | null {
  if (!config.enabled) return null;
  const prefix = config.enclosure_type_prefixes.find(prefix =>
    mediaTypes.some(type => type.trim().toLowerCase().startsWith(prefix)));
  if (prefix !== undefined) return { media_match: "enclosure", matched_media_type_prefix: prefix };
  const rule = matchUrlExclusion(canonicalUrl, config.url_rules);
  return rule === undefined ? null : { media_match: "url", matched_url_marker: urlExclusionMarker(rule) };
}
