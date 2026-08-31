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

/** Which way a tick label must be anchored to stay inside its own plot.
 *
 * The end labels of an axis sit ON the plot edges, so a centred one hangs half
 * its own width past the frame and an `svg` clips what hangs. Measured
 * 2026-08-31 at 1440 on the built console: `What the cap cost, by source` drew
 * `10,000` 3.2px outside its own `svg`, which is why the last two characters
 * were missing.
 */
export type TickAnchor = 'start' | 'middle' | 'end';

export function tickAnchor(at: number, count: number): TickAnchor {
	if (count <= 1) return 'middle';
	if (at === 0) return 'start';
	if (at === count - 1) return 'end';
	return 'middle';
}

/** The size every console axis sets a tick label at. */
export const AXIS_LABEL_PX = 10;

/** Clear pixels between two neighbouring labels. Two dates that touch read as
 * one longer string, so the rule needs room between them and not merely no
 * overlap. */
export const AXIS_LABEL_GAP_PX = 8;

/** How wide one character of a tick label is, as a share of the font size.
 *
 * Measured 2026-08-31 through `getComputedTextLength` in Chromium on the built
 * console at 1440x900, on the page's own font at `font-size="10"`:
 * `20 Aug 2026` is 55.83px over 11 characters, `18 Aug` is 31.53px over 6, and
 * `10,000` is 29.13px over 6. The widest of those averages 5.26px a character,
 * which is 0.526 of the size; this is ten percent over it on purpose. An
 * estimate under the truth lets two labels touch, which is the defect the rule
 * exists to stop, while an estimate over it only ever drops one label an axis
 * could have carried.
 */
export const LABEL_ADVANCE_EM = 0.58;

/** How wide a label will be, before anything has drawn it.
 *
 * The axis is decided on the server, where there is no text engine to ask, and
 * on the client one frame before the browser has laid a label out. So the width
 * is computed from the string rather than measured off the element.
 */
export function labelWidth(text: string, fontSize: number = AXIS_LABEL_PX): number {
	return text.length * fontSize * LABEL_ADVANCE_EM;
}

/** Where a label anchored this way starts and ends, around its own x. */
function labelExtent(
	x: number,
	text: string,
	anchor: TickAnchor,
	fontSize: number
): [number, number] {
	const wide = labelWidth(text, fontSize);
	if (anchor === 'start') return [x, x + wide];
	if (anchor === 'end') return [x - wide, x];
	return [x - wide / 2, x + wide / 2];
}

/** Whether this set of labels can be drawn with room between every neighbour. */
function fits(
	take: readonly number[],
	xs: readonly number[],
	texts: readonly string[],
	anchorOf: (at: number) => TickAnchor,
	fontSize: number,
	gap: number
): boolean {
	let previous = Number.NEGATIVE_INFINITY;
	for (const at of take) {
		const [from, to] = labelExtent(xs[at], texts[at], anchorOf(at), fontSize);
		if (from < previous + gap) return false;
		previous = to;
	}
	return true;
}

/** One column of a day axis. It carries a tick mark, and it may carry a date. */
export interface DayTick {
	/** 0-based column, counted along the dates the chart drew. */
	index: number;
	date: string;
	/** What the label says, or '' where the fit dropped it. The tick mark is
	 * drawn either way: a reader counting columns needs the grid even where the
	 * date is gone. */
	text: string;
	anchor: TickAnchor;
}

export interface DayAxisOptions {
	/** `chart.tick_density` - the MOST labels the axis may carry. A ceiling and
	 * never a target: the measured fit below only ever takes more away. */
	density: number;
	/** Where each day sits, in the chart's own pixels, one entry per date.
	 * `dayColumns` builds it where the days are evenly spaced; a chart whose
	 * columns are not evenly spaced passes its own. */
	columns: readonly number[];
	fontSize?: number;
	gap?: number;
}

/** Which columns of a day axis carry a date, and what each one says.
 *
 * Two rules, in this order. `density` picks the columns that carry a tick mark,
 * evenly spread with the first and last day always among them. Then the labels
 * are measured against the room the plot actually has, and dropped in whole
 * steps until no two of them touch - a count alone cannot hold at 1440 and at
 * 390, and measured 2026-08-31 it did not: six labels over 30 days overlapped
 * by 13.6px on a phone.
 *
 * The rule this replaces labelled the two endpoints and nothing between them,
 * so a spike in the middle of a month could not be attributed to a date without
 * counting columns with a finger.
 */
export function dayTicks(dates: readonly string[], options: DayAxisOptions): DayTick[] {
	const days = dates.length;
	if (days === 0) return [];
	const { density, columns, fontSize = AXIS_LABEL_PX, gap = AXIS_LABEL_GAP_PX } = options;
	const ceiling = Math.max(1, Math.min(days, Math.floor(density)));
	if (ceiling === 1) {
		return [{ index: 0, date: dates[0], text: shortDate(dates[0]), anchor: 'middle' }];
	}

	// Every column the ceiling allows. These carry a tick mark whichever labels
	// survive, so the grid does not change shape as the window does.
	const marks = Array.from({ length: ceiling }, (_, n) =>
		Math.round((n * (days - 1)) / (ceiling - 1))
	);
	// Anchoring is about where a label sits on the plot, not about its rank among
	// the survivors: the first candidate is on the left edge whether or not the
	// one after it was dropped.
	const anchorOf = (at: number) => tickAnchor(at, ceiling);
	const xs = marks.map((index) => columns[index] ?? 0);
	// The longest form of every label, so the fit is decided before the year rule
	// shortens any of them. A shorter label can only ever help.
	const widest = marks.map((index) => shortDate(dates[index]));

	let kept: number[] = [];
	for (let count = ceiling; count >= 2; count -= 1) {
		const take = Array.from({ length: count }, (_, n) =>
			Math.round((n * (ceiling - 1)) / (count - 1))
		);
		if (fits(take, xs, widest, anchorOf, fontSize, gap)) {
			kept = take;
			break;
		}
	}
	// Not even the two ends fit. The newest day is the one an operator reads
	// first, so it is the one that survives.
	if (kept.length === 0) kept = [ceiling - 1];

	const labelled = new Set(kept);
	// The year is printed once and then only where it changes, so a month of
	// columns does not carry four digits that never move. Carried over the
	// labels that survived, never over the ones that were only offered.
	let carried = '';
	return marks.map((index, at) => {
		const date = dates[index];
		if (!labelled.has(at)) return { index, date, text: '', anchor: anchorOf(at) };
		const text = date.slice(0, 4) === carried ? dayMonth(date) : shortDate(date);
		carried = date.slice(0, 4);
		return { index, date, text, anchor: anchorOf(at) };
	});
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

/** Every day column's x, for an axis whose days are evenly spaced.
 *
 * The labels and the marks come out of one function, so they cannot disagree
 * about where a column is.
 */
export function dayColumns(columns: number, box: Frame, pad = 0): number[] {
	return Array.from({ length: columns }, (_, index) => dayColumnX(index, columns, box, pad));
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

/** Every chart on the console says whether it has a column to hover, in markup.
 *
 * A chart that shares a column between its marks carries `data-readout-columns`
 * on the element holding both the plot and the strip, and the strip is the only
 * key it draws. A chart with no shared column - a ranked list, one target bar,
 * a flow, a share of one total - carries `data-readout-none` with the reason in
 * words instead.
 *
 * The second attribute is the point of the pair. "This chart has no hover" is a
 * decision somebody took, and an undeclared chart is indistinguishable from one
 * where the readout was forgotten. `console-readout.spec.ts` enumerates every
 * chart on the three routes and fails on any that declares neither.
 */

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

/** One series of a strip: what it is, what colour it is drawn in, what it read.
 *
 * `value` is asked per column rather than handed as an array, so a strip cannot
 * be built from a list that is a different length from the labels. */
export interface StripSeries {
	label: string;
	/** The colour the chart draws this series in, so the strip is the key. */
	colour: string;
	value: (index: number) => string;
}

/** A strip for an engine-drawn chart, from its category labels and its series.
 *
 * `x` is left at zero: an engine keeps its plot insets in pixels and the
 * element is fluid, so `Chart.svelte` recomputes every column's share of the
 * measured width through `bandShares`. A pixel written here would be the pixel
 * the server drew at and wrong at every other width.
 */
export function columnStrip(
	labels: readonly string[],
	series: readonly StripSeries[]
): DayReadout[] {
	return labels.map((date, index) => ({
		x: 0,
		date,
		rows: series.map((one) => ({
			label: one.label,
			value: one.value(index),
			colour: one.colour
		}))
	}));
}

/** The plot insets an engine-drawn chart leaves around its categories. */
export interface PlotGrid {
	left: number;
	right: number;
}

/** Where each category column sits, as a share of the whole element.
 *
 * A hand-written chart knows its own pixels, so its readout marks carry them.
 * An engine-drawn one does not: the engine keeps its grid insets in pixels and
 * the element is fluid, so the same column sits at a different share at every
 * width. Recomputing the shares from the measured width is what keeps the
 * column a pointer lands on and the column the strip prints the same one.
 *
 * A share rather than a pixel because `pointerReadout` scales a client x by the
 * width it was given: hand it 1 and every mark is already a share.
 */
export function bandShares(count: number, width: number, grid: PlotGrid): number[] {
	if (count <= 0 || width <= 0) return [];
	const inner = Math.max(1, width - grid.left - grid.right);
	return Array.from(
		{ length: count },
		(_, index) => (grid.left + ((index + 0.5) * inner) / count) / width
	);
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
 * trap on a plot that draws two and a half thousand of them. An engine-drawn
 * chart hands its wrapping element instead: the engine owns everything inside
 * it and swaps the prerendered SVG out on hydration, so an action bound to the
 * SVG would come away with the markup it was attached to.
 */
export function pointerReadout(
	node: SVGSVGElement | HTMLElement,
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

	// One list, attached and removed from the same entries, so the two halves
	// cannot drift. The node is an `<svg>` on a hand-written chart and a `<div>`
	// on an engine-drawn one; a union of two element types has two incompatible
	// `addEventListener` overload sets, so the listeners go on the base
	// interface both of them implement.
	const events: EventTarget = node;
	const bound: [string, EventListener][] = [
		['pointermove', track as EventListener],
		['pointerdown', track as EventListener],
		['pointerleave', leave as EventListener],
		['focusin', enter],
		['focusout', away],
		['keydown', step as EventListener]
	];
	for (const [type, handler] of bound) events.addEventListener(type, handler);

	return {
		update(next: ReadoutOptions) {
			current = next;
			// The window moved, so the mark this index named may be gone. Holding
			// the index would print one article's numbers under another's mark.
			if (at !== null && at > next.marks.length - 1) select(null);
		},
		destroy() {
			for (const [type, handler] of bound) events.removeEventListener(type, handler);
		}
	};
}
