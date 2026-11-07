/** Which reported stage measurements justify the full-analysis token rates? */
import {
  DETAILED_TOKEN_METRICS_VERSION, type DetailedTokenMetrics,
} from "./contracts/system-telemetry.schema.js";
import type { LlamaInferenceResponse } from "./query-analysis.js";

function deriveTokenRate(
  reported: number | null | undefined,
  tokens: number | null,
  milliseconds: number | null | undefined,
): number | null {
  if (reported != null) return Number(reported.toFixed(2));
  if (tokens === null || milliseconds == null || milliseconds <= 0) return null;
  return Number((tokens / (milliseconds / 1000)).toFixed(2));
}

export function deriveTokenMetrics(
  inference: Pick<LlamaInferenceResponse, "usage" | "timings">,
  totalDurationMs: number,
): DetailedTokenMetrics {
  const { usage, timings } = inference;
  return {
    version: DETAILED_TOKEN_METRICS_VERSION,
    ...usage,
    prompt_time_ms: timings.prompt_ms == null ? null : Math.round(timings.prompt_ms),
    completion_time_ms: timings.predicted_ms == null ? null : Math.round(timings.predicted_ms),
    total_duration_ms: totalDurationMs,
    prompt_tokens_per_second: deriveTokenRate(
      timings.prompt_per_second, usage.prompt_tokens, timings.prompt_ms,
    ),
    completion_tokens_per_second: deriveTokenRate(
      timings.predicted_per_second, usage.completion_tokens, timings.predicted_ms,
    ),
  };
}
