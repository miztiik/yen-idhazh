/** Which application data does each summarizer event carry? */
import { z } from "zod";
import { readCloudEvent } from "@idhazh/common-contracts/read-cloud-event";
import type { CloudEvent } from "@idhazh/common-contracts/schemas/cloud-event";
import { SummaryStructuredOutputSchema } from "./analysis-result.schema.js";
import {
  DetailedTokenMetricsSchema,
  SourceTypeEnum,
  SwapActivityMetricsSchema,
} from "./system-telemetry.schema.js";

export const PIPELINE_EVENT_VERSION = "2026-11-03" as const;
export const PIPELINE_EVENT_CHANGELOG = [
  { version: PIPELINE_EVENT_VERSION, change: "Use shared CloudEvents with validated summarizer data and explicit operation context." },
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
  }),
  OUTPUT_STRUCTURED: SummaryStructuredOutputSchema,
};

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

export function parsePipelineEventData<T extends PipelineEventType>(
  type: T,
  value: unknown,
): PipelineEventData<T> {
  return PipelineEventDataSchemas[type].parse(value);
}

export function readPipelineEvent(value: unknown): PipelineEvent {
  const { type } = z.object({ type: PipelineEventTypeEnum }).parse(value);
  return { ...readCloudEvent(value, data => parsePipelineEventData(type, data)), type };
}
