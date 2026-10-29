/** Clean one article address identically for identity, permission and dispatch. */
import type { FeedIngestConfig } from "@idhazh/common-contracts";
import { UrlSchema } from "@idhazh/common-contracts";
import { cleanHttpRequestTarget } from "./http-request-target";
import { validateTargetName } from "./safe-target";
import { InvalidArticleUrlError } from "./legacy-article-identity";

export type ArticleUrlPolicy = Pick<FeedIngestConfig["harvest"], "tidy_urls">;

export function normalizeArticleUrlInput(raw: string): string {
  return raw.trim().replace(/^https?:/i, scheme => scheme.toLowerCase());
}

export function cleanArticleUrl(raw: string, policy: ArticleUrlPolicy): string {
  const parsed = UrlSchema.safeParse(normalizeArticleUrlInput(raw));
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
  const serialized = UrlSchema.safeParse(validateTargetName(url.href).href);
  if (!serialized.success) throw new InvalidArticleUrlError("invalid serialized article address", { cause: serialized.error });
  return serialized.data;
}
