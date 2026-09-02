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
export type RailForm = 'clock' | 'yesterday' | 'dated' | 'first-seen' | 'none';

/** One story's time, as the rail says it. */
export interface RailTime {
	/** What the reader reads. Never a relative form. */
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

/** A story's time, in the one vocabulary the day's rail uses.
 *
 * **No relative form, ever.** The page is prerendered once and read for the
 * next 24 hours with script optionally off, so `3 hours ago` baked in at 06:20
 * is wrong by 18:20 and wrong for ever on an archived day. `Yesterday` is not
 * a relative form: it is relative to the day the page IS, which is printed at
 * the top of that page and never moves.
 *
 * **The clock is only ever attributed where the payload attributes it.**
 * `time_source` says which clock `published_at` came from, and the one value
 * that changes what a reader is told is `first_seen` - the feed's date was
 * absent or rejected as impossible, so the stamp is our own first sight of the
 * address. That prints `First seen 06:20` and carries a mark. A story whose
 * `time_source` is absent - every day published before 2026-08-31 - prints the
 * stamp with no attribution at all, because the run recorded no answer and
 * either claim would be one we cannot back.
 */
export function railTime(
	publishedAt: string | null | undefined,
	timeSource: string | null | undefined,
	onDate: string,
	groupMinutes: number
): RailTime {
	if (!publishedAt) return { label: 'No time given', form: 'none', group: 'none' };
	const clock = publishedAt.slice(11, 16);
	const group = slice(publishedAt, groupMinutes);
	if (timeSource === 'first_seen') {
		return { label: `First seen ${clock}`, form: 'first-seen', group: `first-seen:${group}` };
	}
	const offset = dayOffset(publishedAt, onDate);
	if (offset === 0) return { label: clock, form: 'clock', group: `clock:${group}` };
	if (offset === -1) {
		return { label: `Yesterday ${clock}`, form: 'yesterday', group: `yesterday:${group}` };
	}
	const date = publishedAt.slice(0, 10);
	const sameYear = date.slice(0, 4) === onDate.slice(0, 4);
	return {
		label: `${sameYear ? dayMonth(date) : shortDate(date)} ${clock}`,
		form: 'dated',
		group: `dated:${group}`
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
