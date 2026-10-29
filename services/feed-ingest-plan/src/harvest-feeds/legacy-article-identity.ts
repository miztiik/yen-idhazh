/** Recover a prior discovery key without changing the address rules used to write it. */
import { UrlSchema, deriveUrlKey } from "@idhazh/common-contracts";

// Identity constants mirror discover.py; changing them changes article identity.
const trackingKeys = new Set([
  "cmpid", "fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "mkt_tok",
  "msclkid", "ref", "referrer", "s", "src",
]);

export class InvalidArticleUrlError extends Error {}

function validateUrl(value: string): string {
  const parsed = UrlSchema.safeParse(value);
  if (!parsed.success) throw new InvalidArticleUrlError("invalid article address", { cause: parsed.error });
  return parsed.data;
}

export function deriveLegacyArticleIdentity(raw: string): { canonical_url: string; url_key: string } {
  const original = validateUrl(raw.trim().replace(/^https?:/i, scheme => scheme.toLowerCase()));
  let url: URL;
  try { url = new URL(original); }
  catch (error) {
    if (!(error instanceof TypeError) || !("code" in error) || error.code !== "ERR_INVALID_URL") throw error;
    throw new InvalidArticleUrlError("invalid article address", { cause: error });
  }
  if (url.username || url.password) throw new InvalidArticleUrlError("article address must not contain credentials");
  url.hostname = url.hostname.replace(/^www\./, "");
  url.hash = "";
  // URL validates the authority; discovery preserves the offered path's spelling.
  const path = /^https?:\/\/[^/?#]+([^?#]*)/.exec(original)?.[1]?.replace(/\/+$/, "") || "/";
  const kept = [...url.searchParams.entries()]
    .filter(([key]) => !trackingKeys.has(key.toLowerCase()) && !key.toLowerCase().startsWith("utm_"))
    .sort(([keyA, valueA], [keyB, valueB]) => keyA < keyB ? -1 : keyA > keyB ? 1 : valueA < valueB ? -1 : valueA > valueB ? 1 : 0);
  // Python discovery deliberately preserves decoded query text rather than URLSearchParams encoding.
  const query = kept.map(([key, value]) => `${key}=${value}`).join("&");
  const canonical_url = validateUrl(`${url.protocol}//${url.host}${path}${query ? `?${query}` : ""}`);
  return { canonical_url, url_key: deriveUrlKey(canonical_url) };
}
