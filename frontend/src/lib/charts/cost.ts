/** What the counterfactual cost looks like over a window, in both its shapes.
 *
 * The figure itself is a counterfactual and never a bill - nothing bills us,
 * because Actions minutes are free on a public repository, and CLAUDE.md
 * Guardrail #10 carries the owner's carve-out for this one surface on the
 * condition that the rate, its source and the word for what it is stay beside
 * the number. Giving it a shape does not soften that: the word rides the value
 * axis and the readout strip, so it is attached to the drawing rather than to
 * a sentence somewhere near it.
 *
 * **One call returns both shapes.** The per-day bars and the running line are
 * two readings of one array, built here once. Two builders would be two
 * derivations of one quantity, and a reader who found them disagreeing would
 * have nothing on screen saying which to believe - which is the reason the
 * no-re-shaping rule exists, kept while its letter widened.
 */

import type { EChartsOption } from 'echarts';
import { dayMonth, shortDate } from '$lib/format';
import { columnStrip, type DayReadout } from './frame';
import { costOf, money, valueGutter, type CostRate, type RunWork } from './machine';
import { paint, type ChartToken } from './theme';

/** Day by day, or every day so far added up. */
export type CostShape = 'daily' | 'running';

/** Which shape the panel opens on, read by the server that draws the first
 * paint and by the browser that redraws it, so the two can never disagree.
 *
 * Day by day, because it is the shape that answers a question the four numbers
 * above it do not already answer. A running total ends at the window total,
 * which is printed; the daily bars are the only place a day that cost four
 * times its neighbour is visible at all.
 */
export const DEFAULT_COST_SHAPE: CostShape = 'daily';

/** The two states the switch offers, named where the shapes are built.
 *
 * `Running total` rather than `Cumulative`: the panel is read by an operator in
 * a hurry, and a term from a statistics class is not a term for a user. */
export const COST_SHAPES: { value: CostShape; text: string }[] = [
	{ value: 'daily', text: 'Day by day' },
	{ value: 'running', text: 'Running total' }
];

/** Reading, at the bottom of the stack. The same colour the read-against-written
 * panel gives it, so one quantity keeps one colour down the route. */
const READ_TOKEN: ChartToken = '--chart-1';
/** Writing, at the top. Read at the bottom and write at the top, everywhere. */
const WRITTEN_TOKEN: ChartToken = '--chart-4';
/** The running total, which is neither of them added up but both. */
const RUNNING_TOKEN: ChartToken = '--chart-2';

/** Under this, a band is not a band. A browser paints nothing there, and a key
 * pointing at nothing teaches a reader the category is zero. */
const THINNEST_BAND_PX = 1;

/** The room the plot itself gets out of a chart's height, in pixels.
 *
 * The two insets below are the ones the option sets, so the band measurement
 * and the drawing are working from one number rather than two.
 */
const PLOT_TOP = 30;
const PLOT_BOTTOM = 26;

export interface CostDay {
	date: string;
	/** What reading this day's prompts would have cost at the rate handed in. */
	read: number;
	/** What writing this day's answers would have cost. */
	written: number;
	total: number;
	/** This day and every day before it in the window. The line's points. */
	running: number;
	/** Items that reported both token counts. The denominator, printed. */
	items: number;
}

export interface CostShapes {
	/** Oldest first. One column of the bars, one point of the line. */
	days: CostDay[];
	/** The last point of the line, which is what the whole window cost. */
	runningTotal: number;
	/** The smallest band drawn, as a share of the tallest day. Null where no day
	 * draws a split at all. Measured rather than assumed, and printed. */
	thinnestShare: number | null;
	/** True where that band falls under a pixel, so the bar draws whole and the
	 * split becomes a printed figure instead. */
	splitTooThin: boolean;
}

/** Both shapes of the counterfactual cost, from one pass over the runs.
 *
 * A run belongs to its day, and a day that ran twice is one column: the panel
 * asks what a day cost, and two runs on one date are one day's work.
 *
 * The rate is an argument because the operator owns it after mount. Nothing is
 * cached against it - a typed rate is a multiplication away, and a cache keyed
 * on a number a person is typing is a second copy waiting to go stale.
 */
export function costOverDays(
	runs: readonly RunWork[],
	rate: CostRate,
	options: { heightPx: number }
): CostShapes {
	const byDate = new Map<string, { input: number; output: number; items: number }>();
	for (const run of runs) {
		const date = run.date;
		if (date === '') continue;
		const bucket = byDate.get(date) ?? { input: 0, output: 0, items: 0 };
		bucket.input += run.input;
		bucket.output += run.output;
		bucket.items += run.items;
		byDate.set(date, bucket);
	}

	let running = 0;
	const days: CostDay[] = [...byDate.entries()]
		.sort(([left], [right]) => left.localeCompare(right))
		.map(([date, bucket]) => {
			const read = costOf({ input: bucket.input, output: 0 }, rate);
			const written = costOf({ input: 0, output: bucket.output }, rate);
			const total = read + written;
			running += total;
			return { date, read, written, total, running, items: bucket.items };
		});

	// Measured against the tallest column, because that is what sets the value
	// axis and so what a band's height is a share of.
	const tallest = Math.max(0, ...days.map((day) => day.total));
	const bands = days.flatMap((day) => [day.read, day.written]).filter((band) => band > 0);
	const thinnestShare =
		tallest === 0 || bands.length === 0 ? null : Math.min(...bands) / tallest;
	const plotHeight = Math.max(1, options.heightPx - PLOT_TOP - PLOT_BOTTOM);
	return {
		days,
		runningTotal: days.at(-1)?.running ?? 0,
		thinnestShare,
		splitTooThin: thinnestShare !== null && thinnestShare * plotHeight < THINNEST_BAND_PX
	};
}

/** The bands a column is built from, in drawing order, or the one whole bar.
 *
 * Read at the bottom, write at the top - the order is the same on every stacked
 * chart on this console, because a stack whose order moves between panels
 * cannot be compared between them.
 */
function bands(
	shapes: CostShapes
): { label: string; token: ChartToken; value: (day: CostDay) => number }[] {
	if (shapes.splitTooThin) {
		return [{ label: 'Counterfactual, that day', token: READ_TOKEN, value: (day) => day.total }];
	}
	return [
		{ label: 'Reading the prompts', token: READ_TOKEN, value: (day) => day.read },
		{ label: 'Writing the answers', token: WRITTEN_TOKEN, value: (day) => day.written }
	];
}

/** One column a day, or one line over the same days: what it would have cost.
 *
 * **The axis names the counterfactual, not the money.** `Counterfactual cost,
 * USD` rather than `USD`: a currency code alone on an axis is the shape a bill
 * takes, and the one place a reader cannot miss is the label they read before
 * any of the numbers.
 *
 * **One adaptive domain, niced by the engine.** There is no ceiling here for a
 * fixed domain to be measured against - nothing bills us, so there is no budget
 * to draw a line at - and a fixed axis over adaptive data wastes the plot.
 *
 * **A time axis, because both shapes are about time.** The bars say which day
 * cost what and the line says whether the total is still climbing; a ranked list
 * would answer neither.
 */
export function costChart(
	shapes: CostShapes,
	shape: CostShape,
	currency: string
): { option: EChartsOption; empty: boolean; grid: { left: number; right: number } } {
	const highest =
		shape === 'running'
			? (shapes.runningTotal ?? 0)
			: Math.max(0, ...shapes.days.map((day) => day.total));
	const grid = { left: valueGutter(highest), right: 12 };
	if (shapes.days.length === 0) return { option: {}, empty: true, grid };

	const axis = (title: string) => ({
		type: 'value' as const,
		name: title,
		nameTextStyle: { color: paint('--color-text-tertiary'), fontSize: 11 },
		axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11 },
		splitLine: { lineStyle: { color: paint('--chart-grid') } }
	});
	const series =
		shape === 'running'
			? [
					{
						name: 'Counterfactual so far',
						type: 'line' as const,
						symbolSize: 5,
						lineStyle: { width: 1.5, color: paint(RUNNING_TOKEN) },
						itemStyle: { color: paint(RUNNING_TOKEN) },
						data: shapes.days.map((day) => day.running)
					}
				]
			: bands(shapes).map((band) => ({
					name: band.label,
					type: 'bar' as const,
					stack: 'cost',
					barMaxWidth: 24,
					itemStyle: { color: paint(band.token) },
					data: shapes.days.map(band.value)
				}));

	return {
		empty: false,
		grid,
		option: {
			animation: false,
			grid: { ...grid, top: PLOT_TOP, bottom: PLOT_BOTTOM, containLabel: false },
			tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
			xAxis: {
				type: 'category',
				data: shapes.days.map((day) => dayMonth(day.date)),
				axisLine: { lineStyle: { color: paint('--chart-axis') } },
				axisTick: { show: false },
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 10, hideOverlap: true }
			},
			yAxis: axis(
				shape === 'running'
					? `Counterfactual cost so far, ${currency}`
					: `Counterfactual cost, ${currency}`
			),
			series
		}
	};
}

/** Every figure the tooltip carries, printed under the plot as well.
 *
 * The dominant reading device has no hover, so a fact that lives only in a
 * tooltip is a fact half the readers never get. The strip is the key too, which
 * is why no chart carrying one draws a legend beside the plot.
 */
export function costColumns(
	shapes: CostShapes,
	shape: CostShape,
	currency: string
): DayReadout[] {
	const rows =
		shape === 'running'
			? [
					{
						label: 'Counterfactual so far',
						colour: `var(${RUNNING_TOKEN})`,
						value: (index: number) => money(shapes.days[index]?.running ?? 0, currency, 4)
					}
				]
			: bands(shapes).map((band) => ({
					label: band.label,
					colour: `var(${band.token})`,
					value: (index: number) => {
						const day = shapes.days[index];
						return day === undefined ? '-' : money(band.value(day), currency, 4);
					}
				}));
	return columnStrip(
		shapes.days.map((day) => shortDate(day.date)),
		rows
	);
}

/** What the chart is, for anybody who cannot see the marks.
 *
 * The word stays in the sentence. A shape described without it is a shape that
 * reads as a bill, and a reader using a screen reader gets the description
 * rather than the axis.
 */
export function costLabel(shape: CostShape, days: number): string {
	const drawn =
		shape === 'running'
			? 'added up day by day'
			: 'one column a day, reading at the bottom and writing on top';
	return `The counterfactual cost of these ${days} days, ${drawn}. What the work would have cost at a hosted provider's rate, never an amount owed.`;
}
