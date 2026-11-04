/** Hash the same normalized article address used for download. */
import { deriveUrlKey } from "@idhazh/common-contracts";
import { cleanArticleUrl } from "./article-url";

export { InvalidArticleUrlError } from "./article-url";
export function deriveArticleIdentity(raw: string): { canonical_url: string; url_key: string } {
  const canonical_url = cleanArticleUrl(raw);
  return { canonical_url, url_key: deriveUrlKey(canonical_url) };
}
