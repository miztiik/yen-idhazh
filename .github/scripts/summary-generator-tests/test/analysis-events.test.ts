/** Do the moved caller's real entry points preserve full analysis and private operation histories? */
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { promisify } from "node:util";
import { createChildContext, createRootContext } from "@idhazh/common-contracts/create-operation-context";
import { readTraceContext } from "@idhazh/common-contracts/propagate-trace-context";
import { SUMMARY_GENERATOR_TESTS_EVENT_SOURCE } from "../declare-event-source.js";
import { orchestratePipeline } from "../orchestrate-analysis.js";
import { SummaryStructuredOutputSchema } from "../contracts/analysis-result.schema.js";
import { PIPELINE_EVENT_VERSION, readPipelineEvent, type PipelineEvent } from "../contracts/pipeline-event.schema.js";
import { PipelineEventBus, readPipelineEvents } from "../publish-events.js";
import { renderGithubStepSummary } from "../render-report.js";
import { runCli } from "../run.js";
import { loadAnalysisSettings } from "../load-analysis-config.js";
import {
  repositoryRoot, readJson, withConfig, type RecordedNativeReply,
} from "../../../../services/summary-generator/test/model-recordings.js";
import { recordOutput, withRecordedModel } from "./pipeline-recordings.js";

function eventContext(event: PipelineEvent) {
  return readTraceContext({ traceparent: event.traceparent, tracestate: event.tracestate });
}

test("CLI configuration failure exits with no summary and content-free diagnostics", { timeout: 120000 }, () =>
  withConfig(async root => {
    const directory = path.join(root, "configuration-cli");
    mkdirSync(directory);
    const configRoot = path.join(root, "missing-config");
    const inputText = "Private input must not appear in startup diagnostics.";
    const run = promisify(execFile)("node", [
      path.join(repositoryRoot, ".github/scripts/summary-generator-tests/node_modules/tsx/dist/cli.mjs"),
      path.join(repositoryRoot, ".github/scripts/summary-generator-tests/run.ts"),
    ], {
      cwd: directory, env: {
        ...process.env, CONFIG_ROOT: configRoot, URL: "", INPUT_TEXT: inputText,
        PROMPT: "Return the structured summary.", GITHUB_STEP_SUMMARY: "",
      }, timeout: 120000,
    });
    await assert.rejects(run, error => {
      assert.ok(error instanceof Error && "code" in error && "stdout" in error && "stderr" in error);
      assert.equal(error.code, 1);
      assert.equal(error.stdout, "");
      assert.ok(typeof error.stderr === "string");
      assert.match(error.stderr, /SUMMARIZE_FAILED/);
      for (const value of [inputText, configRoot]) assert.equal(error.stderr.includes(value), false);
      return true;
    });
    assert.equal(existsSync(path.join(directory, "pipeline-events.jsonl")), false);
  }));

test("same-operation occurrences retain unchanged current-format historical source readback", () =>
  withConfig(async root => {
    const eventFile = path.join(root, "events.jsonl");
    const context = createRootContext();
    const bus = new PipelineEventBus("/services/summarizer", eventFile);
    const data = { url: "https://source.example/recorded", bytes: 42 };
    const first = bus.emitEvent("URL_HTTP_FETCH_COMPLETED", data, context);
    const second = bus.emitEvent("URL_HTTP_FETCH_COMPLETED", data, context);
    const bytes = readFileSync(eventFile, "utf8");
    assert.equal(PIPELINE_EVENT_VERSION, "2026-11-03");
    assert.notEqual(first.id, second.id);
    assert.equal(first.traceparent, second.traceparent);
    assert.deepEqual(readPipelineEvents(eventFile), [first, second]);
    assert.equal(readFileSync(eventFile, "utf8"), bytes);
    bus.getEventHistory().splice(0);
    assert.deepEqual(bus.getEventHistory(), [first, second]);
    writeFileSync(eventFile, JSON.stringify(first) + "\n"
      + JSON.stringify({ ...second, data: { ...data, bytes: -1 } }) + "\n");
    assert.throws(() => readPipelineEvents(eventFile), /line 2/);
  }));

test("a recorded source failure retains fallback output, classifications and operation context", { timeout: 120000 }, () =>
  withConfig(root => withRecordedModel(root, async ({ runtime, send, calls }) => {
    const context = createRootContext();
    const eventFile = path.join(root, "fallback-events.jsonl");
    const bus = new PipelineEventBus(SUMMARY_GENERATOR_TESTS_EVENT_SOURCE, eventFile);
    const url = "https://source.example/unavailable";
    const inputText = "The original direct input remains available after source failure.";
    let sourceHeaders: Headers | undefined;
    const result = await orchestratePipeline({
      url, input_text: inputText, system_prompt: "Return the structured summary.",
    }, bus, runtime, context, async request => {
      if (request.url === url) {
        sourceHeaders = request.headers;
        return new Response("", { status: 503 });
      }
      return send(request);
    }, loadAnalysisSettings(root));
    assert.equal(result.input_text, inputText);
    assert.equal(result.source_audit.sourceType, "FALLBACK_INPUT_TEXT");
    assert.match(result.source_audit.scrapeError ?? "", /HTTP 503/);
    assert.equal(result.sentiment, "positive");
    assert.equal(result.stance_on_change, "progressivism");
    const events = readPipelineEvents(eventFile);
    assert.deepEqual(events.find(event => event.type === "OUTPUT_STRUCTURED")?.data, result);
    assert.equal(events.filter(event => event.type === "URL_EXTRACTION_FAILED").length, 1);
    assert.ok(events.every(event => eventContext(event)?.traceId === context.traceId));
    const started = events.find(event => event.type === "URL_HTTP_FETCH_STARTED");
    const inference = events.find(event => event.type === "INFERENCE_DISPATCHED");
    assert.ok(started && inference);
    assert.notEqual(started.traceparent, inference.traceparent);
    assert.equal(sourceHeaders?.has("traceparent"), false);
    assert.equal(sourceHeaders?.has("tracestate"), false);
    assert.equal(calls.length, 1);
  })));

test("the actual CLI saves its complete result and report while diagnostics remain content-free", { timeout: 120000 }, () =>
  withConfig(root => withRecordedModel(root, async ({ runtime, send, calls }) => {
    const output = recordOutput(), diagnostic = recordOutput();
    const eventFile = path.join(root, "cli-events.jsonl"), reportFile = path.join(root, "cli-summary.md");
    const inputText = "Local inference keeps source text inside the operator-controlled run.";
    await runCli(send, output.writer, {
      eventFilePath: eventFile, diagnostic: diagnostic.writer,
      environment: {
        CONFIG_ROOT: root, URL: "", INPUT_TEXT: inputText, PROMPT: "Return the structured summary.",
        GITHUB_STEP_SUMMARY: reportFile,
      },
    });
    const result = SummaryStructuredOutputSchema.parse(JSON.parse(output.read()));
    const events = readPipelineEvents(eventFile);
    const saved = events.find(event => event.type === "OUTPUT_STRUCTURED");
    assert.ok(saved);
    assert.equal(saved.source, SUMMARY_GENERATOR_TESTS_EVENT_SOURCE);
    assert.deepEqual(saved.data, result);
    assert.equal(result.input_text, inputText);
    const reply = readJson<RecordedNativeReply>("tests/fixtures/typescript-metadata/summarizer-model-response.json");
    assert.equal(result.raw_output, reply.choices[0].message.content);
    assert.equal(result.token_metrics.prompt_tokens, reply.usage.prompt_tokens);
    assert.equal(result.token_metrics.completion_time_ms, reply.timings.predicted_ms);
    assert.equal(result.token_metrics.prompt_tokens_per_second, reply.timings.prompt_per_second);
    assert.equal(calls.length, 1);
    for (const value of [inputText, result.headline, result.raw_output, result.system_prompt, runtime.base_url]) {
      assert.equal(diagnostic.read().includes(value), false);
    }
    const report = readFileSync(reportFile, "utf8");
    for (const value of [result.headline, result.executive_summary, result.sentiment, inputText, saved.id, saved.time]) {
      assert.ok(report.includes(value));
    }
    const history = [...report.matchAll(/```json\n([\s\S]*?)\n```/g)]
      .map(match => (JSON.parse(match[1]) as unknown[]).map(readPipelineEvent));
    assert.deepEqual(history, [events]);
    const context = eventContext(saved);
    assert.ok(context);
    const bus = new PipelineEventBus(saved.source, path.join(root, "repeated-output.jsonl"));
    const first = bus.emitEvent("OUTPUT_STRUCTURED", result, context);
    const second = bus.emitEvent("OUTPUT_STRUCTURED", result, context);
    assert.notEqual(first.id, second.id);
    assert.deepEqual(readPipelineEvents(path.join(root, "repeated-output.jsonl")), [first, second]);
    writeFileSync(path.join(root, "repeated-output.jsonl"),
      JSON.stringify({ ...first, data: { ...result, key_points: [42] } }) + "\n");
    assert.throws(() => readPipelineEvents(path.join(root, "repeated-output.jsonl")), /line 1/);
  })));

test("concurrent caller operations retain separate histories and reports inside one incoming trace", { timeout: 120000 }, () =>
  withConfig(root => withRecordedModel(root, async ({ runtime, send, calls }) => {
    const incoming = createRootContext({ traceState: "test=recorded" });
    const contexts = [createChildContext(incoming), createChildContext(incoming)];
    const eventFile = path.join(root, "concurrent-events.jsonl");
    const reportFile = path.join(root, "concurrent-report.md");
    const buses = contexts.map(() => new PipelineEventBus(SUMMARY_GENERATOR_TESTS_EVENT_SOURCE, eventFile));
    const inputs = ["First independent source.", "Second independent source."];
    const settings = loadAnalysisSettings(root);
    const results = await Promise.all(inputs.map((input_text, index) => orchestratePipeline({
      input_text, url: "", system_prompt: "Return the structured summary.",
    }, buses[index], runtime, contexts[index], send, settings)));
    const events = readPipelineEvents(eventFile);
    assert.ok(events.findIndex(event => event.type === "INFERENCE_COMPLETED")
      > events.map(event => event.type).lastIndexOf("INFERENCE_DISPATCHED"));
    for (const [index, result] of results.entries()) {
      const history = buses[index].getEventHistory();
      const input = history.find(event => event.type === "INPUT_RESOLVED");
      const dispatched = history.find(event => event.type === "INFERENCE_DISPATCHED");
      const completed = history.find(event => event.type === "INFERENCE_COMPLETED");
      assert.ok(input && dispatched && completed);
      assert.equal(eventContext(input)?.spanId, contexts[index].spanId);
      assert.equal(dispatched.traceparent, completed.traceparent);
      assert.notEqual(eventContext(dispatched)?.spanId, contexts[index].spanId);
      assert.ok(history.every(event => eventContext(event)?.traceId === incoming.traceId));
      assert.equal(history.some(event => JSON.stringify(event.data).includes(inputs[1 - index])), false);
      renderGithubStepSummary(runtime.request.model, result, history, { summaryPath: reportFile, writeNotice: false });
    }
    const histories = [...readFileSync(reportFile, "utf8").matchAll(/```json\n([\s\S]*?)\n```/g)]
      .map(match => (JSON.parse(match[1]) as unknown[]).map(readPipelineEvent));
    assert.deepEqual(histories, buses.map(bus => bus.getEventHistory()));
    assert.deepEqual(new Set(histories.flat().map(event => event.id)), new Set(events.map(event => event.id)));
    assert.equal(new Set(histories.map(history =>
      history.find(event => event.type === "INFERENCE_DISPATCHED")?.traceparent)).size, 2);
    assert.ok(calls.every(call => call.headers.traceparent === undefined && call.headers.tracestate === undefined));
  }, { waitForCalls: 2 })));

test("an incompatible recorded native reply saves no successful CLI output or private report", { timeout: 120000 }, () =>
  withConfig(root => withRecordedModel(root, async ({ send }) => {
    const output = recordOutput(), diagnostic = recordOutput();
    const eventFile = path.join(root, "failed-cli-events.jsonl"), reportFile = path.join(root, "failed-report.md");
    const succeeded = await runCli(send, output.writer, {
      eventFilePath: eventFile, diagnostic: diagnostic.writer,
      environment: { CONFIG_ROOT: root, INPUT_TEXT: "Private incompatible input.", URL: "",
        PROMPT: "Return structured analysis.", GITHUB_STEP_SUMMARY: reportFile },
    });
    assert.equal(succeeded, false);
    assert.equal(output.read(), "");
    assert.match(diagnostic.read(), /SUMMARIZE_FAILED/);
    assert.equal(diagnostic.read().includes("Private incompatible input."), false);
    assert.deepEqual(readPipelineEvents(eventFile).map(event => event.type), ["INPUT_RESOLVED", "INFERENCE_DISPATCHED"]);
    assert.equal(existsSync(reportFile), false);
  }, { fixture: "tests/fixtures/completions/reasoning-channel.json" })));
