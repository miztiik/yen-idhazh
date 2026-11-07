/** Prove the prepared-input, pure-result and truthful-health contracts without a model call. */
import assert from "node:assert/strict";
import { test } from "node:test";
import { writeFileSync } from "node:fs";
import path from "node:path";
import { GeneratorConfigSchema, loadGeneratorConfig } from "../src/config/load-generator-config.js";
import { withConfig } from "./model-recordings.js";
import { SummarizeRequestSchema } from "../src/schemas/request-payload.schema.js";
import {
  SUMMARY_API_VERSION, SUMMARY_API_CHANGELOG, SummaryFieldsSchema,
  SummaryResultSchema, SummaryHealthSchema, SummaryErrorSchema,
} from "../src/schemas/summary-result.schema.js";

test("prepared text and prompt overrides stay exact while removed fields fail", () => {
  const request = { input_text: "  input \n", system_prompt: "  override \n" };
  assert.deepEqual(SummarizeRequestSchema.parse(request), request);
  for (const field of ["url", "server_url", "model_name", "conversation", "session", "messages", "history"]) {
    assert.equal(SummarizeRequestSchema.safeParse({ ...request, [field]: "unsupported" }).success, false);
  }
  for (const input of [{}, { input_text: "" }, { input_text: " \n" }, { input_text: "text", system_prompt: "" }]) {
    assert.equal(SummarizeRequestSchema.safeParse(input).success, false);
  }
});

test("the summary result is strict, keeps nonempty fields and accepts actual zero or absent token counts", () => {
  const result = {
    success: true, data: { headline: "title", executive_summary: "summary", key_points: [] },
    prompt_sha256: "a".repeat(64), prompt_source: "default",
    usage: { prompt_tokens: null, completion_tokens: 0 },
  };
  assert.deepEqual(SummaryResultSchema.parse(result), result);
  assert.equal(SummaryResultSchema.safeParse({ ...result, data: { ...result.data, sentiment: "positive" } }).success, false);
  for (const usage of [{ prompt_tokens: -1, completion_tokens: 0 }, { completion_tokens: 0 }]) {
    assert.equal(SummaryResultSchema.safeParse({ ...result, usage }).success, false);
  }
  for (const data of [
    { ...result.data, headline: "" }, { ...result.data, executive_summary: "" }, { ...result.data, key_points: [""] },
  ]) assert.equal(SummaryFieldsSchema.safeParse(data).success, false);
  assert.equal(SummaryFieldsSchema.safeParse({ ...result.data, headline: " " }).success, true);
});

test("health claims configuration availability only and the native contract has its own date and changelog", () => {
  assert.deepEqual(SummaryHealthSchema.parse({ status: "ok", version: SUMMARY_API_VERSION }),
    { status: "ok", version: SUMMARY_API_VERSION });
  assert.equal(SummaryHealthSchema.safeParse({ status: "ok", version: SUMMARY_API_VERSION, memory: {} }).success, false);
  assert.equal(SummaryHealthSchema.safeParse({ status: "ok", version: "2026-11-05" }).success, false);
  assert.equal(SUMMARY_API_CHANGELOG[0].version, SUMMARY_API_VERSION);
  assert.equal(SummaryErrorSchema.safeParse({ code: "INVALID_REQUEST", error: "Invalid request." }).success, true);
  assert.equal(SummaryErrorSchema.safeParse({ code: "RAW_EXCEPTION", error: "invalid" }).success, false);
});

test("named prompt files preserve exact text and fail on invalid paths, blank text or invalid UTF-8", () =>
  withConfig(async root => {
    const original = loadGeneratorConfig(root).config;
    const text = "  Changed default.\n ";
    const file = path.join(root, "prompts/alternate.txt");
    writeFileSync(file, text);
    writeFileSync(path.join(root, "summary-generator/api.json"), JSON.stringify({
      ...original, prompt_file: "prompts/alternate.txt",
    }));
    assert.equal(loadGeneratorConfig(root).systemPrompt, text);
    writeFileSync(file, " \n");
    assert.throws(() => loadGeneratorConfig(root), /must not be blank/);
    writeFileSync(file, new Uint8Array([255]));
    assert.throws(() => loadGeneratorConfig(root));
    for (const prompt_file of ["../outside.txt", "/absolute.txt", "prompts/../outside.txt", "prompts\\outside.txt", "https://outside.example"]) {
      assert.equal(GeneratorConfigSchema.safeParse({ ...original, prompt_file }).success, false);
    }
  }));
