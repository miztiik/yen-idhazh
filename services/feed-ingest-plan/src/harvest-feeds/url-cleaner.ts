/** Spell one article address using the existing discovery identity rules. */
import { UrlSchema, deriveUrlKey } from "@idhazh/common-contracts";

// Identity constants mirror discover.py; changing them changes article identity.
const trackingKeys = new Set([
  "cmpid", "fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "mkt_tok",
  "msclkid", "ref", "referrer", "s", "src",
]);

export function canonicalizeUrl(raw: string): { canonical_url: string; url_key: string } {
  const url = new URL(UrlSchema.parse(raw.trim().replace(/^https?:/i, scheme => scheme.toLowerCase())));
  if (url.username || url.password) throw new Error("article address must not contain credentials");
  url.hostname = url.hostname.replace(/^www\./, "");
  url.hash = "";
  url.pathname = url.pathname.replace(/\/+$/, "") || "/";
  const kept = [...url.searchParams.entries()]
    .filter(([key]) => !trackingKeys.has(key.toLowerCase()) && !key.toLowerCase().startsWith("utm_"))
    .sort(([keyA, valueA], [keyB, valueB]) => keyA < keyB ? -1 : keyA > keyB ? 1 : valueA < valueB ? -1 : valueA > valueB ? 1 : 0);
  // Python discovery deliberately preserves decoded query text rather than URLSearchParams encoding.
  const query = kept.map(([key, value]) => `${key}=${value}`).join("&");
  const canonical_url = UrlSchema.parse(`${url.protocol}//${url.host}${url.pathname}${query ? `?${query}` : ""}`);
  return { canonical_url, url_key: deriveUrlKey(canonical_url) };
}
