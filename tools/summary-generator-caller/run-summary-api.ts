/** How does one summary caller save its actual API response and publish its own report? */
import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";
import { createCloudEvent } from "@idhazh/common-contracts/create-cloud-event";
import { createChildContext, createRootContext } from "@idhazh/common-contracts/create-operation-context";
import { writeTraceContext } from "@idhazh/common-contracts/propagate-trace-context";
import {
  generatorRepositoryRoot, GeneratorLoggingSchema, readGeneratorConfig,
} from "../../services/summary-generator/src/config/load-generator-config.js";
import { loadModelRuntime } from "../../services/summary-generator/src/config/load-model-runtime.js";
import {
  isCompletionTimeout, type CompletionFetch,
} from "../../services/summary-generator/src/services/request-completion.service.js";
import type { SourceInput } from "./contracts/analysis-request.schema.js";
import {
  SUMMARY_WORKFLOW_VERSION, SUMMARY_WORKFLOW_EVENT_TYPE, SummaryWorkflowDataSchema, type SummaryWorkflowEvent,
} from "./contracts/summary-workflow.schema.js";
import { SUMMARY_GENERATOR_TESTS_EVENT_SOURCE } from "./declare-event-source.js";
import { callSummaryApi } from "./call-summary-api.js";
import { loadAnalysisConfig } from "./load-analysis-config.js";
import { prepareApiInput } from "./prepare-api-input.js";
import { renderSummaryReport } from "./render-summary-report.js";

type SummaryWorkflowOptions = {
  environment?: NodeJS.ProcessEnv;
  configRoot?: string;
  input?: SourceInput;
  systemPrompt?: string;
  send?: CompletionFetch;
  signal?: AbortSignal;
  stepSummaryPath?: string;
};

function saveFile(file: string, value: string) {
  const partial = `${file}.partial`;
  writeFileSync(partial, value, "utf8");
  renameSync(partial, file);
}

export async function runSummaryApi(options: SummaryWorkflowOptions = {}): Promise<SummaryWorkflowEvent> {
  const environment = options.environment ?? process.env;
  const configRoot = options.configRoot ?? environment.CONFIG_ROOT ?? path.join(generatorRepositoryRoot, "config");
  const config = loadAnalysisConfig(configRoot);
  const generator = readGeneratorConfig(configRoot);
  const runtime = loadModelRuntime(configRoot);
  const context = createRootContext();
  const started = performance.now();
  const prepared = await prepareApiInput(
    options.input ?? { url: environment.URL, input_text: environment.INPUT_TEXT },
    context, undefined, options.send, config, options.signal,
  );
  const prompt = options.systemPrompt ?? environment.SYSTEM_PROMPT;
  const request = {
    input_text: prepared.input_text,
    ...(prompt === undefined || prompt === "" ? {} : { system_prompt: prompt }),
  };
  const operation = createChildContext(context, {
    links: prepared.input_context ? [{
      traceId: prepared.input_context.traceId, spanId: prepared.input_context.spanId,
    }] : [],
  });
  const response = await callSummaryApi(request, operation, generator, config, runtime, options.send, options.signal);
  const carriers = writeTraceContext(response.apiContext);
  const event = createCloudEvent({
    source: SUMMARY_GENERATOR_TESTS_EVENT_SOURCE, type: SUMMARY_WORKFLOW_EVENT_TYPE, context: operation,
    data: {
      version: SUMMARY_WORKFLOW_VERSION, model_name: runtime.request.model, request,
      result: response.result, source_audit: prepared.source_audit,
      input_sha256: createHash("sha256").update(request.input_text, "utf8").digest("hex"),
      api_traceparent: carriers.traceparent,
      ...(carriers.tracestate === undefined ? {} : { api_tracestate: carriers.tracestate }),
      duration_ms: performance.now() - started,
      classifications: "not_collected", machine_readings: "not_collected",
    },
    parseData: value => SummaryWorkflowDataSchema.parse(value),
  });
  const report = renderSummaryReport(event);
  const directory = path.join(generatorRepositoryRoot, config.output_directory);
  mkdirSync(directory, { recursive: true });
  saveFile(path.join(directory, "summary-response.json"), JSON.stringify(response.result) + "\n");
  saveFile(path.join(directory, "summary-events.jsonl"), JSON.stringify(event) + "\n");
  saveFile(path.join(directory, "summary-report.md"), report);
  const stepSummary = options.stepSummaryPath ?? environment.GITHUB_STEP_SUMMARY;
  if (stepSummary) appendFileSync(stepSummary, report, "utf8");
  if (environment.GITHUB_OUTPUT) {
    appendFileSync(environment.GITHUB_OUTPUT, `output_directory=${config.output_directory}\n`, "utf8");
  }
  const levels = GeneratorLoggingSchema.shape.level.options;
  if (levels.indexOf(config.logging.level) <= levels.indexOf("INFO")) {
    const diagnostic = JSON.stringify({
      code: event.type, source: event.source, id: event.id, time: event.time,
      traceparent: event.traceparent, prompt_sha256: response.result.prompt_sha256,
    });
    if (Buffer.byteLength(diagnostic, "utf8") > config.logging.max_event_bytes) {
      throw new Error("The caller diagnostic exceeds its configured allowance.");
    }
    console.error(diagnostic);
  }
  return event;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const event = await runSummaryApi();
    process.stdout.write(JSON.stringify(event.data.result) + "\n");
  } catch (error) {
    console.error(JSON.stringify({
      code: "SUMMARY_API_FAILED", source: SUMMARY_GENERATOR_TESTS_EVENT_SOURCE,
      failure: { kind: isCompletionTimeout(error) ? "timeout" : "api_failure" },
    }));
    process.exitCode = 1;
  }
}
