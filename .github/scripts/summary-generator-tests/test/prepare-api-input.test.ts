/** Prove source word boundaries do not replace independent transport byte limits. */
import assert from "node:assert/strict";
import { test } from "node:test";
import { createRootContext } from "@idhazh/common-contracts/create-operation-context";
import { readGeneratorConfig } from "../../../../services/summary-generator/src/config/load-generator-config.js";
import type { ModelRuntime } from "../../../../services/summary-generator/src/config/load-model-runtime.js";
import {
  BodyLimitError, readBoundedText,
} from "../../../../services/summary-generator/src/services/request-completion.service.js";
import { callSummaryApi } from "../call-summary-api.js";
import { loadAnalysisConfig } from "../load-analysis-config.js";
import { prepareApiInput } from "../prepare-api-input.js";
import { queryLlamaServer } from "../query-analysis.js";

const config = loadAnalysisConfig();
const generator = readGeneratorConfig();
const runtime: ModelRuntime = {
  base_url: "http://127.0.0.1:8080",
  request: { model: "recorded-source-limit-model", stream: false },
  reasoning_delimiters: null,
  timeout_seconds: 1,
  repo: "recorded-source-limit-model",
  file: "recorded.gguf",
};

test("the committed caller allowance is 20000 source words", () => {
  assert.equal(config.max_input_words, 20000);
});

for (const count of [6001, 19999, 20000, 20001]) {
  test(`${count} direct source words obey the configured ceiling and retain the original audit`, async () => {
    const text = Array.from({ length: count }, () => "word").join(" ");
    const prepared = await prepareApiInput({ input_text: text }, createRootContext(), undefined, undefined, config);
    const expected = count <= config.max_input_words
      ? text
      : Array.from({ length: config.max_input_words }, () => "word").join(" ")
        + "\n\n[...Truncated to fit context window...]";
    assert.equal(prepared.input_text, expected);
    assert.equal(prepared.original_word_count, count);
    assert.equal(prepared.source_audit.extractedWordCount, count);
    assert.equal(prepared.source_audit.extractedText, text);
    assert.equal(prepared.source_audit.extractedCharCount, text.length);
    assert.equal(prepared.source_audit.sourceType, "INPUT_TEXT");
  });
}

test("the same word ceiling applies to supplied fallback after a source failure", async () => {
  const text = Array.from({ length: config.max_input_words + 1 }, () => "word").join(" ");
  const progress: string[] = [];
  const prepared = await prepareApiInput(
    { url: "https://source.example/unavailable", input_text: text },
    createRootContext(), event => { progress.push(event.type); },
    async () => new Response("", { status: 503 }), config,
  );
  assert.equal(prepared.original_word_count, config.max_input_words + 1);
  assert.equal(prepared.input_text,
    Array.from({ length: config.max_input_words }, () => "word").join(" ")
      + "\n\n[...Truncated to fit context window...]");
  assert.equal(prepared.source_audit.extractedText, text);
  assert.equal(prepared.source_audit.sourceType, "FALLBACK_INPUT_TEXT");
  assert.match(prepared.source_audit.scrapeError ?? "", /HTTP 503/);
  assert.ok(progress.includes("URL_EXTRACTION_FAILED"));
});

test("raw HTML words do not consume the extracted article word allowance", async () => {
  const text = "The city council published its complete decision after a public meeting. "
    + "Residents can read the report and its supporting documents before the next meeting.";
  const markup = Array.from({ length: config.max_input_words + 1 }, () => "<!-- hidden word -->").join("\n");
  const html = `<html><head><title>Council report</title></head><body>${markup}<article><p>${text}</p></article></body></html>`;
  const prepared = await prepareApiInput(
    { url: "https://source.example/article" }, createRootContext(), undefined,
    async () => new Response(html), config,
  );
  assert.equal(prepared.source_audit.sourceType, "URL");
  assert.ok(prepared.input_text.includes(text));
  assert.equal(prepared.input_text, prepared.source_audit.extractedText);
  assert.equal(prepared.input_text.includes("Truncated"), false);
  assert.ok(prepared.original_word_count < config.max_input_words);
});

test("JSON overhead still exceeds both caller and native request limits below the word ceiling", async () => {
  const text = "\"".repeat(Math.floor(config.max_native_request_bytes / 2) + 1);
  const prepared = await prepareApiInput({ input_text: text }, createRootContext(), undefined, undefined, config);
  assert.equal(prepared.original_word_count, 1);
  assert.equal(prepared.input_text, text);
  assert.ok(Buffer.byteLength(text, "utf8") < config.max_native_request_bytes);
  let requests = 0;
  const send = async () => {
    requests += 1;
    throw new Error("An oversized request must not be sent.");
  };
  const isRequestLimit = (error: unknown) => error instanceof BodyLimitError && error.boundary === "request";
  await assert.rejects(() => callSummaryApi(
    { input_text: prepared.input_text }, createRootContext(), generator, config, runtime, send,
  ), isRequestLimit);
  await assert.rejects(() => queryLlamaServer(
    runtime, "Summarize the source.", prepared.input_text, createRootContext(), undefined, send, config,
  ), isRequestLimit);
  assert.equal(requests, 0);
});

test("a larger source word allowance does not bypass the native response byte ceiling", async () => {
  const body = new Response("x".repeat(config.max_native_response_bytes + 1)).body;
  await assert.rejects(() => readBoundedText(
    body, config.max_native_response_bytes, AbortSignal.timeout(config.body_read_timeout_ms),
  ), (error: unknown) => error instanceof BodyLimitError && error.boundary === "response");
  assert.equal(body?.locked, false);
});
