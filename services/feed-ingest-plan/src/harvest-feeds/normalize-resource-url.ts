/** Normalize one HTTP resource address without discarding resource-identifying bytes. */
import { UrlSchema } from "@idhazh/common-contracts";

export class InvalidArticleUrlError extends Error {}

export function normalizeResourceUrlInput(raw: string): string {
  return raw.trim().replace(/^https?:/i, scheme => scheme.toLowerCase());
}

export function normalizeResourceUrl(raw: string): string {
  const parsed = UrlSchema.safeParse(normalizeResourceUrlInput(raw));
  if (!parsed.success) throw new InvalidArticleUrlError("invalid resource address", { cause: parsed.error });
  let url: URL;
  try { url = new URL(parsed.data); }
  catch (error) {
    if (!(error instanceof TypeError)) throw error;
    throw new InvalidArticleUrlError("invalid resource address", { cause: error });
  }
  url.hash = "";
  const serialized = UrlSchema.safeParse(url.href);
  if (!serialized.success) throw new InvalidArticleUrlError("invalid serialized resource address", { cause: serialized.error });
  return serialized.data;
}
