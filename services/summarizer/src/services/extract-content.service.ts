import { parseHTML } from "linkedom";
import { Defuddle } from "defuddle/node";

export interface ExtractedDocument {
  title: string;
  content: string;
  wordCount: number;
}

export async function extractContentFromUrl(
  url: string,
  onProgress?: (step: "FETCH_STARTED" | "FETCH_COMPLETED" | "PARSED", details: any) => void
): Promise<ExtractedDocument> {
  onProgress?.("FETCH_STARTED", { url });

  const headers = {
    "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
  };

  console.log(`[SCRAPER] 🌐 Querying URL: ${url}`);
  const response = await fetch(url, { headers, signal: AbortSignal.timeout(15000) });

  if (!response.ok) {
    throw new Error(`Direct scrape HTTP ${response.status} (${response.statusText})`);
  }

  const html = await response.text();
  onProgress?.("FETCH_COMPLETED", { url, bytes: Buffer.byteLength(html, "utf8") });

  if (html.length < 100) {
    throw new Error(`Received insufficient HTML payload (${html.length} bytes)`);
  }

  const { document } = parseHTML(html);
  const fallbackTitle = document.title || "Web Document";
  const defuddleResult: any = await Defuddle(document, url, { markdown: true });
  const content = defuddleResult.content?.trim() || "";

  if (content.length < 50) {
    throw new Error("Defuddle was unable to isolate substantive textual content from the page.");
  }

  const wordCount = content.split(/\s+/).filter(Boolean).length;
  const title = defuddleResult.title || fallbackTitle;

  onProgress?.("PARSED", { url, title, wordCount });
  console.log(`[SCRAPER] ✅ Successfully extracted with Defuddle: "${title}" (${wordCount} words)`);

  return { title, content, wordCount };
}