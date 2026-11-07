/** Which fields belong to a summary, its effective prompt and actual native token counts? */
import { z } from "zod";

// Payload metadata is independent of the dated HTTP family.
export const SUMMARY_API_VERSION = "2026-11-06";
export const SUMMARY_API_CHANGELOG = [
  { version: SUMMARY_API_VERSION, change: "Separate summary generation from full analysis." },
] as const;
const nonempty = z.string().min(1);

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
