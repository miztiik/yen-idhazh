/** Which application data does each summarizer event carry? */
import { z } from "zod";
import { readCloudEvent } from "@idhazh/common-contracts/read-cloud-event";
import type { CloudEvent } from "@idhazh/common-contracts/schemas/cloud-event";
import {
  SummaryStructuredOutputSchema, readSummaryStructuredOutput,
  type LegacySummaryStructuredOutput,
} from "./analysis-result.schema.js";
import {
  DETAILED_TOKEN_METRICS_VERSION,
  DetailedTokenMetricsSchema,
  LegacyDetailedTokenMetricsSchema,
  SourceTypeEnum,
  SwapActivityMetricsSchema,
} from "./system-telemetry.schema.js";

export const PIPELINE_EVENT_VERSION = DETAILED_TOKEN_METRICS_VERSION;
export const PIPELINE_EVENT_CHANGELOG = [
  { version: PIPELINE_EVENT_VERSION, change: "Save dated nullable token metrics and read unversioned numeric events unchanged." },
  { version: "2026-11-03", change: "Use shared CloudEvents with validated summarizer data and explicit operation context." },
] as const;

export const PipelineEventDataSchemas = {
  URL_HTTP_FETCH_STARTED: z.object({ url: z.string() }),
  URL_HTTP_FETCH_COMPLETED: z.object({ url: z.string(), bytes: z.number().int().nonnegative() }),
  URL_DEFUDDLE_EXTRACTED: z.object({
    url: z.string(), title: z.string(), wordCount: z.number().int().nonnegative(),
  }),
  URL_EXTRACTION_FAILED: z.object({
    url: z.string(), error: z.string(), resolution: z.string(),
  }),
  INPUT_RESOLVED: z.object({
    modelName: z.string(),
    sourceType: SourceTypeEnum,
    sourceIdentifier: z.string(),
    sourceTitle: z.string(),
    wordCount: z.number().int().nonnegative(),
    charCount: z.number().int().nonnegative(),
    inputText: z.string(),
    systemPrompt: z.string(),
    userPrompt: z.string(),
  }),
  INFERENCE_DISPATCHED: z.object({
    serverUrl: z.string().url(),
    targetModel: z.string(),
    sourceType: SourceTypeEnum,
    wordCount: z.number().int().nonnegative(),
    charCount: z.number().int().nonnegative(),
  }),
  INFERENCE_COMPLETED: z.object({
    modelName: z.string(),
    sourceType: SourceTypeEnum,
    tokenMetrics: DetailedTokenMetricsSchema,
    swapMetrics: SwapActivityMetricsSchema,
    rawOutput: z.string(),
  }).strict(),
  OUTPUT_STRUCTURED: SummaryStructuredOutputSchema,
};

const LegacyInferenceCompletedSchema = PipelineEventDataSchemas.INFERENCE_COMPLETED.extend({
  tokenMetrics: LegacyDetailedTokenMetricsSchema,
  swapMetrics: SwapActivityMetricsSchema.passthrough(),
}).passthrough();

export const PipelineEventTypeEnum = z.enum([
  "URL_HTTP_FETCH_STARTED",
  "URL_HTTP_FETCH_COMPLETED",
  "URL_DEFUDDLE_EXTRACTED",
  "URL_EXTRACTION_FAILED",
  "INPUT_RESOLVED",
  "INFERENCE_DISPATCHED",
  "INFERENCE_COMPLETED",
  "OUTPUT_STRUCTURED",
]);
export type PipelineEventType = z.infer<typeof PipelineEventTypeEnum>;
export type PipelineEventData<T extends PipelineEventType> =
  z.infer<(typeof PipelineEventDataSchemas)[T]>;
export type PipelineEvent<T extends PipelineEventType = PipelineEventType> =
  Omit<CloudEvent<PipelineEventData<T>>, "type"> & { type: T };
export type RecordedPipelineEventData = PipelineEventData<PipelineEventType>
  | LegacySummaryStructuredOutput | z.infer<typeof LegacyInferenceCompletedSchema>;
export type RecordedPipelineEvent = Omit<CloudEvent<RecordedPipelineEventData>, "type">
  & { type: PipelineEventType };

export function parsePipelineEventData<T extends PipelineEventType>(
  type: T,
  value: unknown,
): PipelineEventData<T> {
  return PipelineEventDataSchemas[type].parse(value);
}

export function readPipelineEventData(
  type: PipelineEventType,
  value: unknown,
): RecordedPipelineEventData {
  if (type === "OUTPUT_STRUCTURED") return readSummaryStructuredOutput(value);
  if (type === "INFERENCE_COMPLETED") {
    const { tokenMetrics } = z.object({ tokenMetrics: z.record(z.unknown()) }).parse(value);
    return Object.hasOwn(tokenMetrics, "version")
      ? parsePipelineEventData(type, value)
      : LegacyInferenceCompletedSchema.parse(value);
  }
  return parsePipelineEventData(type, value);
}

export function readPipelineEvent(value: unknown): RecordedPipelineEvent {
  const { type } = z.object({ type: PipelineEventTypeEnum }).parse(value);
  return { ...readCloudEvent(value, data => readPipelineEventData(type, data)), type };
}
