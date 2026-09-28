/**
 * Which compact files does a closed range of UTC days need?
 *
 * For each day, the coarsest period that holds it: the month file when
 * `monthly.json` names the day's month, otherwise the day file when `daily.json`
 * names the day. So a day is read through exactly one file, and a day both
 * indexes name is read from the month - reading it twice would double every
 * number drawn from it. A day neither index names is a hole, and the first one,
 * ascending, comes back instead of a file set: drawing the days around a hole
 * would be an undercount nobody could see.
 *
 * Pure: it takes the range and the two entry lists, and reads nothing else.
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
	monthly: readonly CompactEntry[]
): FileSelection {
	const months = new Map(monthly.map((entry) => [entry.covers, entry]));
	const days = new Map(daily.map((entry) => [entry.covers, entry]));
	const chosen = new Map<string, ChosenFile>();
	for (const day of daysBetween(from, to)) {
		const month = months.get(day.slice(0, 7));
		const period: Period = month ? 'monthly' : 'daily';
		const entry = month ?? days.get(day);
		if (entry === undefined) return { hole: day };
		const key = `${period}/${entry.covers}`;
		if (!chosen.has(key)) chosen.set(key, { period, entry, firstDay: day });
	}
	return { files: [...chosen.values()] };
}
