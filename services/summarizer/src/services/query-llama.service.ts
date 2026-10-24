import http from "node:http";
import https from "node:https";
import type { ModelRuntime } from "../config/load-model-runtime.js";
import { buildModelRequest, readModelContent } from "./model-request.service.js";
import { RawModelAnalysisSchema, type RawModelAnalysis } from "../schemas/export-all-schemas.js";

export interface LlamaInferenceTimings {
  prompt_n?: number;
  prompt_ms?: number;
  prompt_per_second?: number;
  predicted_n?: number;
  predicted_ms?: number;
  predicted_per_second?: number;
}

export interface LlamaInferenceResponse {
  rawContent: string;
  parsedAnalysis: RawModelAnalysis;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  timings: LlamaInferenceTimings;
}

function postOpenAIChatCompletion(urlStr: string, payload: unknown, timeoutSeconds: number): Promise<any> {
  return new Promise((resolve, reject) => {
    const targetUrl = new URL(urlStr);
    const bodyData = JSON.stringify(payload);

    const transport = targetUrl.protocol === "https:" ? https : http;
    const req = transport.request(
      targetUrl,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(bodyData),
        },
      },
      (res) => {
        let raw = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => (raw += chunk));
        res.on("end", () => {
          if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
            try {
              resolve(JSON.parse(raw));
            } catch {
              reject(new Error(`Invalid JSON response: ${raw}`));
            }
          } else {
            reject(new Error(`llama-server returned HTTP ${res.statusCode}: ${raw}`));
          }
        });
      }
    );

    req.on("error", reject);
    const deadline = setTimeout(() => req.destroy(new Error("Model request timed out.")), timeoutSeconds * 1000);
    req.on("close", () => clearTimeout(deadline));
    req.write(bodyData);
    req.end();
  });
}

export function buildInferencePrompt(systemPrompt: string, documentTitle: string, documentText: string) {
  const fullSystemPrompt = `${systemPrompt}

You MUST analyze the text and output ONLY a valid JSON object matching this exact schema:
{
  "headline": "A concise, descriptive headline for the document",
  "executive_summary": "Thorough, comprehensive narrative summary of the document. Do not artificially abbreviate or constrain the summary to a fixed sentence count; scale the length proportionally to capture the full depth, arguments, and substance of the content.",
  "key_points": [
    "Comprehensive array of all major arguments, key findings, and essential takeaways from the text (scale the number of points to the depth of the text)"
  ],
  "sentiment": "positive" | "neutral" | "negative" | "mixed",
  "stance_on_change": "conservatism" | "progressivism" | "not_applicable",
  "stance_on_economic_power": "socialism" | "libertarianism" | "not_applicable",
  "stance_on_state_power": "statism" | "constitutionalism" | "not_applicable",
  "stance_on_borders": "nationalism" | "internationalism" | "not_applicable",
  "stance_on_personal_sphere": "civil_libertarianism" | "communitarianism" | "not_applicable"
}

Definitions for classification axes:
- stance_on_change: Evaluates what to do about the existing arrangement.
  * conservatism: Maintain, protect, or return to established structures.
  * progressivism: Reform, replace, or advance beyond existing arrangements.
  * not_applicable: Topic does not address institutional or social arrangements.
- stance_on_economic_power: Evaluates who should hold economic power.
  * socialism: Collective, public, state, or democratic control of economic resources.
  * libertarianism: Private ownership, decentralized free markets, and property rights.
  * not_applicable: Topic does not address economic power allocation.
- stance_on_state_power: Evaluates whether state power is centralized or checked.
  * statism: Strong centralized government authority is necessary or justified.
  * constitutionalism: State power must be strictly constrained, distributed, and checked by rule of law.
  * not_applicable: Topic does not discuss governance authority.
- stance_on_borders: Evaluates whether solutions are inside or outside national borders.
  * nationalism: Focus on domestic sovereignty, borders, and national self-interest.
  * internationalism: Global cooperation, open borders, transnational agreements.
  * not_applicable: Topic does not address borders or national scope.
- stance_on_personal_sphere: Evaluates whether an individual retains an inviolable personal sphere.
  * civil_libertarianism: Strict individual autonomy and privacy that nobody may enter.
  * communitarianism: Social obligations, collective well-being, or communal cohesion supersede individual autonomy.
  * not_applicable: Topic does not discuss individual vs communal rights.`;

  const userPrompt = `Document Title: ${documentTitle}\n\nContent:\n"""\n${documentText}\n"""`;

  return { fullSystemPrompt, userPrompt };
}

export async function queryLlamaServer(
  runtime: ModelRuntime,
  systemPrompt: string,
  userPrompt: string
): Promise<LlamaInferenceResponse> {
  const payload = buildModelRequest(runtime, systemPrompt, userPrompt, { type: "json_object" });

  const endpoint = new URL("/v1/chat/completions", runtime.base_url).href;
  const response = await postOpenAIChatCompletion(endpoint, payload, runtime.timeout_seconds);
  const rawContent = response.choices?.[0]?.message?.content ?? "";
  const answerContent = readModelContent(response, runtime);

  let parsedJson: unknown;
  try {
    const jsonMatch = answerContent.match(/\{[\s\S]*\}/);
    parsedJson = JSON.parse(jsonMatch ? jsonMatch[0] : answerContent);
  } catch (err: any) {
    throw new Error(`Failed to parse JSON from model output: ${err.message}. Raw: ${rawContent}`);
  }

  const parseResult = RawModelAnalysisSchema.safeParse(parsedJson);
  if (!parseResult.success) {
    throw new Error(`Model response failed RawModelAnalysisSchema: ${parseResult.error.message}`);
  }

  const promptTokens = response.usage?.prompt_tokens ?? response.timings?.prompt_n ?? 0;
  const completionTokens = response.usage?.completion_tokens ?? response.timings?.predicted_n ?? 0;

  return {
    rawContent,
    parsedAnalysis: parseResult.data,
    usage: {
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      total_tokens: response.usage?.total_tokens ?? promptTokens + completionTokens,
    },
    timings: response.timings || {},
  };
}