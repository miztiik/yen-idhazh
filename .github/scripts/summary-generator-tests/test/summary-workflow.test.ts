/** Prove the real summary-only caller's saved response, trace, preparation and explicit missing readings. */
import assert from "node:assert/strict";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { createHash } from "node:crypto";
import { readTraceContext } from "@idhazh/common-contracts/propagate-trace-context";
import { createSummaryHandler } from "../../../../services/summary-generator/src/api/serve-http-api.js";
import {
  GENERATE_SUMMARY_PATH, SUMMARY_GENERATOR_HEALTH_PATH, summaryGeneratorUrl,
} from "../../../../services/summary-generator/src/api/api-paths.js";
import { SUMMARY_GENERATOR_EVENT_SOURCE } from "../../../../services/summary-generator/src/declare-event-source.js";
import { loadGeneratorConfig } from "../../../../services/summary-generator/src/config/load-generator-config.js";
import { loadModelRuntime } from "../../../../services/summary-generator/src/config/load-model-runtime.js";
import { SummaryResultSchema } from "../../../../services/summary-generator/src/schemas/summary-result.schema.js";
import {
  readJson, repositoryRoot, withConfig, type RecordedNativeReply,
} from "../../../../services/summary-generator/test/model-recordings.js";
import { loadAnalysisConfig } from "../load-analysis-config.js";
import { readSummaryWorkflowEvent } from "../contracts/summary-workflow.schema.js";
import { SUMMARY_GENERATOR_TESTS_EVENT_SOURCE } from "../declare-event-source.js";
import { runSummaryApi } from "../run-summary-api.js";
import { renderSummaryReport } from "../render-summary-report.js";
import { waitSummaryApi } from "../wait-summary-api.js";

const configuredRuntime = loadModelRuntime();
const recorded = readFileSync(path.join(repositoryRoot, "tests/fixtures/typescript-metadata/summarizer-model-response.json"));
const digest = (value: string) => createHash("sha256").update(value, "utf8").digest("hex");
function configureOutput(root: string, name = "summary-output") {
  const directory = path.join(root, name);
  const config = loadAnalysisConfig(root);
  writeFileSync(path.join(root, "summary-generator/workflow.json"), JSON.stringify({
    ...config, output_directory: path.relative(repositoryRoot, directory).split(path.sep).join("/"),
  }));
  return directory;
}

test("the summary-only workflow saves the actual API response and its own report with native usage and trace", { timeout: 120000 }, () =>
  withConfig(async root => {
    const directory = configureOutput(root);
    const nativeCalls: Request[] = [], diagnostics: unknown[] = [];
    const api = createSummaryHandler({
      ...loadGeneratorConfig(root), runtime: configuredRuntime,
      writeEvent: event => { diagnostics.push(event); },
      send: async request => {
        nativeCalls.push(request);
        return new Response(recorded, { headers: { "Content-Type": "application/json" } });
      },
    });
    const summaryFile = path.join(root, "step-summary.md");
    const outputFile = path.join(root, "step-output.txt");
    writeFileSync(summaryFile, "Earlier step.\n");
    const event = await runSummaryApi({
      configRoot: root, input: { input_text: "Prepared source input." },
      environment: { SYSTEM_PROMPT: "", GITHUB_OUTPUT: outputFile },
      stepSummaryPath: summaryFile, send: api,
    });
    const result = SummaryResultSchema.parse(JSON.parse(readFileSync(path.join(directory, "summary-response.json"), "utf8")));
    const saved = readSummaryWorkflowEvent(JSON.parse(readFileSync(path.join(directory, "summary-events.jsonl"), "utf8")));
    assert.deepEqual(result, event.data.result);
    assert.deepEqual(saved, event);
    assert.equal(event.source, SUMMARY_GENERATOR_TESTS_EVENT_SOURCE);
    assert.equal(event.data.result.prompt_source, "default");
    assert.equal("system_prompt" in event.data.request, false);
    assert.deepEqual(event.data.result.usage, { prompt_tokens: 703, completion_tokens: 340 });
    assert.equal(event.data.input_sha256, digest(event.data.request.input_text));
    assert.equal(nativeCalls.length, 1);
    assert.equal(new URL(nativeCalls[0].url).pathname, "/v1/chat/completions");
    const diagnostic = diagnostics[0] as { source: string; traceparent: string };
    assert.equal(diagnostic.source, SUMMARY_GENERATOR_EVENT_SOURCE);
    assert.equal(diagnostic.traceparent, event.data.api_traceparent);
    const caller = readTraceContext({ traceparent: event.traceparent });
    const producer = readTraceContext({ traceparent: event.data.api_traceparent });
    assert.equal(caller?.traceId, producer?.traceId);
    assert.notEqual(caller?.spanId, producer?.spanId);
    const report = readFileSync(path.join(directory, "summary-report.md"), "utf8");
    assert.equal(report, renderSummaryReport(event));
    for (const value of [event.data.result.data.headline, event.data.result.prompt_sha256, event.id, event.traceparent]) {
      assert.ok(report.includes(value));
    }
    assert.ok(report.includes("Not collected; this call generates a summary only"));
    assert.ok(report.includes("Not collected; this workflow makes no host measurement call"));
    assert.ok(readFileSync(summaryFile, "utf8").startsWith("Earlier step.\n"));
    assert.ok(readFileSync(outputFile, "utf8").includes(loadAnalysisConfig(root).output_directory));
  }));

test("failed URL fallback and caller-owned shortening precede an exact complete API prompt override", { timeout: 120000 }, () =>
  withConfig(async root => {
    configureOutput(root);
    const config = loadAnalysisConfig(root);
    writeFileSync(path.join(root, "summary-generator/workflow.json"), JSON.stringify({ ...config, max_input_words: 2 }));
    const selected = loadGeneratorConfig(root);
    const prompt = " Complete replacement prompt. \n";
    let nativeBody: unknown, sourceHeaders: Headers | undefined;
    const api = createSummaryHandler({
      ...selected, runtime: configuredRuntime, writeEvent: () => {},
      send: async request => {
        nativeBody = JSON.parse(await request.text());
        return new Response(recorded, { headers: { "Content-Type": "application/json" } });
      },
    });
    const event = await runSummaryApi({
      configRoot: root, environment: {}, input: { url: "https://source.example/unavailable", input_text: "one two three" },
      systemPrompt: prompt,
      send: async request => {
        if (new URL(request.url).pathname === GENERATE_SUMMARY_PATH) return api(request);
        sourceHeaders = request.headers;
        return new Response("", { status: 503 });
      },
    });
    assert.equal(event.data.source_audit.sourceType, "FALLBACK_INPUT_TEXT");
    assert.equal(event.data.source_audit.extractedText, "one two three");
    assert.equal(event.data.request.input_text, "one two\n\n[...Truncated to fit context window...]");
    assert.equal(event.data.result.prompt_sha256, digest(prompt));
    assert.equal(event.data.result.prompt_source, "override");
    assert.equal((nativeBody as { messages: { content: string }[] }).messages[0].content, prompt);
    assert.equal(sourceHeaders?.has("traceparent"), false);
    assert.equal(sourceHeaders?.has("tracestate"), false);
    assert.equal(event.data.classifications, "not_collected");
    assert.equal(event.data.machine_readings, "not_collected");
  }));

test("absent native counts remain absent readings while actual zeroes remain actual zeroes", { timeout: 120000 }, () =>
  withConfig(async root => {
    for (const withZero of [false, true]) {
      configureOutput(root, withZero ? "zero-output" : "absent-output");
      const reply: Partial<RecordedNativeReply> = readJson<RecordedNativeReply>(
        "tests/fixtures/typescript-metadata/summarizer-model-response.json",
      );
      if (withZero) reply.usage = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };
      else delete reply.usage;
      const api = createSummaryHandler({
        ...loadGeneratorConfig(root), runtime: configuredRuntime, writeEvent: () => {},
        send: async () => new Response(JSON.stringify(reply), { headers: { "Content-Type": "application/json" } }),
      });
      const event = await runSummaryApi({ configRoot: root, environment: {}, input: { input_text: "source" }, send: api });
      assert.deepEqual(event.data.result.usage, {
        prompt_tokens: withZero ? 0 : null, completion_tokens: withZero ? 0 : null,
      });
      const report = renderSummaryReport(event);
      assert.equal(report.includes("Not provided by the native model"), !withZero);
      assert.equal(report.includes("0 tokens reported by the native model"), withZero);
    }
  }));

test("the caller refuses invalid API results and unrelated carriers without writing a success report", { timeout: 120000 }, () =>
  withConfig(async root => {
    for (const fault of ["result", "carrier", "prompt"] as const) {
      const directory = configureOutput(root, `${fault}-output`);
      const reportFile = path.join(root, `${fault}-step-summary.md`);
      writeFileSync(reportFile, "Earlier step.");
      const api = createSummaryHandler({
        ...loadGeneratorConfig(root), runtime: configuredRuntime, writeEvent: () => {},
        send: async () => new Response(recorded, { headers: { "Content-Type": "application/json" } }),
      });
      await assert.rejects(() => runSummaryApi({
        configRoot: root, environment: {}, input: { input_text: "source" }, stepSummaryPath: reportFile,
        send: async request => {
          const response = await api(request);
          const value = SummaryResultSchema.parse(await response.json());
          if (fault === "result") value.data.headline = "";
          if (fault === "prompt") value.prompt_source = "override";
          const headers = new Headers(response.headers);
          if (fault === "carrier") headers.set("traceparent", "invalid");
          return new Response(JSON.stringify(value), { headers });
        },
      }), fault === "result" ? /headline/ : fault === "carrier" ? /unrelated response carrier/ : /prompt identity/);
      assert.equal(existsSync(path.join(directory, "summary-response.json")), false);
      assert.equal(existsSync(path.join(directory, "summary-events.jsonl")), false);
      assert.equal(existsSync(path.join(directory, "summary-report.md")), false);
      assert.equal(readFileSync(reportFile, "utf8"), "Earlier step.");
    }
  }));

test("readiness uses the configured listener and current health contract without probing model readiness", async () =>
  withConfig(async root => {
    const selected = loadGeneratorConfig(root);
    writeFileSync(path.join(root, "summary-generator/api.json"), JSON.stringify({
      ...selected.config, hostname: "::1", port: selected.config.port + 1,
    }));
    const config = loadAnalysisConfig(root);
    writeFileSync(path.join(root, "summary-generator/workflow.json"), JSON.stringify({
      ...config, api_poll_interval_ms: 1, api_startup_timeout_ms: 200, body_read_timeout_ms: 20,
    }));
    const changed = loadGeneratorConfig(root);
    const api = createSummaryHandler({
      ...changed, runtime: configuredRuntime, writeEvent: () => {}, send: async () => { throw new Error("No model probe."); },
    });
    const requested: string[] = [];
    await waitSummaryApi(root, process.pid, async request => {
      requested.push(request.url);
      return requested.length === 1 ? new Response("", { status: 503 }) : api(request);
    });
    assert.deepEqual(requested, [
      summaryGeneratorUrl(changed.config, SUMMARY_GENERATOR_HEALTH_PATH),
      summaryGeneratorUrl(changed.config, SUMMARY_GENERATOR_HEALTH_PATH),
    ]);
  }));
