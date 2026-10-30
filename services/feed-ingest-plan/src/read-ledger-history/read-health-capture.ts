/** Capture named health days once, excluding this execution before projecting its required fields. */
import type { FeedHealthStateRow } from "@idhazh/common-contracts";
import type { LedgerRegistration } from "@idhazh/ledger-file-writer";
import type { LedgerDayInput } from "../config/service-settings";
import { mapPool } from "../harvest-feeds/harvest-pool";
import { projectFeedHealthFields, readFeedHealthFieldsDay } from "./read-feed-health-fields";
import { createPlannerHistoryCache } from "./read-planner-history";
import type { PlannerHistoryCache } from "./read-planner-history";

export type HealthCaptureInput = {
  root: string; now: string; concurrency: number;
  health: LedgerRegistration; health_days: readonly LedgerDayInput[];
  own_days?: readonly LedgerDayInput[];
  own_rows?: readonly FeedHealthStateRow[];
  current_rows?: readonly FeedHealthStateRow[];
  exclude_execution?: { run_id: string; attempt: number };
};
export type HealthCaptureCache = PlannerHistoryCache<Record<string, unknown>>;
export async function readHealthCapture(
  input: HealthCaptureInput, named: readonly LedgerDayInput[],
  cache: HealthCaptureCache = createPlannerHistoryCache(),
) {
  const loaded = await mapPool([...named, ...input.own_days ?? []], input.concurrency,
    day => readFeedHealthFieldsDay(input.root, input.health, day, cache, input.exclude_execution));
  const inventory = new Set([...input.health_days, ...input.own_days ?? []].map(day => day.day));
  const days = [...new Map(loaded.filter(day => day.represented === true
    || (day.represented === null && inventory.has(day.day)))
    .map(day => [day.day, { day: day.day, complete: day.complete }])).values()];
  const request_days = [...new Map(loaded.map(day => [day.day, { day: day.day, complete: day.complete }])).values()];
  const byDay = new Map<string, Record<string, unknown>[]>();
  function append(day: string, records: readonly Record<string, unknown>[]) {
    const held = byDay.get(day) ?? [];
    held.push(...records);
    byDay.set(day, held);
  }
  const prior = (row: Record<string, unknown>) => input.exclude_execution === undefined
    || row.run_id !== input.exclude_execution.run_id || row.attempt !== input.exclude_execution.attempt;
  for (const day of loaded) append(day.day, day.records.filter(prior));
  for (const row of input.own_rows ?? []) if (prior(row)) append(row.date, [row]);
  for (const row of input.current_rows ?? []) append(row.date, [row]);
  for (const [day, rows] of byDay) if (rows.length > 0 && !days.some(value => value.day === day)) {
    days.push({ day, complete: false });
  }
  const uses = [...byDay].map(([day, rows]) => projectFeedHealthFields(day, rows));
  return {
    days: days.sort((a, b) => a.day.localeCompare(b.day)), request_days,
    uses: {
      feed_rest: { rows: uses.flatMap(use => use.feed_rest.rows), gaps: uses.flatMap(use => use.feed_rest.gaps) },
      feed_reliability: { rows: uses.flatMap(use => use.feed_reliability.rows), gaps: uses.flatMap(use => use.feed_reliability.gaps) },
      article_admission: { rows: uses.flatMap(use => use.article_admission.rows), gaps: uses.flatMap(use => use.article_admission.gaps) },
      request_totals: {
        rows: uses.flatMap(use => use.request_totals.rows),
        partial_rows: uses.flatMap(use => use.request_totals.partial_rows),
        gaps: uses.flatMap(use => use.request_totals.gaps),
      },
    },
  };
}
export type HealthCapture = Awaited<ReturnType<typeof readHealthCapture>>;
