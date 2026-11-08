/** How is one source fetched and extracted with explicit operation context? */
import { createChildContext } from "@idhazh/common-contracts/create-operation-context";
import type { OperationMetadata } from "@idhazh/common-contracts/schemas/operation-metadata";
import { JSDOM } from "jsdom";
import { Defuddle } from "defuddle/node";
import type { PipelineEventData } from "./contracts/pipeline-event.schema.js";
import { loadAnalysisConfig, type AnalysisConfig } from "./load-analysis-config.js";
import {
  cancelResponseBody, type CompletionFetch,
} from "../../services/summary-generator/src/services/request-completion.service.js";

export interface ExtractedDocument {
  title: string;
  content: string;
  wordCount: number;
  context: OperationMetadata;
}

export type ExtractionProgress = {
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
  send: CompletionFetch = request => fetch(request),
  config: AnalysisConfig = loadAnalysisConfig(process.env.CONFIG_ROOT),
  signal?: AbortSignal,
): Promise<ExtractedDocument> {
  const fetchContext = createChildContext(context);
  onProgress?.({ type: "URL_HTTP_FETCH_STARTED", data: { url }, context: fetchContext });

  const headers = {
    "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
  };

  const deadline = AbortSignal.timeout(config.extraction_timeout_ms);
  const cancelled = signal === undefined ? deadline : AbortSignal.any([signal, deadline]);
  const response = await send(new Request(url, {
    headers, signal: cancelled,
  }));

  if (!response.ok) {
    await cancelResponseBody(response.body, cancelled);
    throw new Error(`Direct scrape HTTP ${response.status} (${response.statusText})`);
  }

  const html = await response.text();
  onProgress?.({
    type: "URL_HTTP_FETCH_COMPLETED",
    data: { url, bytes: Buffer.byteLength(html, "utf8") },
    context: fetchContext,
  });

  if (Buffer.byteLength(html, "utf8") < config.min_html_bytes) {
    throw new Error(`Received insufficient HTML payload (${html.length} bytes)`);
  }

  const parseContext = createChildContext(context, {
    links: [{ traceId: fetchContext.traceId, spanId: fetchContext.spanId }],
  });
  return parseExtractedDocument(new JSDOM(html, { url }), url, parseContext, onProgress, config);
}

export async function parseExtractedDocument(
  dom: JSDOM, url: string, context: OperationMetadata,
  onProgress?: (progress: ExtractionProgress) => void,
  config?: AnalysisConfig,
): Promise<ExtractedDocument> {
  try {
    const controls = config ?? loadAnalysisConfig(process.env.CONFIG_ROOT);
    const fallbackTitle = dom.window.document.title || "Web Document";
    const parsed = await Defuddle(dom, url, { markdown: true });
    const content = parsed.content?.trim() || "";
    if (content.length < controls.min_content_characters) {
      throw new Error("Defuddle was unable to isolate substantive textual content from the page.");
    }
    const wordCount = content.split(/\s+/).filter(Boolean).length;
    const title = parsed.title || fallbackTitle;
    onProgress?.({
      type: "URL_DEFUDDLE_EXTRACTED", data: { url, title, wordCount }, context,
    });
    return { title, content, wordCount, context };
  } finally {
    dom.window.close();
  }
}