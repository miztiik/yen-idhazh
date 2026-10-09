/** Articles published against planned, one group a day.
 *
 * The question a run-health figure has to answer is "which day went wrong", and
 * one ratio over a window cannot: a month that publishes 95 percent of what it
 * planned on twenty-nine days and nothing at all on the thirtieth reads the same
 * as a month that lost five percent every day.
 *
 * `planned`, `published` and `failed` are NOT a partition and this module never
 * treats them as one. `items_planned` and `items_failed` are per-run sums;
 * `items_published` is the day's deduped published set, so a story a later run
 * skipped is counted once by publication and twice by planning. An item a run
 * skipped belongs to none of the three. That is why the caller draws three bars
 * side by side rather than one stack, and why `yield` is not bounded above by 1.
 *
 * Geometry only, like `glance.ts::failureLoad`. Nothing here knows a pixel; the
 * component owns the axes and the marks. What each count is called and which
 * colour it is drawn in are here, because `Run health` prints them in a readout
 * the chart does not own, and a swatch set in one file and a bar in another is
 * how the two drift apart.
 */

import type { DayMetrics } from '$lib/server/payload';
import type { ReadoutInputSeries } from './readout';
import { grouped } from './series';
import { indexedRuns } from './indexed-runs';
import { daysInWindow, type TimeWindow } from './viewport';

/** The cells this chart reads, and only those.
 *
 * A slice of the day-metrics record rather than the whole of it, so the server
 * ships four numbers a day instead of a record that also carries the extraction
 * block a panel further down the page already publishes. */
export type RunYieldSource = Pick<
	DayMetrics,
	'date' | 'itemsPlanned' | 'itemsPublished' | 'itemsFailed'
>;

/** One day's three counts, and the share of its plan that reached a reader. */
export interface RunYieldDay {
	date: string;
	planned: number;
	published: number;
	failed: number;
	/** published/planned, or null where planned === 0.
	 *
	 * Null rather than zero, and the caller breaks its line there. A day the
	 * pipeline never planned for has no yield to report, and a zero would say it
	 * planned work and published none of it - which is the one state on this
	 * chart an operator has to act on. */
	yield: number | null;
}

export interface RunYieldLoad {
	/** One entry per day of the window, oldest first, including days with no
	 * record at all. A window is a span the operator chose, so a day nothing
	 * recorded is drawn as the gap it is rather than closed up. */
	columns: RunYieldDay[];
	/** The largest of the three counts anywhere in the window. The count axis is
	 * drawn to this, so the three bars of one day share one scale. */
	peak: number;
	/** No day in the window planned anything. */
	empty: boolean;
}

/** The share axis, nought to one, fixed and staying fixed.
 *
 * Here rather than in the component because it is the one part of this chart
 * that must not follow the data: a share is already on a known scale, and an
 * axis that rescaled to the window would draw a bad month and a good month at
 * the same height. */
export const YIELD_AXIS_TICKS: readonly number[] = [0, 0.25, 0.5, 0.75, 1];

/** Where a share sits on that axis, as a fraction of its height.
 *
 * A day that published more than it planned draws at the ceiling - a later run
 * republishes a story an earlier day planned, so the ratio really does pass
 * one. Only the drawing is held there. `RunYieldDay.yield` keeps the figure it
 * measured, because a clamped number is a wrong one. */
export function placeOnYieldAxis(rate: number): number {
	return Math.min(1, rate);
}

export function runYield(days: readonly RunYieldSource[], window: TimeWindow): RunYieldLoad {
	const byDate = new Map(days.map((day) => [day.date, day]));
	const columns = daysInWindow(window).map((date) => {
		const day = byDate.get(date);
		const planned = day?.itemsPlanned ?? 0;
		const published = day?.itemsPublished ?? 0;
		const failed = day?.itemsFailed ?? 0;
		return {
			date,
			planned,
			published,
			failed,
			yield: planned > 0 ? published / planned : null
		};
	});
	return {
		columns,
		peak: columns.reduce(
			(most, column) => Math.max(most, column.planned, column.published, column.failed),
			0
		),
		empty: columns.every((column) => column.planned === 0)
	};
}

/** Which columns the pipeline planned anything on - the chart's coverage input.
 *
 * Here rather than in the component so that the rule a gap depends on is proven
 * against a fixture. A column standing at zero and a column no run ever touched
 * answer alike, which is the point: neither is a yield, and the span over both
 * is tinted rather than drawn as a day that published nothing. */
export function plannedDays(columns: readonly RunYieldDay[]): boolean[] {
	return columns.map((column) => column.planned > 0);
}

/** The runs of adjacent columns that have a share to draw, as column indices.
 *
 * This is where the line breaks. In the component it would be pixel strings and
 * nothing could check it: an edit that dropped the null columns instead of
 * splitting on them would draw one straight line across a day the pipeline never
 * ran, and every arithmetic case would stay green because no number would have
 * moved.
 *
 * A run of one column is dropped. The component draws a dot at every column that
 * has a share, so a lone point is already on the page, and a one-point polyline
 * draws nothing at all. */
export function yieldRuns(columns: readonly RunYieldDay[]): number[][] {
	return indexedRuns(columns, (column) => column.yield !== null)
		.filter((run) => run.length > 1);
}

/** The three counts, what each is called, and the fill it is drawn in.
 *
 * None of them is `--chart-axis`. The donut this replaced painted its larger
 * slice with the axis token, which an arc gap held apart from its neighbour.
 * Three bars two pixels apart have no such gap, and the chart draws its own
 * three axis rules in that colour - so the quantity everything else is measured
 * against would have been painted as the frame it sits in. */
export const YIELD_SERIES = [
	{ key: 'planned', label: 'Planned', token: '--chart-1' },
	{ key: 'published', label: 'Published', token: '--chart-2' },
	{ key: 'failed', label: 'Failed', token: '--chart-8' }
] as const;

export type YieldKey = (typeof YIELD_SERIES)[number]['key'];

/** The share line's own colour, so it reads as the one mark on the other axis. */
export const YIELD_LINE_TOKEN = '--chart-marker';

/** One of a day's three counts, by name. */
export function yieldCount(column: RunYieldDay, key: YieldKey): number {
	return key === 'planned' ? column.planned : key === 'published' ? column.published : column.failed;
}

/** Whole percent, and `<1%` where a real measurement rounds away. A `0%` there
 * would say the day published nothing. */
export function yieldPercent(rate: number | null): string {
	if (rate === null) return '-';
	const pct = rate * 100;
	if (pct > 0 && pct < 1) return '<1%';
	return `${Math.round(pct)}%`;
}

/** Every day's three counts and its share, as the readout under the chart
 * prints them.
 *
 * Each series carries the colour its mark is drawn in, so the readout is the
 * chart's key as well and the plot needs no legend of its own. A day that
 * planned nothing reads null in all four: it has no share to print, and a row of
 * zeros beside it would read as a day that planned and lost it all. */
export function yieldSeries(columns: readonly RunYieldDay[]): ReadoutInputSeries[] {
	const planned = (column: RunYieldDay) => column.planned > 0;
	return [
		...YIELD_SERIES.map((entry) => ({
			label: entry.label,
			swatch: `var(${entry.token})`,
			values: columns.map((column) => (planned(column) ? yieldCount(column, entry.key) : null)),
			format: (value: number) => grouped(value)
		})),
		{
			label: 'Share published',
			swatch: `var(${YIELD_LINE_TOKEN})`,
			values: columns.map((column) => (planned(column) ? column.yield : null)),
			format: (rate: number) => yieldPercent(rate)
		}
	];
}
