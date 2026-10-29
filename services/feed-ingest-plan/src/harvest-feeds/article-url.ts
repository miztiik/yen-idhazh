/** Clean one article address identically for identity, permission and dispatch. */
import type { FeedIngestConfig } from "@idhazh/common-contracts";
import { UrlSchema } from "@idhazh/common-contracts";
import { cleanHttpRequestTarget } from "./http-request-target";
import { validateTargetName } from "./safe-target";
import { InvalidArticleUrlError } from "./legacy-article-identity";

export type ArticleUrlPolicy = Pick<FeedIngestConfig["harvest"], "tidy_urls">;

export function cleanArticleUrl(raw: string, policy: ArticleUrlPolicy): string {
  const parsed = UrlSchema.safeParse(raw.trim().replace(/^https?:/i, scheme => scheme.toLowerCase()));
  if (!parsed.success) throw new InvalidArticleUrlError("invalid article address", { cause: parsed.error });
  try { new URL(parsed.data); }
  catch (error) {
    if (!(error instanceof TypeError)) throw error;
    throw new InvalidArticleUrlError("invalid article address", { cause: error });
  }
  const offered = validateTargetName(parsed.data);
  const url = policy.tidy_urls ? cleanHttpRequestTarget(offered.href) : offered;
  url.search = "";
  url.hash = "";
  return validateTargetName(url.href).href;
}
