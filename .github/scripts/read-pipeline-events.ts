/** How does a named current-format event file supply saved inference results? */
import { readFileSync } from "node:fs";
import {
  CloudEventSchema,
  readCloudEvent,
  type CloudEvent,
} from "../../packages/common-contracts/src/index.ts";
import type { SummaryStructuredOutput } from "./ai-pipeline.ts";

export type PipelineEventData<T = unknown> = {
  result: T;
  durationMs: number;
  cumulativeMs: number;
};
export type PipelineEvent<T = unknown> = CloudEvent<PipelineEventData<T>>;

export class PipelineInputError extends Error {
  constructor(public readonly code: string, public readonly line?: number) {
    super(line === undefined ? code : `${code} at line ${line}`);
    this.name = "PipelineInputError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function hasStrings(value: unknown, fields: readonly string[]): boolean {
  return isRecord(value) && fields.every(field => typeof value[field] === "string");
}

function hasNumbers(value: unknown, fields: readonly string[]): boolean {
  return isRecord(value) && fields.every(field => typeof value[field] === "number" && Number.isFinite(value[field]));
}

function isFeedArticle(value: unknown): boolean {
  if (!isRecord(value) || !hasStrings(value, ["title", "url", "sourceFeed"])) return false;
  if (!["cleanedUrl", "publishedDate", "extractedMarkdown"].every(field =>
    value[field] === undefined || typeof value[field] === "string")) return false;
  if (value.ageHours !== undefined && (typeof value.ageHours !== "number" || !Number.isFinite(value.ageHours))) return false;
  const shallow = value.shallowResult;
  if (shallow !== undefined && (!isRecord(shallow)
    || !hasStrings(shallow, ["classification", "reason"]) || typeof shallow.passed !== "boolean")) return false;
  const deep = value.deepResult;
  return deep === undefined || (isRecord(deep) && hasStrings(deep, ["classification", "reason"])
    && hasNumbers(deep, ["wordCount", "linkDensity", "listCount"]) && typeof deep.passed === "boolean");
}

function isFeedAudit(value: unknown): boolean {
  return isRecord(value) && Array.isArray(value.configuredFeeds)
    && value.configuredFeeds.every(feed => typeof feed === "string")
    && hasNumbers(value, ["maxAgeHours", "goalCount"]) && typeof value.usedFallback === "boolean"
    && Array.isArray(value.evaluatedArticles) && value.evaluatedArticles.every(isFeedArticle)
    && Array.isArray(value.acceptedArticles) && value.acceptedArticles.every(isFeedArticle);
}

function isSummaryResult(value: unknown): value is SummaryStructuredOutput {
  if (!isRecord(value) || !hasStrings(value, [
    "headline", "analytic_synthesis", "raw_output", "input_text", "system_prompt", "user_prompt",
  ])) return false;
  const choices: Record<string, readonly string[]> = {
    sentiment: ["positive", "neutral", "negative", "mixed"],
    stance_on_change: ["conservatism", "progressivism", "not_applicable"],
    stance_on_economic_power: ["socialism", "libertarianism", "not_applicable"],
    stance_on_state_power: ["statism", "constitutionalism", "not_applicable"],
    stance_on_borders: ["nationalism", "internationalism", "not_applicable"],
    stance_on_personal_sphere: ["civil_libertarianism", "communitarianism", "not_applicable"],
  };
  if (!Object.entries(choices).every(([field, allowed]) =>
    typeof value[field] === "string" && allowed.includes(value[field]))) return false;
  if (!hasNumbers(value.compression, ["inputChars", "outputChars"])
    || !hasStrings(value.compression, ["retentionRatioPercent", "reductionRatioPercent", "explanation"])) return false;
  const audit = value.source_audit;
  if (!isRecord(audit) || !hasStrings(audit, ["sourceIdentifier", "sourceTitle", "extractedText"])
    || !hasNumbers(audit, ["extractedWordCount", "extractedCharCount"])
    || typeof audit.sourceType !== "string"
    || !["FEED", "FEED_DEFAULT_FALLBACK", "URL", "INPUT_TEXT", "FALLBACK_INPUT_TEXT"].includes(audit.sourceType)
    || (audit.scrapeError !== undefined && typeof audit.scrapeError !== "string")
    || (audit.feedAudit !== undefined && !isFeedAudit(audit.feedAudit))) return false;
  if (!hasNumbers(value.token_metrics, [
    "prompt_tokens", "completion_tokens", "total_tokens", "prompt_time_ms",
    "completion_time_ms", "total_duration_ms", "prompt_tokens_per_second", "completion_tokens_per_second",
  ]) || !hasNumbers(value.cpu_metrics, ["maxCpuPercent", "avgCpuPercent", "samplesTaken"])) return false;
  const swap = value.swap_metrics;
  if (!isRecord(swap) || !hasNumbers(swap, [
    "swappiness", "server_vm_rss_mb", "peak_server_swap_mb", "final_server_swap_mb",
    "system_swap_used_mb", "system_swap_total_mb", "swap_bytes_written_mb",
    "swap_bytes_read_mb", "page_size_bytes",
  ]) || !(swap.server_pid === null || (typeof swap.server_pid === "number" && Number.isFinite(swap.server_pid)))
    || typeof swap.is_cgroup_constrained !== "boolean"
    || (swap.diagnostics_error !== undefined && typeof swap.diagnostics_error !== "string")) return false;
  const host = value.host_fingerprint;
  if (!isRecord(host) || !hasStrings(host, ["cpuModel", "l3Cache", "totalRamGb", "rawFingerprint"])
    || !hasNumbers(host, ["coreCount"]) || !Array.isArray(host.avxFlags)
    || !host.avxFlags.every(flag => typeof flag === "string")) return false;
  if (!hasStrings(value.runner_metadata, [
    "runnerName", "runId", "runNumber", "workflow", "osArch", "shardId", "modelFamily", "requestedModelId",
  ]) || !isRecord(value.inference_params)
    || (value.error_flag !== undefined && typeof value.error_flag !== "boolean")) return false;
  return true;
}

function readEventData(value: unknown): PipelineEventData {
  if (!isRecord(value) || !Object.hasOwn(value, "result")
    || Object.keys(value).length !== 3
    || typeof value.durationMs !== "number" || !Number.isInteger(value.durationMs) || value.durationMs < 0
    || typeof value.cumulativeMs !== "number" || !Number.isInteger(value.cumulativeMs) || value.cumulativeMs < 0) {
    throw new Error("INVALID_PIPELINE_EVENT_DATA");
  }
  if (value.cumulativeMs < value.durationMs) throw new Error("INVALID_PIPELINE_EVENT_TIMING");
  if (value.result === undefined) throw new Error("MISSING_PIPELINE_EVENT_RESULT");
  return { result: value.result, durationMs: value.durationMs, cumulativeMs: value.cumulativeMs };
}

export const PipelineEventDataSchema = CloudEventSchema.shape.data.transform(readEventData).meta({
  version: "2026-11-03",
  changelog: [
    { version: "2026-11-03", change: "Keep workflow results and existing log-gap measurements in structured event data." },
  ],
});

export function selectStructuredOutputs(events: readonly PipelineEvent[]): PipelineEvent<SummaryStructuredOutput>[] {
  return events.filter(event => event.type === "OUTPUT_STRUCTURED").map(event => {
    const result = event.data.result;
    if (!isSummaryResult(result)) throw new PipelineInputError("INVALID_SAVED_INFERENCE_RESULT");
    return { ...event, data: { ...event.data, result } };
  });
}

export function readPipelineEvents(path: string): PipelineEvent[] {
  let content: string;
  try {
    content = readFileSync(path, "utf8");
  } catch {
    throw new PipelineInputError("PIPELINE_EVENTS_READ_FAILED");
  }
  if (content === "") return [];
  const lines = content.split("\n");
  if (lines.at(-1) === "") lines.pop();
  return lines.map((line, index) => {
    try {
      const event = readCloudEvent(JSON.parse(line), value => PipelineEventDataSchema.parse(value));
      if (event.type === "OUTPUT_STRUCTURED" && !isSummaryResult(event.data.result)) {
        throw new Error("INVALID_SAVED_INFERENCE_RESULT");
      }
      return event;
    } catch {
      throw new PipelineInputError("INVALID_PIPELINE_EVENT", index + 1);
    }
  });
}
