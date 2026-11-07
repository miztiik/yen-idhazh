/** Do the real workflow writer, saved-input reader and foreign boundary preserve each result? */
import { expect, test } from "bun:test";
import { copyFile, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { join } from "node:path";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";
import {
  createRootContext,
  readTraceContext,
} from "../../../packages/common-contracts/src/index.ts";
import {
  AIEventPipeline, publishStepSummary, WORKFLOW_EVENT_SOURCE,
} from "../../../.github/scripts/ai-pipeline.ts";
import { readPipelineEvents, selectStructuredOutputs, type PipelineEvent } from "../read-pipeline-events.ts";
import {
  CoverageApiFailure,
  prepareEvaluationRequest,
  readEvaluationResponse,
} from "../prepare-evaluation-request.ts";
import {
  CoverageApiConfigurationSchema,
  readCoverageSettings,
  resolveCoverageApiSettings,
} from "../read-coverage-settings.ts";

const fixtures = new URL("../../../tests/fixtures/typescript-metadata/", import.meta.url);
const outputPath = fileURLToPath(new URL("workflow-output-event.json", fixtures));

function readSavedOutput() {
  const [event] = selectStructuredOutputs(readPipelineEvents(outputPath));
  if (!event) throw new Error("The named workflow output recording is missing.");
  return event;
}

function readProducer(event: PipelineEvent) {
  const context = readTraceContext({ traceparent: event.traceparent, tracestate: event.tracestate });
  if (!context) throw new Error("The recorded producer context is invalid.");
  return context;
}

async function withDirectory(run: (directory: string) => Promise<void>) {
  const directory = join(fileURLToPath(new URL("../../../backend/var/", import.meta.url)),
    `workflow-handoff-${randomUUID()}`);
  await mkdir(directory, { recursive: true });
  try {
    await run(directory);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

test("the production reader hands unchanged text to the strict coverage request builder", async () => {
  const saved = await readFile(outputPath, "utf8");
  const event = readSavedOutput();
  const original = structuredClone(event);
  const phase = createRootContext();
  const prepared = prepareEvaluationRequest(event, phase);
  const expected = await Bun.file(new URL("evaluator-request.json", fixtures)).json();
  expect(prepared.request).toEqual({
    source_text: expected.sourceText,
    summary_text: expected.summaryText,
  });
  expect(Object.keys(prepared.request)).toEqual(["source_text", "summary_text"]);
  expect(prepared.request.source_text).toBe(event.data.result.source_audit.extractedText);
  expect(prepared.request.summary_text).toBe(event.data.result.analytic_synthesis);
  const producer = readProducer(event);
  expect(prepared.context.traceId).toBe(phase.traceId);
  expect(prepared.context.parentSpanId).toBe(phase.spanId);
  expect(prepared.context.links).toEqual([{ traceId: producer.traceId, spanId: producer.spanId }]);
  expect(event).toEqual(original);
  expect(await readFile(outputPath, "utf8")).toBe(saved);
});

test("distinct occurrences and input producers survive saved handoff into independent phase operations", async () =>
  withDirectory(async directory => {
    const saved = readSavedOutput();
    const path = join(directory, "events.jsonl");
    const first = new AIEventPipeline(saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, path);
    const second = new AIEventPipeline(saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, path);
    const result = {
      ...saved.data.result,
      source_audit: { ...saved.data.result.source_audit, feedAudit: undefined },
      swap_metrics: { ...saved.data.result.swap_metrics, diagnostics_error: undefined },
    };
    first.logEvent("INPUT_RESOLVED", { wordCount: saved.data.result.source_audit.extractedWordCount });
    const produced = [
      first.logEvent("OUTPUT_STRUCTURED", result),
      first.logEvent("OUTPUT_STRUCTURED", saved.data.result),
      second.logEvent("OUTPUT_STRUCTURED", {
        ...saved.data.result,
        analytic_synthesis: "A separate saved summary.",
        source_audit: { ...saved.data.result.source_audit, extractedText: "A separate saved source." },
      }),
    ];
    expect(new Set(produced.map(event => event.id)).size).toBe(produced.length);
    expect(produced.every(event => event.source === "/workflows/ai-pipeline")).toBe(true);
    expect(produced[0]!.data.result).toEqual(saved.data.result);
    expect(produced[0]!.traceparent).toBe(produced[1]!.traceparent);
    const bytes = await readFile(path, "utf8");
    const selected = selectStructuredOutputs(readPipelineEvents(path));
    expect(produced).toEqual(selected);
    const evaluation = new AIEventPipeline(saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, path);
    evaluation.loadPriorEvents();
    const prepared = selected.map(event =>
      prepareEvaluationRequest(event, evaluation.context));
    expect(new Set(prepared.map(value => value.context.spanId)).size).toBe(selected.length);
    for (const [index, input] of selected.entries()) {
      const current = prepared[index]!;
      const producer = readProducer(input);
      expect(current.context.traceId).toBe(evaluation.context.traceId);
      expect(current.context.traceId).not.toBe(producer.traceId);
      expect(current.context.parentSpanId).toBe(evaluation.context.spanId);
      expect(current.context.links).toEqual([{ traceId: producer.traceId, spanId: producer.spanId }]);
      expect(current.request.source_text).toBe(input.data.result.source_audit.extractedText);
      expect(current.request.summary_text).toBe(input.data.result.analytic_synthesis);
    }
    expect(prepared[2]!.context.links).not.toEqual(prepared[0]!.context.links);
    expect(prepared[2]!.request.source_text).not.toBe(prepared[0]!.request.source_text);
    const anotherPhase = new AIEventPipeline(saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, path);
    expect(anotherPhase.context.traceId).not.toBe(evaluation.context.traceId);
    expect(await readFile(path, "utf8")).toBe(bytes);
  }));

test("the foreign response keeps its machine measurements through native event readback", async () =>
  withDirectory(async directory => {
    const saved = readSavedOutput();
    const response = await Bun.file(new URL("evaluator-response.json", fixtures)).json();
    const originalResponse = structuredClone(response);
    const received = readEvaluationResponse(response);
    expect(received.metrics).toEqual(response.metrics);
    expect(received.serverTelemetry).toEqual(response.event.payload.serverTelemetry);
    const path = join(directory, "events.jsonl");
    const evaluation = new AIEventPipeline(saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, path);
    const { context } = prepareEvaluationRequest(saved, evaluation.context);
    const measurements = { serverTelemetry: received.serverTelemetry };
    const enriched = { ...saved.data.result, quality_metrics: received.metrics };
    evaluation.logEvent("EVALUATION_SERVER_TELEMETRY", measurements, context);
    evaluation.logEvent("OUTPUT_ENRICHED", enriched, context);
    const [telemetry, output] = readPipelineEvents(path);
    expect(telemetry!.data.result).toEqual(measurements);
    expect(output!.data.result).toEqual(enriched);
    expect(readProducer(telemetry!).spanId).toBe(context.spanId);
    expect(readProducer(output!).spanId).toBe(context.spanId);
    expect(response).toEqual(originalResponse);
    expect(() => readEvaluationResponse({ ...response, metrics: { ...response.metrics, fluency: "invalid" } }))
      .toThrow("INVALID_EVALUATION_METRICS");
    const invalidTelemetry = structuredClone(response);
    invalidTelemetry.event.payload.serverTelemetry.duration_ms = "invalid";
    expect(() => readEvaluationResponse(invalidTelemetry)).toThrow("INVALID_EVALUATION_SERVER_TELEMETRY");
  }));

test.each([
  ["QUEUE_FULL", 429],
  ["QUEUE_TIMEOUT", 503],
  ["WORKER_NOT_READY", 503],
  ["EVALUATION_TIMEOUT", 504],
  ["INVALID_MODEL_OUTPUT", 500],
  ["WORKER_EXITED", 500],
] as const)("a native %s refusal stays a failed target without partial metrics", (code, status) => {
  try {
    readEvaluationResponse({
      error: { code, type: "api_error", message: "PrivateResponseMessageCanary" },
    }, status);
    throw new Error("A failed evaluation was accepted");
  } catch (error) {
    expect(error).toBeInstanceOf(CoverageApiFailure);
    expect((error as CoverageApiFailure).code).toBe(code);
    expect((error as CoverageApiFailure).httpStatus).toBe(status);
    expect((error as Error).message).not.toContain("PrivateResponseMessageCanary");
  }
});

test("the caller resolves the actual committed listener and complete transport bounds", () => {
  const settings = readCoverageSettings();
  expect(settings.evaluateUrl).toContain("/api/2026-11-05/evaluate-summary-coverage");
  expect(settings.maxRequestBytes).toBeGreaterThan(0);
  expect(settings.maxResponseBytes).toBeGreaterThan(0);
  expect(settings.requestTimeoutMs).toBeGreaterThan(0);
  expect(settings.evaluateUrl).not.toContain(":9933");
});

function apiConfiguration() {
  const listener = {
    host: "127.0.0.1" as const, port: 4010, max_body_bytes: 1200, body_read_timeout_ms: 30,
  };
  return {
    version: "2026-11-07" as const,
    listeners: {
      hhem: listener,
      unieval: { ...listener, port: 4011 },
      coverage: { ...listener, host: "::1" as const, port: 4012, max_body_bytes: 2400 },
    },
    logging: { level: "INFO" as const, max_event_bytes: 3200 },
    log_directory: "backend/var/scorer-logs",
    shutdown_timeout_ms: 20000,
  };
}

test("coverage resolves its authored modern origin and preserves an explicit legacy listener", () => {
  const modern = apiConfiguration();
  const selected = resolveCoverageApiSettings(modern);
  expect(selected.listener).toEqual(modern.listeners.coverage);
  expect(selected.enabled_routes).toEqual(["coverage"]);
  const legacy = {
    version: modern.version,
    listener: modern.listeners.hhem,
    enabled_routes: ["hhem", "unieval"],
    logging: modern.logging,
    log_directory: modern.log_directory,
    shutdown_timeout_ms: modern.shutdown_timeout_ms,
  };
  expect(resolveCoverageApiSettings(legacy)).toEqual({
    ...legacy, enabled_routes: ["coverage"],
  });
});

test.each(["missing", "unknown", "collision", "mixed", "version", "bound", "routes"])(
  "invalid %s API settings fail without selecting another scorer or destination",
  fault => {
    const modern = apiConfiguration();
    let value: unknown = modern;
    if (fault === "missing") {
      const { coverage: _removed, ...listeners } = modern.listeners;
      value = { ...modern, listeners };
    } else if (fault === "unknown") {
      value = { ...modern, listeners: { ...modern.listeners, other: modern.listeners.hhem } };
    } else if (fault === "collision") {
      value = { ...modern, listeners: { ...modern.listeners, coverage: modern.listeners.hhem } };
    } else if (fault === "mixed") {
      value = { ...modern, listener: modern.listeners.coverage, enabled_routes: ["coverage"] };
    } else if (fault === "version") {
      value = { ...modern, version: "2026-11-05" };
    } else if (fault === "bound") {
      value = { ...modern, listeners: { ...modern.listeners,
        coverage: { ...modern.listeners.coverage, max_body_bytes: 0 } } };
    } else {
      const { listeners: _removed, ...shared } = modern;
      value = { ...shared, listener: modern.listeners.coverage, enabled_routes: ["coverage", "coverage"] };
    }
    expect(CoverageApiConfigurationSchema.safeParse(value).success).toBe(false);
    expect(() => resolveCoverageApiSettings(value)).toThrow();
  },
);

test("the real coverage reader follows changed committed listener and transport bounds", async () =>
  withDirectory(async directory => {
    const api = apiConfiguration();
    await mkdir(join(directory, "config", "summary-evals", "unieval-evaluator"), { recursive: true });
    await writeFile(join(directory, "config", "summary-evals", "api.json"), JSON.stringify(api));
    await writeFile(join(directory, "config", "summary-evals", "unieval-evaluator", "coverage.json"),
      JSON.stringify({
        evaluation: { timeout_ms: 40 }, queue: { wait_timeout_ms: 50 },
        worker: { shutdown_timeout_ms: 60, max_reply_bytes: 4800 },
      }));
    expect(readCoverageSettings(directory)).toEqual({
      evaluateUrl: "http://[::1]:4012/api/2026-11-05/evaluate-summary-coverage",
      maxRequestBytes: 2400, maxResponseBytes: 4800, requestTimeoutMs: 180,
    });
    api.listeners.coverage.port = 4022;
    api.listeners.coverage.max_body_bytes = 2500;
    await writeFile(join(directory, "config", "summary-evals", "api.json"), JSON.stringify(api));
    const changed = readCoverageSettings(directory);
    expect(changed.evaluateUrl).toBe("http://[::1]:4022/api/2026-11-05/evaluate-summary-coverage");
    expect(changed.maxRequestBytes).toBe(2500);
  }));

test("metrics-only reporting preserves scores and explicitly leaves machine readings uncollected", async () =>
  withDirectory(async directory => {
    const saved = readSavedOutput();
    const historic = await Bun.file(new URL("evaluator-response.json", fixtures)).json();
    const received = readEvaluationResponse({ status: "success", metrics: historic.metrics });
    expect(received.serverTelemetry).toBeUndefined();
    const pipeline = new AIEventPipeline(
      saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, join(directory, "events.jsonl"),
    );
    pipeline.logEvent("EVALUATION_SERVER_TELEMETRY", {
      sourceIdentifier: saved.data.result.source_audit.sourceIdentifier,
      serverTelemetry: historic.event.payload.serverTelemetry,
    });
    pipeline.logEvent("QUALITY_EVALUATION_STARTED", { articleCount: 1 });
    pipeline.logEvent("QUALITY_EVALUATION_COMPLETED", {
      sourceIdentifier: saved.data.result.source_audit.sourceIdentifier, metrics: received.metrics,
    });
    const previous = process.env.GITHUB_STEP_SUMMARY;
    const path = join(directory, "report.md");
    process.env.GITHUB_STEP_SUMMARY = path;
    try {
      const output = { ...saved.data.result, quality_metrics: received.metrics };
      publishStepSummary(
        "eval", "recorded-model", [output], pipeline.getEventHistory(), output.inference_params,
      );
      const report = await readFile(path, "utf8");
      expect(report).toContain(String(received.metrics.overall_consistency));
      expect(report).toContain(`${received.metrics.chunk_coverage_percent}%`);
      expect(report).toContain("Machine readings: uncollected for this evaluation phase.");
      expect(report).not.toContain("Historical evaluator measurements:");
    } finally {
      if (previous === undefined) delete process.env.GITHUB_STEP_SUMMARY;
      else process.env.GITHUB_STEP_SUMMARY = previous;
    }
  }));

test("a historical measured response remains readable and reportable without a new measurement", async () =>
  withDirectory(async directory => {
    const saved = readSavedOutput();
    const historic = await Bun.file(new URL("evaluator-response.json", fixtures)).json();
    const received = readEvaluationResponse(historic);
    const pipeline = new AIEventPipeline(
      saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, join(directory, "events.jsonl"),
    );
    pipeline.logEvent("QUALITY_EVALUATION_STARTED", { articleCount: 1 });
    pipeline.logEvent("EVALUATION_SERVER_TELEMETRY", {
      sourceIdentifier: saved.data.result.source_audit.sourceIdentifier,
      serverTelemetry: received.serverTelemetry,
    });
    const path = join(directory, "historic-report.md");
    const previous = process.env.GITHUB_STEP_SUMMARY;
    process.env.GITHUB_STEP_SUMMARY = path;
    try {
      const output = { ...saved.data.result, quality_metrics: received.metrics };
      publishStepSummary(
        "eval", "recorded-model", [output], pipeline.getEventHistory(), output.inference_params,
      );
      const report = await readFile(path, "utf8");
      expect(report).toContain("Historical evaluator measurements:");
      expect(report).toContain(`${received.serverTelemetry!.duration_ms} ms`);
      expect(report).not.toContain("Machine readings: uncollected");
    } finally {
      if (previous === undefined) delete process.env.GITHUB_STEP_SUMMARY;
      else process.env.GITHUB_STEP_SUMMARY = previous;
    }
  }));

test("a failed target is unavailable rather than a zero-valued coverage success", async () =>
  withDirectory(async directory => {
    const saved = readSavedOutput();
    const path = join(directory, "failed-report.md");
    const previous = process.env.GITHUB_STEP_SUMMARY;
    process.env.GITHUB_STEP_SUMMARY = path;
    try {
      const output = { ...saved.data.result, quality_metrics: undefined };
      publishStepSummary("eval", "recorded-model", [output], [saved], output.inference_params);
      const report = await readFile(path, "utf8");
      expect(report).toContain("N/A");
      expect(report).toContain("Evaluation failed: source coverage did not return complete metrics.");
      expect(report).not.toContain("`0%`");
      expect(report).not.toContain("for stack traces");
    } finally {
      if (previous === undefined) delete process.env.GITHUB_STEP_SUMMARY;
      else process.env.GITHUB_STEP_SUMMARY = previous;
    }
  }));

test("resuming keeps the cumulative counter while each new log gap uses the phase clock", async () =>
  withDirectory(async directory => {
    const saved = readSavedOutput();
    const path = join(directory, "events.jsonl");
    await copyFile(outputPath, path);
    const pipeline = new AIEventPipeline(saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, path);
    const beforeLoad = performance.now();
    pipeline.loadPriorEvents();
    const afterLoad = performance.now();
    const beforeFirst = performance.now();
    const first = pipeline.logEvent("QUALITY_EVALUATION_STARTED", { articleCount: 1 });
    const afterFirst = performance.now();
    expect(first.data.durationMs).toBeGreaterThanOrEqual(Math.max(0, Math.floor(beforeFirst - afterLoad)));
    expect(first.data.durationMs).toBeLessThanOrEqual(Math.ceil(afterFirst - beforeLoad));
    expect(first.data.cumulativeMs - saved.data.cumulativeMs)
      .toBeGreaterThanOrEqual(Math.floor(beforeFirst - afterLoad));
    expect(first.data.cumulativeMs - saved.data.cumulativeMs)
      .toBeLessThanOrEqual(Math.ceil(afterFirst - beforeLoad));
    const beforeSecond = performance.now();
    const second = pipeline.logEvent("QUALITY_EVALUATION_BATCH_COMPLETED", { evaluatedCount: 1 });
    const afterSecond = performance.now();
    expect(second.data.durationMs).toBeGreaterThanOrEqual(Math.max(0, Math.floor(beforeSecond - afterFirst)));
    expect(second.data.durationMs).toBeLessThanOrEqual(Math.ceil(afterSecond - beforeFirst));
    expect(readPipelineEvents(path)[0]).toEqual(saved);
  }));

test.each(["json", "carrier", "measurement", "result", "blank"])(
  "a malformed saved %s record fails the real reader and continuation without rewriting the file",
  async failure => withDirectory(async directory => {
    const saved = readSavedOutput();
    const malformed = {
      json: "{",
      carrier: JSON.stringify({ ...saved, traceparent: "invalid" }),
      measurement: JSON.stringify({ ...saved, data: { ...saved.data, durationMs: "invalid" } }),
      result: JSON.stringify({ ...saved, data: {
        ...saved.data, result: { ...saved.data.result, source_audit: {
          ...saved.data.result.source_audit, extractedText: null,
        } },
      } }),
      blank: "",
    }[failure]!;
    const path = join(directory, "events.jsonl");
    const content = `${JSON.stringify(saved)}\n${malformed}\n`;
    await writeFile(path, content);
    expect(() => readPipelineEvents(path)).toThrow("INVALID_PIPELINE_EVENT at line 2");
    const pipeline = new AIEventPipeline(saved.data.result.runner_metadata, WORKFLOW_EVENT_SOURCE, path);
    expect(() => pipeline.loadPriorEvents()).toThrow("INVALID_PIPELINE_EVENT at line 2");
    expect(await readFile(path, "utf8")).toBe(content);
  }),
);

test("empty input selects no work and missing input fails rather than rerunning inference", async () =>
  withDirectory(async directory => {
    const path = join(directory, "empty.jsonl");
    await writeFile(path, "");
    expect(selectStructuredOutputs(readPipelineEvents(path))).toEqual([]);
    expect(() => readPipelineEvents(join(directory, "absent.jsonl"))).toThrow("PIPELINE_EVENTS_READ_FAILED");
  }));

test("the actual report reads the saved event identity and both stored measurements", async () =>
  withDirectory(async directory => {
    const event = readSavedOutput();
    const path = join(directory, "summary.md");
    const previous = process.env.GITHUB_STEP_SUMMARY;
    process.env.GITHUB_STEP_SUMMARY = path;
    try {
      publishStepSummary("infer", "recorded-model", [event.data.result], [event], event.data.result.inference_params);
      const report = await readFile(path, "utf8");
      expect(report).toContain(event.id);
      expect(report).toContain(event.time);
      expect(report).toContain(`+${event.data.durationMs} ms`);
      expect(report).toContain(`${event.data.cumulativeMs} ms`);
    } finally {
      if (previous === undefined) delete process.env.GITHUB_STEP_SUMMARY;
      else process.env.GITHUB_STEP_SUMMARY = previous;
    }
  }));
