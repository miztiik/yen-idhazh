/** Parse fetched bytes without granting their contents network or filesystem authority. */
import { extractArticle } from "./dom-extractor";
import { parseFeed } from "./parse-feed";
import type { ExtractionControls } from "./extraction-controls";
import { ArticleParserPool } from "./article-parser-pool";

export function parseDocument(kind: "feed", body: string, url: string): ReturnType<typeof parseFeed>;
export function parseDocument(kind: "article", body: string, url: string, config: ExtractionControls, form: "article" | "abstract", pool?: ArticleParserPool, options?: Parameters<ArticleParserPool["parse"]>[4]): Promise<ReturnType<typeof extractArticle>>;
export async function parseDocument(kind: "feed" | "article", body: string, url: string, config?: ExtractionControls, form: "article" | "abstract" = "article", pool?: ArticleParserPool, options?: Parameters<ArticleParserPool["parse"]>[4]) {
  if (kind === "feed") return parseFeed(body);
  if (!config) throw new Error("Article parsing requires validated extraction controls");
  const owned = pool ?? new ArticleParserPool(1);
  try { return await owned.parse(body, url, config, form, options); }
  finally { if (pool === undefined) owned.close(); }
}
