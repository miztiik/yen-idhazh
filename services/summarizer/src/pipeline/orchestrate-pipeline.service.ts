import { performance } from "node:perf_hooks";
import {
  type SummarizeRequest,
  type SummaryStructuredOutput,
  type SourceAudit,
  type DetailedTokenMetrics,
  SummarizeRequestSchema,
  SummaryStructuredOutputSchema,
} from "../schemas/export-all-schemas.js";
import { extractContentFromUrl } from "../services/extract-content.service.js";
import {
  getVmstatSwap,
  getMemorySnapshot,
  finalizeSwapMetrics,
} from "../services/collect-telemetry.service.js";
import {
  buildInferencePrompt,
  queryLlamaServer,
} from "../services/query-llama.service.js";
import { PipelineEventBus } from "../services/dispatch-event.service.js";

export async function orchestratePipeline(
  requestInput: SummarizeRequest,
  eventBus: PipelineEventBus,
  defaults: { serverUrl: string; modelName: string }
): Promise<SummaryStructuredOutput> {
  const validatedInput = SummarizeRequestSchema.parse(requestInput);

  const cleanUrl = (validatedInput.url || "").trim();
  const fallbackText = (validatedInput.input_text || "").trim();
  const systemPrompt = validatedInput.system_prompt;
  const serverUrl = validatedInput.server_url || defaults.serverUrl;
  const modelName = validatedInput.model_name || defaults.modelName;

  let targetText = fallbackText;
  let sourceAudit: SourceAudit;

  // 1. Ingestion Phase (URL direct scrape or fallback)
  if (cleanUrl.length > 0) {
    eventBus.emitEvent("URL_HTTP_FETCH_STARTED", { url: cleanUrl });

    try {
      const extracted = await extractContentFromUrl(cleanUrl, (phase, details) => {
        if (phase === "FETCH_COMPLETED") eventBus.emitEvent("URL_HTTP_FETCH_COMPLETED", details);
        if (phase === "PARSED") eventBus.emitEvent("URL_DEFUDDLE_EXTRACTED", details);
      });

      sourceAudit = {
        sourceType: "URL",
        sourceIdentifier: cleanUrl,
        sourceTitle: extracted.title,
        extractedWordCount: extracted.wordCount,
        extractedCharCount: extracted.content.length,
        extractedText: extracted.content,
      };
      targetText = extracted.content;
    } catch (err: any) {
      if (!fallbackText) {
        throw new Error(`Scraping URL failed (${err.message}) and no input_text fallback was provided.`);
      }

      console.warn(`[PIPELINE] ⚠️ Direct fetch failed (${err.message}). Using fallback input_text.`);
      eventBus.emitEvent("URL_EXTRACTION_FAILED", {
        url: cleanUrl,
        error: err.message,
        resolution: "Fallback to direct input_text",
      });

      const fallbackWordCount = fallbackText.split(/\s+/).filter(Boolean).length;
      sourceAudit = {
        sourceType: "FALLBACK_INPUT_TEXT",
        sourceIdentifier: `Fallback (URL failed: ${cleanUrl})`,
        sourceTitle: "Direct Text (Fallback)",
        extractedWordCount: fallbackWordCount,
        extractedCharCount: fallbackText.length,
        extractedText: fallbackText,
        scrapeError: err.message,
      };
      targetText = fallbackText;
    }
  } else {
    const wordCount = fallbackText.split(/\s+/).filter(Boolean).length;
    sourceAudit = {
      sourceType: "INPUT_TEXT",
      sourceIdentifier: "Direct Text Input",
      sourceTitle: "Direct Input Text",
      extractedWordCount: wordCount,
      extractedCharCount: fallbackText.length,
      extractedText: fallbackText,
    };
    targetText = fallbackText;
  }

  // Safety truncate to ~6,000 words
  const words = targetText.split(/\s+/).filter(Boolean);
  if (words.length > 6000) {
    targetText = words.slice(0, 6000).join(" ") + "\n\n[...Truncated to fit context window...]";
  }

  const { fullSystemPrompt, userPrompt } = buildInferencePrompt(
    systemPrompt,
    sourceAudit.sourceTitle,
    targetText
  );

  eventBus.emitEvent("INPUT_RESOLVED", {
    modelName,
    sourceType: sourceAudit.sourceType,
    sourceIdentifier: sourceAudit.sourceIdentifier,
    sourceTitle: sourceAudit.sourceTitle,
    wordCount: words.length,
    charCount: targetText.length,
    inputText: targetText,
    systemPrompt: fullSystemPrompt,
    userPrompt,
  });

  // 2. Telemetry Baseline
  const vmstatStart = getVmstatSwap();
  let peakProcessSwapMb = getMemorySnapshot().vmSwapMb;

  eventBus.emitEvent("INFERENCE_DISPATCHED", {
    serverUrl,
    targetModel: modelName,
    sourceType: sourceAudit.sourceType,
    wordCount: words.length,
    charCount: targetText.length,
  });

  const startTime = performance.now();
  const heartbeatTimer = setInterval(() => {
    const elapsed = Math.round((performance.now() - startTime) / 1000);
    const snap = getMemorySnapshot();
    peakProcessSwapMb = Math.max(peakProcessSwapMb, snap.vmSwapMb);
    console.log(
      `[HEARTBEAT] ⏳ Processing... (${elapsed}s) | RAM RSS: ${snap.vmRssMb} MB | Server Swap: ${snap.vmSwapMb} MB`
    );
  }, 10000);

  // 3. Execution Phase
  let inferenceResult;
  try {
    inferenceResult = await queryLlamaServer(serverUrl, modelName, fullSystemPrompt, userPrompt);
  } finally {
    clearInterval(heartbeatTimer);
  }

  const totalDurationMs = Math.round(performance.now() - startTime);
  const swapMetrics = finalizeSwapMetrics(peakProcessSwapMb, vmstatStart);

  // Token Metrics calculation
  const promptTokens = inferenceResult.usage.prompt_tokens;
  const completionTokens = inferenceResult.usage.completion_tokens;
  const promptTimeMs = inferenceResult.timings.prompt_ms
    ? Math.round(inferenceResult.timings.prompt_ms)
    : 0;
  let completionTimeMs = inferenceResult.timings.predicted_ms
    ? Math.round(inferenceResult.timings.predicted_ms)
    : 0;

  if (promptTimeMs === 0 && completionTimeMs === 0) {
    completionTimeMs = totalDurationMs;
  }

  const promptTokensPerSec = inferenceResult.timings.prompt_per_second
    ? Number(inferenceResult.timings.prompt_per_second.toFixed(2))
    : promptTimeMs > 0
    ? Number((promptTokens / (promptTimeMs / 1000)).toFixed(2))
    : 0;

  const completionTokensPerSec = inferenceResult.timings.predicted_per_second
    ? Number(inferenceResult.timings.predicted_per_second.toFixed(2))
    : completionTimeMs > 0
    ? Number((completionTokens / (completionTimeMs / 1000)).toFixed(2))
    : 0;

  const tokenMetrics: DetailedTokenMetrics = {
    prompt_tokens: promptTokens,
    completion_tokens: completionTokens,
    total_tokens: inferenceResult.usage.total_tokens,
    prompt_time_ms: promptTimeMs,
    completion_time_ms: completionTimeMs,
    total_duration_ms: totalDurationMs,
    prompt_tokens_per_second: promptTokensPerSec,
    completion_tokens_per_second: completionTokensPerSec,
  };

  eventBus.emitEvent("INFERENCE_COMPLETED", {
    modelName,
    sourceType: sourceAudit.sourceType,
    tokenMetrics,
    swapMetrics,
    rawOutput: inferenceResult.rawContent,
  });

  const structuredOutput: SummaryStructuredOutput = {
    ...inferenceResult.parsedAnalysis,
    compression_ratio: `${((inferenceResult.rawContent.length / targetText.length) * 100).toFixed(1)}%`,
    raw_output: inferenceResult.rawContent,
    source_audit: sourceAudit,
    token_metrics: tokenMetrics,
    swap_metrics: swapMetrics,
    input_text: targetText,
    system_prompt: fullSystemPrompt,
    user_prompt: userPrompt,
  };

  // Validate the final aggregate object with Zod contract
  const validatedFinalResult = SummaryStructuredOutputSchema.parse(structuredOutput);
  eventBus.emitEvent("OUTPUT_STRUCTURED", validatedFinalResult);

  return validatedFinalResult;
}