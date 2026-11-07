/** Do unavailable measurements and recorded zeroes survive calculation and saved-format reading? */
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { createCloudEvent } from "@idhazh/common-contracts/create-cloud-event";
import { createRootContext } from "@idhazh/common-contracts/create-operation-context";
import type { ModelRuntime } from "../../../../services/summary-generator/src/config/load-model-runtime.js";
import { withConfig } from "../../../../services/summary-generator/test/model-recordings.js";
import {
  SummaryStructuredOutputSchema, readSummaryStructuredOutput,
  type LegacySummaryStructuredOutput, type RawModelAnalysis,
} from "../contracts/analysis-result.schema.js";
import {
  parsePipelineEventData, readPipelineEvent, type PipelineEventType,
} from "../contracts/pipeline-event.schema.js";
import {
  DETAILED_TOKEN_METRICS_VERSION, DetailedTokenMetricsSchema, type DetailedTokenMetrics,
} from "../contracts/system-telemetry.schema.js";
import { deriveTokenMetrics } from "../derive-token-metrics.js";
import {
  queryLlamaServer, type LlamaInferenceResponse, type LlamaInferenceTimings,
} from "../query-analysis.js";
import { renderGithubStepSummary } from "../render-report.js";
import { readPipelineEvents } from "../publish-events.js";
import { recordOutput } from "./pipeline-recordings.js";

const analysis: RawModelAnalysis = {
  headline: "Recorded headline", executive_summary: "Recorded summary.", key_points: ["Recorded point."],
  sentiment: "neutral", stance_on_change: "not_applicable", stance_on_economic_power: "not_applicable",
  stance_on_state_power: "not_applicable", stance_on_borders: "not_applicable",
  stance_on_personal_sphere: "not_applicable",
};
const absentUsage: LlamaInferenceResponse["usage"] = {
  prompt_tokens: null, completion_tokens: null, total_tokens: null,
};
const runtime: ModelRuntime = {
  base_url: "http://127.0.0.1:8080", request: { model: "recorded-analysis", stream: false },
  reasoning_delimiters: null, timeout_seconds: 60, repo: "recorded/model", file: "recorded.gguf",
};
const legacyResult: LegacySummaryStructuredOutput = {
  ...analysis, compression_ratio: "50.0%", raw_output: JSON.stringify(analysis),
  source_audit: {
    sourceType: "INPUT_TEXT", sourceIdentifier: "Direct input", sourceTitle: "Recorded article",
    extractedWordCount: 2, extractedCharCount: 13, extractedText: "Article text.",
  },
  token_metrics: {
    prompt_tokens: 0, completion_tokens: 0, total_tokens: 0,
    prompt_time_ms: 0, completion_time_ms: 2250, total_duration_ms: 2250,
    prompt_tokens_per_second: 0, completion_tokens_per_second: 0,
  },
  swap_metrics: {
    swappiness: 0, server_pid: null, server_vm_rss_mb: 0, peak_server_swap_mb: 0,
    final_server_swap_mb: 0, system_swap_used_mb: 0, system_swap_total_mb: 0,
    swap_bytes_written_mb: 0, swap_bytes_read_mb: 0,
  },
  input_text: "Article text.", system_prompt: "System instruction.", user_prompt: "Article text.",
};

test("native counts preserve missing, zero, partial, independent-total and timing-fallback values", async () => {
  const cases: {
    name: string;
    usage?: Partial<LlamaInferenceResponse["usage"]> | null;
    timings?: LlamaInferenceTimings | null;
    expected: LlamaInferenceResponse["usage"];
  }[] = [
    { name: "absent fields", expected: absentUsage },
    { name: "null fields", usage: null, timings: null, expected: absentUsage },
    { name: "empty fields", usage: {}, timings: {}, expected: absentUsage },
    {
      name: "usage zero wins over timing counts", usage: { prompt_tokens: 0, completion_tokens: 0 },
      timings: { prompt_n: 8, predicted_n: 4 },
      expected: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
    },
    { name: "prompt only", usage: { prompt_tokens: 7 }, expected: { ...absentUsage, prompt_tokens: 7 } },
    { name: "completion only", usage: { completion_tokens: 3 }, expected: { ...absentUsage, completion_tokens: 3 } },
    { name: "independent total", usage: { total_tokens: 17 }, expected: { ...absentUsage, total_tokens: 17 } },
    { name: "independent zero total", usage: { total_tokens: 0 }, expected: { ...absentUsage, total_tokens: 0 } },
    {
      name: "timing counts", timings: { prompt_n: 8, predicted_n: 4 },
      expected: { prompt_tokens: 8, completion_tokens: 4, total_tokens: 12 },
    },
    {
      name: "timing zero counts", timings: { prompt_n: 0, predicted_n: 0 },
      expected: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
    },
    {
      name: "partial timing count", usage: { prompt_tokens: null }, timings: { prompt_n: 8 },
      expected: { ...absentUsage, prompt_tokens: 8 },
    },
    {
      name: "mixed usage and timing counts", usage: { prompt_tokens: 7, completion_tokens: null },
      timings: { prompt_n: 8, predicted_n: 4 },
      expected: { prompt_tokens: 7, completion_tokens: 4, total_tokens: 11 },
    },
    {
      name: "reported total wins over a sum", usage: { prompt_tokens: 7, completion_tokens: 3, total_tokens: 17 },
      expected: { prompt_tokens: 7, completion_tokens: 3, total_tokens: 17 },
    },
  ];
  for (const { name, expected, ...measurements } of cases) {
    const result = await queryLlamaServer(runtime, "system", "input", createRootContext(), undefined,
      async () => new Response(JSON.stringify({
        choices: [{ message: { content: JSON.stringify(analysis) } }], ...measurements,
      }), { headers: { "Content-Type": "application/json" } }),
      { max_native_request_bytes: 1048576, max_native_response_bytes: 1048576 });
    assert.deepEqual(result.usage, expected, name);
    assert.deepEqual(result.parsedAnalysis, analysis, name);
  }
});

test("rates require their own measurements and never use whole-request duration", () => {
  const empty = {
    ...absentUsage, prompt_time_ms: null, completion_time_ms: null,
    prompt_tokens_per_second: null, completion_tokens_per_second: null,
  };
  const cases: {
    name: string; usage: LlamaInferenceResponse["usage"]; timings: LlamaInferenceTimings;
    expected: Omit<DetailedTokenMetrics, "version" | "total_duration_ms">;
  }[] = [
    { name: "all missing", usage: absentUsage, timings: {}, expected: empty },
    {
      name: "counts without stage times", usage: { prompt_tokens: 7, completion_tokens: 3, total_tokens: 10 },
      timings: {}, expected: { ...empty, prompt_tokens: 7, completion_tokens: 3, total_tokens: 10 },
    },
    {
      name: "reported times and rates without counts", usage: absentUsage,
      timings: { prompt_ms: 1000, predicted_ms: 0, prompt_per_second: 12.345, predicted_per_second: 0 },
      expected: { ...empty, prompt_time_ms: 1000, completion_time_ms: 0,
        prompt_tokens_per_second: 12.35, completion_tokens_per_second: 0 },
    },
    {
      name: "reported zero times cannot derive rates", usage: { prompt_tokens: 7, completion_tokens: 3, total_tokens: 10 },
      timings: { prompt_ms: 0, predicted_ms: 0 },
      expected: { ...empty, prompt_tokens: 7, completion_tokens: 3, total_tokens: 10,
        prompt_time_ms: 0, completion_time_ms: 0 },
    },
    {
      name: "zero counts with positive times derive zero rates", usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
      timings: { prompt_ms: 1000, predicted_ms: 500 },
      expected: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0, prompt_time_ms: 1000,
        completion_time_ms: 500, prompt_tokens_per_second: 0, completion_tokens_per_second: 0 },
    },
    {
      name: "partial counts preserve both times and an independent total", usage: { ...absentUsage, prompt_tokens: 7, total_tokens: 17 },
      timings: { prompt_ms: 2000, predicted_ms: 500 },
      expected: { ...empty, prompt_tokens: 7, total_tokens: 17, prompt_time_ms: 2000,
        completion_time_ms: 500, prompt_tokens_per_second: 3.5 },
    },
    {
      name: "native rates win over derivation", usage: { prompt_tokens: 7, completion_tokens: 3, total_tokens: 10 },
      timings: { prompt_ms: 1000, predicted_ms: 500, prompt_per_second: 0, predicted_per_second: 9 },
      expected: { prompt_tokens: 7, completion_tokens: 3, total_tokens: 10, prompt_time_ms: 1000,
        completion_time_ms: 500, prompt_tokens_per_second: 0, completion_tokens_per_second: 9 },
    },
    {
      name: "positive sub-millisecond measurement remains usable", usage: { ...absentUsage, prompt_tokens: 2 },
      timings: { prompt_ms: 0.25 },
      expected: { ...empty, prompt_tokens: 2, prompt_time_ms: 0, prompt_tokens_per_second: 8000 },
    },
  ];
  for (const { name, usage, timings, expected } of cases) {
    assert.deepEqual(deriveTokenMetrics({ usage, timings }, 250), {
      ...expected, version: DETAILED_TOKEN_METRICS_VERSION, total_duration_ms: 250,
    }, name);
  }
});

test("invalid native counts fail at intake instead of becoming missing measurements", async () => {
  for (const measurements of [
    { usage: { prompt_tokens: -1 }, timings: { prompt_n: 8 } },
    { usage: { completion_tokens: 0.5 }, timings: { predicted_n: 4 } },
    { usage: { total_tokens: -1 } },
    { timings: { predicted_n: -1 } },
  ]) {
    await assert.rejects(() => queryLlamaServer(runtime, "system", "input", createRootContext(), undefined,
      async () => new Response(JSON.stringify({
        choices: [{ message: { content: JSON.stringify(analysis) } }], ...measurements,
      }), { headers: { "Content-Type": "application/json" } }),
      { max_native_request_bytes: 1048576, max_native_response_bytes: 1048576 }), error => {
      assert.ok(error instanceof Error);
      assert.match(error.message, /"path": \[\s+"(?:usage|timings)"/);
      return true;
    });
  }
});

test("current writers and readers reject invalid or unversioned nullable metrics without legacy fallback", () => {
  const metrics = deriveTokenMetrics({ usage: absentUsage, timings: {} }, 250);
  const current = { ...legacyResult, token_metrics: metrics };
  assert.deepEqual(readSummaryStructuredOutput(current), current);
  assert.throws(() => SummaryStructuredOutputSchema.parse(legacyResult));
  const { version, ...unversioned } = metrics;
  assert.equal(version, "2026-11-07");
  for (const invalid of [
    unversioned, { ...metrics, version: "2026-11-08" }, { ...metrics, version: null },
    { ...metrics, version: undefined }, { ...metrics, prompt_tokens: -1 },
    { ...legacyResult.token_metrics, version: "2026-11-08" },
    { ...legacyResult.token_metrics, version: null }, { ...legacyResult.token_metrics, version: undefined },
    { ...metrics, completion_tokens: 0.5 }, { ...metrics, total_duration_ms: null },
    { ...metrics, prompt_tokens_per_second: Infinity }, { ...metrics, unexpected: 1 },
    { version: DETAILED_TOKEN_METRICS_VERSION },
  ]) {
    assert.throws(() => DetailedTokenMetricsSchema.parse(invalid));
    assert.throws(() => readSummaryStructuredOutput({ ...current, token_metrics: invalid }));
    for (const type of ["INFERENCE_COMPLETED", "OUTPUT_STRUCTURED"] as const) {
      const data = type === "OUTPUT_STRUCTURED" ? { ...current, token_metrics: invalid } : {
        modelName: "recorded-analysis", sourceType: "INPUT_TEXT", tokenMetrics: invalid,
        swapMetrics: legacyResult.swap_metrics, rawOutput: legacyResult.raw_output,
      };
      const event = createCloudEvent({
        source: "/services/summarizer", type, context: createRootContext(), data: {}, parseData: value => value,
      });
      assert.throws(() => readPipelineEvent({ ...event, data }));
    }
  }
  assert.throws(() => readSummaryStructuredOutput({ ...current, unexpected: 1 }));
});

test("legacy numeric results and both event products retain original values and identities", () =>
  withConfig(root => {
    const legacy = {
      ...legacyResult, recorded_extension: "retained",
      source_audit: { ...legacyResult.source_audit, recorded_extension: "retained" },
      token_metrics: { ...legacyResult.token_metrics, recorded_extension: "retained" },
      swap_metrics: { ...legacyResult.swap_metrics, recorded_extension: "retained" },
    };
    assert.deepEqual(readSummaryStructuredOutput(legacy), legacy);
    const definitions: { type: PipelineEventType; data: unknown }[] = [
      { type: "OUTPUT_STRUCTURED", data: legacy },
      { type: "INFERENCE_COMPLETED", data: {
        modelName: "recorded-analysis", sourceType: "INPUT_TEXT", tokenMetrics: legacy.token_metrics,
        swapMetrics: legacy.swap_metrics, rawOutput: legacy.raw_output, recorded_extension: "retained",
      } },
    ];
    const events = definitions.map(({ type, data }) => {
      const event = createCloudEvent({
        source: "/services/summarizer", type, context: createRootContext({ traceState: "test=legacy" }),
        data, parseData: value => value,
      });
      const original = { ...event, time: "2026-11-03T00:00:00Z" };
      assert.throws(() => parsePipelineEventData(type, data));
      assert.deepEqual(readPipelineEvent(original), original);
      return readPipelineEvent(original);
    });
    const eventFile = path.join(root, "legacy-token-events.jsonl");
    const bytes = events.map(event => JSON.stringify(event)).join("\n") + "\n";
    writeFileSync(eventFile, bytes);
    assert.deepEqual(readPipelineEvents(eventFile), events);
    assert.equal(readFileSync(eventFile, "utf8"), bytes);
    const reportFile = path.join(root, "legacy-token-report.md");
    renderGithubStepSummary("recorded-analysis", readSummaryStructuredOutput(legacy), events, {
      summaryPath: reportFile, writeNotice: false,
    });
    const report = readFileSync(reportFile, "utf8");
    assert.match(report, /zeroes may mean unavailable data/);
    assert.match(report, /stage times may include whole-request timing/);
    assert.match(report, /\*\*0 tokens\*\* \| 0\.00s \| \*\*0 tokens\/sec\*\*/);
    const saved = report.match(/```json\n([\s\S]*?)\n```/);
    assert.ok(saved);
    assert.deepEqual(JSON.parse(saved[1]), events);
  }));

test("report and notice distinguish unknown measurements from independent totals, rates and real zeroes", () =>
  withConfig(root => {
    const result = {
      ...legacyResult,
      token_metrics: deriveTokenMetrics({
        usage: { prompt_tokens: null, completion_tokens: 0, total_tokens: 17 },
        timings: { prompt_ms: null, predicted_ms: 0, prompt_per_second: 12.5, predicted_per_second: 0 },
      }, 250),
    };
    const diagnostic = recordOutput(), reportFile = path.join(root, "current-token-report.md");
    renderGithubStepSummary("recorded-analysis", result, [], { summaryPath: reportFile, diagnostic: diagnostic.writer });
    const report = readFileSync(reportFile, "utf8");
    assert.match(report, /\*\*Not reported\*\* \| Not reported \| \*\*12\.5 tokens\/sec\*\*/);
    assert.match(report, /\*\*0 tokens\*\* \| 0\.00s \| \*\*0 tokens\/sec\*\*/);
    assert.match(report, /\*\*17 tokens\*\* \| \*\*0\.25s\*\*/);
    assert.match(diagnostic.read(), /Input: 12\.5 tokens\/sec \(Not reported\)/);
    assert.match(diagnostic.read(), /Output: 0 tokens\/sec \(0 tokens\)/);
    for (const invalid of ["null tokens", "Batched", "Historical measurements"]) {
      assert.equal(report.includes(invalid), false);
    }
    const missing = recordOutput();
    renderGithubStepSummary("recorded-analysis", {
      ...result, token_metrics: deriveTokenMetrics({ usage: absentUsage, timings: {} }, 250),
    }, [], { summaryPath: "", diagnostic: missing.writer });
    assert.match(missing.read(), /Input: Not reported \(Not reported\) \| Output: Not reported \(Not reported\)/);
  }));
