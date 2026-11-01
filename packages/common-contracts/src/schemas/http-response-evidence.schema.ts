/** Which safe response facts can a failed source request retain? */
import { z } from "zod";
import { CountSchema, PositiveCountSchema, reject } from "./primitives";

export const RequestProfileSchema = z.enum(["firefox", "chrome"]);
export const DiagnosticHeaderNameSchema = z.string().max(128).regex(/^[a-z0-9-]+$/).refine(
  name => !/authorization|cookie|credential|token|secret|api-key|authenticate|location|refresh/.test(name),
  "response_diagnostics.header_names must not include credentials or redirect addresses",
);
export const ResponseDiagnosticsConfigSchema = z.strictObject({
  header_names: z.array(DiagnosticHeaderNameSchema).max(32),
  max_header_value_chars: PositiveCountSchema.max(512),
}).superRefine((value, ctx) => {
  if (new Set(value.header_names).size !== value.header_names.length) {
    reject(ctx, "response_diagnostics.header_names must not repeat a header", ["header_names"]);
  }
});
export const HttpResponseEvidenceSchema = z.strictObject({
  content_type: z.string().max(512).regex(/^[\x20-\x7e]*$/).nullable(),
  decoded_bytes: CountSchema.nullable(),
  declared_content_length: CountSchema.nullable(),
  selected_headers: z.record(DiagnosticHeaderNameSchema, z.string().max(512).regex(/^[\x20-\x7e]*$/))
    .refine(value => Object.keys(value).length <= 32, "response evidence admits at most 32 selected headers"),
  headers_truncated: z.array(DiagnosticHeaderNameSchema).max(32),
  request_profile: RequestProfileSchema,
}).superRefine((value, ctx) => {
  if (new Set(value.headers_truncated).size !== value.headers_truncated.length
    || value.headers_truncated.some(name => !Object.hasOwn(value.selected_headers, name))) {
    reject(ctx, "headers_truncated must name distinct retained headers", ["headers_truncated"]);
  }
}).meta({
  version: "2026-11-01",
  changelog: [{ version: "2026-11-01", change: "Declare bounded body-free native response evidence." }],
});
export type HttpResponseEvidence = z.infer<typeof HttpResponseEvidenceSchema>;
