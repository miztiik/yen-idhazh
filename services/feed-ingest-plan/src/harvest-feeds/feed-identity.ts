/** Hash one feed document with the same conservative resource URL protocol as articles. */
import { deriveUrlKey } from "@idhazh/common-contracts";
import { normalizeResourceUrl } from "./normalize-resource-url";

export function deriveFeedIdentity(raw: string): { canonical_url: string; url_key: string } {
  const canonical_url = normalizeResourceUrl(raw);
  return { canonical_url, url_key: deriveUrlKey(canonical_url) };
}
