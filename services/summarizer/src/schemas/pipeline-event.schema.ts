import { z } from "zod";

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

export const PipelineEventSchema = z.object({
  eventId: z.string().regex(/^evt-[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i),
  eventType: PipelineEventTypeEnum,
  timestamp: z.string().datetime(),
  correlationId: z.string(),
  payload: z.unknown(),
});

export type PipelineEvent<T = unknown> = Omit<z.infer<typeof PipelineEventSchema>, "payload"> & {
  payload: T;
};