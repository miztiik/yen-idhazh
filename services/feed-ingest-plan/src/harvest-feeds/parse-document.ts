/** Parse fetched bytes without granting their contents network or filesystem authority. */
import { extractArticle } from "./dom-extractor";
import { parseFeed } from "./parse-feed";

export function parseDocument(kind: "feed", body: string, url: string, markers: readonly string[]): ReturnType<typeof parseFeed>;
export function parseDocument(kind: "article", body: string, url: string, markers: readonly string[]): Promise<ReturnType<typeof extractArticle>>;
export async function parseDocument(kind: "feed" | "article", body: string, url: string, markers: readonly string[]) {
  return kind === "feed" ? parseFeed(body) : extractArticle(body, url, markers);
}
