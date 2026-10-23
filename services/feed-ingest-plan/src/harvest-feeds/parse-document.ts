/** Parse fetched bytes without granting their contents network or filesystem authority. */
import { extractArticle } from "./dom-extractor";
import { parseFeed } from "./parse-feed";
import type { ExtractionControls } from "./extraction-controls";

export function parseDocument(kind: "feed", body: string, url: string): ReturnType<typeof parseFeed>;
export function parseDocument(kind: "article", body: string, url: string, config: ExtractionControls, form: "article" | "abstract"): Promise<ReturnType<typeof extractArticle>>;
export async function parseDocument(kind: "feed" | "article", body: string, url: string, config?: ExtractionControls, form: "article" | "abstract" = "article") {
  if (kind === "feed") return parseFeed(body);
  if (!config) throw new Error("Article parsing requires validated extraction controls");
  return extractArticle(body, url, config, form);
}
