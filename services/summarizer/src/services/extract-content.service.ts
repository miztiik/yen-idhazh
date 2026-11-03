/** How is one source fetched and extracted with explicit operation context? */
import { createChildContext } from "@idhazh/common-contracts/create-operation-context";
import type { OperationMetadata } from "@idhazh/common-contracts/schemas/operation-metadata";
import { parseHTML } from "linkedom";
import { Defuddle } from "defuddle/node";
import type { PipelineEventData } from "../schemas/pipeline-event.schema.js";

export interface ExtractedDocument {
  title: string;
  content: string;
  wordCount: number;
  context: OperationMetadata;
}

type ExtractionProgress = {
  [T in "URL_HTTP_FETCH_STARTED" | "URL_HTTP_FETCH_COMPLETED" | "URL_DEFUDDLE_EXTRACTED"]: {
    type: T;
    data: PipelineEventData<T>;
    context: OperationMetadata;
  };
}["URL_HTTP_FETCH_STARTED" | "URL_HTTP_FETCH_COMPLETED" | "URL_DEFUDDLE_EXTRACTED"];

export async function extractContentFromUrl(
  url: string,
  context: OperationMetadata,
  onProgress?: (progress: ExtractionProgress) => void,
): Promise<ExtractedDocument> {
  const fetchContext = createChildContext(context);
  onProgress?.({ type: "URL_HTTP_FETCH_STARTED", data: { url }, context: fetchContext });

  const headers = {
    "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
  };

  const response = await fetch(url, { headers, signal: AbortSignal.timeout(15000) });

  if (!response.ok) {
    throw new Error(`Direct scrape HTTP ${response.status} (${response.statusText})`);
  }

  const html = await response.text();
  onProgress?.({
    type: "URL_HTTP_FETCH_COMPLETED",
    data: { url, bytes: Buffer.byteLength(html, "utf8") },
    context: fetchContext,
  });

  if (html.length < 100) {
    throw new Error(`Received insufficient HTML payload (${html.length} bytes)`);
  }

  const parseContext = createChildContext(context, {
    links: [{ traceId: fetchContext.traceId, spanId: fetchContext.spanId }],
  });
  const { document } = parseHTML(html);
  const fallbackTitle = document.title || "Web Document";
  const defuddleResult: any = await Defuddle(document, url, { markdown: true });
  const content = defuddleResult.content?.trim() || "";

  if (content.length < 50) {
    throw new Error("Defuddle was unable to isolate substantive textual content from the page.");
  }

  const wordCount = content.split(/\s+/).filter(Boolean).length;
  const title = defuddleResult.title || fallbackTitle;

  onProgress?.({
    type: "URL_DEFUDDLE_EXTRACTED", data: { url, title, wordCount }, context: parseContext,
  });

  return { title, content, wordCount, context: parseContext };
}