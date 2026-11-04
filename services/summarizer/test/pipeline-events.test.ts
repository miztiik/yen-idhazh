/** Do real entry points preserve summary data while isolating event occurrences and request context? */
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import http from "node:http";
import path from "node:path";
import { test } from "node:test";
import { promisify } from "node:util";
import { createRootContext } from "@idhazh/common-contracts/create-operation-context";
import { loadEventSources } from "@idhazh/common-contracts/load-event-sources";
import { readTraceContext, writeTraceContext } from "@idhazh/common-contracts/propagate-trace-context";
import { createHttpServer } from "../src/api/serve-http-api.js";
import { orchestratePipeline } from "../src/pipeline/orchestrate-pipeline.service.js";
import { SummaryStructuredOutputSchema } from "../src/schemas/analysis-result.schema.js";
import { readPipelineEvent, type PipelineEvent } from "../src/schemas/pipeline-event.schema.js";
import { PipelineEventBus, readPipelineEvents } from "../src/services/dispatch-event.service.js";
import { extractContentFromUrl } from "../src/services/extract-content.service.js";
import { repositoryRoot, readJson, withConfig } from "./model-recordings.js";
import { close, listen, withRecordedModel } from "./pipeline-recordings.js";

function eventContext(event: PipelineEvent) {
  return readTraceContext({ traceparent: event.traceparent, tracestate: event.tracestate });
}

function executeCli(configRoot: string, directory: string, inputText: string) {
  mkdirSync(directory);
  return promisify(execFile)(
    "node",
    [
      path.join(repositoryRoot, "services/summarizer/node_modules/tsx/dist/cli.mjs"),
      path.join(repositoryRoot, "services/summarizer/src/execute-cli-pipeline.ts"),
    ],
    {
      cwd: directory,
      env: {
        ...process.env, CONFIG_ROOT: configRoot, URL: "", INPUT_TEXT: inputText,
        PROMPT: "Return the structured summary.", GITHUB_STEP_SUMMARY: "",
      },
      timeout: 120000,
    },
  );
}

async function assertCliFailure(run: Promise<unknown>, privateValues: readonly string[]) {
  await assert.rejects(run, error => {
    assert.ok(error instanceof Error && "code" in error && "stdout" in error && "stderr" in error);
    assert.equal(error.code, 1);
    assert.equal(error.stdout, "");
    assert.ok(typeof error.stderr === "string");
    assert.match(error.stderr, /SUMMARIZE_FAILED/);
    for (const privateValue of privateValues) {
      assert.equal(error.stderr.includes(privateValue), false);
    }
    return true;
  });
}

test("CLI configuration failure returns no summary and keeps diagnostics content-free", { timeout: 120000 }, () =>
  withConfig(async root => {
    const directory = path.join(root, "configuration-cli");
    const configRoot = path.join(root, "missing-config");
    const inputText = "Private input must not appear in startup diagnostics.";
    await assertCliFailure(executeCli(configRoot, directory, inputText), [inputText, configRoot]);
    assert.equal(existsSync(path.join(directory, "pipeline-events.jsonl")), false);
  }));

test("same-operation occurrences survive saved-event readback without losing validated data", () =>
  withConfig(async root => {
    const sources = await loadEventSources(path.join(repositoryRoot, "config/typescript-event-sources.json"));
    const eventFile = path.join(root, "events.jsonl");
    const context = createRootContext();
    const bus = new PipelineEventBus(sources.summarizer, eventFile);
    const data = { url: "https://source.example/recorded", bytes: 42 };
    const first = bus.emitEvent("URL_HTTP_FETCH_COMPLETED", data, context);
    const second = bus.emitEvent("URL_HTTP_FETCH_COMPLETED", data, context);
    assert.notEqual(first.id, second.id);
    assert.equal(first.traceparent, second.traceparent);
    assert.deepEqual(readPipelineEvents(eventFile), [first, second]);
    bus.getEventHistory().splice(0);
    assert.deepEqual(bus.getEventHistory(), [first, second]);
    writeFileSync(eventFile, JSON.stringify(first) + "\n"
      + JSON.stringify({ ...second, data: { ...data, bytes: -1 } }) + "\n");
    assert.throws(() => readPipelineEvents(eventFile), /line 2/);
  }));

test("a real source failure retains fallback output and the request's operation context", { timeout: 120000 }, () =>
  withConfig(root => withRecordedModel(root, async ({ runtime }) => {
    const source = http.createServer((_request, response) => {
      response.writeHead(503);
      response.end();
    });
    const url = await listen(source);
    try {
      const context = createRootContext();
      const sources = await loadEventSources(path.join(repositoryRoot, "config/typescript-event-sources.json"));
      const eventFile = path.join(root, "fallback-events.jsonl");
      const bus = new PipelineEventBus(sources.summarizer, eventFile);
      const inputText = "The original direct input remains available after source failure.";
      const result = await orchestratePipeline({
        url, input_text: inputText, system_prompt: "Return the structured summary.",
      }, bus, runtime, context);
      assert.equal(result.input_text, inputText);
      assert.equal(result.source_audit.sourceType, "FALLBACK_INPUT_TEXT");
      assert.match(result.source_audit.scrapeError ?? "", /HTTP 503/);
      const events = readPipelineEvents(eventFile);
      assert.deepEqual(events.find(event => event.type === "OUTPUT_STRUCTURED")?.data, result);
      assert.equal(events.filter(event => event.type === "URL_EXTRACTION_FAILED").length, 1);
      assert.ok(events.every(event => eventContext(event)?.traceId === context.traceId));
      const started = events.find(event => event.type === "URL_HTTP_FETCH_STARTED");
      const inference = events.find(event => event.type === "INFERENCE_DISPATCHED");
      assert.ok(started && inference);
      assert.notEqual(started.traceparent, inference.traceparent);
    } finally {
      await close(source);
    }
  })));

test("the actual CLI saves its complete returned summary and keeps diagnostics content-free", { timeout: 120000 }, () =>
  withConfig(root => withRecordedModel(root, async ({ runtime, calls }) => {
    const directory = path.join(root, "cli");
    const inputText = "Local inference keeps the source text inside the operator-controlled run.";
    const { stdout, stderr } = await executeCli(root, directory, inputText);
    const result = SummaryStructuredOutputSchema.parse(JSON.parse(stdout));
    const events = readPipelineEvents(path.join(directory, "pipeline-events.jsonl"));
    const output = events.find(event => event.type === "OUTPUT_STRUCTURED");
    assert.ok(output);
    assert.deepEqual(output.data, result);
    assert.equal(result.input_text, inputText);
    const reply = readJson("tests/fixtures/typescript-metadata/summarizer-model-response.json");
    assert.equal(result.raw_output, reply.choices[0].message.content);
    assert.equal(result.token_metrics.prompt_tokens, reply.usage.prompt_tokens);
    assert.equal(result.token_metrics.completion_time_ms, reply.timings.predicted_ms);
    assert.equal(result.token_metrics.prompt_tokens_per_second, reply.timings.prompt_per_second);
    assert.equal(calls.length, 1);
    for (const privateValue of [inputText, result.headline, result.raw_output, result.system_prompt, runtime.base_url]) {
      assert.equal(stderr.includes(privateValue), false);
    }

    const context = eventContext(output);
    assert.ok(context);
    const bus = new PipelineEventBus(output.source, path.join(directory, "repeated-output.jsonl"));
    const first = bus.emitEvent("OUTPUT_STRUCTURED", result, context);
    const second = bus.emitEvent("OUTPUT_STRUCTURED", result, context);
    const saved = readPipelineEvents(path.join(directory, "repeated-output.jsonl"));
    assert.notEqual(first.id, second.id);
    assert.deepEqual(saved.map(event => event.data), [result, result]);
    assert.deepEqual(saved, [first, second]);
    writeFileSync(path.join(directory, "repeated-output.jsonl"),
      JSON.stringify({ ...first, data: { ...result, key_points: [42] } }) + "\n");
    assert.throws(() => readPipelineEvents(path.join(directory, "repeated-output.jsonl")), /line 1/);
  })));

test("concurrent HTTP requests retain separate histories even when their incoming trace is shared", { timeout: 120000 }, () =>
  withConfig(root => withRecordedModel(root, async ({ runtime, calls }) => {
    const eventFile = path.join(root, "http-events.jsonl");
    const reportFile = path.join(root, "http-summary.md");
    const previousSummary = process.env.GITHUB_STEP_SUMMARY;
    process.env.GITHUB_STEP_SUMMARY = reportFile;
    const sources = await loadEventSources(path.join(repositoryRoot, "config/typescript-event-sources.json"));
    const app = createHttpServer({ port: 0, runtime, eventSource: sources.summarizer, eventFilePath: eventFile });
    const baseUrl = await listen(app.server);
    try {
      const incoming = createRootContext({ traceState: "test=recorded" });
      const inputs = ["The first independent source stays with its request.", "The second independent source stays with its request."];
      const responses = await Promise.all(inputs.map(inputText => fetch(`${baseUrl}/api/summarize`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...writeTraceContext(incoming) },
        body: JSON.stringify({ input_text: inputText, system_prompt: "Return the structured summary." }),
      })));
      const results = await Promise.all(responses.map(async response => {
        assert.equal(response.status, 200);
        const body: unknown = await response.json();
        assert.ok(typeof body === "object" && body !== null && "success" in body && "data" in body);
        assert.equal(body.success, true);
        return SummaryStructuredOutputSchema.parse(body.data);
      }));
      const contexts = responses.map(response => readTraceContext(Object.fromEntries(response.headers)));
      assert.ok(contexts[0] && contexts[1]);
      assert.notEqual(contexts[0].spanId, contexts[1].spanId);
      for (const context of contexts) {
        assert.equal(context?.traceId, incoming.traceId);
        assert.equal(context?.traceState, incoming.traceState);
        assert.notEqual(context?.spanId, incoming.spanId);
      }
      const events = readPipelineEvents(eventFile);
      assert.equal(events.filter(event => event.type === "INFERENCE_DISPATCHED").length, 2);
      assert.ok(events.findIndex(event => event.type === "INFERENCE_COMPLETED")
        > events.map(event => event.type).lastIndexOf("INFERENCE_DISPATCHED"));
      assert.equal(new Set(events.map(event => event.id)).size, events.length);
      const histories = [...readFileSync(reportFile, "utf8").matchAll(/```json\n([\s\S]*?)\n```/g)]
        .map(match => {
          const saved: unknown = JSON.parse(match[1]);
          assert.ok(Array.isArray(saved));
          return saved.map(readPipelineEvent);
        });
      assert.equal(histories.length, 2);
      for (const [index, result] of results.entries()) {
        assert.equal(result.input_text, inputs[index]);
        const history = histories.find(history => history.some(event =>
          event.type === "OUTPUT_STRUCTURED" && eventContext(event)?.spanId === contexts[index]?.spanId));
        assert.ok(history);
        assert.equal(history.length, 4);
        const output = history.find(event => event.type === "OUTPUT_STRUCTURED");
        const input = history.find(event => event.type === "INPUT_RESOLVED");
        assert.ok(output);
        assert.ok(input);
        assert.equal(eventContext(input)?.spanId, contexts[index]?.spanId);
        assert.deepEqual(output.data, result);
        assert.deepEqual(events.find(event => event.id === output.id)?.data, result);
        assert.equal(history.some(event => JSON.stringify(event.data).includes(inputs[1 - index])), false);
        const dispatched = history.find(event => event.type === "INFERENCE_DISPATCHED");
        const completed = history.find(event => event.type === "INFERENCE_COMPLETED");
        assert.ok(dispatched && completed);
        assert.equal(dispatched.traceparent, completed.traceparent);
        assert.notEqual(eventContext(dispatched)?.spanId, contexts[index]?.spanId);
        assert.ok(history.every(event => eventContext(event)?.traceId === incoming.traceId));
      }
      assert.equal(new Set(histories.map(history =>
        history.find(event => event.type === "INFERENCE_DISPATCHED")?.traceparent)).size, 2);
      assert.deepEqual(new Set(histories.flat().map(event => event.id)), new Set(events.map(event => event.id)));
      assert.ok(calls.every(call => call.headers.traceparent === undefined && call.headers.tracestate === undefined));

      const standalone = await fetch(`${baseUrl}/api/summarize`, {
        method: "POST", headers: { "Content-Type": "application/json", traceparent: "invalid" },
        body: JSON.stringify({ input_text: inputs[0], system_prompt: "Return the structured summary." }),
      });
      assert.equal(standalone.status, 200);
      assert.notEqual(readTraceContext(Object.fromEntries(standalone.headers))?.traceId, incoming.traceId);
      await standalone.json();
      const refused = await fetch(`${baseUrl}/api/summarize`, {
        method: "POST", headers: { "Content-Type": "application/json", traceparent: "invalid" },
        body: JSON.stringify({ input_text: inputs[0], system_prompt: "Return the structured summary.", model_name: "not-selected" }),
      });
      assert.equal(refused.status, 500);
      assert.match(JSON.stringify(await refused.json()), /selected model declaration/);
      assert.equal(calls.length, 3);
    } finally {
      if (previousSummary === undefined) delete process.env.GITHUB_STEP_SUMMARY;
      else process.env.GITHUB_STEP_SUMMARY = previousSummary;
      await close(app.server);
    }
  }, { waitForCalls: 2 })));

test("a recorded model validation failure does not save a successful output", { timeout: 120000 }, () =>
  withConfig(root => withRecordedModel(root, async ({ runtime }) => {
    const eventFile = path.join(root, "failed-events.jsonl");
    const sources = await loadEventSources(path.join(repositoryRoot, "config/typescript-event-sources.json"));
    const app = createHttpServer({ port: 0, runtime, eventSource: sources.summarizer, eventFilePath: eventFile });
    const baseUrl = await listen(app.server);
    try {
      const response = await fetch(`${baseUrl}/api/summarize`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_text: "Recorded incompatible response.", system_prompt: "Return the structured summary." }),
      });
      assert.equal(response.status, 500);
      const context = readTraceContext(Object.fromEntries(response.headers));
      assert.ok(context);
      const events = readPipelineEvents(eventFile);
      assert.deepEqual(events.map(event => event.type), ["INPUT_RESOLVED", "INFERENCE_DISPATCHED"]);
      assert.ok(events.every(event => eventContext(event)?.traceId === context.traceId));

      const directory = path.join(root, "failed-cli");
      const inputText = "Recorded incompatible response.";
      const recorded = readJson("tests/fixtures/completions/reasoning-channel.json");
      await assertCliFailure(
        executeCli(root, directory, inputText),
        [inputText, recorded.choices[0].message.content, runtime.base_url],
      );
      assert.deepEqual(
        readPipelineEvents(path.join(directory, "pipeline-events.jsonl")).map(event => event.type),
        ["INPUT_RESOLVED", "INFERENCE_DISPATCHED"],
      );
    } finally {
      await close(app.server);
    }
  }, { fixture: "tests/fixtures/completions/reasoning-channel.json" })));

test("source callbacks retain fetch context without propagating it to a source", { timeout: 120000 }, () =>
  withConfig(async root => {
    const sources = await loadEventSources(path.join(repositoryRoot, "config/typescript-event-sources.json"));
    const bus = new PipelineEventBus(sources.summarizer, path.join(root, "source-events.jsonl"));
    const context = createRootContext();
    let sourceHeaders: http.IncomingHttpHeaders | undefined;
    const server = http.createServer((request, response) => {
      sourceHeaders = request.headers;
      response.writeHead(503);
      response.end();
    });
    const url = await listen(server);
    try {
      await assert.rejects(() => extractContentFromUrl(url, context, progress => {
        assert.equal(progress.context.traceId, context.traceId);
        assert.equal(progress.context.parentSpanId, context.spanId);
        bus.emitEvent(progress.type, progress.data, progress.context);
      }), /HTTP 503/);
      const [started] = bus.getEventHistory();
      assert.equal(started.type, "URL_HTTP_FETCH_STARTED");
      assert.notEqual(eventContext(started)?.spanId, context.spanId);
      assert.equal(sourceHeaders?.traceparent, undefined);
      assert.equal(sourceHeaders?.tracestate, undefined);
    } finally {
      await close(server);
    }
  }));
