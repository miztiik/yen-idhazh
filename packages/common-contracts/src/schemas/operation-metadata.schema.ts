/** Which identifiers and relationships describe one operation without recording a trace? */
import { createTraceState } from "@opentelemetry/api";
import { z } from "zod";

export const OPERATION_METADATA_VERSION = "2026-11-03" as const;

export const TraceIdSchema = z.string().regex(/^[0-9a-f]{32}$/)
  .refine(value => value !== "0".repeat(32), "traceId must be nonzero");
export const SpanIdSchema = z.string().regex(/^[0-9a-f]{16}$/)
  .refine(value => value !== "0".repeat(16), "spanId must be nonzero");
export const TraceStateSchema = z.string().min(1)
  .refine(value => createTraceState(value).serialize() === value, "must be valid serialized W3C tracestate");

export const OperationLinkSchema = z.strictObject({
  traceId: TraceIdSchema,
  spanId: SpanIdSchema,
});
export type OperationLink = z.infer<typeof OperationLinkSchema>;

export const OperationMetadataSchema = z.strictObject({
  traceId: TraceIdSchema,
  spanId: SpanIdSchema,
  parentSpanId: SpanIdSchema.optional(),
  links: z.array(OperationLinkSchema),
  traceState: TraceStateSchema.optional(),
}).refine(value => value.parentSpanId !== value.spanId, {
  message: "an operation cannot be its own parent",
  path: ["parentSpanId"],
}).meta({
  version: OPERATION_METADATA_VERSION,
  changelog: [
    { version: OPERATION_METADATA_VERSION, change: "Declare native execution, operation, parent and input-link metadata." },
  ],
});
export type OperationMetadata = z.infer<typeof OperationMetadataSchema>;
