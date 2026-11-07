/** Prove that model declarations and native answer parsing remain independent of model names. */
import assert from "node:assert/strict";
import { test } from "node:test";
import { loadModelRuntime } from "../src/config/load-model-runtime.js";
import { loadGeneratorConfig } from "../src/config/load-generator-config.js";
import { buildModelRequest, readModelContent } from "../src/services/model-request.service.js";
import { queryLlamaServer } from "../src/services/query-llama.service.js";
import { readJson, withConfig, writeEntry, type RecordedNativeReply } from "./model-recordings.js";

test("a previously unseen declaration supplies all sampling and template values", { timeout: 120000 }, () =>
  withConfig(async (root, entry) => {
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
      assert.deepEqual((request as Record<string, unknown>)[key], value);
    }
    assert.deepEqual(request.chat_template_kwargs, { ...entry.chat_template_kwargs, reasoning_mode: true });
    assert.deepEqual(runtime.reasoning_delimiters, entry.reasoning_delimiters);
    assert.equal(runtime.timeout_seconds, 15);
    assert.equal(runtime.base_url,
      readJson<{ model_server: { base_url: string } }>("config/idhazh.json").model_server.base_url);
    assert.deepEqual(request.messages, [
      { role: "system", content: "System instruction" }, { role: "user", content: "Article text" },
    ]);
    assert.deepEqual(request.response_format, { type: "json_object" });
    assert.equal(request.stream, false);
    let sent: unknown;
    const recorded = readJson<RecordedNativeReply>("tests/fixtures/typescript-metadata/summarizer-model-response.json");
    await queryLlamaServer(runtime, "System instruction", "Article text", loadGeneratorConfig(root).config,
      undefined, async native => {
        sent = JSON.parse(await native.text());
        return new Response(JSON.stringify(recorded), { headers: { "Content-Type": "application/json" } });
      });
    assert.deepEqual(sent, request);
  }));

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

test("native controls cannot overwrite this caller's messages or decoding control", { timeout: 120000 }, () =>
  withConfig((root, entry) => {
    const runtime = loadModelRuntime(root);
    for (const key of ["messages", "response_format"]) {
      assert.throws(() => buildModelRequest({
        ...runtime, request: { ...runtime.request, [key]: {} },
      }, "system", "article", { type: "json_object" }), /sampling may not set/);
      entry.sampling = { [key]: {} };
      writeEntry(root, entry);
      assert.throws(() => loadModelRuntime(root), new RegExp(key));
    }
  }));

test("recorded replies use the native reasoning channel before explicit inline delimiters", () => {
  const split = readJson<RecordedNativeReply>("tests/fixtures/completions/reasoning-channel.json");
  const inline = readJson<RecordedNativeReply>("tests/fixtures/completions/reasoned-anyway.json");
  const declared = { reasoning_delimiters: ["<think>", "</think>"] as [string, string] };
  assert.equal(readModelContent(split, declared), split.choices[0].message.content);
  assert.equal(readModelContent(inline, { reasoning_delimiters: null }), inline.choices[0].message.content);
  assert.equal(JSON.parse(readModelContent(inline, declared)).title,
    "Example Lab publishes smaller inference model under a permissive licence");
  const emptyChannel = structuredClone(inline);
  emptyChannel.choices[0].message.reasoning_content = "";
  assert.equal(readModelContent(emptyChannel, declared), readModelContent(inline, declared));
  assert.equal(emptyChannel.choices[0].message.content, inline.choices[0].message.content);
  assert.equal(readModelContent(
    readJson<RecordedNativeReply>("tests/fixtures/completions/misfiled-into-reasoning.json"), declared,
  ), "");
  const quoted = '{"summary": "The article quotes <think> as ordinary text."}';
  assert.equal(readModelContent({ choices: [{ message: { content: quoted } }] }, declared), quoted);
  assert.throws(() => readModelContent({
    choices: [{ message: { content: "<think>unfinished" } }],
  }, declared), /unfinished reasoning block/);
});
