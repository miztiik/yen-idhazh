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
	const { zero = true, tickCount = 4 } = options;
	const finite = values.filter((value) => Number.isFinite(value));
	const [low, high] = extent(finite);
	let lower = low ?? 0;
	let upper = high ?? 1;
	if (zero) {
		lower = Math.min(0, lower);
		upper = Math.max(0, upper);
	}
	if (lower === upper) upper = lower + 1;
	const scale = scaleLinear().domain([lower, upper]).nice(tickCount).range([...range]);
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
