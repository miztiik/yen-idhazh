/** When does the last console update need an absent or late-record warning?
 *
 * The band's `generated_at` dates that update, never the reach of every ledger.
 * A fresh timestamp belongs in the date disclosure, not a standing paragraph.
 * Only the browser's UTC clock can establish lateness.
 */
import { clockUtc, MONTHS } from '$lib/format';

/** A format literal: the English weekday names, in `getUTCDay()` order. */
const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

/** A protocol constant: the milliseconds in one UTC day. */
const DAY_MS = 86_400_000;

export type Completeness =
	/** No record was read, so nothing can be said about how complete it is. */
	| { kind: 'unread' }
	/** The record is as fresh as a working pipeline leaves it. */
	| { kind: 'complete'; finished: number }
	/** Whole UTC days have passed with nothing recorded. */
	| { kind: 'behind'; finished: number; missingDays: number };

/** Which of the three the page is in.
 *
 * `finishedAt` is the band's `generated_at`, or null when no band was read.
 * `now` is the reader's clock in epoch milliseconds, or null where there is no
 * reader - at build time. `graceDays` is `console.completeness_grace_days`: how
 * many whole UTC days the record's day may trail the reader's before the page
 * says days are missing. It decides only whether the count is said. The count
 * is always the whole days between the record's day and today, because today is
 * still being recorded and the record's own day is not missing.
 */
export function completenessOf(
	finishedAt: string | null,
	now: number | null,
	graceDays: number
): Completeness {
	const finished = finishedAt === null ? Number.NaN : Date.parse(finishedAt);
	if (Number.isNaN(finished)) return { kind: 'unread' };
	if (now === null) return { kind: 'complete', finished };
	const behind = Math.floor(now / DAY_MS) - Math.floor(finished / DAY_MS);
	if (behind <= graceDays) return { kind: 'complete', finished };
	return { kind: 'behind', finished, missingDays: behind - 1 };
}

/** "18:23 UTC on Sunday 27 September". The year is left out: a record old
 * enough for the year to matter is one the sentence is already counting the
 * missing days of. */
export function spelledInstant(finished: number): string {
	const at = new Date(finished);
	const day = `${WEEKDAYS[at.getUTCDay()]} ${at.getUTCDate()} ${MONTHS[at.getUTCMonth()]}`;
	return `${clockUtc(at.toISOString())} on ${day}`;
}

export function completenessSentence(state: Completeness): string {
	if (state.kind === 'unread') {
		return 'This page cannot say when the last run finished - its record did not load.';
	}
	if (state.kind === 'complete') return '';
	const when = spelledInstant(state.finished);
	const missing =
		state.missingDays === 1 ? '1 day is missing.' : `${state.missingDays} days are missing.`;
	return `Nothing has been recorded since ${when}. ${missing}`;
}

/** Milliseconds from `now` to the next 00:00 UTC, which is the only moment the
 * answer can change while a page stays open. */
export function untilNextUtcDay(now: number): number {
	return DAY_MS - (now % DAY_MS);
}
