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

import { scaleLinear, scaleLog } from 'd3-scale';

import { countDays, nameSpan } from '../console/span-words';
import { dayMonth, shortDate } from '../format';
import type { ReadoutLine } from './readout';
import { grouped } from './series';

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

/** The least and greatest of the values a predicate keeps, in one pass.
 *
 * The rule this replaces filtered the values into a fresh array and handed that
 * to `d3.extent`, so an axis read its own numbers twice and built a throwaway
 * array between the reads. The bounds are the same and the second scan is gone.
 * `undefined` on a side nothing was kept, exactly as `extent` returns for an
 * empty input.
 */
function keptBounds(
	values: readonly number[],
	keep: (value: number) => boolean
): [number | undefined, number | undefined] {
	let low: number | undefined;
	let high: number | undefined;
	for (const value of values) {
		if (!keep(value)) continue;
		if (low === undefined || value < low) low = value;
		if (high === undefined || value > high) high = value;
	}
	return [low, high];
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
	const [low, high] = keptBounds(values, Number.isFinite);
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
	const [low, high] = keptBounds(values, (value) => Number.isFinite(value) && value > 0);
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

/** The most of a frame a column of row labels may take before the plot stops
 * being the chart.
 *
 * Measured 2026-09-01 at 390 on the built console: `What the cap cost, by
 * source` gave its source names a fixed 168px of a 324px frame, so the plot
 * itself got 144px - 44 percent - and the six tracks drew inside 91px of it. A
 * gutter wider than the plot is a list with a chart in the margin.
 */
export const MAX_GUTTER_SHARE = 0.3;

/** The room a column of labels needs, or null where the frame cannot spare it.
 *
 * Null is the caller's cue to put the labels somewhere else - above the mark
 * they name, usually - and never to clip them or to shrink the plot behind
 * them. A source id is the ledger's own spelling of a name and there is no
 * shorter true form of it.
 */
export function labelGutter(
	texts: readonly string[],
	fontSize: number,
	gap: number,
	width: number
): number | null {
	const widest = texts.reduce((most, text) => Math.max(most, labelWidth(text, fontSize)), 0);
	const room = Math.ceil(widest) + gap;
	return room > width * MAX_GUTTER_SHARE ? null : room;
}

/** A label on an axis: the string, and where its centre sits in the plot. */
export interface AxisLabel {
	x: number;
	text: string;
}

/** Which of an axis's labels can be drawn without two of them touching.
 *
 * A label is kept only where its left edge clears the last kept label's right
 * edge by `gap`. Two numbers that touch read as one longer number, which on a
 * doubling axis is a wrong reading and not merely an ugly one. The first and
 * the last are always kept - they are the two ends the whole axis is read
 * against - and a dropped label leaves its mark, so nothing about the data
 * goes with it.
 *
 * Measured 2026-09-01: eleven doubling edges from 0 to 1024 seconds, in the
 * 306px of plot a 390px phone leaves, need 388px of type. Drawn every edge,
 * seven pairs touch.
 */
export function thinLabels<T extends AxisLabel>(
	labels: readonly T[],
	fontSize: number = AXIS_LABEL_PX,
	gap: number = AXIS_LABEL_GAP_PX
): T[] {
	if (labels.length <= 2) return [...labels];
	const half = (text: string) => labelWidth(text, fontSize) / 2;
	const last = labels[labels.length - 1];
	const kept = [labels[0]];
	let right = labels[0].x + half(labels[0].text);
	const lastLeft = last.x - half(last.text);
	for (const label of labels.slice(1, -1)) {
		if (label.x - half(label.text) < right + gap) continue;
		// It also has to clear the end label, which is always drawn.
		if (label.x + half(label.text) + gap > lastLeft) continue;
		kept.push(label);
		right = label.x + half(label.text);
	}
	kept.push(last);
	return kept;
}

/** The least a chart row may be and still carry two lines of type with air
 * between one row and the next. `rowPitch` clamps to it and never below. */
export const ROW_PITCH_MIN = 40;
/** How tall one row of a horizontal chart is, in the frame it was given.
 *
 * `cellFor` in `run-history.ts` grows a run-strip cell the same way, and for
 * the same reason: a pitch that is right for a phone leaves a page-wide chart
 * as a stack of rules with air nowhere. Solve for the frame, then clamp - the
 * floor is the type the row carries and the ceiling is where rows stop reading
 * as one set.
 */
export function rowPitch(innerWidth: number, min: number, max: number): number {
	if (!Number.isFinite(innerWidth) || innerWidth <= 0) return min;
	return Math.max(min, Math.min(max, Math.round(innerWidth * ROW_PITCH_OF_WIDTH)));
}

/** How tall a row is against the plot it sits in. A track a fortieth of the
 * plot's width reads as a rule rather than as a length. */
const ROW_PITCH_OF_WIDTH = 1 / 24;


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
	bounds?: readonly [number, number];
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
	const xs = marks.map((index) => columns[index] ?? 0);
	// The longest form of every label, so the fit is decided before the year rule
	// shortens any of them. A shorter label can only ever help.
	const widest = marks.map((index) => shortDate(dates[index]));
	const [left, right] = options.bounds ?? [xs[0], xs[xs.length - 1]];
	const anchorOf = (at: number): TickAnchor => {
		const width = labelWidth(widest[at], fontSize);
		if (at === 0) {
			if (xs[at] - width >= left) return 'end';
			return xs[at] - width / 2 >= left ? 'middle' : 'start';
		}
		if (at === ceiling - 1) {
			if (xs[at] + width <= right) return 'start';
			return xs[at] + width / 2 <= right ? 'middle' : 'end';
		}
		return 'middle';
	};

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

/** Where a change to the summarizing pipeline falls on a day axis.
 *
 * `x` is in the chart's own pixels, on the leading edge of the day that
 * changed - between two columns rather than through either one's marks.
 * Everything left of it was written by the setup that had just been replaced,
 * which is the whole of what the mark is for. `ThroughputTrend` has drawn it
 * that way since 2026-08-30; this is that rule made shared.
 */
export interface ModelRule {
	date: string;
	x: number;
}

/** The rules a chart draws, for the changes that fall inside the days it drew.
 *
 * Not the days the window covers - a chart can draw fewer. The caller passes
 * the dates it actually put on the axis and the pixel of each, so the count of
 * rules is a fact about the drawing rather than about the control above it.
 *
 * A change on the first drawn day draws nothing, and that is not an omission.
 * The rule would sit on the value axis with no day to its left, so it would
 * separate nothing from nothing: the change is at the edge of the span rather
 * than inside it, and every day drawn ran the setup that came out of it.
 */
export function modelRules(
	changes: readonly string[],
	dates: readonly string[],
	columns: readonly number[]
): ModelRule[] {
	const changed = new Set(changes);
	const rules: ModelRule[] = [];
	for (let index = 1; index < dates.length; index += 1) {
		if (!changed.has(dates[index])) continue;
		const at = columns[index];
		const before = columns[index - 1];
		if (at === undefined || before === undefined) continue;
		rules.push({ date: dates[index], x: (at + before) / 2 });
	}
	return rules;
}

/** What the rule says on the plot itself, without being pointed at.
 *
 * Two words, at the top of the line, in every chart that draws one. A rule a
 * reader has to hover to identify is a rule most readers never identify: the
 * finding is that a comparison across this line is not like-for-like, and a
 * finding nobody can see has not been reported. The date is not repeated here
 * because the day axis underneath already carries it.
 */
export const MODEL_RULE_LABEL = 'setup changed';

/** What one rule says to anybody who points at it.
 *
 * One sentence in one place, so two charts cannot describe one event
 * differently. Where the run record named the fields that moved, they are named
 * here; where it did not, the sentence names the set the stamp covers rather
 * than saying "the model", because the stamp moves for a reworded prompt or a
 * rebuilt runtime as readily as for new weights and four of the five stamps in
 * the ledger cannot be expanded into their cause at all (measured 2026-08-27,
 * `docs/concepts/evaluation.md`). Naming one candidate cause would be a guess.
 *
 * `settings` arrives already in words - `$lib/console/settings-moved` owns the
 * translation from a contract field name, so no chart holds a second copy of it.
 */
export function modelRuleTitle(date: string, settings: string = ''): string {
	const what = settings === '' ? 'A new model, prompt or setting' : capitalise(settings);
	return `${what} started on ${shortDate(date)}. Everything left of this line was written by the one before it.`;
}

/** A sentence opener out of a phrase that begins "the ...". */
function capitalise(text: string): string {
	return text.charAt(0).toUpperCase() + text.slice(1);
}

/** The readout line a chart prints on a day the pipeline changed.
 *
 * No swatch, because it is an event and not a series - the strip draws a
 * swatch only where a mark on the plot is that colour.
 */
export const MODEL_RULE_ROW: ReadoutLine = {
	label: 'How summaries are written',
	value: 'changed on this day',
	swatch: null
};

/** The same row, naming what moved where the record named it.
 *
 * The label never changes, so a reader stepping the columns with an arrow key
 * meets one heading whatever the day holds, and every setting the day moved is
 * on one line - five hairlines on one date would be a smear, and five lines in
 * the strip would be the same smear written out.
 */
export function modelRuleRow(settings: string): ReadoutLine {
	if (settings === '') return MODEL_RULE_ROW;
	return { ...MODEL_RULE_ROW, value: `${settings} changed on this day` };
}

/** What a chart says where the days it drew hold no change.
 *
 * A named state and never a missing element: an absent rule and a rule nobody
 * remembered to draw look identical, and only one of them is an answer.
 */
export function noModelRuleNote(days: number): string {
	return `Nothing changed about how the summaries are written inside ${nameSpan(days)}.`;
}

/** What a dashed rule means, said once under a chart that draws one.
 *
 * The rule's own name says which day and what moved, and the strip says so on
 * that day; this says what the line divides, in the place a chart with no rule
 * says it drew none. A hairline is not a thing a reader can point at, so the
 * meaning cannot live only on the rule.
 */
export const MODEL_RULE_NOTE = `A dashed rule marked "${MODEL_RULE_LABEL}" is a day a new model, prompt or setting started, and everything left of it was written by the one before it.`;

/** Below this share of a window's days, a chart states the span nothing
 * measured instead of letting its marks pile against one edge.
 *
 * Half, because half is where the empty part becomes the larger part of the
 * picture. Measured 2026-09-01 at 1440 on the built console: `Time per item, by
 * stage` drew a 1,292px plot with every mark between x=1,030 and x=1,342 - 312px,
 * 24 percent of the plot, all on the right - because the window was 30 days and
 * 8 carried a timing. `Failure rate against volume` and `Summary length against
 * the length asked for` drew columns on the same 8 of 30.
 *
 * A drawing rule and not a knob in `config/`: it decides what a chart says
 * about itself, the way `LABEL_ADVANCE_EM` and `CELL_MAX` decide what an axis
 * and a strip look like. Nothing an operator would tune sits behind it.
 */
export const SPARSE_COVERAGE = 0.5;

/** How much of the span a chart drew its own measure actually covered. */
export interface Coverage {
	/** Columns drawn - the window the control set, never the data's own extent. */
	days: number;
	/** Columns carrying a measurement. */
	measured: number;
	/** True where the note and the tinted span are drawn. */
	sparse: boolean;
	/** Each unbroken run of columns nothing measured, as first and last index. */
	gaps: [number, number][];
}

/** What a chart covered, from one flag per column.
 *
 * The caller decides what "measured" means for its own series, because the
 * three charts that draw this window disagree about it: a day the pipeline
 * planned no item and a day it planned items and timed none are the same blank
 * column and are not the same fact.
 */
export function coverage(
	measured: readonly boolean[],
	threshold: number = SPARSE_COVERAGE
): Coverage {
	const days = measured.length;
	// One pass: count the measured columns and close each gap as its last unseen
	// column ends. The rule this replaces read the flags once to count and again
	// to group, so every window was scanned twice for one answer.
	let count = 0;
	const gaps: [number, number][] = [];
	let open: number | null = null;
	for (let index = 0; index < days; index += 1) {
		if (measured[index]) {
			count += 1;
			if (open !== null) {
				gaps.push([open, index - 1]);
				open = null;
			}
		} else if (open === null) {
			open = index;
		}
	}
	if (open !== null) gaps.push([open, days - 1]);
	return {
		days,
		measured: count,
		sparse: days > 0 && count > 0 && count / days < threshold,
		gaps
	};
}

/** One tinted region: where it starts, how wide it is, and what it covers. */
export interface CoverageRegion {
	x: number;
	width: number;
	from: string;
	to: string;
}

/** The empty spans of a chart, in the chart's own pixels.
 *
 * Nothing at all above the threshold. A window missing a day or two draws that
 * day as a break in a line and a reader can see it; the tint is for the case
 * where the empty part is the larger part of the picture and the marks read as
 * a chart squashed into one corner.
 *
 * A region runs from halfway between the gap's first column and the one before
 * it to halfway past its last, so the tint stops between two columns rather
 * than through the marks on either side. It is clipped to the plot, because a
 * gap at either end of the window has no neighbour to meet.
 *
 * Tinted rather than hatched: a hatch is a pattern a reader stops to decode,
 * and this one has nothing to say beyond "no measurement reached here".
 */
export function coverageRegions(
	found: Coverage,
	dates: readonly string[],
	columns: readonly number[],
	box: Frame
): CoverageRegion[] {
	if (!found.sparse) return [];
	const regions: CoverageRegion[] = [];
	for (const [from, to] of found.gaps) {
		const at = columns[from];
		const end = columns[to];
		if (at === undefined || end === undefined) continue;
		const before = columns[from - 1];
		const after = columns[to + 1];
		const left = Math.max(box.left, before === undefined ? box.left : (before + at) / 2);
		const right = Math.min(box.right, after === undefined ? box.right : (end + after) / 2);
		// A sliver narrower than a hairline is a smudge on the plot rather than a
		// span a reader can point at.
		if (right - left < 1) continue;
		regions.push({
			x: left,
			width: right - left,
			from: dates[from] ?? '',
			to: dates[to] ?? ''
		});
	}
	return regions;
}

/** The item clause of a coverage sentence, where the chart counts items too.
 *
 * `low` and `high` differ only where the chart's series disagree about how much
 * of a day they reached, and then the numerator is a range. Summing across the
 * series would count one item once per series, and picking one of them would be
 * arbitrary.
 */
export interface CoverageItems {
	low: number;
	high: number;
	total: number;
}

/** One sentence for the whole chart: how much of its window it measured.
 *
 * Null above the threshold, and null where the chart measured every column. A
 * sentence that only ever says "all of it" is noise, and one printed under a
 * chart with two days missing of thirty is a caveat nobody reads. Both numbers
 * are named rather than a share, so a reader can check the claim against the
 * columns he can see (CLAUDE.md Guardrail #10).
 *
 * `lead` is the subject and the verb, because the three charts that draw this
 * window measure three different things and no one verb is true of all of them:
 * one timed a day, one wrote summaries on it, and one planned items for it.
 */
export function coverageSentence(
	found: Coverage,
	lead: string,
	items: CoverageItems | null = null
): string | null {
	if (!found.sparse) return null;
	const days = `${lead} ${found.measured} of ${countDays(found.days)}`;
	const count =
		items === null
			? ''
			: `, and ${
					items.low === items.high
						? grouped(items.low)
						: `${grouped(items.low)} to ${grouped(items.high)}`
				} of the ${grouped(items.total)} items on them`;
	return `${days}${count}. The tinted span is days nothing recorded, not quiet days.`;
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
