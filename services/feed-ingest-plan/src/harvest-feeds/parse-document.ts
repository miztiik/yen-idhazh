/** Parse fetched bytes without granting their contents network or filesystem authority. */
import { extractArticle } from "./dom-extractor";
import { parseFeed } from "./parse-feed";
import type { ExtractionControls } from "./extraction-controls";
import { ArticleParserPool } from "./article-parser-pool";

export function parseDocument(fetchItemType: "feed", body: string, url: string, config?: undefined, pool?: ArticleParserPool, options?: Parameters<ArticleParserPool["parse"]>[3]): ReturnType<typeof parseFeed>;
export function parseDocument(fetchItemType: "article", body: string, url: string, config: ExtractionControls, pool?: ArticleParserPool, options?: Parameters<ArticleParserPool["parse"]>[3]): ReturnType<typeof extractArticle>;
export async function parseDocument(fetchItemType: "feed" | "article", body: string, url: string, config?: ExtractionControls, pool?: ArticleParserPool, options?: Parameters<ArticleParserPool["parse"]>[3]) {
  if (fetchItemType === "article" && !config) throw new Error("Article parsing requires validated extraction controls");
  const owned = pool ?? new ArticleParserPool(1);
  try { return fetchItemType === "feed" ? await owned.parseFeed(body, options) : await owned.parse(body, url, config!, options); }
  finally { if (pool === undefined) owned.close(); }
}
