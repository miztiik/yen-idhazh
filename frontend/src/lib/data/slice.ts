/**
 * Which compact files does a closed range of UTC days need?
 *
 * For each day, the coarsest period that holds it: the year file when
 * `yearly.json` names the day's year, else the month file when `monthly.json`
 * names the day's month, otherwise the day file when `daily.json` names the day.
 * So a day is read through exactly one file, and a day two indexes name is read
 * from the coarser - reading it twice would double every number drawn from it.
 * A day no index names is a hole, and the first one, ascending, comes back
 * instead of a file set: drawing the days around a hole would be an undercount
 * nobody could see.
 *
 * Where the ledger starts is worked out here too, `firstNamed()`, so the slice
 * and the reach never disagree about which hole lies before it.
 *
 * Pure: it takes the range and the three entry lists, and reads nothing else.
 */

import type { CompactEntry, Period } from './compact-index';
import type { DateStamp } from './slice-shapes';

/** One file a range needs, and the first day of the range it answers for. */
export interface ChosenFile {
	period: Period;
	entry: CompactEntry;
	firstDay: DateStamp;
}

/** The files a range needs, in ascending order, or the first day nothing holds. */
export type FileSelection = { files: ChosenFile[] } | { hole: DateStamp };

const DAY_MS = 86_400_000;

/** Every UTC day from `from` to `to`, both included, ascending. */
export function daysBetween(from: DateStamp, to: DateStamp): DateStamp[] {
	const days: DateStamp[] = [];
	for (let at = Date.parse(`${from}T00:00:00Z`); at <= Date.parse(`${to}T00:00:00Z`); at += DAY_MS) {
		days.push(new Date(at).toISOString().slice(0, 10));
	}
	return days;
}

/** The first day of what one coarser entry covers: a month's 1st, a year's 1 January. */
const FIRST_DAY: Record<Exclude<Period, 'daily'>, (covers: string) => DateStamp> = {
	monthly: (covers) => `${covers}-01`,
	yearly: (covers) => `${covers}-01-01`
};

/** The oldest day any index names, a month counting from its first day and a
 *  year from its 1 January. `daily` names at least one day; a hole before this
 *  day is before the ledger starts, and a hole from it on is a day the packing
 *  lost. */
export function firstNamed(
	daily: readonly CompactEntry[],
	monthly: readonly CompactEntry[],
	yearly: readonly CompactEntry[]
): DateStamp {
	const named = [
		daily[0]?.covers ?? null,
		monthly[0] ? FIRST_DAY.monthly(monthly[0].covers) : null,
		yearly[0] ? FIRST_DAY.yearly(yearly[0].covers) : null
	].filter((day): day is DateStamp => day !== null);
	if (named.length === 0) throw new Error('firstNamed needs at least one named period');
	return named.sort()[0];
}

function lastDayOfMonth(month: string): DateStamp {
	const [year, oneBased] = month.split('-').map(Number);
	return new Date(Date.UTC(year ?? 0, oneBased ?? 0, 0)).toISOString().slice(0, 10);
}

/** The newest day any index names; a month counts through its last UTC day and a year through 31 December. */
export function newestNamed(
	daily: readonly CompactEntry[],
	monthly: readonly CompactEntry[],
	yearly: readonly CompactEntry[]
): DateStamp | null {
	const named = [
		daily.at(-1)?.covers ?? null,
		monthly.at(-1) ? lastDayOfMonth(monthly.at(-1)!.covers) : null,
		yearly.at(-1) ? `${yearly.at(-1)!.covers}-12-31` : null
	].filter((day): day is DateStamp => day !== null);
	return named.length === 0 ? null : named.sort().at(-1)!;
}

/** The files that answer every day from `from` to `to`, one file a day. */
export function filesFor(
	from: DateStamp,
	to: DateStamp,
	daily: readonly CompactEntry[],
	monthly: readonly CompactEntry[],
	yearly: readonly CompactEntry[]
): FileSelection {
	const years = new Map(yearly.map((entry) => [entry.covers, entry]));
	const months = new Map(monthly.map((entry) => [entry.covers, entry]));
	const days = new Map(daily.map((entry) => [entry.covers, entry]));
	const chosen = new Map<string, ChosenFile>();
	for (const day of daysBetween(from, to)) {
		const year = years.get(day.slice(0, 4));
		const month = year === undefined ? months.get(day.slice(0, 7)) : undefined;
		const period: Period = year ? 'yearly' : month ? 'monthly' : 'daily';
		const entry = year ?? month ?? days.get(day);
		if (entry === undefined) return { hole: day };
		const key = `${period}/${entry.covers}`;
		if (!chosen.has(key)) chosen.set(key, { period, entry, firstDay: day });
	}
	return { files: [...chosen.values()] };
}

/** The days after the newest packed day that the staged site listed for a ledger. */
export function writerDaysFor(
	from: DateStamp,
	to: DateStamp,
	newestPacked: DateStamp | null,
	listedThrough: DateStamp | null
): DateStamp[] {
	if (listedThrough === null) return [];
	if (newestPacked !== null && to <= newestPacked) return [];
	const start = newestPacked === null || from > newestPacked ? from : daysBetween(newestPacked, to)[1] ?? to;
	if (start > to || start > listedThrough) return [];
	const end = to < listedThrough ? to : listedThrough;
	return daysBetween(start, end);
}
