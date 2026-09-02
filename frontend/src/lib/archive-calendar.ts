/** The archive's day list, as arithmetic.
 *
 * Separate from the page for the reason `day-shape.ts` is: the rule here is a
 * decision - how many days stay out and how the rest are grouped - and a
 * decision is worth testing without a browser. It is also the only way to drive
 * it over seven hundred days, which is two years more than the archive holds.
 *
 * **Nothing here drops a day.** Every published date sits inside exactly one
 * month, and the newest few are ALSO listed above it. That block is a shortcut
 * rather than a partition, so a month row's `20 of 31 days` is the truth about
 * that month whether or not some of its days are also on the page above.
 *
 * The day inside a month is a NUMBER and not a date. The month key already
 * carries the year and the month, and the prerendered document pays for every
 * byte of what is left.
 */

import { MONTHS } from './format';

/** One published day, as the archive's `load` reads it off the payload. */
export interface ArchiveDay {
	date: string;
	items: number;
	partial: boolean;
}

/** A month of the archive, as one disclosure row. */
export interface ArchiveMonth {
	/** `YYYY-MM`. */
	month: string;
	/** "August 2026". Built here rather than in the page, so the only thing the
	 * archive route imports from this module is a type. */
	label: string;
	/** The days of the month that published, newest first. */
	days: number[];
	/** How many days that calendar month has, so the row can say `20 of 31`. */
	length: number;
	stories: number;
}

/** A year older than the newest published one, as one disclosure row. */
export interface ArchiveYear {
	year: string;
	months: ArchiveMonth[];
	/** Published days in the year, and days in the year, in that order. */
	days: number;
	length: number;
	stories: number;
}

export interface ArchiveCalendar {
	/** The newest published year's months, newest first. */
	months: ArchiveMonth[];
	/** Every year before it, newest first, each wrapping its own months. */
	years: ArchiveYear[];
}

/** Days in a calendar month, where `month` is 1 to 12.
 *
 * Day zero of the next month is the last day of this one, and every part is
 * given in UTC, so the answer never moves with the machine's time zone.
 */
function monthLength(year: number, month: number): number {
	return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

function yearLength(year: number): number {
	let total = 0;
	for (let month = 1; month <= 12; month += 1) total += monthLength(year, month);
	return total;
}

/** Every published day, grouped by month and then by year.
 *
 * `days` may arrive in any order; the result is newest first throughout.
 */
export function archiveCalendar(days: ArchiveDay[]): ArchiveCalendar {
	const byMonth = new Map<string, ArchiveMonth>();
	for (const day of [...days].sort((a, b) => b.date.localeCompare(a.date))) {
		const key = day.date.slice(0, 7);
		const year = Number(key.slice(0, 4));
		const month = Number(key.slice(5, 7));
		let entry = byMonth.get(key);
		if (!entry) {
			entry = {
				month: key,
				label: `${MONTHS[month - 1] ?? key} ${year}`,
				days: [],
				length: monthLength(year, month),
				stories: 0
			};
			byMonth.set(key, entry);
		}
		entry.days.push(Number(day.date.slice(8, 10)));
		entry.stories += day.items;
	}

	const months = [...byMonth.values()];
	const newest = months[0]?.month.slice(0, 4) ?? '';
	const years: ArchiveYear[] = [];
	for (const month of months) {
		const year = month.month.slice(0, 4);
		if (year === newest) continue;
		let entry = years.at(-1);
		if (!entry || entry.year !== year) {
			entry = { year, months: [], days: 0, length: yearLength(Number(year)), stories: 0 };
			years.push(entry);
		}
		entry.months.push(month);
		entry.days += month.days.length;
		entry.stories += month.stories;
	}

	return { months: months.filter((month) => month.month.startsWith(newest)), years };
}

/** The `/YYYY-MM-DD/` path segment for one day inside a month. */
export function dayDate(month: string, day: number): string {
	return `${month}-${String(day).padStart(2, '0')}`;
}
