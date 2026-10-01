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
	let first = daily[0].covers;
	const coarser: [Exclude<Period, 'daily'>, readonly CompactEntry[]][] = [
		['monthly', monthly],
		['yearly', yearly]
	];
	for (const [period, entries] of coarser) {
		const oldest = entries.length > 0 ? FIRST_DAY[period](entries[0].covers) : null;
		if (oldest !== null && oldest < first) first = oldest;
	}
	return first;
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
