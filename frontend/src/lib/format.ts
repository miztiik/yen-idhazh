/** Formatting a reader sees. Deterministic, so two builds agree.
 *
 * Every route carries this module, so a formatter only one route prints does
 * not belong here - it lands on the first-load path of six pages that never
 * call it. `dayRange` sat here for one build and cost 64 gzipped bytes on
 * `/404`; it lives in `assist/search.ts` with the page that says it.
 */

export const MONTHS = [
	'January',
	'February',
	'March',
	'April',
	'May',
	'June',
	'July',
	'August',
	'September',
	'October',
	'November',
	'December'
];

export function longDate(date: string): string {
	const [year, month, day] = date.split('-').map(Number);
	if (!year || !month || !day) return date;
	return `${day} ${MONTHS[month - 1]} ${year}`;
}

export function shortDate(date: string): string {
	const [year, month, day] = date.split('-').map(Number);
	if (!year || !month || !day) return date;
	return `${dayMonth(date)} ${year}`;
}

/** "20 Aug" - the short form without the year, for a dense axis. */
export function dayMonth(date: string): string {
	const [year, month, day] = date.split('-').map(Number);
	if (!year || !month || !day) return date;
	return `${day} ${MONTHS[month - 1]!.slice(0, 3)}`;
}

export function clockUtc(timestamp: string): string {
	return timestamp.slice(11, 16) + ' UTC';
}

/** Which shape the day's rail printed a story's time in.
 *
 * Named so a check can assert the branch rather than pattern-matching the
 * string it produced. `first-seen` is the one that says the printed clock is
 * ours; every other form prints the stamp the day published and claims nothing
 * about whose clock wrote it.
 */
export type RailForm = 'clock' | 'dated' | 'first-seen' | 'none';

/** One story's time, as the rail says it. */
export interface RailTime {
	/** What the reader reads. Digits and separators, never a word. */
	label: string;
	form: RailForm;
	/** Stories sharing this draw one marker between them, on the first of them. */
	group: string;
}

const MINUTES_A_DAY = 1440;

/** Which slice of its own day a stamp falls in, at the configured coarseness.
 *
 * The date leads it, so two stamps at the same hour on different days never
 * share a group however coarse the slices are.
 */
function slice(stamp: string, minutes: number): string {
	const span = Math.min(Math.max(Math.round(minutes), 1), MINUTES_A_DAY);
	const minute = Number(stamp.slice(11, 13)) * 60 + Number(stamp.slice(14, 16));
	return `${stamp.slice(0, 10)}#${Math.floor(minute / span)}`;
}

/** How many calendar days a stamp sits from the day being read. */
function dayOffset(stamp: string, onDate: string): number {
	const day = Date.parse(`${stamp.slice(0, 10)}T00:00:00Z`);
	const anchor = Date.parse(`${onDate}T00:00:00Z`);
	if (Number.isNaN(day) || Number.isNaN(anchor)) return 0;
	return Math.round((day - anchor) / 86_400_000);
}

/** A story's time, in the one vocabulary the day's rail uses: digits.
 *
 * **No words, and no relative form.** The rail prints a clock, and a date in
 * front of it when the stamp is not from the day being read. `Yesterday`,
 * `First seen` and `No time given` are gone - the column already says
 * `Times shown in UTC` once, above itself, so a reader who can read a clock can
 * read every mark on it without being told anything twice. A relative form
 * would be worse than a word: the page is prerendered once and read for the
 * next 24 hours with script optionally off, so `3 hours ago` baked in at 06:20
 * is wrong by 18:20 and wrong for ever on an archived day.
 *
 * **The clock is still only ever attributed where the payload attributes it.**
 * `time_source: first_seen` means the feed's date was absent or rejected as
 * impossible and the stamp is our own first sight of the address. That keeps
 * its own form, and `TimeRail.svelte` draws a mark beside it - a mark rather
 * than a sentence, so the rail stays numbers.
 *
 * A story with no stamp at all has no number to print and gets an empty label.
 */
export function railTime(
	publishedAt: string | null | undefined,
	timeSource: string | null | undefined,
	onDate: string,
	groupMinutes: number
): RailTime {
	if (!publishedAt) return { label: '', form: 'none', group: 'none' };
	const clock = publishedAt.slice(11, 16);
	const group = slice(publishedAt, groupMinutes);
	const offset = dayOffset(publishedAt, onDate);
	const date = publishedAt.slice(0, 10);
	const sameYear = date.slice(0, 4) === onDate.slice(0, 4);
	// The day being read needs no date in front of it; every other day does, and
	// the year only when it is not the year on the page.
	const stamp =
		offset === 0 ? clock : `${sameYear ? date.slice(5) : date} ${clock}`;
	if (timeSource === 'first_seen') {
		return { label: stamp, form: 'first-seen', group: `first-seen:${group}` };
	}
	return {
		label: stamp,
		form: offset === 0 ? 'clock' : 'dated',
		group: `${offset === 0 ? 'clock' : 'dated'}:${group}`
	};
}

/** Initials of the first two meaningful words: "Ars Technica - AI" -> "AT". */
export function monogram(name: string): string {
	const skip = new Set(['the', 'a', 'an', 'of', 'and', 'for']);
	const words = name
		.split(/[\s\-/|]+/)
		.map((word) => word.replace(/[^A-Za-z0-9.]/g, ''))
		.filter((word) => word.length > 0 && !skip.has(word.toLowerCase()));
	if (words.length === 0) return '??';
	if (words.length === 1) return words[0]!.slice(0, 2).toUpperCase();
	return (words[0]![0]! + words[1]![0]!).toUpperCase();
}

/** Stable per source, so a publication keeps its colour between visits. */
export function swatchIndex(sourceId: string): number {
	let hash = 0;
	for (let i = 0; i < sourceId.length; i += 1) {
		hash = (hash * 31 + sourceId.charCodeAt(i)) >>> 0;
	}
	return hash % 8;
}

export function plural(count: number, one: string, many: string): string {
	return `${count} ${count === 1 ? one : many}`;
}
