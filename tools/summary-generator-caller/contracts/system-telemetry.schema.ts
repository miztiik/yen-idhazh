/** Which source and native-cost readings does a complete analysis retain? */
import { z } from "zod";

export const SourceTypeEnum = z.enum(["URL", "INPUT_TEXT", "FALLBACK_INPUT_TEXT"]);
export type SourceType = z.infer<typeof SourceTypeEnum>;

export const SourceAuditSchema = z.object({
  sourceType: SourceTypeEnum,
  sourceIdentifier: z.string(),
  sourceTitle: z.string(),
  extractedWordCount: z.number().int().nonnegative(),
  extractedCharCount: z.number().int().nonnegative(),
  extractedText: z.string(),
  scrapeError: z.string().optional(),
});

export type SourceAudit = z.infer<typeof SourceAuditSchema>;

export const DETAILED_TOKEN_METRICS_VERSION = "2026-11-07" as const;
export const DETAILED_TOKEN_METRICS_CHANGELOG = [
  { version: DETAILED_TOKEN_METRICS_VERSION, change: "Distinguish unavailable native measurements from reported zeroes." },
] as const;

export const LegacyDetailedTokenMetricsSchema = z.object({
  prompt_tokens: z.number().int().nonnegative(),
  completion_tokens: z.number().int().nonnegative(),
  total_tokens: z.number().int().nonnegative(),
  prompt_time_ms: z.number().nonnegative(),
  completion_time_ms: z.number().nonnegative(),
  total_duration_ms: z.number().nonnegative(),
  prompt_tokens_per_second: z.number().nonnegative(),
  completion_tokens_per_second: z.number().nonnegative(),
}).passthrough();

export const DetailedTokenMetricsSchema = LegacyDetailedTokenMetricsSchema.extend({
  version: z.literal(DETAILED_TOKEN_METRICS_VERSION),
  prompt_tokens: LegacyDetailedTokenMetricsSchema.shape.prompt_tokens.nullable(),
  completion_tokens: LegacyDetailedTokenMetricsSchema.shape.completion_tokens.nullable(),
  total_tokens: LegacyDetailedTokenMetricsSchema.shape.total_tokens.nullable(),
  prompt_time_ms: LegacyDetailedTokenMetricsSchema.shape.prompt_time_ms.finite().nullable(),
  completion_time_ms: LegacyDetailedTokenMetricsSchema.shape.completion_time_ms.finite().nullable(),
  total_duration_ms: LegacyDetailedTokenMetricsSchema.shape.total_duration_ms.finite(),
  prompt_tokens_per_second: LegacyDetailedTokenMetricsSchema.shape.prompt_tokens_per_second.finite().nullable(),
  completion_tokens_per_second: LegacyDetailedTokenMetricsSchema.shape.completion_tokens_per_second.finite().nullable(),
}).strict();

export type DetailedTokenMetrics = z.infer<typeof DetailedTokenMetricsSchema>;

export const SwapActivityMetricsSchema = z.object({
  swappiness: z.number(),
  server_pid: z.number().nullable(),
  server_vm_rss_mb: z.number().nonnegative(),
  peak_server_swap_mb: z.number().nonnegative(),
  final_server_swap_mb: z.number().nonnegative(),
  system_swap_used_mb: z.number().nonnegative(),
  system_swap_total_mb: z.number().nonnegative(),
  swap_bytes_written_mb: z.number().nonnegative(),
  swap_bytes_read_mb: z.number().nonnegative(),
});

export type SwapActivityMetrics = z.infer<typeof SwapActivityMetricsSchema>;