/** How is the caller's complete analysis read through the shared native transport? */
import { z } from "zod";
import type { OperationMetadata } from "@idhazh/common-contracts/schemas/operation-metadata";
import type { ModelRuntime } from "../../../services/summary-generator/src/config/load-model-runtime.js";
import { buildModelRequest, readModelContent } from "../../../services/summary-generator/src/services/model-request.service.js";
import { requestCompletion, type CompletionFetch } from "../../../services/summary-generator/src/services/request-completion.service.js";
import { RawModelAnalysisSchema, type RawModelAnalysis } from "./contracts/analysis-result.schema.js";
import type { NativeBounds } from "../../../services/summary-generator/src/config/load-generator-config.js";
import { loadAnalysisConfig, loadAnalysisSettings } from "./load-analysis-config.js";

const timings = z.object({
  prompt_n: z.number().nullable().optional(), prompt_ms: z.number().nullable().optional(),
  prompt_per_second: z.number().nullable().optional(), predicted_n: z.number().nullable().optional(),
  predicted_ms: z.number().nullable().optional(), predicted_per_second: z.number().nullable().optional(),
}).passthrough();
const reply = z.object({
  choices: z.array(z.object({
    message: z.object({
      content: z.string().nullable().optional(),
      reasoning_content: z.string().nullable().optional(),
    }).passthrough(),
  }).passthrough()).min(1),
  usage: z.object({
    prompt_tokens: z.number().nullable().optional(), completion_tokens: z.number().nullable().optional(),
    total_tokens: z.number().nullable().optional(),
  }).passthrough().nullable().optional(),
  timings: timings.nullable().optional(),
}).passthrough();
export type LlamaInferenceTimings = z.infer<typeof timings>;
export interface LlamaInferenceResponse {
  context: OperationMetadata;
  rawContent: string;
  parsedAnalysis: RawModelAnalysis;
  usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
  timings: LlamaInferenceTimings;
}
export function buildInferencePrompt(
  systemPrompt: string, documentTitle: string, documentText: string,
  analysisPrompt = loadAnalysisSettings(process.env.CONFIG_ROOT).analysisPrompt,
) {
  return {
    fullSystemPrompt: `${systemPrompt}\n\n${analysisPrompt}`,
    userPrompt: `Document Title: ${documentTitle}\n\nContent:\n"""\n${documentText}\n"""`,
  };
}
export async function queryLlamaServer(
  runtime: ModelRuntime, systemPrompt: string, userPrompt: string,
  context: OperationMetadata, onDispatched?: (context: OperationMetadata) => void,
  send?: CompletionFetch,
  bounds: NativeBounds = loadAnalysisConfig(process.env.CONFIG_ROOT),
  signal?: AbortSignal,
): Promise<LlamaInferenceResponse> {
  onDispatched?.(context);
  const payload = buildModelRequest(runtime, systemPrompt, userPrompt, { type: "json_object" });
  const response = reply.parse(await requestCompletion(runtime, payload, bounds, signal, send));
  const rawContent = response.choices[0].message.content ?? "";
  const answer = readModelContent(response, runtime);
  const jsonMatch = answer.match(/\{[\s\S]*\}/);
  const parsed: unknown = JSON.parse(jsonMatch ? jsonMatch[0] : answer);
  const parsedAnalysis = RawModelAnalysisSchema.parse(parsed);
  // These defaults retain the caller's existing saved measurement contract.
  const promptTokens = response.usage?.prompt_tokens ?? response.timings?.prompt_n ?? 0;
  const completionTokens = response.usage?.completion_tokens ?? response.timings?.predicted_n ?? 0;
  return {
    context, rawContent, parsedAnalysis,
    usage: {
      prompt_tokens: promptTokens, completion_tokens: completionTokens,
      total_tokens: response.usage?.total_tokens ?? promptTokens + completionTokens,
    },
    timings: response.timings ?? {},
  };
}
