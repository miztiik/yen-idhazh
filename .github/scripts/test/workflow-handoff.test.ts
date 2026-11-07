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
import { AIEventPipeline, publishStepSummary } from "../ai-pipeline.ts";
import { WORKFLOW_EVENT_SOURCE } from "../declare-workflow-event-source.ts";
import { readPipelineEvents, selectStructuredOutputs, type PipelineEvent } from "../read-pipeline-events.ts";
import { prepareEvaluationRequest, readEvaluationResponse } from "../prepare-evaluation-request.ts";

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

test("the production reader hands unchanged source and summary to the foreign request builder", async () => {
  const saved = await readFile(outputPath, "utf8");
  const event = readSavedOutput();
  const original = structuredClone(event);
  const phase = createRootContext();
  const prepared = prepareEvaluationRequest(event, phase, event.data.result.runner_metadata);
  const expected = await Bun.file(new URL("evaluator-request.json", fixtures)).json();
  const { correlationId: recordedId, ...expectedBody } = expected;
  const { correlationId, ...body } = prepared.request;
  expect(body).toEqual(expectedBody);
  expect(body.sourceText).toBe(event.data.result.source_audit.extractedText);
  expect(body.summaryText).toBe(event.data.result.analytic_synthesis);
  expect(correlationId).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  expect(correlationId).not.toBe(recordedId);
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
      prepareEvaluationRequest(event, evaluation.context, saved.data.result.runner_metadata));
    expect(new Set(prepared.map(value => value.context.spanId)).size).toBe(selected.length);
    for (const [index, input] of selected.entries()) {
      const current = prepared[index]!;
      const producer = readProducer(input);
      expect(current.context.traceId).toBe(evaluation.context.traceId);
      expect(current.context.traceId).not.toBe(producer.traceId);
      expect(current.context.parentSpanId).toBe(evaluation.context.spanId);
      expect(current.context.links).toEqual([{ traceId: producer.traceId, spanId: producer.spanId }]);
      expect(current.request.sourceText).toBe(input.data.result.source_audit.extractedText);
      expect(current.request.summaryText).toBe(input.data.result.analytic_synthesis);
    }
    expect(prepared[2]!.context.links).not.toEqual(prepared[0]!.context.links);
    expect(prepared[2]!.request.sourceText).not.toBe(prepared[0]!.request.sourceText);
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
    const { context } = prepareEvaluationRequest(saved, evaluation.context, saved.data.result.runner_metadata);
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
