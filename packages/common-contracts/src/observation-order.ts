/** Which lifecycle facts hold for every order allowed by the saved clock precision? */
export const RECORDED_INSTANT_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/;
const millisecondsPerSecond = 1000;
const millisecondsPerDay = 86_400_000;
export type TimeBounds = Readonly<{ lower: number; upper: number }>;
export type HealthObservation = Readonly<{
  date: string; run_id: string; checked_at?: string | undefined;
  outcome: string; items: number;
}>;

export function validRecordedInstant(value: string): boolean {
  if (!RECORDED_INSTANT_PATTERN.test(value) || value.startsWith("0000")) return false;
  const time = Date.parse(value);
  const canonical = value.includes(".") ? value : value.slice(0, -1) + ".000Z";
  return Number.isFinite(time) && new Date(time).toISOString() === canonical;
}

export function instantBounds(value: string): TimeBounds {
  if (!validRecordedInstant(value)) throw new Error("Recorded instant must be a valid UTC second or millisecond string");
  const lower = Date.parse(value);
  return { lower, upper: lower + (value.includes(".") ? 1 : millisecondsPerSecond) };
}

export function definitelyAfter(later: string, earlier: string): boolean {
  return instantBounds(later).lower >= instantBounds(earlier).upper;
}

function observationBounds(row: HealthObservation): TimeBounds {
  if (row.checked_at) return instantBounds(row.checked_at);
  const lower = instantBounds(`${row.date}T00:00:00Z`).lower;
  return { lower, upper: lower + millisecondsPerDay };
}

export function observationGroups<T extends HealthObservation>(rows: readonly T[]): T[][] {
  const ordered = rows.map(row => ({ row, ...observationBounds(row) })).sort((a, b) =>
    a.lower - b.lower || a.upper - b.upper || a.row.run_id.localeCompare(b.row.run_id));
  const groups: T[][] = [];
  let upper = Number.NEGATIVE_INFINITY;
  for (const item of ordered) {
    if (item.lower >= upper) {
      groups.push([]);
      upper = item.upper;
    } else upper = Math.max(upper, item.upper);
    groups[groups.length - 1]!.push(item.row);
  }
  return groups;
}

export function availabilityEvidence(rows: readonly HealthObservation[], threshold?: number) {
  if (threshold !== undefined && (!Number.isSafeInteger(threshold) || threshold < 1)) throw new Error("Rest threshold must be a positive integer");
  const failing = (row: HealthObservation) => ["blocked", "permanent", "transient"].includes(row.outcome)
    || (row.outcome === "ok" && row.items === 0);
  const failures = rows.filter(failing);
  const resets = rows.filter(row => !failing(row) && !["skipped", "robots_denied"].includes(row.outcome));
  const skips = rows.filter(row => row.outcome === "skipped");
  const nonSkips = rows.filter(row => row.outcome !== "skipped");
  const [strikesLow, strikesHigh] = countAfter(failures, resets);
  const [skipsLow, skipsHigh] = countAfter(skips, nonSkips);
  const resting = threshold === undefined ? null : strikesLow >= threshold && skipsHigh < threshold ? true
    : strikesHigh < threshold || skipsLow >= threshold ? false : null;
  return {
    strikes: strikesLow === strikesHigh ? strikesLow : null,
    rested_runs: skipsLow === skipsHigh ? skipsLow : null,
    resting,
    failing: strikesLow > 0 ? true : strikesHigh === 0 ? false : null,
  };
}

function countAfter(values: readonly HealthObservation[], resets: readonly HealthObservation[]): [number, number] {
  if (resets.length === 0) return [values.length, values.length];
  const { lower: lastStart, upper: lastEnd } = latestBounds(resets);
  return [
    values.filter(row => observationBounds(row).lower >= lastEnd).length,
    values.filter(row => observationBounds(row).upper > lastStart).length,
  ];
}

export function latestObservations<T extends HealthObservation>(rows: readonly T[]): T[] {
  if (rows.length === 0) return [];
  const lastStart = latestBounds(rows).lower;
  return rows.filter(row => observationBounds(row).upper > lastStart);
}

function latestBounds(rows: readonly HealthObservation[]): TimeBounds {
  let lower = Number.NEGATIVE_INFINITY;
  let upper = Number.NEGATIVE_INFINITY;
  for (const row of rows) {
    const bounds = observationBounds(row);
    lower = Math.max(lower, bounds.lower);
    upper = Math.max(upper, bounds.upper);
  }
  return { lower, upper };
}
