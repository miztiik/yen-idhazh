/** How does one caller validate a bounded summary response and its request-local carrier? */
import { readTraceContext, writeTraceContext } from "@idhazh/common-contracts/propagate-trace-context";
import type { OperationMetadata } from "@idhazh/common-contracts/schemas/operation-metadata";
import {
  GENERATE_SUMMARY_PATH, summaryGeneratorUrl,
} from "../../../services/summary-generator/src/api/api-paths.js";
import type { GeneratorConfig } from "../../../services/summary-generator/src/config/load-generator-config.js";
import type { ModelRuntime } from "../../../services/summary-generator/src/config/load-model-runtime.js";
import { SummarizeRequestSchema, type SummarizeRequest } from "../../../services/summary-generator/src/schemas/request-payload.schema.js";
import { SummaryErrorSchema, SummaryResultSchema } from "../../../services/summary-generator/src/schemas/summary-result.schema.js";
import {
  BodyLimitError, cancelResponseBody, readBoundedText, type CompletionFetch,
} from "../../../services/summary-generator/src/services/request-completion.service.js";
import type { AnalysisConfig } from "./load-analysis-config.js";

export async function callSummaryApi(
  input: SummarizeRequest, context: OperationMetadata, generator: GeneratorConfig,
  config: AnalysisConfig, runtime: Pick<ModelRuntime, "timeout_seconds">,
  send: CompletionFetch = request => fetch(request), signal?: AbortSignal,
) {
  const request = SummarizeRequestSchema.parse(input);
  const body = JSON.stringify(request);
  if (Buffer.byteLength(body, "utf8") > config.max_native_request_bytes) {
    throw new BodyLimitError("request");
  }
  const deadline = AbortSignal.timeout(runtime.timeout_seconds * 1000 + config.body_read_timeout_ms);
  const cancelled = signal === undefined ? deadline : AbortSignal.any([signal, deadline]);
  cancelled.throwIfAborted();
  const response = await send(new Request(summaryGeneratorUrl(generator, GENERATE_SUMMARY_PATH), {
    method: "POST", headers: { "Content-Type": "application/json", ...writeTraceContext(context) },
    body, redirect: "error", signal: cancelled,
  }));
  const responseDeadline = AbortSignal.any([cancelled, AbortSignal.timeout(config.body_read_timeout_ms)]);
  if (response.headers.get("content-type")?.split(";", 1)[0]?.trim() !== "application/json"
    || ![null, "identity"].includes(response.headers.get("content-encoding"))) {
    await cancelResponseBody(response.body, responseDeadline);
    throw new Error("The summary API returned an unsupported representation.");
  }
  const value: unknown = JSON.parse(await readBoundedText(
    response.body, config.max_native_response_bytes, responseDeadline,
  ));
  if (!response.ok) {
    const failure = SummaryErrorSchema.parse(value);
    throw new Error(`The summary API refused the request (${failure.code}).`);
  }
  const result = SummaryResultSchema.parse(value);
  const apiContext = readTraceContext(Object.fromEntries(response.headers));
  if (!apiContext || apiContext.traceId !== context.traceId || apiContext.spanId === context.spanId) {
    throw new Error("The summary API returned an unrelated response carrier.");
  }
  return { result, apiContext };
}
