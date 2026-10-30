/** Read the named represented days needed for feed reliability and article admission. */
import { z } from "zod";
import type { FeedHealthStateRow, SourceSnapshot } from "@idhazh/common-contracts";
import { inputEndpointKey, summarizePlanningHealth } from "./health-summary";
import { readHealthCapture } from "./read-health-capture";
import type { HealthCaptureCache, HealthCaptureInput } from "./read-health-capture";

export const FeedHistoryPolicySchema = z.object({
  reliability_window_days: z.int().positive(), reliability_floor: z.number().finite().min(0).max(1),
});
export type FeedHistoryPolicy = z.infer<typeof FeedHistoryPolicySchema>;
export type SourceHistoryEvidence = Readonly<{
  lifecycle: "eligible" | "resting" | "retired" | "unknown"; endpoint_key: string;
  strikes: number | null; rested_runs: number | null;
  reliability: FeedHealthStateRow["reliability"];
  article_pass_rate?: number | null;
}>;
export const endpointKey = inputEndpointKey;
export type FeedHistoryInput = HealthCaptureInput & {
  sources: readonly SourceSnapshot[]; policy: FeedHistoryPolicy;
  lifecycle_window_days: number; request_report_closed_days: number; concurrency: number;
};
export async function readFeedHistory(input: FeedHistoryInput, cache?: HealthCaptureCache) {
  const limit = Math.max(input.lifecycle_window_days, input.policy.reliability_window_days);
  if (input.health_days.length > limit + input.request_report_closed_days) {
    throw new Error("Planner health inventory exceeds its configured represented-day and closed-day bounds");
  }
  const named = new Set<string>();
  for (const day of input.health_days) {
    if (named.has(day.day) || day.day > input.now.slice(0, 10)) throw new Error("Planner health inventory must name distinct past UTC days");
    named.add(day.day);
  }
  const capture = await readHealthCapture(input, input.health_days, cache);
  return { ...capture, ...summarizePlanningHealth({ ...input, ...capture }) };
}
export type FeedHistory = Awaited<ReturnType<typeof readFeedHistory>>;
