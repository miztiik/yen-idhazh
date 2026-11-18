import { dayMonth } from '../format';
import { formatNumber, type NumberFormatConfig } from '../number-format';

/** Where the cut fell, and over which days it was the cut in force. */
export interface CapLine {
	words: number;
	/** Oldest and newest day in view that was cut at this length. */
	first: string;
	last: string;
}

/** What one cap line says about itself.
 *
 * A lone cap needs no date at all - it is the cut, over the whole window. Where
 * there are several the labels read as a handover: the oldest names the last
 * day it applied, and each later one names the first day it did.
 *
 * The source-cut range plot is the only caller; it derives its own cut points
 * in `capPoints`.
 */
export function capLabel(
	caps: readonly CapLine[],
	index: number,
	numberFormat: NumberFormatConfig
): string {
	const cap = caps[index];
	const words = `cut at ${grouped(cap.words, numberFormat)} words`;
	if (caps.length === 1) return words;
	return index === 0
		? `${words} (to ${dayMonth(cap.last)})`
		: `${words} (from ${dayMonth(cap.first)})`;
}

/** Exact counts use the same configured locale as every other number. */
export function grouped(value: number, numberFormat: NumberFormatConfig): string {
	return formatNumber(value, numberFormat, { exact: true, si: false });
}

/** One stage's day: the median, and the count behind it.
 *
 * `ms` is null where nothing was timed. Zero is a measurement - a cheap stage
 * finishes inside a millisecond clock's own resolution - so the two facts
 * cannot share a value. `timed` against the day's `items` carries the third
 * one: a day timed in full and a day timed in part are not the same day either.
 */
export interface StageTiming {
	ms: number | null;
	timed: number;
}

/** One day's median milliseconds per stage, over the item-health census.
 *
 * The three stages an item waits on, and only those. Scoring is timed too and
 * it is not here: it runs after the summary is written, so nothing waits on it
 * and a fourth line on a critical-path chart read as a fourth constraint. It is
 * on the Model route, beside the cost of writing the summary it checks.
 */
export interface StageTimingDay {
	date: string;
	items: number;
	fetch: StageTiming;
	extract: StageTiming;
	summarize: StageTiming;
}

/** The spread of one day's per-item rates. A candle, never an average.
 *
 * The spread is the point. A worker summarises its short articles first and its
 * long ones last, so the slowest item of a day is several times slower than the
 * fastest, and a single number hides the fact that the two ends moved apart.
 */
export interface RateSpread {
	min: number;
	p25: number;
	median: number;
	p75: number;
	max: number;
}

/** One run's median rates. Four of these sit behind a day's candle. */
export interface ThroughputRun {
	runId: string;
	read: number;
	write: number;
}

export interface ThroughputDay {
	date: string;
	items: number;
	read: RateSpread;
	write: RateSpread;
	/** The whole day's tokens over the whole day's milliseconds. Weighted by
	 * work done, unlike the median, which weighs a release note like a feature. */
	readTps: number;
	writeTps: number;
	cacheHitPct: number;
	runs: ThroughputRun[];
	/** What wrote the day, where a ledger says. Two days on different models are
	 * two measurements, so nothing compares them. */
	model: string | null;
}

/** The axis the model-swap comparison shares, as fractions of the plot width.
 *
 * Every row is drawn against its own value on the older model, so no change is
 * 100 percent on all of them and that point is the axis centre. Symmetric on
 * purpose: an axis running 78 to 120 would draw a fifth off as a longer track
 * than a fifth on, and the whole panel is a reader comparing seven track
 * lengths.
 *
 * Pure arithmetic, so the geometry can be checked in Node without a browser.
 */
export interface SwapScale {
	/** Percentage points either side of no change. */
	half: number;
	/** Low, no change, high. */
	ticks: [number, number, number];
	/** A percent to a share of the plot, 0 at the left edge and 1 at the right. */
	at: (percent: number) => number;
}

export function swapScale(percents: readonly number[], minHalf = 25): SwapScale {
	const half = Math.max(minHalf, ...percents.map((percent) => Math.abs(percent - 100)));
	return {
		half,
		ticks: [100 - half, 100, 100 + half],
		at: (percent: number) => (percent - (100 - half)) / (half * 2)
	};
}

/** Where one source's row of the length range plot sits, in chart pixels. */
export interface RangeMarks {
	/** The shortest, the middle and the longest article of that source. */
	x0: number;
	xMid: number;
	x1: number;
	/** Where the text past the cut point starts, held inside the row's own span.
	 *
	 * Equal to `x1` where nothing this source published reached the cut point,
	 * so the emphasised segment has no length and draws nothing.
	 */
	xCut: number;
	/** True where the longest article ran past the cut point. */
	past: boolean;
}

/** One row of the length range plot, placed.
 *
 * Pure arithmetic over a scale somebody else built, so the plot's geometry can
 * be checked in Node against an identity scale. The clamp is the part worth
 * having in one place: a cut point left of a source's shortest article would
 * otherwise draw the emphasised segment starting outside the track it belongs
 * to, which reads as text lost from an article that is not on the row.
 */
export function rangeMarks(
	range: { min: number; median: number; max: number },
	capWords: number | null,
	scale: (words: number) => number
): RangeMarks {
	const x0 = scale(range.min);
	const xMid = scale(range.median);
	const x1 = scale(range.max);
	const past = capWords !== null && range.max > capWords;
	return {
		x0,
		xMid,
		x1,
		xCut: past ? Math.min(x1, Math.max(x0, scale(capWords as number))) : x1,
		past
	};
}

// ---------------------------------------------------------------------------
// How long one thing took, as a distribution
// ---------------------------------------------------------------------------

/** The value at a fraction of the way through a sorted list, interpolated. */
export function quantile(sorted: readonly number[], fraction: number): number {
	if (sorted.length === 1) return sorted[0];
	const position = (sorted.length - 1) * fraction;
	const low = Math.floor(position);
	const high = Math.ceil(position);
	return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

/** One bar of a time histogram.
 *
 * `from` and `to` are whole seconds and `from` is zero on the first bar, which
 * is the one holding everything under a second. The edges double, so a bar is
 * one doubling wide wherever it sits on the axis - which is what lets a
 * distribution running from a third of a second to twelve minutes be read at
 * all.
 */
export interface WriteBin {
	/** Lower edge, whole seconds. Zero means "under one second". */
	from: number;
	/** Upper edge, whole seconds. The bar holds `from <= t < to`. */
	to: number;
	n: number;
	/** Every item finished in `to` seconds or less, as whole percent. */
	throughPct: number;
}

/** How long one thing took, over every one of them a clock recorded.
 *
 * The bars and the two rules, and nothing about which window they came from -
 * that belongs to the caller, which knows what it asked for. Four panels draw
 * this shape over four different clocks: the model reading a prompt and writing
 * a summary on Pipelines, and the whole model call and the checker's own clock
 * on Summaries. It is the same question every time - how long did one take, and
 * how bad does it get - so it is one binning and one pair of rules rather than
 * four that can drift apart.
 *
 * The median and the 95th are taken over the values themselves and never off
 * the bars: a percentile read out of a bin is a guess at where inside the bin
 * it fell, and these two are the figures somebody quotes.
 */
export interface Distribution {
	bins: WriteBin[];
	/** Timings behind the chart. The denominator for every bar. */
	n: number;
	/** Milliseconds. */
	median: number;
	p95: number;
	slowest: number;
	fastest: number;
}

/** The bars and the rules, or null where nothing was timed.
 *
 * Null is the empty state and it is not a chart of zeroes. Nothing measured it;
 * it did not run instantly.
 *
 * It lives here rather than beside the first panel that drew it because a
 * browser cannot import `$lib/server/`, and the Pipelines route bins the two
 * model clocks in the same doublings the Summaries route bins its own in.
 */
export function distribution(values: readonly number[]): Distribution | null {
	const sorted = [...values].sort((a, b) => a - b);
	if (sorted.length === 0) return null;

	// The first edge is one second, so every label on the axis is a whole
	// number. Everything below it shares one bar, labelled the way the console
	// spells a measurement that rounds away.
	const top = Math.max(1, sorted[sorted.length - 1] / 1000);
	const edges = [0, 1];
	while (edges[edges.length - 1] <= top) edges.push(edges[edges.length - 1] * 2);

	const bins: WriteBin[] = [];
	let through = 0;
	// One advancing cursor down the sorted values rather than a full scan per
	// bin. The values are ascending and the edges are ascending, so every value
	// belongs to the bin the cursor is standing in.
	let cursor = 0;
	// Anything below the first edge belongs to no bin, which is what a full scan
	// did too: the first bin asks for `>= from` and every later one starts at or
	// above one second.
	while (cursor < sorted.length && sorted[cursor] / 1000 < edges[0]) cursor += 1;
	for (let index = 0; index < edges.length - 1; index += 1) {
		const from = edges[index];
		const to = edges[index + 1];
		const opened = cursor;
		while (cursor < sorted.length && sorted[cursor] / 1000 < to) cursor += 1;
		const n = cursor - opened;
		through += n;
		bins.push({ from, to, n, throughPct: Math.round((through / sorted.length) * 100) });
	}

	// Leading and trailing empty bars are axis, not data. A gap between two
	// occupied bars stays: it is the distribution saying nothing landed there.
	const first = bins.findIndex((bin) => bin.n > 0);
	const last = bins.length - 1 - [...bins].reverse().findIndex((bin) => bin.n > 0);

	return {
		bins: bins.slice(first, last + 1),
		n: sorted.length,
		median: quantile(sorted, 0.5),
		p95: quantile(sorted, 0.95),
		slowest: sorted[sorted.length - 1],
		fastest: sorted[0]
	};
}
