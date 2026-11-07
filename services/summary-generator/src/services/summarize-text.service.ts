/** Which effective prompt and summary belong to this fresh text request? */
import { createHash } from "node:crypto";
import type { ModelRuntime } from "../config/load-model-runtime.js";
import type { NativeBounds } from "../config/load-generator-config.js";
import { SummarizeRequestSchema, type SummarizeRequest } from "../schemas/request-payload.schema.js";
import { SummaryResultSchema, type SummaryResult } from "../schemas/summary-result.schema.js";
import { queryLlamaServer } from "./query-llama.service.js";
import type { CompletionFetch } from "./request-completion.service.js";

export async function summarizeText(
  input: SummarizeRequest, runtime: ModelRuntime, defaultPrompt: string,
  bounds: NativeBounds, signal?: AbortSignal, send?: CompletionFetch,
): Promise<SummaryResult> {
  const request = SummarizeRequestSchema.parse(input);
  const prompt = request.system_prompt ?? defaultPrompt;
  const result = await queryLlamaServer(runtime, prompt, request.input_text, bounds, signal, send);
  return SummaryResultSchema.parse({
    success: true,
    ...result,
    prompt_sha256: createHash("sha256").update(prompt, "utf8").digest("hex"),
    prompt_source: request.system_prompt === undefined ? "default" : "override",
  });
}
