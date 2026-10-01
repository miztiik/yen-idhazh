/** How complete the console's record is, as one sentence: when the last run
 * finished, and - once a reader's clock is known - how many whole days have
 * passed with nothing recorded.
 *
 * Every chart on the console draws the newest days that exist rather than the
 * last N days, so when the record stops a chart gains no gap at its right edge.
 * It slides back in time and looks as full as it did the day before. This
 * sentence is what tells a stopped pipeline from a quiet one.
 *
 * All of it is UTC (CLAUDE.md section 2). The instant is the band's
 * `generated_at`, the moment the run that wrote the record finished. The day
 * is always spelled out, weekday and date and never `today`: the page's day is
 * the UTC day, and a reader's own day can be a different one.
 *
 * It dates the last run and never the newest packed day, and it does not call
 * the page complete. A chart drawn from a packed ledger can end days before
 * that run, and the route's own note for that record says how far it reaches
 * (`recording.ts`).
 *
 * No clock is read here. The prerendered page has no reader's clock to judge
 * against, so it states the instant and nothing more; a browser passes its own
 * clock once the page is open, and only then can the record be late.
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
	const when = spelledInstant(state.finished);
	if (state.kind === 'complete') {
		return `The latest run on this page finished at ${when}. A run still going is not on this page yet.`;
	}
	const missing =
		state.missingDays === 1 ? '1 day is missing.' : `${state.missingDays} days are missing.`;
	return `Nothing has been recorded since ${when}. ${missing}`;
}

/** Milliseconds from `now` to the next 00:00 UTC, which is the only moment the
 * answer can change while a page stays open. */
export function untilNextUtcDay(now: number): number {
	return DAY_MS - (now % DAY_MS);
}
