// Prove that new declarations reach real chat requests without a model-name branch.
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import http from "node:http";
import path from "node:path";
import { test } from "node:test";
import { createChildContext, createRootContext } from "@idhazh/common-contracts/create-operation-context";
import { loadModelRuntime } from "../src/config/load-model-runtime.js";
import { EnvironmentVariablesSchema } from "../src/schemas/environment-variable.schema.js";
import { buildModelRequest, readModelContent } from "../src/services/model-request.service.js";
import { queryLlamaServer } from "../src/services/query-llama.service.js";
import { orchestratePipeline } from "../src/pipeline/orchestrate-pipeline.service.js";
import { PipelineEventBus } from "../src/services/dispatch-event.service.js";
import { readJson, repositoryRoot, withConfig, writeEntry } from "./model-recordings.js";
import { withRecordedModel } from "./pipeline-recordings.js";

test("a previously unseen declaration supplies all sampling and template values", { timeout: 120000 }, () =>
  withConfig((root, entry) => {
    entry.id = "independent-substitution";
    entry.arch = "previously-unseen-architecture";
    entry.thinking_kwarg = "reasoning_mode";
    entry.thinking_close = "[/analysis]";
    entry.chat_template_kwargs = { response_style: "concise", nested_option: { level: 2 } };
    entry.reasoning_delimiters = ["[analysis]", "[/analysis]"];
    entry.request_timeout_minutes = 0.25;
    entry.sampling = { temperature: 0.73, top_p: 0.61, max_tokens: 123, adaptive_p: 0.42 };
    writeEntry(root, entry);
    const runtime = loadModelRuntime(root);
    const request = buildModelRequest(runtime, "System instruction", "Article text", { type: "json_object" });
    assert.equal(request.model, entry.id);
    for (const [key, value] of Object.entries(entry.sampling)) {
      assert.deepEqual(request[key as keyof typeof request], value);
    }
    assert.deepEqual(request.chat_template_kwargs, {
      ...entry.chat_template_kwargs, reasoning_mode: true,
    });
    assert.deepEqual(runtime.reasoning_delimiters, entry.reasoning_delimiters);
    assert.equal(runtime.timeout_seconds, 15);
    assert.equal(runtime.base_url, readJson("config/idhazh.json").model_server.base_url);
    assert.deepEqual(request.messages, [
      { role: "system", content: "System instruction" },
      { role: "user", content: "Article text" },
    ]);
    assert.deepEqual(request.response_format, { type: "json_object" });
    assert.equal(request.stream, false);
  }));

test("inference callbacks retain the supplied parent and input link with a real recorded result", { timeout: 120000 }, () =>
  withConfig(root => withRecordedModel(root, async ({ runtime }) => {
    const parent = createRootContext({ traceState: "test=recorded" });
    const input = createRootContext();
    const context = createChildContext(parent, {
      links: [{ traceId: input.traceId, spanId: input.spanId }],
    });
    let dispatched = 0;
    const result = await queryLlamaServer(runtime, "System instruction", "Article text", context, operation => {
      dispatched += 1;
      assert.deepEqual(operation, context);
    });
    assert.equal(dispatched, 1);
    assert.deepEqual(result.context, context);
    const recorded = readJson("tests/fixtures/typescript-metadata/summarizer-model-response.json");
    assert.equal(result.rawContent, recorded.choices[0].message.content);
    assert.deepEqual(result.parsedAnalysis, JSON.parse(result.rawContent));
    assert.deepEqual(result.usage, recorded.usage);
  })));

test("a template with no reasoning switch accepts an empty or arbitrary keyword map", { timeout: 120000 }, () =>
  withConfig((root, entry) => {
    entry.thinking_kwarg = null;
    entry.thinking_close = "[/analysis]";
    entry.chat_template_kwargs = {};
    entry.reasoning_delimiters = null;
    writeEntry(root, entry);
    assert.equal("chat_template_kwargs" in loadModelRuntime(root).request, false);
    entry.chat_template_kwargs = { output_style: "direct" };
    writeEntry(root, entry);
    assert.deepEqual(loadModelRuntime(root).request.chat_template_kwargs, entry.chat_template_kwargs);
    delete entry.thinking_kwarg;
    writeEntry(root, entry);
    assert.throws(() => loadModelRuntime(root), /thinking_kwarg/);
  }));

test("environment values cannot replace the committed model or destination", { timeout: 120000 }, () =>
  withConfig((root) => {
    const environment = EnvironmentVariablesSchema.parse({
      CONFIG_ROOT: root, SERVER_URL: "https://wrong.example", MODEL_NAME: "not-selected",
    });
    assert.equal("SERVER_URL" in environment, false);
    assert.equal("MODEL_NAME" in environment, false);
    const runtime = loadModelRuntime(environment.CONFIG_ROOT);
    assert.notEqual(runtime.base_url, "https://wrong.example");
    assert.notEqual(runtime.request.model, "not-selected");
    assert.throws(
      () => buildModelRequest(
        { ...runtime, request: { ...runtime.request, messages: [] } },
        "system", "article", { type: "json_object" },
      ),
      /sampling may not set messages/,
    );
  }));

test("recorded replies use the runtime reasoning channel before explicit inline delimiters", () => {
  const split = readJson("tests/fixtures/completions/reasoning-channel.json");
  const inline = readJson("tests/fixtures/completions/reasoned-anyway.json");
  const declared = { reasoning_delimiters: ["<think>", "</think>"] as [string, string] };
  assert.equal(readModelContent(split, declared), split.choices[0].message.content);
  assert.equal(readModelContent(inline, { reasoning_delimiters: null }), inline.choices[0].message.content);
  assert.equal(JSON.parse(readModelContent(inline, declared)).title,
    "Example Lab publishes smaller inference model under a permissive licence");
  const emptyChannel = structuredClone(inline);
  emptyChannel.choices[0].message.reasoning_content = "";
  assert.equal(readModelContent(emptyChannel, declared), readModelContent(inline, declared));
  assert.equal(emptyChannel.choices[0].message.content, inline.choices[0].message.content);
  assert.equal(readModelContent(readJson("tests/fixtures/completions/misfiled-into-reasoning.json"), declared), "");
  const quoted = '{"summary": "The article quotes <think> as ordinary text."}';
  assert.equal(readModelContent({ choices: [{ message: { content: quoted } }] }, declared), quoted);
  assert.throws(() => readModelContent({
    choices: [{ message: { content: "<think>unfinished" } }],
  }, declared), /unfinished reasoning block/);
});

test("the real HTTP caller sends selected settings and rejects incompatible recorded replies", { timeout: 120000 }, () =>
  withConfig(async (root, entry) => {
    const recorded = [
      readFileSync(path.join(repositoryRoot, "tests", "fixtures", "completions", "reasoning-channel.json")),
      readFileSync(path.join(repositoryRoot, "tests", "fixtures", "completions", "reasoned-anyway.json")),
    ];
    const received: { path: string | undefined; payload: any }[] = [];
    const server = http.createServer((request, response) => {
      let body = "";
      request.on("data", (chunk) => { body += chunk; });
      request.on("end", () => {
        const reply = recorded[received.length];
        received.push({ path: request.url, payload: JSON.parse(body) });
        response.writeHead(200, { "Content-Type": "application/json" });
        response.end(reply);
      });
    });
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    try {
      const address = server.address();
      assert.ok(address && typeof address !== "string");
      const pointer = JSON.parse(readFileSync(path.join(root, "idhazh.json"), "utf8"));
      pointer.model_server.base_url = `http://127.0.0.1:${address.port}`;
      writeFileSync(path.join(root, "idhazh.json"), JSON.stringify(pointer));
      entry.id = "recorded-boundary";
      entry.thinking_kwarg = "reasoning_mode";
      entry.thinking_close = null;
      entry.chat_template_kwargs = { response_style: "short" };
      entry.reasoning_delimiters = ["<think>", "</think>"];
      entry.sampling = { temperature: 0.47, max_tokens: 321, adaptive_p: 0.19 };
      writeEntry(root, entry);
      const runtime = loadModelRuntime(root);
      await assert.rejects(
        () => queryLlamaServer(runtime, "System instruction", "Article text", createRootContext()),
        /Model response failed RawModelAnalysisSchema/,
      );
      assert.equal(received.length, 1);
      assert.equal(received[0].path, "/v1/chat/completions");
      assert.equal(received[0].payload.model, "recorded-boundary");
      assert.equal(received[0].payload.adaptive_p, 0.19);
      assert.equal(received[0].payload.max_tokens, 321);
      assert.deepEqual(received[0].payload.chat_template_kwargs, {
        response_style: "short", reasoning_mode: false,
      });
      await assert.rejects(
        () => queryLlamaServer(runtime, "System instruction", "Article text", createRootContext()),
        /Model response failed RawModelAnalysisSchema/,
      );
      const eventBus = new PipelineEventBus(readJson("config/typescript-event-sources.json").summarizer);
      await assert.rejects(() => orchestratePipeline({
        input_text: "Article text", url: "", system_prompt: "System instruction",
        server_url: "https://wrong.example",
      }, eventBus, runtime, createRootContext()), /committed model_server.base_url/);
      await assert.rejects(() => orchestratePipeline({
        input_text: "Article text", url: "", system_prompt: "System instruction",
        model_name: "not-selected",
      }, eventBus, runtime, createRootContext()), /selected model declaration/);
      assert.equal(received.length, 2);
    } finally {
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    }
  }));
