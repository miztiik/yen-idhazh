/** Which configured host and path rule excludes this canonical article URL? */
import type { FeedIngestConfig } from "@idhazh/common-contracts";

type UrlExclusion = FeedIngestConfig["harvest"]["url_exclusions"][number];

export function matchUrlExclusion(canonicalUrl: string, rules: readonly UrlExclusion[]): UrlExclusion | undefined {
  const url = new URL(canonicalUrl);
  return rules.find(rule => {
    const host = rule.host.toLowerCase();
    return (url.hostname === host || (rule.include_subdomains && url.hostname.endsWith(`.${host}`)))
      && (rule.path_prefix === "/" || url.pathname === rule.path_prefix
        || url.pathname.startsWith(`${rule.path_prefix}/`));
  });
}

export function urlExclusionMarker(rule: UrlExclusion): string {
  return `${rule.host}${rule.path_prefix}${rule.path_prefix === "/" ? "" : "/"}`;
}
