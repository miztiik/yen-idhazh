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
 * **An entry may name a period that has no file.** An `empty` one held no row,
 * so its days are quiet and nothing is fetched for them. A `lost` day lost its
 * rows, and so did each day a month or a year lists in its `lost_days`: those
 * days come back by name, beside the files, because a day with no record is not
 * a day with no rows. `namesFile()` is the one reading of whether an entry has a
 * file, so every reader and the site build agree on it. **An entry may also
 * count files its packing set aside unread** (`set_aside`); each such period
 * the range is read from comes back with its count, because its file, if it has
 * one, holds every row but theirs.
 *
 * Where the ledger starts is worked out here too, `firstNamed()`, and how far it
 * is packed, `newestNamed()`, so every reader cuts a span at the same first day
 * and clamps it at the same newest one; and where its rows stop, `newestHeld()`,
 * so a console route can say so without reading a day before its window.
 *
 * Pure: it takes the range and the three entry lists, and reads nothing else.
 * It imports types only, so the site build loads it in plain Node.
 */

import type { CompactEntry, Period } from './compact-index';
import type { DateStamp, SetAsideFiles } from './slice-shapes';

/** One file a range needs, and the first day of the range it answers for. */
export interface ChosenFile {
	period: Period;
	entry: CompactEntry;
	firstDay: DateStamp;
}

/** The files a range needs, in ascending order, the days in it recorded lost, and the
 *  files its periods set aside unread; or the first day nothing holds. */
export type FileSelection = { files: ChosenFile[]; lostDays: DateStamp[]; setAside: SetAsideFiles } | { hole: DateStamp };

const DAY_MS = 86_400_000;

/** Whether an index entry names a file. A `packed` period has one; an `empty`
 *  or a `lost` one has none. An entry with no state was written before entries
 *  had one, when every entry named a file, so it reads as `packed`. */
export function namesFile(entry: CompactEntry): boolean {
	return entry.state === undefined || entry.state === 'packed';
}

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
 *  year from its 1 January. At least one index names a period; a day before
 *  this one is before the ledger began, so a reader cuts a span there, and a day
 *  from it on that no index names is a hole. */
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

/** The first and the last UTC day one entry covers: a day, a month or a year. */
export function coveredDays(period: Period, covers: string): { first: DateStamp; last: DateStamp } {
	if (period === 'daily') return { first: covers, last: covers };
	return { first: FIRST_DAY[period](covers), last: period === 'monthly' ? lastDayOfMonth(covers) : `${covers}-12-31` };
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

/** The file of the newest entry that names one, a day before a month before a
 *  year, or null when no entry names a file. Whatever days it covers, it holds
 *  the ledger's newest columns. */
export function newestFile(
	daily: readonly CompactEntry[],
	monthly: readonly CompactEntry[],
	yearly: readonly CompactEntry[]
): ChosenFile | null {
	const day = daily.findLast(namesFile);
	if (day !== undefined) return { period: 'daily', entry: day, firstDay: day.covers };
	const month = monthly.findLast(namesFile);
	if (month !== undefined) return { period: 'monthly', entry: month, firstDay: FIRST_DAY.monthly(month.covers) };
	const year = yearly.findLast(namesFile);
	return year === undefined ? null : { period: 'yearly', entry: year, firstDay: FIRST_DAY.yearly(year.covers) };
}

/** One period an index names: a day, a month or a year, by its `covers`. */
export interface HeldPeriod {
	period: Period;
	covers: string;
}

/** The newest period whose file holds rows, a day before a month before a year,
 *  or null when no entry holds a row. The packing moves a closed month's days out
 *  of `daily.json` and a packed year's months out of `monthly.json`, so a day that
 *  holds rows is newer than any month, and a month than any year. A reader that
 *  reads nothing before its window learns from this where a ledger's rows stop. */
export function newestHeld(
	daily: readonly CompactEntry[],
	monthly: readonly CompactEntry[],
	yearly: readonly CompactEntry[]
): HeldPeriod | null {
	const holds = (entry: CompactEntry): boolean => namesFile(entry) && entry.rows > 0;
	const day = daily.findLast(holds);
	if (day !== undefined) return { period: 'daily', covers: day.covers };
	const month = monthly.findLast(holds);
	if (month !== undefined) return { period: 'monthly', covers: month.covers };
	const year = yearly.findLast(holds);
	return year === undefined ? null : { period: 'yearly', covers: year.covers };
}

/** The files that answer every day from `from` to `to`, one file a day, the days
 *  among them an index records lost, and the files set aside by the periods they
 *  are read from. */
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
	const lostDays: DateStamp[] = [];
	const setAside: Record<string, number> = {};
	for (const day of daysBetween(from, to)) {
		const year = years.get(day.slice(0, 4));
		const month = year === undefined ? months.get(day.slice(0, 7)) : undefined;
		const period: Period = year ? 'yearly' : month ? 'monthly' : 'daily';
		const entry = year ?? month ?? days.get(day);
		if (entry === undefined) return { hole: day };
		if (entry.set_aside !== undefined && entry.set_aside > 0) setAside[entry.covers] = entry.set_aside;
		if (entry.state === 'lost' || entry.lost_days?.includes(day)) {
			lostDays.push(day);
			continue;
		}
		if (!namesFile(entry)) continue;
		const key = `${period}/${entry.covers}`;
		if (!chosen.has(key)) chosen.set(key, { period, entry, firstDay: day });
	}
	return { files: [...chosen.values()], lostDays, setAside };
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
