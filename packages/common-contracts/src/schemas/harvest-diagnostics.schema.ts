/** Which bounded fetch and extraction evidence survives every planner boundary? */
import { z } from "zod";
import { CountSchema } from "./primitives";

export const FetchFailureSchema = z.enum([
  "http", "timeout", "unsafe-target", "dns", "network", "robots-denied",
  "robots-unknown", "body-too-large", "redirect-loop",
]);
export const ExtractionFailureSchema = z.enum([
  "missing-document-root", "dom-depth-exceeded", "empty-content", "missing-title",
]);
export const HarvestDiagnosticsSchema = z.strictObject({
  http_status: z.int().min(100).max(599).nullable().default(null),
  robots: z.enum(["allowed", "denied", "unknown"]).nullable().default(null),
  fetch_failure: FetchFailureSchema.nullable().default(null),
  robots_failure: FetchFailureSchema.nullable().default(null),
  robots_http_status: z.int().min(100).max(599).nullable().default(null),
  error_code: z.string().max(64).regex(/^[A-Z][A-Z0-9_]*$/).nullable().default(null),
  extraction_failure: ExtractionFailureSchema.nullable().default(null),
  failure_code: z.enum([
    "robots_denied", "robots_unreachable", "blocked_address", "http_client_error",
    "http_rate_limited", "http_server_error", "network_error", "no_text", "no_title", "unknown",
  ]).nullable().default(null),
  stopped_stage: z.enum(["fetch", "extract", "parse"]).nullable().default(null),
  detail: z.enum([
    ...FetchFailureSchema.options, ...ExtractionFailureSchema.options, "malformed-feed", "empty-feed",
  ]).nullable().default(null),
  fetch_ms: CountSchema.nullable().default(null),
  extract_ms: CountSchema.nullable().default(null),
  warnings: z.array(z.literal("malformed-json-ld")).max(1).default([]),
});
export type HarvestDiagnostics = z.infer<typeof HarvestDiagnosticsSchema>;
export type FetchFailure = z.infer<typeof FetchFailureSchema>;
export type ExtractionFailure = z.infer<typeof ExtractionFailureSchema>;
