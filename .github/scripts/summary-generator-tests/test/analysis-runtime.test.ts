/** Prove that full-analysis overrides, prompts and preparation remain outside the summary API. */
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { createChildContext, createRootContext } from "@idhazh/common-contracts/create-operation-context";
import { EnvironmentVariablesSchema } from "../contracts/analysis-environment.schema.js";
import { RawModelAnalysisSchema } from "../contracts/analysis-result.schema.js";
import { SummaryFieldsSchema } from "../../../../services/summary-generator/src/schemas/summary-result.schema.js";
import { buildModelRequest } from "../../../../services/summary-generator/src/services/model-request.service.js";
import { queryLlamaServer, buildInferencePrompt } from "../query-analysis.js";
import { orchestratePipeline } from "../orchestrate-analysis.js";
import { PipelineEventBus } from "../publish-events.js";
import { SUMMARY_GENERATOR_TESTS_EVENT_SOURCE } from "../declare-event-source.js";
import { loadAnalysisConfig, loadAnalysisSettings, loadEnvConfig } from "../load-analysis-config.js";
import {
  readJson, withConfig, type RecordedNativeReply,
} from "../../../../services/summary-generator/test/model-recordings.js";
import { recordOutput, withRecordedModel } from "./pipeline-recordings.js";

test("inference callbacks retain the supplied parent and input link with a recorded full analysis", { timeout: 120000 }, () =>
  withConfig(root => withRecordedModel(root, async ({ runtime, send }) => {
    const parent = createRootContext({ traceState: "test=recorded" });
    const input = createRootContext();
    const context = createChildContext(parent, { links: [{ traceId: input.traceId, spanId: input.spanId }] });
    let dispatched = 0;
    const result = await queryLlamaServer(runtime, "System instruction", "Article text", context, operation => {
      dispatched += 1;
      assert.deepEqual(operation, context);
    }, send, loadAnalysisConfig(root));
    assert.equal(dispatched, 1);
    assert.deepEqual(result.context, context);
    const recorded = readJson<RecordedNativeReply>("tests/fixtures/typescript-metadata/summarizer-model-response.json");
    assert.equal(result.rawContent, recorded.choices[0].message.content);
    assert.deepEqual(result.parsedAnalysis, JSON.parse(result.rawContent));
    assert.deepEqual(result.usage, recorded.usage);
    for (const key of ["headline", "executive_summary", "key_points"] as const) {
      assert.equal(RawModelAnalysisSchema.shape[key], SummaryFieldsSchema.shape[key]);
    }
  })));

test("environment values and legacy request overrides cannot replace the selected model or destination", { timeout: 120000 }, () =>
  withConfig(root => withRecordedModel(root, async ({ runtime, send, calls }) => {
    const environment = EnvironmentVariablesSchema.parse({
      CONFIG_ROOT: root, SERVER_URL: "https://wrong.example", MODEL_NAME: "not-selected",
    });
    assert.equal("SERVER_URL" in environment, false);
    assert.equal("MODEL_NAME" in environment, false);
    assert.notEqual(runtime.base_url, "https://wrong.example");
    assert.notEqual(runtime.request.model, "not-selected");
    const settings = loadAnalysisSettings(root);
    const bus = new PipelineEventBus(SUMMARY_GENERATOR_TESTS_EVENT_SOURCE, path.join(root, "override-events.jsonl"));
    for (const override of [
      { server_url: "https://wrong.example" }, { model_name: "not-selected" },
    ]) {
      await assert.rejects(() => orchestratePipeline({
        input_text: "Article text", url: "", system_prompt: "System instruction", ...override,
      }, bus, runtime, createRootContext(), send, settings), /committed model_server|selected model/);
    }
    assert.equal(calls.length, 0);
    await orchestratePipeline({
      input_text: "Article text", url: "", system_prompt: "System instruction",
      server_url: runtime.base_url, model_name: runtime.request.model,
    }, bus, runtime, createRootContext(), send, settings);
    assert.equal(calls.length, 1);
  })));

test("configured base and suffix files preserve the two-newline composition and the legacy base override", { timeout: 120000 }, () =>
  withConfig(root => withRecordedModel(root, async ({ runtime, send, calls }) => {
    const original = loadAnalysisConfig(root);
    const base = readFileSync(path.join(root, original.base_prompt_file), "utf8");
    const suffix = readFileSync(path.join(root, original.analysis_prompt_file), "utf8");
    const environment = loadEnvConfig({ CONFIG_ROOT: root });
    assert.equal(environment.PROMPT, base);
    assert.equal(buildInferencePrompt(base, "Title", "Text", suffix).fullSystemPrompt, `${base}\n\n${suffix}`);
    writeFileSync(path.join(root, "prompts/changed-base.txt"), "Changed base.");
    writeFileSync(path.join(root, "prompts/changed-analysis.txt"), "Changed full-analysis suffix.");
    writeFileSync(path.join(root, "summary-generator/workflow.json"), JSON.stringify({
      ...original, max_input_words: 2, base_prompt_file: "prompts/changed-base.txt",
      analysis_prompt_file: "prompts/changed-analysis.txt", heartbeat_ms: 1,
    }));
    const configured = loadEnvConfig({ CONFIG_ROOT: root, PROMPT: " Exact base override. " });
    assert.equal(loadEnvConfig({ CONFIG_ROOT: root }).PROMPT, "Changed base.");
    const diagnostic = recordOutput();
    const bus = new PipelineEventBus(
      SUMMARY_GENERATOR_TESTS_EVENT_SOURCE, path.join(root, "configured-events.jsonl"),
      configured.workflow.logging, diagnostic.writer,
    );
    const result = await orchestratePipeline({
      input_text: "one two three", url: "", system_prompt: configured.PROMPT,
    }, bus, runtime, createRootContext(), send,
    { config: configured.workflow, analysisPrompt: configured.analysisPrompt });
    assert.equal(result.input_text, "one two\n\n[...Truncated to fit context window...]");
    assert.equal(result.source_audit.extractedText, "one two three");
    assert.equal(result.system_prompt, "Exact base override.\n\nChanged full-analysis suffix.");
    assert.deepEqual(calls[0].data, buildModelRequest(runtime, result.system_prompt, result.user_prompt, { type: "json_object" }));
  })));

test("the caller's configured native byte bounds reach the shared transport rather than a default root", { timeout: 120000 }, () =>
  withConfig(root => withRecordedModel(root, async ({ runtime, send, calls }) => {
    const original = loadAnalysisConfig(root);
    const settings = loadAnalysisSettings(root);
    const prompt = buildInferencePrompt("base", "Direct Input Text", "text", settings.analysisPrompt);
    const bytes = Buffer.byteLength(JSON.stringify(buildModelRequest(
      runtime, prompt.fullSystemPrompt, prompt.userPrompt, { type: "json_object" },
    )));
    writeFileSync(path.join(root, "summary-generator/workflow.json"), JSON.stringify({
      ...original, max_native_request_bytes: bytes - 1,
    }));
    const bus = new PipelineEventBus(SUMMARY_GENERATOR_TESTS_EVENT_SOURCE, path.join(root, "bounded-events.jsonl"));
    await assert.rejects(() => orchestratePipeline({
      input_text: "text", url: "", system_prompt: "base",
    }, bus, runtime, createRootContext(), send, loadAnalysisSettings(root)), /byte allowance/);
    assert.equal(calls.length, 0);
    assert.equal(bus.getEventHistory().some(event => event.type === "OUTPUT_STRUCTURED"), false);
  })));

test("explicitly missing native measurements retain only the full-analysis caller's legacy defaults", { timeout: 120000 }, () =>
  withConfig(async root => {
    const { loadModelRuntime } = await import("../../../../services/summary-generator/src/config/load-model-runtime.js");
    const runtime = loadModelRuntime(root);
    const reply = readJson<RecordedNativeReply>("tests/fixtures/typescript-metadata/summarizer-model-response.json");
    const result = await queryLlamaServer(runtime, "system", "input", createRootContext(), undefined,
      async () => new Response(JSON.stringify({
        ...reply, usage: { prompt_tokens: null, completion_tokens: null }, timings: null,
      }), { headers: { "Content-Type": "application/json" } }), loadAnalysisConfig(root));
    assert.deepEqual(result.usage, { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 });
    assert.deepEqual(result.timings, {});
    assert.equal(result.rawContent, reply.choices[0].message.content);
  }));
