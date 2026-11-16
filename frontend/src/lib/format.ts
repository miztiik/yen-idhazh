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

/** Which shape a story printed its own time in.
 *
 * Named so a check can assert the branch rather than pattern-matching the
 * string it produced. `first-seen` is the one that says the printed clock is
 * ours; every other form prints the stamp the day published and claims nothing
 * about whose clock wrote it.
 */
export type TimeForm = 'clock' | 'dated' | 'first-seen' | 'none';

/** One story's time, as the item prints it beside its heading. */
export interface ItemTime {
	/** The reader-facing absolute time, including its timezone. */
	label: string;
	form: TimeForm;
}

/** A story's own absolute time, labelled in UTC.
 *
 * Only a story published today in today's edition gets a clock alone. Every
 * other stamp includes its full date, even when it matches an archived edition.
 * `todayUtc` comes from the mounted reader; null keeps the full date before the
 * browser clock is available rather than freezing "today" into a static build.
 *
 * **The clock is still only ever attributed where the payload attributes it.**
 * `time_source: first_seen` means the feed's date was absent or rejected as
 * impossible and the stamp is our own first sight of the address. That keeps
 * its own form, and `DigestItem.svelte` draws a mark beside it without claiming
 * the source supplied that time.
 *
 * A story with no stamp at all has no number to print and gets an empty label,
 * which is the one case the item draws nothing for.
 */
export function itemTime(
	publishedAt: string | null | undefined,
	timeSource: string | null | undefined,
	onDate: string,
	todayUtc: string | null
): ItemTime {
	if (!publishedAt || timeSource === 'unknown') return { label: '', form: 'none' };
	const clock = clockUtc(publishedAt);
	const date = publishedAt.slice(0, 10);
	const clockOnly = onDate === todayUtc && date === todayUtc;
	// Reuse the shared month vocabulary, retaining the stamp's two-digit day.
	const month = MONTHS[Number(date.slice(5, 7)) - 1]!.slice(0, 3);
	const stamp = clockOnly
		? clock
		: `${date.slice(8, 10)} ${month} ${date.slice(0, 4)} ${clock}`;
	if (timeSource === 'first_seen') return { label: stamp, form: 'first-seen' };
	return { label: stamp, form: clockOnly ? 'clock' : 'dated' };
}

/** A published block's paragraphs, in order.
 *
 * The separator is one blank line, which `Prose` in the backend contract is the
 * only writer of. One entry where there is no break - every day published before
 * 2026-09-17, and every short summary written since - so a caller renders the
 * result the same way whichever kind it has.
 */
export function paragraphsOf(prose: string): string[] {
	return prose.split('\n\n');
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
