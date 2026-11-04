/** How does one request produce its complete summary without sharing operation state? */
import { performance } from "node:perf_hooks";
import { createChildContext } from "@idhazh/common-contracts/create-operation-context";
import type { OperationMetadata } from "@idhazh/common-contracts/schemas/operation-metadata";
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
import type { ModelRuntime } from "../config/load-model-runtime.js";

export async function orchestratePipeline(
  requestInput: SummarizeRequest,
  eventBus: PipelineEventBus,
  runtime: ModelRuntime,
  context: OperationMetadata,
): Promise<SummaryStructuredOutput> {
  const validatedInput = SummarizeRequestSchema.parse(requestInput);

  const cleanUrl = (validatedInput.url || "").trim();
  const fallbackText = (validatedInput.input_text || "").trim();
  const systemPrompt = validatedInput.system_prompt;
  const serverUrl = runtime.base_url;
  const modelName = runtime.request.model;
  if (validatedInput.server_url && validatedInput.server_url.replace(/\/$/, "") !== serverUrl.replace(/\/$/, "")) {
    throw new Error("server_url must match the committed model_server.base_url.");
  }
  if (validatedInput.model_name && validatedInput.model_name !== modelName) {
    throw new Error("model_name must match the selected model declaration.");
  }

  let targetText = fallbackText;
  let sourceAudit: SourceAudit;
  let inputContext: OperationMetadata | undefined;

  // 1. Ingestion Phase (URL direct scrape or fallback)
  if (cleanUrl.length > 0) {
    const extractionContext = createChildContext(context);

    try {
      const extracted = await extractContentFromUrl(
        cleanUrl,
        extractionContext,
        progress => eventBus.emitEvent(progress.type, progress.data, progress.context),
      );
      inputContext = extracted.context;

      sourceAudit = {
        sourceType: "URL",
        sourceIdentifier: cleanUrl,
        sourceTitle: extracted.title,
        extractedWordCount: extracted.wordCount,
        extractedCharCount: extracted.content.length,
        extractedText: extracted.content,
      };
      targetText = extracted.content;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Source extraction failed.";
      if (!fallbackText) {
        throw new Error(`Scraping URL failed (${message}) and no input_text fallback was provided.`);
      }

      eventBus.emitEvent("URL_EXTRACTION_FAILED", {
        url: cleanUrl,
        error: message,
        resolution: "Fallback to direct input_text",
      }, extractionContext);

      const fallbackWordCount = fallbackText.split(/\s+/).filter(Boolean).length;
      sourceAudit = {
        sourceType: "FALLBACK_INPUT_TEXT",
        sourceIdentifier: `Fallback (URL failed: ${cleanUrl})`,
        sourceTitle: "Direct Text (Fallback)",
        extractedWordCount: fallbackWordCount,
        extractedCharCount: fallbackText.length,
        extractedText: fallbackText,
        scrapeError: message,
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
  }, context);

  // 2. Telemetry Baseline
  const vmstatStart = getVmstatSwap();
  let peakProcessSwapMb = getMemorySnapshot().vmSwapMb;

  const inferenceContext = createChildContext(context, {
    links: inputContext ? [{ traceId: inputContext.traceId, spanId: inputContext.spanId }] : [],
  });

  // 3. Execution Phase
  let timing: { startedAt: number; heartbeat: ReturnType<typeof setInterval> } | undefined;
  let inferenceResult;
  try {
    inferenceResult = await queryLlamaServer(
      runtime,
      fullSystemPrompt,
      userPrompt,
      inferenceContext,
      operation => {
        eventBus.emitEvent("INFERENCE_DISPATCHED", {
          serverUrl,
          targetModel: modelName,
          sourceType: sourceAudit.sourceType,
          wordCount: words.length,
          charCount: targetText.length,
        }, operation);
        const startedAt = performance.now();
        const heartbeat = setInterval(() => {
          const snap = getMemorySnapshot();
          peakProcessSwapMb = Math.max(peakProcessSwapMb, snap.vmSwapMb);
          console.error(JSON.stringify({
            code: "INFERENCE_WAITING",
            traceId: operation.traceId,
            spanId: operation.spanId,
            elapsedSeconds: Math.round((performance.now() - startedAt) / 1000),
            rssMb: snap.vmRssMb,
            swapMb: snap.vmSwapMb,
          }));
        }, 10000);
        timing = { startedAt, heartbeat };
      },
    );
  } finally {
    if (timing) clearInterval(timing.heartbeat);
  }

  if (!timing) throw new Error("Inference completed without dispatch.");
  const totalDurationMs = Math.round(performance.now() - timing.startedAt);
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
  }, inferenceResult.context);

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
  eventBus.emitEvent("OUTPUT_STRUCTURED", validatedFinalResult, context);

  return validatedFinalResult;
}