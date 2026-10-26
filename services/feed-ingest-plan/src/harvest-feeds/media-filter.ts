/** Which configured enclosure type or structured address identifies a media offer? */
import type { FeedIngestConfig, RejectionDetails } from "@idhazh/common-contracts";
import { matchUrlExclusion, urlExclusionMarker } from "./url-exclusions";
import { cleanRequestTarget } from "./request-url";
import { UnsafeTargetError } from "./safe-target";

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

export function matchMediaArticle(
  offeredUrl: string, canonicalUrl: string, mediaTypes: readonly string[], config: FeedIngestConfig,
): Partial<RejectionDetails> | null {
  const filter = config.content_filters.media;
  const matched = matchMediaOffer(canonicalUrl, mediaTypes, filter);
  if (matched !== null || !filter.enabled || !config.harvest.tidy_urls) return matched;
  let target: URL;
  try { target = cleanRequestTarget(offeredUrl); }
  catch (error) {
    // Unsafe cleanup remains a typed fetch refusal, never a content exclusion.
    if (error instanceof UnsafeTargetError) return null;
    throw error;
  }
  return matchMediaOffer(target.href, [], filter);
}
