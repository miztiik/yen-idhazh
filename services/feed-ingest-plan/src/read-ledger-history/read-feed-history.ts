/** Read only the current planner family's named represented days and request-report days. */
import { z } from "zod";
import { FeedHealthStateRowContract } from "@idhazh/common-contracts";
import type { FeedHealthStateRow, SourceSnapshot } from "@idhazh/common-contracts";
import type { LedgerRegistration } from "@idhazh/ledger-file-writer";
import type { SeenDayInput } from "../config/service-settings";
import { defaultDayInput } from "./named-days";
import { mapPool } from "../harvest-feeds/harvest-pool";
import { readPlannerDay } from "./read-planner-history";
import { closedRequestDays, inputEndpointKey, summarizeHealth, settleHealthRows } from "./health-summary";

export const FeedHistoryPolicySchema = z.object({
  availability_strikes_before_rest: z.int().positive(),
  reliability_window_days: z.int().positive(), reliability_floor: z.number().finite().min(0).max(1),
});
export type FeedHistoryPolicy = z.infer<typeof FeedHistoryPolicySchema>;
export type SourceHistoryEvidence = Readonly<{
  lifecycle: "eligible" | "resting" | "retired" | "unknown"; endpoint_key: string;
  strikes: number | null; rested_runs: number | null;
  reliability: FeedHealthStateRow["reliability"];
}>;
export const endpointKey = inputEndpointKey;
export async function readFeedHistory(input: {
  root: string; now: string; sources: readonly SourceSnapshot[]; policy: FeedHistoryPolicy;
  lifecycle_window_days: number; request_report_closed_days: number; concurrency: number;
  health: LedgerRegistration; health_days: readonly SeenDayInput[];
  own_days?: readonly SeenDayInput[];
}) {
  const limit = Math.max(input.lifecycle_window_days, input.policy.reliability_window_days);
  if (input.health_days.length > limit + input.request_report_closed_days) {
    throw new Error("Planner health inventory exceeds its configured represented-day and closed-day bounds");
  }
  const named = new Map<string, SeenDayInput>();
  for (const day of input.health_days) {
    if (named.has(day.day) || day.day > input.now.slice(0, 10)) throw new Error("Planner health inventory must name distinct past UTC days");
    named.set(day.day, day);
  }
  for (const day of closedRequestDays(input.now, input.request_report_closed_days)) {
    if (!named.has(day)) named.set(day, defaultDayInput(input.health.prefix, day));
  }
  const loaded = await mapPool([...named.values()].sort((a, b) => a.day.localeCompare(b.day)), input.concurrency,
    day => readPlannerDay(input.root, input.health, day, FeedHealthStateRowContract));
  const own = await mapPool(input.own_days ?? [], input.concurrency,
    day => readPlannerDay(input.root, input.health, day, FeedHealthStateRowContract));
  const rows = settleHealthRows([...loaded, ...own].flatMap(day => day.rows));
  const represented = new Set([...input.health_days, ...input.own_days ?? []].map(day => day.day));
  const days = [...new Map([...loaded, ...own].filter(day => represented.has(day.day) || day.complete || day.rows.length > 0)
    .map(day => [day.day, { day: day.day, complete: day.complete }])).values()]
    .sort((a, b) => a.day.localeCompare(b.day));
  return { rows, days, ...summarizeHealth({ ...input, rows, days }) };
}
export type FeedHistory = Awaited<ReturnType<typeof readFeedHistory>>;
