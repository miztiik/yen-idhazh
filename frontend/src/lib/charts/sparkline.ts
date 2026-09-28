/** Direction at a glance, inside a card.
 *
 * The question: which way is this going. Not "by how much" - the number beside
 * it says that. So the sparkline carries no axis, no gridline and no label: it
 * is a shape, and anything else on it is competing with the number it exists to
 * support.
 *
 * The domain is the drawn extent rather than zero. A sparkline is about change,
 * and anchoring at zero flattens every series whose variation is small next to
 * its level - which is most of them.
 *
 * Its strip is built here too, from the same points the line is drawn from, so
 * a day the line drops cannot leave its date behind under another day's value.
 */

import { shortDate } from '../format';
import { readoutOf, type Readout } from './readout';

/** The rules one line is drawn by, with no drawing attached.
 *
 * A trend inside a list row cannot be a chart instance - a failure ledger has
 * one per row. So the domain rule, the movement rule and the two-point minimum
 * live here, where the card, the row and every test read them from one place. */
export interface SparklineShape {
	/** The finite values, in order. */
	values: number[];
	min: number;
	max: number;
	/** Last minus first, as a share of first. Null where the first is zero or
	 * there is nothing to compare. The card prints this; the line only shows it. */
	movement: number | null;
	rising: boolean;
	empty: boolean;
}

/** One reading of a line: the day it was taken, in the ledger's spelling, and
 * its value, or null where the ledger has none. The date travels with the
 * value, so a reading that is dropped takes its date with it. */
export interface SparkPoint {
	date: string;
	value: number | null;
}

/** The shape plus the points to draw. Kept apart so the console does not carry
 * the normalising arithmetic for a line it does not draw as markup. */
export interface SparklineMarks extends SparklineShape {
	/** The points in the unit square, y measured downward the way SVG does. A
	 * flat series sits on the middle line rather than on an edge. */
	points: { x: number; y: number }[];
	/** The day of each finite value, one per value and in the same order. */
	dates: string[];
}

/** What a line measures, as its strip names and prints it. */
export interface SparklineSeries {
	/** The strip entry's label. */
	label: string;
	/** The one formatter the figure beside the line and the strip both print
	 * through, told the day a value was taken on. */
	format: (value: number, date: string) => string;
}

/** A sentence that belongs to one drawn day - the model changed on it. */
export interface SparklineRule {
	/** Which drawn point it lands on, counted from the oldest. */
	point: number;
	label: string;
}

/** The colour a line is drawn in, and so the swatch its strip prints as its key. */
export const SPARKLINE_SWATCH = 'var(--chart-2)';

/** What a strip prints for a day with no value. A line drops a missing reading
 * before it draws, so no column it keeps is ever unmeasured; this is the one
 * sentence the builder asks every strip for. */
const NOT_MEASURED = 'Nothing was recorded on this day.';

export function sparklineShape(values: readonly number[]): SparklineShape {
	const points = values.filter((v) => Number.isFinite(v));
	// Two points is the minimum that has a direction. One is a dot, and a dot
	// with a trend arrow beside it is a lie.
	if (points.length < 2) {
		return { values: points, min: 0, max: 0, movement: null, rising: false, empty: true };
	}

	const first = points[0];
	const last = points[points.length - 1];

	return {
		values: points,
		min: Math.min(...points),
		max: Math.max(...points),
		movement: first === 0 ? null : (last - first) / first,
		rising: last >= first,
		empty: false
	};
}

/** The line a component draws, from its readings oldest first. */
export function sparklineMarks(readings: readonly SparkPoint[]): SparklineMarks {
	const kept = readings.filter(
		(reading): reading is { date: string; value: number } =>
			reading.value !== null && Number.isFinite(reading.value)
	);
	const dates = kept.map((reading) => reading.date);
	const shape = sparklineShape(kept.map((reading) => reading.value));
	if (shape.empty) return { ...shape, points: [], dates };

	const span = shape.max - shape.min;
	return {
		...shape,
		points: shape.values.map((v, i) => ({
			x: i / (shape.values.length - 1),
			y: span === 0 ? 0.5 : 1 - (v - shape.min) / span
		})),
		dates
	};
}

/** The strip a line reads into: one column per drawn day, its one series, and
 * each rule's sentence on the day it lands on.
 *
 * One function for every line, whether the line prints its own strip or the
 * list it sits in prints one for all of its rows, so the two cannot show one
 * row two different ways. A line too short to draw has no column, and the
 * strip prints nothing for it. */
export function sparklineReadout(
	marks: SparklineMarks,
	series: SparklineSeries,
	rules: readonly SparklineRule[]
): Readout {
	const dates = marks.empty ? [] : marks.dates;
	return readoutOf({
		type: 'dateSeries',
		columns: dates.map(shortDate),
		series: [
			{
				label: series.label,
				swatch: SPARKLINE_SWATCH,
				values: marks.empty ? [] : marks.values,
				format: (value, column) => series.format(value, dates[column])
			}
		],
		events: {
			lines: dates.map((_, column) =>
				rules
					.filter((rule) => rule.point === column)
					.map((rule) => ({ label: rule.label, value: '', swatch: null }))
			)
		},
		notMeasured: NOT_MEASURED,
		resting: 'newest'
	});
}
