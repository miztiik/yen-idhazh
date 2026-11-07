/** Prove the real summary handler's product, freshness and bounded native transport. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { createRootContext } from "@idhazh/common-contracts/create-operation-context";
import { readCloudEvent } from "@idhazh/common-contracts/read-cloud-event";
import { readTraceContext, writeTraceContext } from "@idhazh/common-contracts/propagate-trace-context";
import { createSummaryHandler } from "../src/api/serve-http-api.js";
import { createSummaryListener } from "../src/api/create-summary-listener.js";
import { SUMMARY_GENERATOR_EVENT_SOURCE } from "../src/declare-event-source.js";
import { GENERATE_SUMMARY_PATH, SUMMARY_GENERATOR_HEALTH_PATH } from "../src/api/api-paths.js";
import { loadGeneratorConfig, type GeneratorConfig } from "../src/config/load-generator-config.js";
import { loadModelRuntime } from "../src/config/load-model-runtime.js";
import { SummaryResultSchema } from "../src/schemas/summary-result.schema.js";
import { buildModelRequest } from "../src/services/model-request.service.js";
import type { CompletionFetch } from "../src/services/request-completion.service.js";
import { readJson, repositoryRoot, withConfig, type RecordedNativeReply } from "./model-recordings.js";

const recorded = readFileSync(path.join(repositoryRoot, "tests/fixtures/typescript-metadata/summarizer-model-response.json"));
const configuredRuntime = loadModelRuntime();
const request = (body: unknown, headers: Record<string, string> = {}, signal?: AbortSignal) =>
  new Request(`http://localhost${GENERATE_SUMMARY_PATH}`, {
    method: "POST", headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body), signal,
  });
const reply = () => new Response(recorded, { headers: { "Content-Type": "application/json" } });
const digest = (value: string) => createHash("sha256").update(value, "utf8").digest("hex");
function barrier() {
  let release = () => {};
  const ready = new Promise<void>(resolve => { release = resolve; });
  return { ready, release: () => release() };
}
function streamedRequest(body: ReadableStream<Uint8Array>, signal?: AbortSignal, headers = {}) {
  const options: RequestInit & { duplex: "half" } = {
    method: "POST", body, signal, headers: { "Content-Type": "application/json", ...headers }, duplex: "half",
  };
  return new Request(`http://localhost${GENERATE_SUMMARY_PATH}`, options);
}

test("fresh default and override requests return only summaries and never publish private reports", () =>
  withConfig(async root => {
    const selected = loadGeneratorConfig(root);
    const runtime = structuredClone(configuredRuntime);
    const calls: unknown[] = [], events: unknown[] = [];
    const report = path.join(root, "step-summary.md");
    writeFileSync(report, "Existing report.");
    const previous = process.env.GITHUB_STEP_SUMMARY;
    process.env.GITHUB_STEP_SUMMARY = report;
    const handler = createSummaryHandler({
      ...selected, runtime, writeEvent: event => { events.push(event); },
      send: async native => { calls.push(JSON.parse(await native.text())); return reply(); },
    });
    try {
      const incoming = createRootContext({ traceState: "test=recorded" });
      const first = await handler(request({ input_text: " First source. " }, writeTraceContext(incoming)));
      const second = await handler(request({
        input_text: "Second source.", system_prompt: " Exact replacement prompt. ",
      }, writeTraceContext(incoming)));
      const a = SummaryResultSchema.parse(await first.json()), b = SummaryResultSchema.parse(await second.json());
      assert.equal(first.status, 200); assert.equal(second.status, 200);
      assert.deepEqual(Object.keys(a.data), ["headline", "executive_summary", "key_points"]);
      assert.deepEqual(a.usage, { prompt_tokens: 703, completion_tokens: 340 });
      assert.equal(a.prompt_source, "default"); assert.equal(a.prompt_sha256, digest(selected.systemPrompt));
      assert.equal(b.prompt_source, "override"); assert.equal(b.prompt_sha256, digest(" Exact replacement prompt. "));
      assert.deepEqual(calls, [
        buildModelRequest(runtime, selected.systemPrompt, " First source. ", { type: "json_object" }),
        buildModelRequest(runtime, " Exact replacement prompt. ", "Second source.", { type: "json_object" }),
      ]);
      const contexts = [first, second].map(response => readTraceContext(Object.fromEntries(response.headers)));
      assert.equal(contexts[0]?.traceId, incoming.traceId);
      assert.equal(contexts[1]?.traceId, incoming.traceId);
      assert.notEqual(contexts[0]?.spanId, contexts[1]?.spanId);
      assert.equal(readFileSync(report, "utf8"), "Existing report.");
      assert.equal(existsSync(path.join(root, "pipeline-events.jsonl")), false);
      assert.ok(events.every(event => !JSON.stringify(event).includes("source.")));
    } finally {
      if (previous === undefined) delete process.env.GITHUB_STEP_SUMMARY;
      else process.env.GITHUB_STEP_SUMMARY = previous;
    }
  }));

test("a changed default, long text and an unseen sampler require no hidden input rewrite", () =>
  withConfig(async root => {
    const config = loadGeneratorConfig(root).config;
    const prompt = "Changed configured default.";
    writeFileSync(path.join(root, config.prompt_file), prompt);
    const runtime = structuredClone(configuredRuntime);
    runtime.request.future_sampler_control = { strength: 0.41 };
    const input = Array.from({ length: readJson<{ max_input_words: number }>("config/summary-generator/workflow.json").max_input_words + 1 },
      () => "word").join(" ");
    let sent: unknown;
    const response = await createSummaryHandler({
      ...loadGeneratorConfig(root), runtime, writeEvent: () => {},
      send: async native => { sent = JSON.parse(await native.text()); return reply(); },
    })(request({ input_text: input }));
    assert.equal(response.status, 200);
    assert.equal(SummaryResultSchema.parse(await response.json()).prompt_sha256, digest(prompt));
    assert.deepEqual(sent, buildModelRequest(runtime, prompt, input, { type: "json_object" }));
  }));

test("removed fields, blank inputs and retired routes are refused without native calls", () =>
  withConfig(async root => {
    let calls = 0;
    const handler = createSummaryHandler({
      ...loadGeneratorConfig(root), runtime: configuredRuntime, writeEvent: () => {},
      send: async () => { calls += 1; return reply(); },
    });
    for (const body of [
      {}, { input_text: " " }, { input_text: "text", system_prompt: " " },
      ...["url", "server_url", "model_name", "conversation", "session"].map(field => ({
        input_text: "text", [field]: "removed",
      })),
    ]) {
      const response = await handler(request(body));
      assert.equal(response.status, 400);
      assert.equal((await response.json() as { code: string }).code, "INVALID_REQUEST");
    }
    for (const old of ["/health", "/api/diagnostics", "/api/summarize", `${GENERATE_SUMMARY_PATH}/`]) {
      assert.equal((await handler(new Request(`http://localhost${old}`))).status, 404);
    }
    const health = await handler(new Request(`http://localhost${SUMMARY_GENERATOR_HEALTH_PATH}`));
    assert.equal(health.status, 200);
    const observed = await health.json();
    assert.ok(typeof observed === "object" && observed !== null);
    assert.equal("memory" in observed, false);
    const wrongMethod = await handler(new Request(`http://localhost${GENERATE_SUMMARY_PATH}`));
    assert.equal(wrongMethod.status, 405);
    assert.equal(wrongMethod.headers.get("allow"), "POST");
    assert.equal(calls, 0);
  }));

test("both exact request-byte limits pass and one byte over either returns the declared refusal", () =>
  withConfig(async root => {
    const selected = loadGeneratorConfig(root), runtime = configuredRuntime;
    const body = { input_text: "UTF-8 \u00e9 text." };
    const inputBytes = Buffer.byteLength(JSON.stringify(body));
    const nativeBytes = Buffer.byteLength(JSON.stringify(
      buildModelRequest(runtime, selected.systemPrompt, body.input_text, { type: "json_object" }),
    ));
    for (const [inputLimit, nativeLimit, expected] of [
      [inputBytes, nativeBytes, 200], [inputBytes - 1, nativeBytes, 413], [inputBytes, nativeBytes - 1, 413],
    ]) {
      writeFileSync(path.join(root, "summary-generator/api.json"), JSON.stringify({
        ...selected.config, max_request_bytes: inputLimit, max_native_request_bytes: nativeLimit,
      }));
      const handler = createSummaryHandler({
        ...loadGeneratorConfig(root), runtime, writeEvent: () => {}, send: async () => reply(),
      });
      const response = await handler(request(body));
      assert.equal(response.status, expected);
      if (expected === 413) assert.equal((await response.json() as { code: string }).code, "REQUEST_TOO_LARGE");
    }
  }));

test("absent native counts stay null and response limits, redirects and cancellation remain explicit", () =>
  withConfig(async root => {
    const selected = loadGeneratorConfig(root), runtime = configuredRuntime;
    const absent: Partial<RecordedNativeReply> = readJson<RecordedNativeReply>(
      "tests/fixtures/typescript-metadata/summarizer-model-response.json",
    );
    delete absent.usage;
    const cases: [CompletionFetch, Partial<GeneratorConfig>, number][] = [
      [async () => new Response(JSON.stringify(absent), { headers: { "Content-Type": "application/json" } }), {}, 200],
      [async () => reply(), { max_native_response_bytes: recorded.byteLength }, 200],
      [async () => reply(), { max_native_response_bytes: recorded.byteLength - 1 }, 500],
      [async native => {
        assert.equal(native.redirect, "error");
        return new Response("redirect", { status: 302, headers: { Location: "/elsewhere" } });
      }, {}, 500],
      [async () => new Response(new Uint8Array([255]), {
        headers: { "Content-Type": "application/json" },
      }), {}, 500],
    ];
    for (const [send, patch, status] of cases) {
      const response = await createSummaryHandler({
        ...selected, runtime, config: { ...selected.config, ...patch }, send, writeEvent: () => {},
      })(request({ input_text: "text" }));
      assert.equal(response.status, status);
      if (send === cases[0][0]) {
        assert.deepEqual(SummaryResultSchema.parse(await response.json()).usage,
          { prompt_tokens: null, completion_tokens: null });
      }
    }
    let cancelled = false;
    const stalled = new ReadableStream<Uint8Array>({
      start(controller) { controller.enqueue(new TextEncoder().encode("{")); },
      cancel() { cancelled = true; },
    });
    const response = await createSummaryHandler({
      ...selected, runtime: { ...runtime, timeout_seconds: 0.01 }, writeEvent: () => {},
      send: async () => new Response(stalled, { headers: { "Content-Type": "application/json" } }),
    })(request({ input_text: "text" }));
    assert.equal(response.status, 500);
    assert.equal(cancelled, true);
  }));

test("the Bun adapter derives listener settings and leaves body admission and logging to the real handler", () =>
  withConfig(async root => {
    const original = loadGeneratorConfig(root).config;
    writeFileSync(path.join(root, "summary-generator/api.json"), JSON.stringify({
      ...original, hostname: "::1", port: original.port + 1,
      logging: { ...original.logging, level: "ERROR" },
    }));
    const events: unknown[] = [];
    let refuseNative = false;
    const listener = createSummaryListener({
      ...loadGeneratorConfig(root), runtime: configuredRuntime,
      writeEvent: event => { events.push(event); },
      send: async () => refuseNative ? new Response("private native failure", { status: 503 }) : reply(),
    });
    assert.equal(listener.hostname, "::1");
    assert.equal(listener.port, original.port + 1);
    assert.equal(listener.maxRequestBodySize, Number.MAX_SAFE_INTEGER);
    assert.equal(listener.idleTimeout, 0);
    assert.equal((await listener.fetch(request({ input_text: "Private source." }))).status, 200);
    assert.equal((await listener.fetch(request({ input_text: "Private source.", url: "removed" }))).status, 400);
    assert.equal(events.length, 0);
    refuseNative = true;
    const failed = await listener.fetch(request({ input_text: "Private source." }));
    assert.equal(failed.status, 500);
    assert.equal(events.length, 1);
    const event = readCloudEvent(events[0], value => value);
    assert.equal(event.source, SUMMARY_GENERATOR_EVENT_SOURCE);
    assert.equal(event.traceparent, failed.headers.get("traceparent"));
    assert.equal(event.type, "GENERATE_SUMMARY_FAILED");
    assert.equal(JSON.stringify(event).includes("Private source"), false);
    assert.equal(JSON.stringify(event).includes("private native failure"), false);
  }));

test("malformed, incomplete and non-summary native replies never become successful summaries", () =>
  withConfig(async root => {
    const selected = loadGeneratorConfig(root);
    const original = readJson<RecordedNativeReply>("tests/fixtures/typescript-metadata/summarizer-model-response.json");
    for (const fault of ["summary", "json", "incomplete", "count", "choices"]) {
      const reply = structuredClone(original);
      if (fault === "summary") reply.choices[0].message.content = '{"headline":"Only a title"}';
      if (fault === "json") reply.choices[0].message.content = "private invalid model reply";
      if (fault === "incomplete") reply.choices[0].finish_reason = "length";
      if (fault === "count") reply.usage.completion_tokens = -1;
      if (fault === "choices") reply.choices = [];
      const response = await createSummaryHandler({
        ...selected, runtime: configuredRuntime, writeEvent: () => {},
        send: async () => new Response(JSON.stringify(reply), { headers: { "Content-Type": "application/json" } }),
      })(request({ input_text: "Private source." }));
      assert.equal(response.status, 500);
      const result = await response.json();
      assert.deepEqual(result, { error: "The summary could not be generated.", code: "GENERATE_SUMMARY_FAILED" });
    }
  }));

test("unused native choices remain opaque and explicitly missing usage stays nullable", () =>
  withConfig(async root => {
    const reply = readJson<RecordedNativeReply>("tests/fixtures/typescript-metadata/summarizer-model-response.json");
    const runtime = { ...configuredRuntime, request: { ...configuredRuntime.request, n: 2 } };
    let native: unknown;
    const response = await createSummaryHandler({
      ...loadGeneratorConfig(root), runtime, writeEvent: () => {},
      send: async request => {
        native = JSON.parse(await request.text());
        return new Response(JSON.stringify({
          ...reply, choices: [...reply.choices, { index: 1, unconsumed_native_field: true }],
          usage: { prompt_tokens: null, completion_tokens: null },
        }), { headers: { "Content-Type": "application/json" } });
      },
    })(request({ input_text: "One primary summary." }));
    assert.equal(response.status, 200);
    assert.equal((native as { n: number }).n, 2);
    assert.deepEqual(SummaryResultSchema.parse(await response.json()).usage,
      { prompt_tokens: null, completion_tokens: null });
  }));

test("request-body deadlines and declared oversized carriers cancel admission without calling the model", () =>
  withConfig(async root => {
    const selected = loadGeneratorConfig(root);
    let calls = 0;
    const handler = createSummaryHandler({
      ...selected, runtime: configuredRuntime,
      config: { ...selected.config, body_read_timeout_ms: 10 },
      writeEvent: () => {}, send: async () => { calls += 1; return reply(); },
    });
    const incoming = createRootContext();
    let bodyCancelled = false;
    const stalled = new ReadableStream<Uint8Array>({
      start(controller) { controller.enqueue(new TextEncoder().encode("{")); },
      cancel() { bodyCancelled = true; },
    });
    const timed = await handler(streamedRequest(stalled, undefined, writeTraceContext(incoming)));
    assert.equal(timed.status, 408);
    assert.equal((await timed.json() as { code: string }).code, "REQUEST_BODY_TIMEOUT");
    assert.equal(readTraceContext(Object.fromEntries(timed.headers))?.traceId, incoming.traceId);
    assert.equal(bodyCancelled, true);
    let oversizedCancelled = false;
    const oversized = new ReadableStream<Uint8Array>({
      cancel() { oversizedCancelled = true; return new Promise<void>(() => {}); },
    });
    const refused = await handler(streamedRequest(oversized, undefined, {
      "Content-Length": String(selected.config.max_request_bytes + 1),
    }));
    assert.equal(refused.status, 413);
    assert.equal((await refused.json() as { code: string }).code, "REQUEST_TOO_LARGE");
    assert.equal(oversizedCancelled, true);
    assert.equal(calls, 0);
  }));

test("request cancellation propagates before headers and cancels even a late native response body", () =>
  withConfig(async root => {
    const started = barrier(), closed = barrier();
    const controller = new AbortController();
    let provideHeaders: (response: Response) => void = () => {};
    let nativeSignal: AbortSignal | undefined;
    const handler = createSummaryHandler({
      ...loadGeneratorConfig(root), runtime: configuredRuntime, writeEvent: () => {},
      send: async native => {
        nativeSignal = native.signal;
        started.release();
        return new Promise<Response>(resolve => { provideHeaders = resolve; });
      },
    });
    const pending = handler(request({ input_text: "Cancelled before headers." }, {}, controller.signal));
    await started.ready;
    controller.abort();
    const response = await pending;
    assert.equal(response.status, 500);
    assert.equal(nativeSignal?.aborted, true);
    const late = new ReadableStream<Uint8Array>({ cancel() { closed.release(); } });
    provideHeaders(new Response(late, { headers: { "Content-Type": "application/json" } }));
    await closed.ready;
    assert.equal(late.locked, false);
  }));

test("native header and full-body deadlines remain active and external body cancellation closes the reader", () =>
  withConfig(async root => {
    const selected = loadGeneratorConfig(root);
    let headerAborted = false;
    const headerFailure = await createSummaryHandler({
      ...selected, runtime: { ...configuredRuntime, timeout_seconds: 0.01 }, writeEvent: () => {},
      send: async native => {
        native.signal.addEventListener("abort", () => { headerAborted = true; }, { once: true });
        return new Promise<Response>(() => {});
      },
    })(request({ input_text: "Header timeout." }));
    assert.equal(headerFailure.status, 500);
    assert.equal(headerAborted, true);
    const reading = barrier();
    let bodyCancelled = false;
    const controller = new AbortController();
    const body = new ReadableStream<Uint8Array>({
      pull(stream) { stream.enqueue(new TextEncoder().encode("{")); reading.release(); },
      cancel() { bodyCancelled = true; },
    }, { highWaterMark: 0 });
    const pending = createSummaryHandler({
      ...selected, runtime: configuredRuntime, writeEvent: () => {},
      send: async native => {
        assert.equal(native.signal.aborted, false);
        return new Response(body, { headers: { "Content-Type": "application/json" } });
      },
    })(request({ input_text: "Cancelled while reading." }, {}, controller.signal));
    await reading.ready;
    controller.abort();
    assert.equal((await pending).status, 500);
    assert.equal(bodyCancelled, true);
    assert.equal(body.locked, false);
  }));

test("native status, representation and oversized-body refusals cancel bodies even when cancellation stalls", () =>
  withConfig(async root => {
    const selected = loadGeneratorConfig(root);
    for (const [status, headers, oversized] of [
      [302, { "Content-Type": "application/json" }, false],
      [200, { "Content-Type": "text/plain" }, false],
      [200, { "Content-Type": "application/json", "Content-Encoding": "gzip" }, false],
      [200, { "Content-Type": "application/json" }, true],
    ] as const) {
      let cancelled = false;
      const body = new ReadableStream<Uint8Array>({
        start(stream) { stream.enqueue(new Uint8Array(oversized ? selected.config.max_native_response_bytes + 1 : 1)); },
        cancel() { cancelled = true; return new Promise<void>(() => {}); },
      });
      const response = await createSummaryHandler({
        ...selected, runtime: { ...configuredRuntime, timeout_seconds: 0.01 }, writeEvent: () => {},
        send: async () => new Response(body, { status, headers }),
      })(request({ input_text: "Representation refusal." }));
      assert.equal(response.status, 500);
      assert.equal((await response.json() as { code: string }).code, "GENERATE_SUMMARY_FAILED");
      assert.equal(cancelled, true);
      assert.equal(body.locked, false);
    }
  }));

test("concurrent requests share no answer or diagnostic context even inside the same incoming trace", () =>
  withConfig(async root => {
    const selected = loadGeneratorConfig(root);
    const incoming = createRootContext({ traceState: "test=recorded" });
    const pending: ((response: Response) => void)[] = [];
    const calls: unknown[] = [], events: unknown[] = [];
    const handler = createSummaryHandler({
      ...selected, runtime: configuredRuntime, writeEvent: event => { events.push(event); },
      send: async native => {
        assert.equal(native.headers.has("traceparent"), false);
        calls.push(JSON.parse(await native.text()));
        return new Promise<Response>(resolve => {
          pending.push(resolve);
          if (pending.length === 2) for (const finish of pending.splice(0).reverse()) finish(reply());
        });
      },
    });
    const inputs = ["First independent text.", "Second independent text."];
    const responses = await Promise.all(inputs.map(input_text => handler(request(
      { input_text }, writeTraceContext(incoming),
    ))));
    const contexts = responses.map(response => readTraceContext(Object.fromEntries(response.headers)));
    assert.notEqual(contexts[0]?.spanId, contexts[1]?.spanId);
    assert.ok(contexts.every(context => context?.traceId === incoming.traceId));
    assert.deepEqual(calls, inputs.map(input => buildModelRequest(
      configuredRuntime, selected.systemPrompt, input, { type: "json_object" },
    )));
    assert.deepEqual(new Set(events.map(event => readCloudEvent(event, value => value).traceparent)),
      new Set(responses.map(response => response.headers.get("traceparent"))));
    assert.ok(responses.every(response => response.status === 200));
  }));

test("empty native chunks cannot grow the read or starve its complete deadline", () =>
  withConfig(async root => {
    let cancelled = false;
    const stream = new ReadableStream<Uint8Array>({
      pull(controller) { controller.enqueue(new Uint8Array()); },
      cancel() { cancelled = true; },
    }, { highWaterMark: 0 });
    const response = await createSummaryHandler({
      ...loadGeneratorConfig(root), runtime: { ...configuredRuntime, timeout_seconds: 0.01 }, writeEvent: () => {},
      send: async () => new Response(stream, { headers: { "Content-Type": "application/json" } }),
    })(request({ input_text: "Empty native stream." }));
    assert.equal(response.status, 500);
    assert.equal(cancelled, true);
    assert.equal(stream.locked, false);
  }));

test("an environment proxy cannot redirect source text away from the committed native destination", () =>
  withConfig(async root => {
    const previous = process.env.HTTP_PROXY;
    process.env.HTTP_PROXY = "http://unreviewed-proxy.example";
    let calls = 0;
    try {
      const response = await createSummaryHandler({
        ...loadGeneratorConfig(root), runtime: configuredRuntime, writeEvent: () => {},
        send: async () => { calls += 1; return reply(); },
      })(request({ input_text: "Private source must stay at its configured recipient." }));
      assert.equal(response.status, 500);
      assert.deepEqual(await response.json(), { error: "The summary could not be generated.", code: "GENERATE_SUMMARY_FAILED" });
      assert.equal(calls, 0);
    } finally {
      if (previous === undefined) delete process.env.HTTP_PROXY;
      else process.env.HTTP_PROXY = previous;
    }
  }));
