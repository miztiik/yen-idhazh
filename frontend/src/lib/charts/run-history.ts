/** The run strip's time axis: which columns carry a date, and what it says.
 *
 * Separate from the page because the rule it encodes is arithmetic - how many
 * labels a strip of N days can carry before two of them touch - and arithmetic
 * is worth testing without a browser.
 *
 * A date is read as text, never through a `Date`, so the strip cannot shift by
 * a column because the machine that built it sat west of UTC.
 */

import { dayTicks } from './frame';
import { dayMonth, shortDate } from '../format';

export type LabelAlign = 'start' | 'centre' | 'end';

export interface AxisLabel {
	/** 1-based grid column. A label is placed, never sized, so it can never
	 * widen the day track it points at. */
	column: number;
	text: string;
	align: LabelAlign;
}

/** One day, and the gap after it, when nothing has measured the strip yet.
 *
 * The ratio is what matters and is fixed: the strip is a time axis, so two days
 * apart must measure twice one day apart whatever the labels say. The SIZE is
 * not fixed - see `cellFor`. Sixteen and four were chosen when the page was
 * 624px wide, and a strip drawn at 16px per day inside a 1500px frame leaves
 * most of the frame empty.
 */
export const CELL_PX = 16;
export const GAP_PX = 4;

/** The strip grows into room it is given and never shrinks below the pair it
 * has always used. Shrinking would let a wide window silently change what a
 * phone does - the strip there scrolls and opens on the newest run, and that is
 * a behaviour, not a side effect of the cell being 16. */
const CELL_MIN = CELL_PX;
const CELL_MAX = 34;

/** The gap holds its share of the column at every size, so the rhythm of the
 * strip does not change as it grows. Measured off the original pair. */
const GAP_SHARE = GAP_PX / CELL_PX;

export interface StripMetrics {
	cell: number;
	gap: number;
	/** What the strip will actually occupy, so a caller can tell an underfull
	 * strip from a full one. Not an offset: the strip anchors left and the spare
	 * room is on the right, so nothing has to be computed to place it. */
	width: number;
}

/** How wide a day column should be, given the room the strip has.
 *
 * Null width means nothing has measured yet - the server, or the first frame -
 * and the fixed pair is used, so the prerendered strip is never zero-width.
 */
export function cellFor(available: number | null, days: number): StripMetrics {
	if (available === null || available <= 0 || days <= 0) {
		return { cell: CELL_PX, gap: GAP_PX, width: days * (CELL_PX + GAP_PX) };
	}
	// Solve for the cell that fills the room, then clamp. Growing past CELL_MAX
	// would make a fortnight of runs look like a row of tiles rather than a
	// sequence, which is the thing the strip exists to show.
	const raw = available / (days * (1 + GAP_SHARE));
	const cell = Math.max(CELL_MIN, Math.min(CELL_MAX, Math.floor(raw)));
	const gap = Math.max(2, Math.round(cell * GAP_SHARE));
	return { cell, gap, width: days * (cell + gap) };
}

/** The room a strip gets when it sits inside a row rather than across a page. */
export const ROW_STRIP_PX = 240;

/** Small enough to fit ninety days in a list row, big enough to still be a
 * square rather than a tick. */
const DENSE_MIN = 3;

/** No taller than the target bar it sits beside. A strip drawn larger than the
 * bar would read as the more important of the two, and it is not. */
const DENSE_MAX = 14;

/** A strip that has to fit the room it is given, however many days that is.
 *
 * `cellFor` grows a strip into a page-wide frame and never goes below the pair
 * it has always used, because that strip scrolls when it runs out of room. A
 * strip inside a list row cannot scroll - twenty scrollbars in one column is
 * not a list - so this one shrinks instead, and stops where a square stops
 * being visible rather than where it stops being comfortable.
 */
export function denseCellFor(available: number, days: number): StripMetrics {
	if (available <= 0 || days <= 0) return { cell: DENSE_MIN, gap: 1, width: 0 };
	const raw = Math.floor(available / (days * (1 + GAP_SHARE)));
	const cell = Math.max(DENSE_MIN, Math.min(DENSE_MAX, raw));
	const gap = Math.max(1, Math.round(cell * GAP_SHARE));
	// Every column but the last carries a gap after it. Counting a trailing one
	// would put the axis a gap to the right of the squares it labels.
	return { cell, gap, width: days * cell + Math.max(0, days - 1) * gap };
}

/** A label a week apart, because a week is the cadence an operator counts in. */
const WEEK = 7;

/** At or below this many days the strip carries one label for the whole span.
 * A cadence needs at least two intervals to read as one. */
const SPAN_MAX_DAYS = WEEK - 1;

function year(date: string): string {
	return date.slice(0, 4);
}

function month(date: string): string {
	return date.slice(0, 7);
}

/** The whole span as one label, for a strip too short to carry a cadence. */
export function spanLabel(first: string, last: string): string {
	if (first === last) return shortDate(first);
	// The month and the year are stated once when both ends share them. "18-20
	// Aug 2026" is the same fact as "18 Aug 2026 - 20 Aug 2026", said once.
	if (month(first) === month(last)) return `${Number(first.slice(8))}-${shortDate(last)}`;
	if (year(first) === year(last)) return `${dayMonth(first)} - ${shortDate(last)}`;
	return `${shortDate(first)} - ${shortDate(last)}`;
}

export interface StripAxisOptions {
	/** `chart.tick_density` - the most labels the strip may carry. */
	density: number;
	/** One column's pitch in pixels: `cell + gap` from `cellFor` or
	 * `denseCellFor`. The room a grid-placed label actually has. */
	pitch: number;
}

/** Where each date label sits, for a strip of `dates` in chronological order.
 *
 * The thinning is `dayTicks`, not a rule of its own. This strip had a weekly
 * cadence with a hand-written "drop an intermediate within six columns of the
 * end" clause, and six columns is only the right number at one cell size - the
 * cell here runs from 3px to 34px. Two helpers is how the two axes drifted, so
 * there is one, and this converts its answer into grid columns.
 */
export function axisLabels(dates: string[], options: StripAxisOptions): AxisLabel[] {
	const last = dates.length;
	if (last === 0) return [];
	if (last <= SPAN_MAX_DAYS) {
		return [{ column: last, text: spanLabel(dates[0], dates[last - 1]), align: 'end' }];
	}
	return dayTicks(dates, {
		density: options.density,
		columns: dates.map((_, index) => index * options.pitch)
	})
		.filter((tick) => tick.text !== '')
		.map((tick) => ({
			column: tick.index + 1,
			text: tick.text,
			align: tick.anchor === 'middle' ? 'centre' : tick.anchor
		}));
}
