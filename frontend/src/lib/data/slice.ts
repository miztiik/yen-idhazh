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
