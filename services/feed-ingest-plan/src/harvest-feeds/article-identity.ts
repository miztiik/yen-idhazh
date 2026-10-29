/** Hash the same cleaned article address used for permission and download. */
import { deriveUrlKey } from "@idhazh/common-contracts";
import { cleanArticleUrl } from "./article-url";
import type { ArticleUrlPolicy } from "./article-url";

export { InvalidArticleUrlError } from "./legacy-article-identity";
export function deriveArticleIdentity(raw: string, policy: ArticleUrlPolicy): { canonical_url: string; url_key: string } {
  const canonical_url = cleanArticleUrl(raw, policy);
  return { canonical_url, url_key: deriveUrlKey(canonical_url) };
}
