/** How does one HTTP request return only a bounded summary with its own trace carriers? */
import { performance } from "node:perf_hooks";
import { createChildContext, createRootContext } from "@idhazh/common-contracts/create-operation-context";
import { createCloudEvent } from "@idhazh/common-contracts/create-cloud-event";
import { readTraceContext, writeTraceContext } from "@idhazh/common-contracts/propagate-trace-context";
import { z } from "zod";
import { SUMMARY_GENERATOR_EVENT_SOURCE } from "../declare-event-source.js";
import { GeneratorLoggingSchema, type GeneratorConfig } from "../config/load-generator-config.js";
import type { ModelRuntime } from "../config/load-model-runtime.js";
import { SummarizeRequestSchema } from "../schemas/request-payload.schema.js";
import { summarizeText } from "../services/summarize-text.service.js";
import {
  BodyLimitError, cancelResponseBody, readBoundedText, type CompletionFetch,
} from "../services/request-completion.service.js";
import { GENERATE_SUMMARY_PATH, SUMMARY_GENERATOR_HEALTH_PATH } from "./api-paths.js";

export type SummaryHandlerOptions = {
  config: GeneratorConfig;
  runtime: ModelRuntime;
  systemPrompt: string;
  send?: CompletionFetch;
  writeEvent?: (event: unknown) => void;
};
const diagnostic = z.object({
  code: z.string(),
  duration_ms: z.number().nonnegative().finite(),
  prompt_sha256: z.string().regex(/^[a-f0-9]{64}$/).optional(),
}).strict();

export function createSummaryHandler(options: SummaryHandlerOptions) {
  return async (request: Request): Promise<Response> => {
    const incoming = readTraceContext(Object.fromEntries(request.headers));
    const context = incoming ? createChildContext(incoming) : createRootContext();
    const headers = { "Content-Type": "application/json", ...writeTraceContext(context) };
    const reply = (body: unknown, status: number) => new Response(JSON.stringify(body), { status, headers });
    const started = performance.now();
    const emit = (code: string, promptSha256?: string) => {
      const levels = GeneratorLoggingSchema.shape.level.options;
      const level = code === "SUMMARY_GENERATOR_COMPLETED" ? "INFO" :
        code === "GENERATE_SUMMARY_FAILED" ? "ERROR" : "WARNING";
      if (levels.indexOf(level) < levels.indexOf(options.config.logging.level)) return;
      const data = {
        code, duration_ms: performance.now() - started,
        ...(promptSha256 === undefined ? {} : { prompt_sha256: promptSha256 }),
      };
      const event = createCloudEvent({
        source: SUMMARY_GENERATOR_EVENT_SOURCE, type: code, context, data,
        parseData: value => diagnostic.parse(value),
      });
      const line = JSON.stringify(event);
      if (Buffer.byteLength(line, "utf8") > options.config.logging.max_event_bytes) {
        throw new Error("The diagnostic envelope exceeds its configured allowance.");
      }
      (options.writeEvent ?? (value => console.error(JSON.stringify(value))))(event);
    };
    const path = new URL(request.url).pathname;
    if (path === SUMMARY_GENERATOR_HEALTH_PATH && request.method !== "GET"
      || path === GENERATE_SUMMARY_PATH && request.method !== "POST") {
      return new Response(JSON.stringify({ error: "Method not allowed.", code: "METHOD_NOT_ALLOWED" }), {
        status: 405,
        headers: { ...headers, Allow: path === SUMMARY_GENERATOR_HEALTH_PATH ? "GET" : "POST" },
      });
    }
    if (path === SUMMARY_GENERATOR_HEALTH_PATH) {
      return reply({ status: "ok", version: options.config.version }, 200);
    }
    if (path !== GENERATE_SUMMARY_PATH) {
      return reply({ error: "Not found.", code: "NOT_FOUND" }, 404);
    }
    const fail = (code: string, status: number, message: string) => {
      try {
        emit(code);
      } catch {
        return reply({ error: "Summary diagnostics could not be recorded.", code: "GENERATE_SUMMARY_FAILED" }, 500);
      }
      return reply({ error: message, code }, status);
    };
    const deadline = new AbortController();
    const timeout = setTimeout(() => deadline.abort(), options.config.body_read_timeout_ms);
    let text: string;
    try {
      const declaredBytes = request.headers.get("content-length");
      if (declaredBytes !== null && /^\d+$/.test(declaredBytes)
        && Number(declaredBytes) > options.config.max_request_bytes) {
        try {
          await cancelResponseBody(request.body, AbortSignal.any([request.signal, deadline.signal]));
        } catch (cause) {
          throw new BodyLimitError("request", { cause });
        }
        throw new BodyLimitError("request");
      }
      text = await readBoundedText(request.body, options.config.max_request_bytes,
        AbortSignal.any([request.signal, deadline.signal]), "request");
    } catch (error) {
      if (error instanceof BodyLimitError) return fail("REQUEST_TOO_LARGE", 413, "The request is too large.");
      if (deadline.signal.aborted) return fail("REQUEST_BODY_TIMEOUT", 408, "The request body timed out.");
      return fail("INVALID_REQUEST", 400, "The summary request is invalid.");
    } finally {
      clearTimeout(timeout);
    }
    let input: z.infer<typeof SummarizeRequestSchema>;
    try {
      input = SummarizeRequestSchema.parse(JSON.parse(text));
    } catch {
      return fail("INVALID_REQUEST", 400, "The summary request contains invalid or unsupported fields.");
    }
    try {
      const result = await summarizeText(input, options.runtime, options.systemPrompt,
        options.config, request.signal, options.send);
      emit("SUMMARY_GENERATOR_COMPLETED", result.prompt_sha256);
      return reply(result, 200);
    } catch (error) {
      if (error instanceof BodyLimitError && error.boundary === "request") {
        return fail("REQUEST_TOO_LARGE", 413, "The native summary request is too large.");
      }
      return fail("GENERATE_SUMMARY_FAILED", 500, "The summary could not be generated.");
    }
  };
}
