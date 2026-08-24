/** The run strip's time axis: which columns carry a date, and what it says.
 *
 * Separate from the page because the rule it encodes is arithmetic - how many
 * labels a strip of N days can carry before two of them touch - and arithmetic
 * is worth testing without a browser.
 *
 * A date is read as text, never through a `Date`, so the strip cannot shift by
 * a column because the machine that built it sat west of UTC.
 */

import { dayMonth, shortDate } from '../format';

export type LabelAlign = 'start' | 'centre' | 'end';

export interface AxisLabel {
	/** 1-based grid column. A label is placed, never sized, so it can never
	 * widen the day track it points at. */
	column: number;
	text: string;
	align: LabelAlign;
}

/** One day, and the gap after it. Fixed: the strip is a time axis, so two days
 * apart must measure twice one day apart whatever the labels say. */
export const CELL_PX = 16;
export const GAP_PX = 4;

/** A label a week apart, because a week is the cadence an operator counts in. */
const WEEK = 7;

/** At or below this many days the strip carries one label for the whole span.
 * A cadence needs at least two intervals to read as one. */
const SPAN_MAX_DAYS = WEEK - 1;

/** How close an intermediate label may come to the newest endpoint before it is
 * dropped. Under six columns the two texts share pixels. */
const MIN_GAP_COLUMNS = 6;

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

/** Where each date label sits, for a strip of `dates` in chronological order. */
export function axisLabels(dates: string[]): AxisLabel[] {
	const last = dates.length;
	if (last === 0) return [];
	if (last <= SPAN_MAX_DAYS) {
		return [{ column: last, text: spanLabel(dates[0], dates[last - 1]), align: 'end' }];
	}

	const labels: AxisLabel[] = [{ column: 1, text: shortDate(dates[0]), align: 'start' }];
	// The year is repeated only when it changes, so the axis says "3 Jan 2026"
	// once instead of carrying four digits every week that never move.
	let carried = year(dates[0]);
	for (let column = 1 + WEEK; column < last; column += WEEK) {
		// An intermediate that lands under the newest endpoint is not a second
		// reading of the axis, it is the same reading twice.
		if (last - column < MIN_GAP_COLUMNS) continue;
		const date = dates[column - 1];
		labels.push({
			column,
			text: year(date) === carried ? dayMonth(date) : shortDate(date),
			align: 'centre'
		});
		carried = year(date);
	}
	labels.push({ column: last, text: shortDate(dates[last - 1]), align: 'end' });
	return labels;
}
