import { dayMonth } from '../format';
import { formatNumber, type NumberFormatConfig } from '../number-format';
import { daysInWindow, type TimeWindow } from './viewport';

export interface TelemetryRow {
	date: string;
	run_id: string;
	item_id: string;
	vertical: string;
	source_id: string;
	stage: string;
	outcome: string;
	code: string;
	/** Words the model was given: the body after the cap cut it. */
	source_words: number | null;
	summary_words: number | null;
	/** Words the body held before the cap. Null on every run before 2026-08-28,
	 * and on any run the cap never fired for. */
	source_words_before_cap: number | null;
	/** Milliseconds the fetch took. Null where the stage never ran. */
	fetch_ms: number | null;
	/** Milliseconds the extract took. Null where the stage never ran. */
	extract_ms: number | null;
	/** Milliseconds the text analysis took, the step that names the article's
	 * people and places. Null on every row written before the step existed, and
	 * where it never ran. */
	analyze_ms: number | null;
	/** Milliseconds the summarizer held the item. Null where it never ran. */
	summarize_ms: number | null;
	/** The part of `summarize_ms` spent reading the prompt. */
	prefill_ms: number | null;
	/** The part of `summarize_ms` spent writing the summary. */
	decode_ms: number | null;
	input_tokens: number | null;
	output_tokens: number | null;
	/** Tokens the server answered from its prompt cache, added over every call the
	 * row records. Zero means nothing was cached; null means the server reported no
	 * figure at all. Ask `label_cached_tokens` instead when the question is whether
	 * the cache answered: a second call reusing the first call's prompt makes this
	 * non-zero on every item. */
	cached_tokens: number | null;
	/** How many model calls the totals above add up over. Null on every row
	 * published before 2026-09-12. It is what says how many of the two call slots
	 * below are filled. */
	model_calls: number | null;
	/** Which call ran first: `summarize`, `visual_plan`, `label` or
	 * `summarize_and_plan`. Empty where no split was published. */
	label_kind: string;
	/** The first call's own share of each total. Both calls are published now, so
	 * nothing here has to be derived by subtracting: the writer refuses a row whose
	 * totals are not the sum of its calls.
	 * `label_prefill_ms` is a duration and never a rate - a prompt token costs more
	 * the deeper into the context it sits, so a per-call tok/s cannot be compared
	 * with another call's. */
	label_prefill_ms: number | null;
	label_decode_ms: number | null;
	label_input_tokens: number | null;
	label_output_tokens: number | null;
	/** Prompt tokens the first call reused. Zero is the cold-slot answer and is a
	 * measurement; null means no split was published for this row. */
	label_cached_tokens: number | null;
	/** Which call ran second, or empty where the item made one call. */
	summary_kind: string;
	/** The second call's own share of each total. Small prefill on a warm slot,
	 * because that prompt is the first call's prompt extended. */
	summary_prefill_ms: number | null;
	summary_decode_ms: number | null;
	summary_input_tokens: number | null;
	summary_output_tokens: number | null;
	summary_cached_tokens: number | null;
	/** How long the item waited before its worker started it, its own fetch and
	 * extract subtracted. Outside `item_total_ms`, so it is not a band: the stage
	 * fetches every item and then runs the model over them in a different order,
	 * and counting the wait would charge each item for the queue ahead of it. */
	queue_wait_ms: number | null;
	/** Wall time of the label call. A slice of `summarize_ms`, never an addition
	 * to it - which is why neither this nor `summary_ms` is one of the stages
	 * `stage_gap_ms` subtracts. */
	label_ms: number | null;
	/** Wall time of the summarize-and-plan call. The other slice. */
	summary_ms: number | null;
	/** Wall time attributed to the visual plan, which is decoded inside the
	 * second call. A share of `summary_ms` and not a clock of its own. */
	visual_plan_ms: number | null;
	/** `'True'` where `visual_plan_ms` was apportioned rather than timed. A page
	 * that draws the plan's share has to be able to mark it as an estimate. */
	visual_plan_ms_is_estimate: string;
	/** Wall time of the model-free faithfulness scorers. */
	faithfulness_ms: number | null;
	/** Time spent waiting on the model server rather than being served. Inside
	 * `summarize_ms`, so a rising wait with a flat decode rate is a queue. */
	model_wait_ms: number | null;
	/** What the item cost, from the item starting to the item ending with
	 * `queue_wait_ms` taken out. The denominator every stage share is taken
	 * against. */
	item_total_ms: number | null;
	/** `item_total_ms` minus fetch, extract, analyze, summarize and faithfulness. The only
	 * cell that can catch a regression in a step nobody named, and signed on
	 * purpose: negative means two clocks overlapped. */
	stage_gap_ms: number | null;
	/** Output tokens of the second call that belong to the plan, not the summary. */
	visual_plan_tokens_written: number | null;
	/** Per-call throughput. A total cannot say whether the model slowed or the
	 * work grew; a rate beside the tokens written can. */
	label_prefill_tokens_per_s: number | null;
	label_decode_tokens_per_s: number | null;
	summary_prefill_tokens_per_s: number | null;
	summary_decode_tokens_per_s: number | null;
	/** The processor the runner reported. A throughput number with no machine
	 * beside it is not a measurement. Empty where the run recorded none. */
	cpu_model: string;
	/** Mean busy share of every processor over this item. */
	cpu_busy_pct: number | null;
	/** One-minute load average when the item ended. */
	load_1m: number | null;
}

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

/** One stage's day: the median, and the counts behind it.
 *
 * `ms` is null where nothing was timed. Zero is a measurement - a cheap stage
 * finishes inside a millisecond clock's own resolution - so the two facts
 * cannot share a value. `timed` against `total` carries the third one: a day
 * timed in full and a day timed in part are not the same day either.
 */
export interface StageTiming {
	ms: number | null;
	timed: number;
	total: number;
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
	items: number;
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

/** The steps an item's clock is split into, bottom of the stack first.
 *
 * `key` is what a test names and `label` is what a reader sees. The order is
 * the order the work happens in, so reading the stack bottom to top is reading
 * the item's life in order.
 *
 * **`gap` is the one that matters most.** It is `stage_gap_ms` - the item's own
 * wall clock minus every stage the pipeline named - so anything a later change
 * adds without timing it lands there and is visible the day it appears. A
 * split that dropped it would look complete and be wrong by however much
 * nobody measured.
 *
 * `model` is the same idea one level down: the summarize stage's time that
 * neither call claimed. On a run that published no per-call split it is the
 * whole stage, which is the honest reading - the stage was timed, the calls
 * inside it were not.
 */
export const TIME_BANDS = [
	{ key: 'fetch', label: 'Fetch' },
	{ key: 'extract', label: 'Extract' },
	{ key: 'analyze', label: 'Analyze' },
	{ key: 'label', label: 'Label call' },
	{ key: 'summary', label: 'Summary' },
	{ key: 'plan', label: 'Visual plan' },
	{ key: 'model', label: 'Model, unsplit' },
	{ key: 'faithfulness', label: 'Faithfulness' },
	{ key: 'gap', label: 'Unattributed' }
] as const;

export type TimeBandKey = (typeof TIME_BANDS)[number]['key'];

/** One day of the item-time split.
 *
 * `ms` is the MEAN milliseconds an item spent in each band, not the median, and
 * that is the whole reason this shape exists. Medians do not add: a stack of
 * per-stage medians draws a column whose height is not the median item, so
 * every share it prints is wrong by an amount nobody can see. Means add
 * exactly, so the bands sum to `total` and a reader can take a share off the
 * chart. The spread is answered elsewhere - the stage-timing chart is a median
 * with its quartiles - and this one answers composition.
 *
 * `items` counts the rows that carried `item_total_ms`, and it is the
 * denominator of every band. A row with no item clock is not in the average at
 * all: counting it would divide real milliseconds by items nobody timed and
 * shrink every band on the day a new instrument was rolled out.
 *
 * A band can be negative. `stage_gap_ms` is signed on purpose - below zero
 * means two named stages overlapped or two clocks disagreed - and clamping it
 * would hide exactly the fault it exists to show.
 */
export interface TimeSplitDay {
	date: string;
	/** Rows on this day that carried an item clock. */
	items: number;
	/** Mean milliseconds an item took, end to end. The sum of `ms`. */
	total: number;
	/** Mean milliseconds an item spent in each band, in `TIME_BANDS` order. */
	ms: number[];
}

function msCell(value: number | null): number {
	return value ?? 0;
}

/** One item's milliseconds, split into the bands, in `TIME_BANDS` order.
 *
 * The bands are built to add up to `item_total_ms` whatever the row carries.
 * `label_ms` and `summary_ms` are a split of `summarize_ms` rather than stages
 * beside it, so they are taken out of the stage and what is left is `model`;
 * `visual_plan_ms` is decoded inside the second call, so it is taken out of
 * `summary`. A row missing any of those reads the missing cell as zero and the
 * time stays in the wider band it belongs to, which is why an unsplit run draws
 * its whole model stage as `model` rather than losing it.
 */
export function itemTimeBands(row: TelemetryRow): number[] {
	const summarize = msCell(row.summarize_ms);
	const label = msCell(row.label_ms);
	const summary = msCell(row.summary_ms);
	const plan = msCell(row.visual_plan_ms);
	return [
		msCell(row.fetch_ms),
		msCell(row.extract_ms),
		msCell(row.analyze_ms),
		label,
		summary - plan,
		plan,
		summarize - label - summary,
		msCell(row.faithfulness_ms),
		msCell(row.stage_gap_ms)
	];
}

/** Where the day's items spent their time, one entry per day in the window.
 *
 * A day with no timed row is present with `items: 0` and every band at zero, so
 * the column keeps its place on the axis: a day dropped from the array shifts
 * every day after it and draws a gap as if it were the next day along.
 */
export function timeSplit(rows: TelemetryRow[], window: TimeWindow): TimeSplitDay[] {
	const summed = new Map<string, { items: number; ms: number[] }>();
	for (const row of rowsInWindow(rows, window)) {
		if (row.item_total_ms === null) continue;
		let day = summed.get(row.date);
		if (day === undefined) {
			day = { items: 0, ms: TIME_BANDS.map(() => 0) };
			summed.set(row.date, day);
		}
		day.items += 1;
		const bands = itemTimeBands(row);
		for (let index = 0; index < bands.length; index += 1) {
			day.ms[index] += bands[index];
		}
	}
	return daysInWindow(window).map((date) => {
		const day = summed.get(date);
		if (day === undefined || day.items === 0) {
			return { date, items: 0, total: 0, ms: TIME_BANDS.map(() => 0) };
		}
		const ms = day.ms.map((total) => total / day.items);
		return { date, items: day.items, total: ms.reduce((sum, band) => sum + band, 0), ms };
	});
}

export function rowsInWindow<T extends { date: string }>(rows: T[], window: TimeWindow): T[] {
	return rows.filter((row) => row.date >= window.start && row.date <= window.end);
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
