/** How does one caller request preserve its full analysis, private events and measurements? */
import { performance } from "node:perf_hooks";
import { createChildContext } from "@idhazh/common-contracts/create-operation-context";
import type { OperationMetadata } from "@idhazh/common-contracts/schemas/operation-metadata";
import {
  type SummarizeRequest,
  type SummaryStructuredOutput,
  type DetailedTokenMetrics,
  SummarizeRequestSchema,
  SummaryStructuredOutputSchema,
} from "./contracts/export-analysis-schemas.js";
import { prepareApiInput } from "./prepare-api-input.js";
import {
  getVmstatSwap,
  getMemorySnapshot,
  finalizeSwapMetrics,
} from "./collect-measurements.js";
import {
  buildInferencePrompt,
  queryLlamaServer,
} from "./query-analysis.js";
import { PipelineEventBus } from "./publish-events.js";
import type { ModelRuntime } from "../../../services/summary-generator/src/config/load-model-runtime.js";
import type { CompletionFetch } from "../../../services/summary-generator/src/services/request-completion.service.js";
import { loadAnalysisSettings, type AnalysisSettings } from "./load-analysis-config.js";

export async function orchestratePipeline(
  requestInput: SummarizeRequest,
  eventBus: PipelineEventBus,
  runtime: ModelRuntime,
  context: OperationMetadata,
  send?: CompletionFetch,
  settings: AnalysisSettings = loadAnalysisSettings(process.env.CONFIG_ROOT),
  signal?: AbortSignal,
): Promise<SummaryStructuredOutput> {
  const validatedInput = SummarizeRequestSchema.parse(requestInput);
  const controls = settings.config;

  const systemPrompt = validatedInput.system_prompt;
  const serverUrl = runtime.base_url;
  const modelName = runtime.request.model;
  if (validatedInput.server_url && validatedInput.server_url.replace(/\/$/, "") !== serverUrl.replace(/\/$/, "")) {
    throw new Error("server_url must match the committed model_server.base_url.");
  }
  if (validatedInput.model_name && validatedInput.model_name !== modelName) {
    throw new Error("model_name must match the selected model declaration.");
  }

  const prepared = await prepareApiInput(validatedInput, context,
    progress => eventBus.emitEvent(progress.type, progress.data, progress.context),
    send, controls, signal);
  const targetText = prepared.input_text;
  const sourceAudit = prepared.source_audit;
  const inputContext = prepared.input_context;

  const { fullSystemPrompt, userPrompt } = buildInferencePrompt(
    systemPrompt,
    sourceAudit.sourceTitle,
    targetText,
    settings.analysisPrompt,
  );

  eventBus.emitEvent("INPUT_RESOLVED", {
    modelName,
    sourceType: sourceAudit.sourceType,
    sourceIdentifier: sourceAudit.sourceIdentifier,
    sourceTitle: sourceAudit.sourceTitle,
    wordCount: prepared.original_word_count,
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
          wordCount: prepared.original_word_count,
          charCount: targetText.length,
        }, operation);
        const startedAt = performance.now();
        const heartbeat = setInterval(() => {
          const snap = getMemorySnapshot();
          peakProcessSwapMb = Math.max(peakProcessSwapMb, snap.vmSwapMb);
          eventBus.recordDiagnostic({
            code: "INFERENCE_WAITING",
            traceId: operation.traceId,
            spanId: operation.spanId,
            elapsedSeconds: Math.round((performance.now() - startedAt) / 1000),
            rssMb: snap.vmRssMb,
            swapMb: snap.vmSwapMb,
          });
        }, controls.heartbeat_ms);
        timing = { startedAt, heartbeat };
      },
      send,
      controls,
      signal,
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