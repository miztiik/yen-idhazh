/** The one coordinate frame every console chart draws through.
 *
 * Each chart used to pick its own `viewBox` width and its own domain. A
 * `viewBox` is a scale factor, not a unit, so `font-size="10"` rendered as
 * 4.5px in the three-up failure panel and 16.6px in the chart beneath it -
 * measured 2026-08-25 at a 1057px window. Type set in one place cannot come out
 * four sizes on one page.
 *
 * The rule this module enforces: a chart draws in CSS pixels at the width it
 * actually occupies, so one unit is one pixel everywhere. The server draws at
 * `console.chart_width`, which is why a prerendered chart has a real width
 * before any script runs; the client redraws once it has measured the element.
 *
 * `d3-scale` computes the mapping and `d3-array` computes the extent. Neither
 * draws anything - the marks, the SVG and the prerendering stay ours. `.nice()`
 * and `ticks()` are the part a hand-rolled axis gets wrong.
 */

import { extent } from 'd3-array';
import { scaleLinear, scaleLog } from 'd3-scale';

import { dayMonth, shortDate } from '../format';

export interface Margin {
	top: number;
	right: number;
	bottom: number;
	left: number;
}

/** Room for one row of tick labels below and one column beside. */
export const MARGIN: Margin = { top: 8, right: 8, bottom: 22, left: 34 };

/** The drawing box, in CSS pixels, with the plot edges already worked out. */
export interface Frame {
	width: number;
	height: number;
	margin: Margin;
	left: number;
	right: number;
	top: number;
	bottom: number;
	innerWidth: number;
	innerHeight: number;
}

export function frame(width: number, height: number, margin: Margin = MARGIN): Frame {
	const left = margin.left;
	const top = margin.top;
	// A frame narrower than its own margins would flip the plot inside out.
	const right = Math.max(left, width - margin.right);
	const bottom = Math.max(top, height - margin.bottom);
	return {
		width,
		height,
		margin,
		left,
		right,
		top,
		bottom,
		innerWidth: right - left,
		innerHeight: bottom - top
	};
}

/** A mapping from data to pixels, plus the tick values that label it. */
export interface Axis {
	domain: [number, number];
	scale: (value: number) => number;
	ticks: number[];
}

export interface LinearAxisOptions {
	/** Anchor the domain at zero. A bar chart that does not is a lie. */
	zero?: boolean;
	tickCount?: number;
	/** Round the domain outward to whole tick steps. Turn it off where the
	 * domain is already decided by something else - rounding it there moves
	 * every mark on the chart to buy a label nobody asked to change. */
	nice?: boolean;
}

/** Domain rule one: rounded to human numbers, and zero-anchored by default.
 *
 * An empty series still returns a usable axis. A chart with no rows draws its
 * frame and says so in type; it never divides by nothing.
 */
export function linearAxis(
	values: readonly number[],
	range: readonly [number, number],
	options: LinearAxisOptions = {}
): Axis {
	const { zero = true, tickCount = 4, nice = true } = options;
	const finite = values.filter((value) => Number.isFinite(value));
	const [low, high] = extent(finite);
	let lower = low ?? 0;
	let upper = high ?? 1;
	if (zero) {
		lower = Math.min(0, lower);
		upper = Math.max(0, upper);
	}
	if (lower === upper) upper = lower + 1;
	const scale = scaleLinear().domain([lower, upper]).range([...range]);
	if (nice) scale.nice(tickCount);
	return {
		domain: scale.domain() as [number, number],
		scale: (value: number) => scale(value),
		ticks: scale.ticks(tickCount)
	};
}

/** Domain rule two: snapped to whole decades, and labelled at each one.
 *
 * Source words run from a release note to a long read, so the axis is a log
 * one. Decades are the only tick a reader can place without counting: a domain
 * that starts at 37 and ends at 8412 has no landmark on it.
 *
 * Zero and negative values cannot sit on a log axis and are dropped from the
 * domain rather than clamped, because a clamped zero draws a point that is not
 * where the data is.
 */
export function logAxis(values: readonly number[], range: readonly [number, number]): Axis {
	const positive = values.filter((value) => Number.isFinite(value) && value > 0);
	const [low, high] = extent(positive);
	const lower = 10 ** Math.floor(Math.log10(low ?? 1));
	const upper = 10 ** Math.ceil(Math.log10(Math.max(high ?? 10, (low ?? 1) * 10)));
	const scale = scaleLog().domain([lower, upper]).range([...range]);
	const decades: number[] = [];
	for (let power = Math.log10(lower); power <= Math.log10(upper) + 0.5; power += 1) {
		decades.push(10 ** Math.round(power));
	}
	return {
		domain: [lower, upper],
		scale: (value: number) => scale(Math.max(lower, value)),
		ticks: decades
	};
}

/** The width to draw at: the measured one, or the knob until there is one. */
export function chartWidth(measured: number | null, fallback: number): number {
	return measured !== null && measured > 0 ? Math.round(measured) : fallback;
}

/** One column of a day axis that carries a date. */
export interface DayTick {
	/** 0-based column, counted along the dates the chart drew. */
	index: number;
	date: string;
	text: string;
	anchor: 'start' | 'middle' | 'end';
}

/** Which columns of a day axis carry a date, and what each one says.
 *
 * `density` is `chart.tick_density`: the most labels the axis may carry. Fewer
 * days than that and every day is labelled; more, and the labels spread evenly
 * with the first and last day always among them.
 *
 * The rule this replaces labelled the two endpoints and nothing between them,
 * so a spike in the middle of a month could not be attributed to a date without
 * counting columns with a finger. Six labels over thirty days puts every mark
 * within three columns of a date.
 */
export function dayTicks(dates: readonly string[], density: number): DayTick[] {
	const days = dates.length;
	if (days === 0) return [];
	const wanted = Math.max(1, Math.min(days, Math.floor(density)));
	if (wanted === 1) {
		return [{ index: 0, date: dates[0], text: shortDate(dates[0]), anchor: 'middle' }];
	}
	const ticks: DayTick[] = [];
	// The year is printed once and then only where it changes, so a month of
	// columns does not carry four digits that never move.
	let carried = '';
	for (let n = 0; n < wanted; n += 1) {
		const index = Math.round((n * (days - 1)) / (wanted - 1));
		const date = dates[index];
		ticks.push({
			index,
			date,
			text: date.slice(0, 4) === carried ? dayMonth(date) : shortDate(date),
			anchor: n === 0 ? 'start' : n === wanted - 1 ? 'end' : 'middle'
		});
		carried = date.slice(0, 4);
	}
	return ticks;
}

/** Where a day's column sits, in the chart's own pixels.
 *
 * `pad` is the room a mark needs on each side so the oldest and the newest day
 * sit inside the plot rather than straddling its edge - a candle needs half its
 * own width, a dot needs its radius, a bare polyline needs none. One column is
 * drawn at the centre, because a single day at the left edge reads as the start
 * of a series that is not there.
 */
export function dayColumnX(index: number, columns: number, box: Frame, pad = 0): number {
	const left = box.left + pad;
	const right = Math.max(left, box.right - pad);
	if (columns <= 1) return (left + right) / 2;
	return left + (index * (right - left)) / (columns - 1);
}

/** How wide the readout strip under a plot may be, as an inline style.
 *
 * The strip sits below the plot, so it cannot cover a mark whatever its width.
 * The cap is what stops it becoming a paragraph: a reader glancing at a chart
 * reads a short column of values, not a block of prose. `share` is
 * `chart.readout_max_share`, and it is a share of the plot rather than a pixel
 * count so the cap holds at every window width.
 */
export function readoutCapStyle(share: number): string {
	const capped = Math.min(1, Math.max(0, share));
	return `max-width: ${(capped * 100).toFixed(2)}%`;
}

/** Report an element's own width, now and whenever it changes.
 *
 * A Svelte action, so a chart writes `use:observeWidth={...}` and never reads
 * the DOM itself. It runs only in a browser; the prerendered chart is already
 * complete without it.
 */
export function observeWidth(
	node: HTMLElement,
	onWidth: (width: number) => void
): { destroy: () => void } {
	const report = () => onWidth(node.getBoundingClientRect().width);
	const observer = new ResizeObserver(report);
	observer.observe(node);
	report();
	return { destroy: () => observer.disconnect() };
}

/** One mark a readout can land on: where it sits, and what it says. */
export interface ReadoutMark {
	/** The mark's x in the chart's own pixels. The hit rule is nearest by x. */
	x: number;
	/** The sentences to print, in order. The first is the label, the rest the
	 * numbers. A chart that already builds a sentence passes that sentence. */
	lines: string[];
}

/** One row of a readout strip: a series, what it read, and the line's colour. */
export interface ReadoutRow {
	label: string;
	value: string;
	/** The series colour, so the strip is also the legend and one fact is drawn
	 * once. Empty where the chart has no colour to lend. */
	colour: string;
}

/** One column of a day chart, as the strip under it prints it. */
export interface DayReadout {
	/** The column's x in the chart's own pixels. */
	x: number;
	/** The date, already written the way a reader reads it. */
	date: string;
	rows: ReadoutRow[];
}

/** The action's marks, built from the strip's own rows.
 *
 * The strip draws the rows and the action announces the sentences, so both come
 * from one array and cannot disagree about what a column said.
 */
export function readoutMarks(columns: readonly DayReadout[]): ReadoutMark[] {
	return columns.map((column) => ({
		x: column.x,
		lines: [column.date, ...column.rows.map((row) => `${row.label} ${row.value}`)]
	}));
}

export interface ReadoutOptions {
	marks: ReadoutMark[];
	/** The width the chart drew at, so a client x can be scaled into chart
	 * pixels even in the frame before the resize observer has reported. */
	width: number;
	/** Which mark is selected now, or null for none. */
	onSelect: (index: number | null) => void;
}

/** Report which mark the reader is pointing at, or has stepped to.
 *
 * A Svelte action, so a chart writes `use:pointerReadout={...}` and never reads
 * the DOM itself. One `pointermove` and `pointerdown` stream covers mouse, pen
 * and touch, which an SVG `<title>` never did: a `<title>` needs a hover, so on
 * a phone the numbers in it did not exist. The `<title>` stays as the mark's
 * accessible name, and nothing this action reports is needed to read the chart.
 *
 * The `<svg>` itself takes the focus, not its marks. A tab stop per point is a
 * trap on a plot that draws two and a half thousand of them.
 */
export function pointerReadout(
	node: SVGSVGElement,
	options: ReadoutOptions
): { update: (next: ReadoutOptions) => void; destroy: () => void } {
	let current = options;
	let at: number | null = null;

	const select = (next: number | null) => {
		if (next === at) return;
		at = next;
		current.onSelect(next);
	};

	/** Nearest mark by x, never by straight-line distance. Two articles of the
	 * same length sit on top of each other, and a reader pointing at a column
	 * means the column rather than whichever of them is nearer the pointer. */
	const nearest = (clientX: number): number | null => {
		if (current.marks.length === 0) return null;
		const rect = node.getBoundingClientRect();
		if (rect.width === 0) return null;
		const x = ((clientX - rect.left) * current.width) / rect.width;
		let best = 0;
		let gap = Number.POSITIVE_INFINITY;
		current.marks.forEach((mark, index) => {
			const distance = Math.abs(mark.x - x);
			if (distance < gap) {
				gap = distance;
				best = index;
			}
		});
		return best;
	};

	const track = (event: PointerEvent) => select(nearest(event.clientX));

	/** A touch ends the moment the thumb lifts, and a lift raises this event.
	 * Clearing there would blank the readout before it could be read, so only a
	 * mouse leaving the plot clears it. */
	const leave = (event: PointerEvent) => {
		if (event.pointerType === 'mouse') select(null);
	};

	const enter = () => {
		if (at === null && current.marks.length > 0) select(0);
	};

	const away = () => select(null);

	const step = (event: KeyboardEvent) => {
		const last = current.marks.length - 1;
		if (last < 0) return;
		const from = at ?? 0;
		if (event.key === 'ArrowLeft') select(Math.max(0, from - 1));
		else if (event.key === 'ArrowRight') select(Math.min(last, from + 1));
		else if (event.key === 'Home') select(0);
		else if (event.key === 'End') select(last);
		else if (event.key === 'Escape') select(null);
		else return;
		event.preventDefault();
		// The chart consumed the key. The compression scatter sits inside the
		// viewport control, which pans on the same two arrows - left unstopped,
		// one step through the marks also moved the window under them and left
		// the readout pointing at a mark that had gone.
		event.stopPropagation();
	};

	node.addEventListener('pointermove', track);
	node.addEventListener('pointerdown', track);
	node.addEventListener('pointerleave', leave);
	node.addEventListener('focusin', enter);
	node.addEventListener('focusout', away);
	node.addEventListener('keydown', step);

	return {
		update(next: ReadoutOptions) {
			current = next;
			// The window moved, so the mark this index named may be gone. Holding
			// the index would print one article's numbers under another's mark.
			if (at !== null && at > next.marks.length - 1) select(null);
		},
		destroy() {
			node.removeEventListener('pointermove', track);
			node.removeEventListener('pointerdown', track);
			node.removeEventListener('pointerleave', leave);
			node.removeEventListener('focusin', enter);
			node.removeEventListener('focusout', away);
			node.removeEventListener('keydown', step);
		}
	};
}

