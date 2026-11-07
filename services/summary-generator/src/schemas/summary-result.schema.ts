/** Which fields belong to a summary and its native generation metadata? */
import { z } from "zod";

// Payload metadata is independent of the dated HTTP family.
export const SUMMARY_API_VERSION = "2026-11-07";
export const SUMMARY_API_CHANGELOG = [
  { version: SUMMARY_API_VERSION, change: "Report the native server's model name without enforcing model selection." },
  { version: "2026-11-06", change: "Separate summary generation from full analysis." },
] as const;
const nonempty = z.string().min(1);

export const SummaryReportedModelSchema = z.string()
  .refine(value => value.trim().length > 0, "The server-reported model name must not be blank.")
  .nullable();
export const SummaryFieldsSchema = z.object({
  headline: nonempty,
  executive_summary: nonempty,
  key_points: z.array(nonempty),
});
export const SummaryUsageSchema = z.object({
  prompt_tokens: z.number().int().nonnegative().nullable(),
  completion_tokens: z.number().int().nonnegative().nullable(),
}).strict();
export const SummaryResultSchema = z.object({
  success: z.literal(true),
  data: SummaryFieldsSchema.strict(),
  model: SummaryReportedModelSchema.optional()
    .describe("Server-reported model name, not verified weights; omitted only in older saved results."),
  prompt_sha256: z.string().regex(/^[a-f0-9]{64}$/),
  prompt_source: z.enum(["default", "override"]),
  usage: SummaryUsageSchema,
}).strict();
export type SummaryFields = z.infer<typeof SummaryFieldsSchema>;
export type SummaryResult = z.infer<typeof SummaryResultSchema>;

export const SummaryErrorCodeSchema = z.enum([
  "INVALID_REQUEST", "REQUEST_TOO_LARGE", "REQUEST_BODY_TIMEOUT", "GENERATE_SUMMARY_FAILED",
  "NOT_FOUND", "METHOD_NOT_ALLOWED",
]);
export const SummaryErrorSchema = z.object({
  error: nonempty,
  code: SummaryErrorCodeSchema,
}).strict();
export const SummaryHealthSchema = z.object({
  status: z.literal("ok"),
  version: z.literal(SUMMARY_API_VERSION),
}).strict();
