/** Which structured JSON event envelope keeps occurrence identity separate from operation context? */
import { z } from "zod";
import { readTraceContext } from "../propagate-trace-context";
import { TraceStateSchema } from "./operation-metadata.schema";
import { RecordedInstantSchema } from "./recorded-instant.schema";

export const CLOUD_EVENT_VERSION = "2026-11-03" as const;

// This reserved base validates URI references; it is never a fetch destination.
const URI_REFERENCE_BASE = "https://event-source.invalid/";
const URI_REFERENCE_PATTERN = /^(?:[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=-]|%[0-9A-Fa-f]{2})+$/;

export const EventSourceSchema = z.string().min(1).refine(
  value => URI_REFERENCE_PATTERN.test(value) && URL.canParse(value, URI_REFERENCE_BASE),
  "source must be a URI reference",
);

export const CloudEventSchema = z.strictObject({
  specversion: z.literal("1.0"),
  id: z.uuid({ version: "v4" }).regex(/^[0-9a-f-]+$/),
  source: EventSourceSchema,
  type: z.string().min(1),
  time: RecordedInstantSchema.describe("Actual event occurrence instant in UTC."),
  datacontenttype: z.literal("application/json"),
  traceparent: z.string(),
  tracestate: TraceStateSchema.optional(),
  data: z.json(),
}).refine(value => readTraceContext({ traceparent: value.traceparent }) !== undefined, {
  message: "traceparent must contain valid W3C operation context",
  path: ["traceparent"],
}).meta({
  version: CLOUD_EVENT_VERSION,
  changelog: [
    { version: CLOUD_EVENT_VERSION, change: "Declare structured JSON events with native occurrence and W3C context." },
  ],
});

export type CloudEvent<T> = Omit<z.infer<typeof CloudEventSchema>, "data"> & { data: T };
