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

import { dayMonth, shortDate } from '../format';
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

/** What one rule says to anybody who points at it.
 *
 * One sentence in one place, so two charts cannot describe one event
 * differently. It names the set the stamp actually covers rather than saying
 * "the model": the stamp moves for a reworded prompt or a rebuilt runtime as
 * readily as for new weights, and four of the five stamps in the ledger cannot
 * be expanded into their cause at all (measured 2026-08-27,
 * `docs/concepts/evaluation.md`). Naming one candidate cause would be a guess.
 */
export function modelRuleTitle(date: string): string {
	return `A new model, prompt or setting started on ${shortDate(date)}. Everything left of this line was written by the one before it.`;
}

/** The readout row a chart prints on a day the pipeline changed.
 *
 * No colour, because it is an event and not a series - the strip draws a swatch
 * only where a mark on the plot is that colour.
 */
export const MODEL_RULE_ROW: ReadoutRow = {
	label: 'How summaries are written',
	value: 'changed on this day',
	colour: ''
};

/** What a chart says where the days it drew hold no change.
 *
 * A named state and never a missing element: an absent rule and a rule nobody
 * remembered to draw look identical, and only one of them is an answer.
 */
export function noModelRuleNote(days: number): string {
	return `Nothing changed about how the summaries are written inside these ${days} ${days === 1 ? 'day' : 'days'}.`;
}

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

/** What one tinted span says to anybody who points at it. */
export function coverageRegionTitle(region: CoverageRegion): string {
	const span =
		region.from === region.to
			? shortDate(region.from)
			: `${shortDate(region.from)} to ${shortDate(region.to)}`;
	return `Nothing was measured over ${span}. The span is drawn because it happened, not because it was quiet.`;
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
 * columns he can see (CLAUDE.md Rule #10).
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
	const days = `${lead} ${found.measured} of these ${found.days} days`;
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

/** The readout row a chart prints on a column nothing measured.
 *
 * Measured, a pointer on one of those columns selected it and printed a set of
 * blanks or a set of zeros, which is what reads as a broken hover rather than
 * as an empty day. No colour: nothing on the plot is this row's mark.
 */
export function notMeasuredRow(sentence: string): ReadoutRow {
	return { label: sentence, value: '', colour: '' };
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

/** One mark a readout can land on: where it sits.
 *
 * It carried a second field, `lines`, holding one preformatted sentence per
 * series on the premise that the action would read them out. Nothing ever did.
 * `ChartReadout.svelte` is the live region and it prints `DayReadout.rows`
 * straight, so every hover target on every console chart was built with a
 * string per series that no element and no reader saw. Deleted 2026-09-06
 * after a grep over `frontend/` found one reader, and it was a test asserting
 * the field's own shape.
 */
export interface ReadoutMark {
	/** The mark's x in the chart's own pixels. The hit rule is nearest by x. */
	x: number;
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

/** The action's marks: where each column of the strip sits.
 *
 * The strip and the action are built from one array, so the column a pointer
 * lands on and the column the strip prints cannot be two different ones.
 */
export function readoutMarks(columns: readonly DayReadout[]): ReadoutMark[] {
	return columns.map((column) => ({ x: column.x }));
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

/** How far a mark may sit from an evenly spaced one and still count as evenly
 * spaced, as a share of one step.
 *
 * `dayColumns` computes `left + (index * (right - left)) / (columns - 1)`, so
 * two neighbouring columns come out a bit or two of a double apart rather than
 * exactly one step apart. A millionth of a step admits that and admits nothing
 * else: over the widest axis this ships, 366 columns, the arithmetic below can
 * then be out by at most a thousandth of a column, and it checks a whole column
 * either side of its own answer.
 */
const EVEN_SPACING_SLACK = 1e-6;

/** How a set of marks lies along x, which decides how a pointer is answered. */
export type MarkSpacing = 'even' | 'ordered' | 'scan';

/** Which of the three rules a set of marks gets, and the rule itself. */
export interface ColumnLookup {
	/** `even` where the marks are evenly spaced, so a column is one division;
	 * `ordered` where they only ascend, so it is a binary search; `scan` where
	 * they do neither. Published so a test can say which rule ran, rather than
	 * only that the answer came out right - an implementation that quietly
	 * walked every mark every time would pass a parity test in silence. */
	rule: MarkSpacing;
	/** The column a pointer at this x means, or null where there are none. */
	at: (x: number) => number | null;
}

function spacingOf(xs: readonly number[]): MarkSpacing {
	for (let index = 0; index < xs.length; index += 1) {
		// A mark that is not a real number, or one sitting before the mark before
		// it, is outside what either fast rule can promise. Neither happens on a
		// console chart and both are cheap to hand back to the walk.
		if (!Number.isFinite(xs[index])) return 'scan';
		if (index > 0 && xs[index] < xs[index - 1]) return 'scan';
	}
	if (xs.length < 2) return 'ordered';
	const first = xs[0];
	const step = (xs[xs.length - 1] - first) / (xs.length - 1);
	// Every mark at one x, which is what `columnStrip` builds before an
	// engine-drawn chart is given its real shares. The search answers it.
	if (!(step > 0)) return 'ordered';
	const slack = step * EVEN_SPACING_SLACK;
	for (let index = 1; index < xs.length - 1; index += 1) {
		if (Math.abs(xs[index] - (first + index * step)) > slack) return 'ordered';
	}
	return 'even';
}

/** The first mark at or past `x`, looking only at the first `to` of them. */
function firstAtOrPast(xs: readonly number[], x: number, to: number): number {
	let low = 0;
	let high = to;
	while (low < high) {
		const middle = (low + high) >> 1;
		if (xs[middle] < x) low = middle + 1;
		else high = middle;
	}
	return low;
}

/** Which column a pointer at an x means, worked out once for one set of marks.
 *
 * The walk this replaces measured every mark on every `pointermove`, so a chart
 * with a column a day over a ninety-day window did ninety subtractions to
 * answer a question a dragging thumb asks many times a second, and it did them
 * again for a move that did not change the answer. The layout is settled once
 * instead, when the marks change:
 *
 * - **Evenly spaced** - every day chart on the console, because `dayColumns`
 *   and `bandShares` both divide the plot evenly. The column is then one
 *   division, and only its two neighbours are measured to settle a pointer
 *   sitting on a boundary.
 * - **Ascending but not evenly spaced** - a chart placing its columns by a
 *   value rather than by a count, and any strip whose marks share an x. A
 *   binary search finds the first mark at or past the pointer and measures the
 *   pair around it.
 * - **Neither** - the walk, unchanged. Nothing on the console produces this,
 *   and a rule that guessed here would be a rule nobody could check.
 *
 * All three answer the same, including the tie: where two marks are the same
 * distance away the lower index wins, because the strip prints one column and
 * a chart with two runs of one day at one x needs the pointer and the strip to
 * agree which. `frame.spec.ts` holds every rule to the walk, at every mark,
 * every midpoint and every duplicate.
 */
export function nearestColumn(marks: readonly ReadoutMark[]): ColumnLookup {
	const xs = marks.map((mark) => mark.x);
	const count = xs.length;
	const rule = spacingOf(xs);

	/** The nearest of a run of candidates, lowest index on a tie. The walk's own
	 * comparison, so a fast rule that narrows the field cannot change the pick. */
	const best = (x: number, from: number, to: number): number => {
		let at = from;
		let gap = Math.abs(xs[from] - x);
		for (let index = from + 1; index <= to; index += 1) {
			const distance = Math.abs(xs[index] - x);
			if (distance < gap) {
				gap = distance;
				at = index;
			}
		}
		return at;
	};

	if (count === 0) return { rule, at: () => null };

	if (rule === 'even') {
		const first = xs[0];
		const step = (xs[count - 1] - first) / (count - 1);
		return {
			rule,
			at: (x: number) => {
				// The walk keeps its first candidate against every distance it cannot
				// beat, so an x that is not a number picks the first column.
				if (!Number.isFinite(x)) return 0;
				// `ceil(t - 0.5)` is the nearest column with an exact halfway point
				// sent down, which is the walk's tie rule.
				const guess = Math.ceil((x - first) / step - 0.5);
				const near = Math.min(count - 1, Math.max(0, guess));
				return best(x, Math.max(0, near - 1), Math.min(count - 1, near + 1));
			}
		};
	}

	if (rule === 'ordered') {
		return {
			rule,
			at: (x: number) => {
				if (!Number.isFinite(x)) return 0;
				const past = firstAtOrPast(xs, x, count);
				if (past === 0) return 0;
				// A second search rather than a walk back over the duplicates: a strip
				// whose marks all share an x is the case that would make that walk the
				// whole array again.
				const firstOf = (index: number) => firstAtOrPast(xs, xs[index], index + 1);
				if (past === count) return firstOf(count - 1);
				return xs[past] - x < x - xs[past - 1] ? past : firstOf(past - 1);
			}
		};
	}

	return { rule, at: (x: number) => best(x, 0, count - 1) };
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
	let column = nearestColumn(options.marks);

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
		return column.at(((clientX - rect.left) * current.width) / rect.width);
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
			// The layout of the marks is settled here rather than on every pointer
			// move, which is the whole of what this action costs a dragging thumb.
			if (next.marks !== current.marks) column = nearestColumn(next.marks);
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
