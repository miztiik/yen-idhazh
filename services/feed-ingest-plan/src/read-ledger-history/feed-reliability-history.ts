/** Reuse saved read counts and adjust only known changes to their bounded window. */
import {
  FeedHealthReadFieldsSchema, FeedHealthReliabilitySchema, FeedHealthReliabilityFieldsSchema, definitelyAfter,
} from "@idhazh/common-contracts";
import { z } from "zod";
import type { FeedHealthReliability, FeedHealthStateRow } from "@idhazh/common-contracts";
import { selectSavedReliability } from "./saved-reliability";
import { feedReliability } from "./feed-reliability";

const partialReliability = z.object(FeedHealthReliabilityFieldsSchema.shape).partial();
type Evidence = z.infer<typeof partialReliability>;
type Read = { key: string; date: string; checked_at: string; productive: boolean };

export function settleLogicalFeedReads(rows: readonly Evidence[], now: string): Read[] {
  const reads = new Map<string, Read>();
  const seen = new Map<string, string>();
  for (const row of rows) {
    const parsed = FeedHealthReadFieldsSchema.safeParse(row);
    if (!parsed.success || row.checked_at == null || row.items == null || row.outcome == null
      || Date.parse(row.checked_at) > Date.parse(now)
      || row.outcome === "skipped" || row.outcome === "robots_denied") continue;
    if (row.check_request_id !== null && row.check_request_id !== undefined) {
      const fact = JSON.stringify([row.checked_at, row.items, row.outcome]);
      const previous = seen.get(row.check_request_id);
      if (previous !== undefined && previous !== fact) throw new Error("Conflicting copies of one completed logical feed read");
      seen.set(row.check_request_id, fact);
    }
    const key = `${row.run_id}:${row.feed_id}`;
    const value: Read = { key, date: row.date!, checked_at: row.checked_at, productive: row.outcome === "ok" && row.items > 0 };
    const previous = reads.get(key);
    if (previous === undefined || (value.productive && !previous.productive)
      || (value.productive === previous.productive && definitelyAfter(value.checked_at, previous.checked_at))) {
      reads.set(key, value);
    }
  }
  return [...reads.values()];
}

export function reuseFeedReliability(input: {
  rows: readonly Evidence[]; current: readonly FeedHealthStateRow[];
  days: readonly string[]; history_days: readonly string[]; knownDay: (day: string) => boolean;
  saved?: FeedHealthReliability;
  now: string; floor: number; window: number; onGap: (reason: string) => void;
}): FeedHealthReliability {
  const bounds = { from_day: input.days[0] ?? null, through_day: input.days.at(-1) ?? null };
  const saved = input.saved === undefined ? selectSavedReliability(input.rows.flatMap(row => {
    const parsed = FeedHealthReliabilitySchema.safeParse(row.reliability);
    return parsed.success ? [{
      at: row.checked_at ?? row.availability_updated_at ?? null, value: parsed.data,
    }] : [];
  }), bounds, input.now) : { value: structuredClone(input.saved), conflicting: [] };
  const coverage = input.days.length >= input.window && input.days.every(input.knownDay);
  let value = saved.value;
  let reads: Read[] | undefined;
  const evidence = () => reads ??= settleLogicalFeedReads(input.rows, input.now);
  if (saved.conflicting.length) {
    input.onGap("reliability-order-ambiguous");
    value = { productive: null, attempted: null, success_fraction: null, production_factor: null, ...bounds, complete: false };
  }
  if (value === null) {
    input.onGap("reliability-calculation-missing");
    const measured = evidence().filter(row => input.days.includes(row.date));
    value = {
      productive: measured.length ? measured.filter(row => row.productive).length : null,
      attempted: measured.length || null, success_fraction: null, production_factor: null,
      ...bounds, complete: coverage && measured.length > 0,
    };
  } else if (value.from_day !== bounds.from_day || value.through_day !== bounds.through_day) {
    const oldFrom = value.from_day;
    const oldThrough = value.through_day;
    const overlapKnown = oldFrom !== null && oldThrough !== null
      && input.knownDay(oldFrom) && input.knownDay(oldThrough);
    const changedDays = input.days.filter(day => oldFrom === null || oldThrough === null || day < oldFrom || day > oldThrough);
    const leavingDays = input.history_days.filter(day => oldFrom !== null && oldThrough !== null
      && day >= oldFrom && day <= oldThrough && !input.days.includes(day));
    if (!overlapKnown || !changedDays.every(input.knownDay) || !leavingDays.every(input.knownDay)) {
      input.onGap("reliability-window-contributions-missing");
      const work = settleLogicalFeedReads(input.current, input.now);
      if (work.length === 0) return { ...value, complete: false };
      const measured = settleLogicalFeedReads([...input.rows, ...input.current], input.now)
        .filter(row => input.days.includes(row.date));
      const productive = measured.filter(row => row.productive).length;
      return { productive, attempted: measured.length, ...bounds, complete: false,
        ...feedReliability(productive, measured.length, input.floor) };
    } else {
      const leaving = evidence().filter(row => row.date >= oldFrom! && row.date <= oldThrough!
        && !input.days.includes(row.date));
      const entering = evidence().filter(row => changedDays.includes(row.date));
      value = {
        ...value, ...bounds,
        productive: value.productive === null ? null : value.productive
          - leaving.filter(row => row.productive).length + entering.filter(row => row.productive).length,
        attempted: value.attempted === null ? null : value.attempted - leaving.length + entering.length,
        complete: value.complete && coverage,
      };
    }
  }
  const current = settleLogicalFeedReads(input.current, input.now);
  for (const check of current.filter(row => input.days.includes(row.date))) {
    const previous = settleLogicalFeedReads(input.rows.filter(row => `${row.run_id}:${row.feed_id}` === check.key), input.now)
      .find(row => input.days.includes(row.date));
    const productive = check.productive || previous?.productive === true;
    if (previous === undefined) {
      // With no measured baseline, current work is a supported partial count, not complete history.
      value.productive = value.productive === null && saved.value === null ? Number(productive)
        : value.productive === null ? null : value.productive + Number(productive);
      value.attempted = value.attempted === null && saved.value === null ? 1
        : value.attempted === null ? null : value.attempted + 1;
    } else if (productive && !previous.productive && value.productive !== null) value.productive++;
  }
  if (input.current.some(row => row.check_request_id !== null && (row.items === null || row.check_result === "interrupted"))) {
    input.onGap("reliability-current-work-incomplete");
    value.complete = false;
  }
  if ((value.productive !== null && value.productive < 0) || (value.attempted !== null && value.attempted < 0)
    || (value.productive !== null && value.attempted !== null && value.productive > value.attempted)) {
    input.onGap("reliability-snapshot-conflict");
    value = { ...value, productive: null, attempted: null, success_fraction: null,
      production_factor: null, complete: false };
  }
  if (value.productive !== null && value.attempted !== null && value.attempted > 0) {
    Object.assign(value, feedReliability(value.productive, value.attempted, input.floor));
  } else if (value.attempted === 0) {
    value.success_fraction = null;
    value.production_factor = null;
  }
  return FeedHealthReliabilitySchema.parse(value);
}
