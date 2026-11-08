/** How does the caller prepare one URL or fallback source without hiding acquisition inside HTTP? */
import { createChildContext } from "@idhazh/common-contracts/create-operation-context";
import type { OperationMetadata } from "@idhazh/common-contracts/schemas/operation-metadata";
import type { CompletionFetch } from "../../services/summary-generator/src/services/request-completion.service.js";
import { SourceInputSchema, type SourceInput } from "./contracts/analysis-request.schema.js";
import type { SourceAudit } from "./contracts/system-telemetry.schema.js";
import type { PipelineEventData } from "./contracts/pipeline-event.schema.js";
import { extractContentFromUrl, type ExtractionProgress } from "./extract-content.js";
import { loadAnalysisConfig, type AnalysisConfig } from "./load-analysis-config.js";

export type PreparationProgress = ExtractionProgress | {
  type: "URL_EXTRACTION_FAILED";
  data: PipelineEventData<"URL_EXTRACTION_FAILED">;
  context: OperationMetadata;
};

export async function prepareApiInput(
  input: SourceInput, context: OperationMetadata,
  onProgress?: (progress: PreparationProgress) => void,
  send?: CompletionFetch, config: AnalysisConfig = loadAnalysisConfig(process.env.CONFIG_ROOT),
  signal?: AbortSignal,
) {
  const source = SourceInputSchema.parse(input);
  let text = source.input_text;
  let sourceAudit: SourceAudit;
  let inputContext: OperationMetadata | undefined;
  if (source.url) {
    const extractionContext = createChildContext(context);
    try {
      const extracted = await extractContentFromUrl(
        source.url, extractionContext, onProgress, send, config, signal,
      );
      text = extracted.content;
      inputContext = extracted.context;
      sourceAudit = {
        sourceType: "URL", sourceIdentifier: source.url, sourceTitle: extracted.title,
        extractedWordCount: extracted.wordCount, extractedCharCount: text.length, extractedText: text,
      };
    } catch (error) {
      signal?.throwIfAborted();
      const message = error instanceof Error ? error.message : "Source extraction failed.";
      if (!source.input_text) {
        throw new Error(`Scraping URL failed (${message}) and no input_text fallback was provided.`);
      }
      onProgress?.({
        type: "URL_EXTRACTION_FAILED",
        data: { url: source.url, error: message, resolution: "Fallback to direct input_text" },
        context: extractionContext,
      });
      sourceAudit = {
        sourceType: "FALLBACK_INPUT_TEXT",
        sourceIdentifier: `Fallback (URL failed: ${source.url})`,
        sourceTitle: "Direct Text (Fallback)",
        extractedWordCount: text.split(/\s+/).filter(Boolean).length,
        extractedCharCount: text.length, extractedText: text, scrapeError: message,
      };
    }
  } else {
    sourceAudit = {
      sourceType: "INPUT_TEXT", sourceIdentifier: "Direct Text Input", sourceTitle: "Direct Input Text",
      extractedWordCount: text.split(/\s+/).filter(Boolean).length,
      extractedCharCount: text.length, extractedText: text,
    };
  }
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length > config.max_input_words) {
    text = words.slice(0, config.max_input_words).join(" ") + "\n\n[...Truncated to fit context window...]";
  }
  return {
    input_text: text, source_audit: sourceAudit,
    original_word_count: words.length, input_context: inputContext,
  };
}
