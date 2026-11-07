/** How is one complete summary parsed from an independent native model reply? */
import { z } from "zod";
import type { ModelRuntime } from "../config/load-model-runtime.js";
import type { NativeBounds } from "../config/load-generator-config.js";
import {
  SummaryFieldsSchema, SummaryReportedModelSchema, SummaryUsageSchema,
} from "../schemas/summary-result.schema.js";
import { buildModelRequest, readModelContent } from "./model-request.service.js";
import { requestCompletion, type CompletionFetch } from "./request-completion.service.js";

const primaryChoice = z.object({
  index: z.literal(0).optional(),
  finish_reason: z.literal("stop"),
  message: z.object({
    content: z.string().nullable().optional(),
    reasoning_content: z.string().nullable().optional(),
  }).passthrough(),
}).passthrough();
const nativeReply = z.object({
  choices: z.array(z.unknown()).min(1),
  model: SummaryReportedModelSchema.optional().catch(null),
  usage: z.object({
    prompt_tokens: z.number().int().nonnegative().nullable().optional(),
    completion_tokens: z.number().int().nonnegative().nullable().optional(),
  }).passthrough().nullable().optional(),
  timings: z.object({
    prompt_n: z.number().int().nonnegative().nullable().optional(),
    predicted_n: z.number().int().nonnegative().nullable().optional(),
  }).passthrough().nullable().optional(),
}).passthrough();

export async function queryLlamaServer(
  runtime: ModelRuntime, systemPrompt: string, inputText: string,
  bounds: NativeBounds, signal?: AbortSignal, send?: CompletionFetch,
) {
  const payload = buildModelRequest(runtime, systemPrompt, inputText, { type: "json_object" });
  const response = nativeReply.parse(await requestCompletion(runtime, payload, bounds, signal, send));
  const choice = primaryChoice.parse(response.choices[0]);
  const answer = readModelContent({ choices: [choice] }, runtime);
  const data = SummaryFieldsSchema.parse(JSON.parse(answer));
  const usage = SummaryUsageSchema.parse({
    prompt_tokens: response.usage?.prompt_tokens ?? response.timings?.prompt_n ?? null,
    completion_tokens: response.usage?.completion_tokens ?? response.timings?.predicted_n ?? null,
  });
  return { data, model: response.model ?? null, usage };
}
