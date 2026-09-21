/** What the machine did, drawn from what the two surviving ledgers counted.
 *
 * `$lib/server/machine-counters.ts` reads `state/host-fingerprint/` and
 * `state/item-health/` and hands back one figure per shard and per run. This
 * module turns those figures into the eight things an operator can act on:
 * which shard was slow and why, whether the seconds went on reading or on
 * writing, whether the prompt cache is earning its keep, how much of the
 * context window a run actually used, how near the runner's 16 GB a run got,
 * whether the two clocks agree, whether the tail is growing, and what a run's
 * tokens would have cost somewhere else.
 *
 * Every function here is pure and every one takes its ceiling as an argument,
 * so a test drives it from a fixture ledger and Guardrail #6 keeps the knobs in
 * `config/`. Nothing reaches the disk and nothing reaches the network.
 *
 * **An empty cell is unknown and never zero.** The reader hands absence through
 * as `null` and so does this module: a figure that did not run leaves here as
 * `null` and a component prints a dash or a sentence. A zero is a measurement.
 */

import type { EChartsOption } from 'echarts';
import type { MachineRun, ShardCounters } from '$lib/server/machine-counters';
import { dayMonth } from '../format';
import { AXIS_LABEL_GAP_PX, LABEL_ADVANCE_EM, labelWidth, type DayReadout } from './frame';
import { percentOf } from './rank';
import { grouped } from './series';
import { stacked, type StackShape } from './stacked';
import { targetMarks, type TargetMarks } from './targetbar';
import { paint, type ChartToken, type Polarity } from './theme';

/** The runner's memory, from CLAUDE.md Guardrail #2: 4 vCPU, 16 GB RAM, no GPU.
 *
 * A constant and not a `config/` knob, for the same reason `PAGES_CAP_BYTES` in
 * `glance.ts` is a constant: it is a property of the platform we run on, not a
 * preference anybody may tune. Turning it into a knob would let a run that no
 * longer fits be made to look as though it did.
 */
export const RUNNER_MEMORY_BYTES = 16 * 1024 * 1024 * 1024;

/** Which way is better for a memory high-water mark, said once, here.
 *
 * At the measure and never at the paint site: a bar and a delta drawn from the
 * same figure on two different panels cannot then disagree about which
 * direction is good. Less is better because the ceiling is the runner's and we
 * cannot raise it - a mark that climbs is a run getting nearer to not fitting.
 */
export const MEMORY_POLARITY: Polarity = 'lower-is-better';

/** The room an engine-drawn value axis needs for its own widest label.
 *
 * `stacked` and the run-by-run bars both took a fixed 48px, which is a gutter
 * sized for a four-digit count. Measured 2026-09-01 at 1440, 768 and 390 on the
 * built console, that clipped `200,000` by 1.35px and `1,200,000` by 10.44px on
 * the prompt-cache chart - six labels cut on every width. The engine picks its
 * own top tick, so the widest label it can draw is the largest value grouped
 * plus at most one more character; that character is the slack added here.
 */
export function valueGutter(highest: number, fontSize = 11): number {
	const widest = labelWidth(grouped(Math.round(highest)), fontSize) + fontSize * LABEL_ADVANCE_EM;
	return Math.ceil(widest) + AXIS_LABEL_GAP_PX;
}

/** The five points a latency curve is quoted at.
 *
 * p50 says what a normal item costs and p99 says what the worst one costs, and
 * the three between them are what makes the line a shape rather than two dots.
 */
export const PERCENTILES = [50, 75, 90, 95, 99] as const;

function sum(values: readonly number[]): number {
	return values.reduce((total, value) => total + value, 0);
}

/** Linear interpolation between the two nearest ranks.
 *
 * The rule matters and is stated wherever a percentile is drawn: at the item
 * counts a run reaches - about a hundred - the nearest-rank rule and this one
 * disagree by more than the difference between two runs, so a page that did not
 * say which it used could not be checked. This is the same rule the Model
 * route's throughput spread uses, so two panels never quote two p90s.
 *
 * `sorted` must be ascending and non-empty.
 */
export function quantile(sorted: readonly number[], fraction: number): number {
	if (sorted.length === 1) return sorted[0];
	const position = (sorted.length - 1) * fraction;
	const low = Math.floor(position);
	const high = Math.ceil(position);
	return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

/** Seconds as a clock a person reads, or the honest absence of one. */
export function seconds(value: number | null): string {
	if (value === null) return '-';
	if (value < 60) return `${value.toFixed(value < 10 ? 1 : 0)} s`;
	const minutes = Math.floor(value / 60);
	const rest = Math.round(value - minutes * 60);
	return minutes < 60
		? `${minutes} m ${rest} s`
		: `${Math.floor(minutes / 60)} h ${minutes % 60} m`;
}

/** Bytes as gibibytes, which is the unit the runner's own limit is quoted in. */
export function gib(value: number | null): string {
	return value === null ? '-' : `${(value / 1024 / 1024 / 1024).toFixed(2)} GiB`;
}

// ---------------------------------------------------------------------------
// The shard board
// ---------------------------------------------------------------------------

/** One shard of one run, as a row a person reads left to right.
 *
 * The shard is the unit and not a tooltip: a per-run average of a run whose
 * fastest reader ran 4.31x its slowest reports neither end of it, which is the
 * defect this whole route exists to close.
 */
export interface BoardRow {
	shard: number;
	/** Items this shard finished. The work half of the work-or-host question: a
	 * long clock at a normal read rate and a high count is a lot of articles. */
	items: number;
	readSeconds: number | null;
	writeSeconds: number | null;
	/** The two together. Null unless the shard reported both. */
	modelSeconds: number | null;
	/** CSS lengths for the two segments, against the heaviest shard's total, so
	 * a short row means a short shard rather than a differently scaled bar. */
	readWidth: string;
	writeWidth: string;
	/** False where the smaller segment would draw under one pixel at
	 * `console.chart_width`. The track then draws whole and the two seconds are
	 * printed, because a band nobody can see teaches a category is zero. */
	splitDrawn: boolean;
	readTokensPerSecond: number | null;
	writeTokensPerSecond: number | null;
	/** The two rates as CSS lengths, against whichever domain the board chose. */
	readRateWidth: string;
	writeRateWidth: string;
	/** The processor, as the text `/proc/cpuinfo` printed. Null on a shard that
	 * ran before the cell existed - which is absence, not an unknown machine. */
	cpuModel: string | null;
	cpuBusyPct: number | null;
	/** A typical item's memory against the shard's worst, on the board's one
	 * memory domain. */
	memory: RangeMark;
	/** A typical item's CPU against the shard's worst, on nought to a hundred. */
	cpu: RangeMark;
	/** A typical item's stolen share against the shard's worst, on the same
	 * nought to a hundred the busy share is drawn on - the two are halves of one
	 * reading and a second domain would invite a comparison that is not there.
	 *
	 * Beside the busy share rather than in a column of its own: a busy figure is
	 * only readable once a reader knows how much of the interval we were given,
	 * and a shard that lost a tenth of its processor explains the read rate two
	 * cells to its left. */
	stolen: RangeMark;
	/** Items of the shard that recorded a stolen share. Zero on a shard that ran
	 * before the ledger split it out of the busy share, which is why an empty
	 * mark here is not a host that took nothing. */
	stolenItems: number;
	/** The highest load any of the shard's items ended under. */
	loadMax: number | null;
	/** Cores the host let the job see. The load figure's denominator. */
	cores: number | null;
	/** The load against those cores. Empty where either is missing. */
	load: TargetMarks;
	/** What the host had left to swap into, and what it has. */
	swapFreeBytes: number | null;
	swapTotalBytes: number | null;
	/** Which of the three things the swap pair can say. `none` is a box with no
	 * swap at all, which is not an emergency; `unrecorded` is a run older than
	 * the cell. Carried rather than derived in markup so a test can name it. */
	swapState: SwapState;
	/** What the shard paid opening the weights, before its first item. */
	modelLoadMs: number | null;
	/** Seconds of this shard's items that no named stage claimed, added over
	 * them and drawn exactly as the ledger stores it.
	 *
	 * **Signed, and never recomputed here.** The column is the one thing that can
	 * catch a regression in a stage nobody named, and a figure this page worked
	 * out from the stage clocks would agree with them by construction. Below zero
	 * means the named stages claim more time than the items took - two clocks
	 * disagreeing - and that is the reading, not a zero. */
	unclaimedSeconds: number | null;
	/** How many of the shard's items carried unclaimed time below zero. A sum can
	 * cancel; a count cannot. */
	clocksDisagreed: number;
	/** How many of the shard's item rows carried an unclaimed figure at all. The
	 * denominator the count above is read against. */
	clockedItems: number;
	/** The typical item's wait and the worst one, on the board's clock scale.
	 *
	 * Never a total. Each item's wait covers the queue ahead of it, so adding
	 * them counts that queue once per item. */
	queue: RangeMark;
	queueMedianSeconds: number | null;
	queueMaxSeconds: number | null;
	jobSeconds: number | null;
	/** The job clock against `run.shard_timeout_minutes`. */
	job: TargetMarks;
}

export type SwapState = 'measured' | 'none' | 'unrecorded';

/** A typical reading and the worst one, on one track.
 *
 * Two numbers with a span, drawn once rather than written as two sentences: the
 * fill runs to the median and the notch stands at the maximum, so the distance
 * between them IS the spread. Four figures each written as prose is four
 * sentences no two of which can be compared.
 */
export interface RangeMark {
	median: number | null;
	max: number | null;
	medianWidth: string;
	notchWidth: string;
	empty: boolean;
}

export interface ShardBoardView {
	runId: string;
	date: string;
	/** Ranked by job clock, slowest first. A shard with no clock cannot be
	 * ranked, so it follows in shard order rather than being dropped. */
	rows: BoardRow[];
	/** Shards the run planned. `rows.length` is short of it when a shard's job
	 * died before it recorded anything. Null where the manifest recorded no
	 * count, which is unknown rather than however many answered. */
	shards: number | null;
	/** The fastest reader over the slowest. Null with fewer than two readers -
	 * one shard cannot spread against itself. */
	readSpread: number | null;
	/** The seconds the widest bar stands for. Every row shares it, and the queue
	 * bars share it with the model bars - which is the whole point of drawing the
	 * wait here rather than as a number of its own: a queue longer than the model
	 * time is a length a reader can see against it. */
	scaleSeconds: number;
	/** The tokens a second the widest rate bar stands for, taken from the rates
	 * drawn and never from a fixed ceiling. A 4x spread draws a quarter-length
	 * bar rather than being clipped at a round number somebody chose. */
	rateScale: number;
	/** The write series' own domain. The same number as `rateScale` while the
	 * two share an axis, and the write series' own maximum once they cannot. */
	writeRateScale: number;
	/** The larger rate over the smaller, measured across every rate on the
	 * board. Null with nothing to compare. */
	rateRatio: number | null;
	/** True while `rateRatio` is under `RATE_AXIS_RATIO_LIMIT`, so the two rates
	 * are lengths a reader may compare. False past it, when the smaller would
	 * draw under a twentieth of the track and read as zero. */
	ratesShareAxis: boolean;
	/** The bytes the widest memory mark stands for: the largest of what the
	 * shards reached and the runner's own ceiling, so a breach draws past the
	 * ceiling rather than being clipped at it. */
	memoryScaleBytes: number;
	/** What the job clock is measured against, in seconds. Null unconfigured. */
	timeoutSeconds: number | null;
	/** Shards that named a processor, and shards the run had. */
	cpuKnown: number;
	/** Shards whose host recorded how much swap it has. Zero is every run
	 * written before the cell landed, and the cells then say so. */
	swapKnown: number;
	empty: boolean;
}

function modelSeconds(shard: ShardCounters): number | null {
	return shard.readSeconds === null || shard.writeSeconds === null
		? null
		: shard.readSeconds + shard.writeSeconds;
}

/** How far apart two series may be and still share one axis.
 *
 * Past this the smaller draws under a twentieth of the track and reads as zero,
 * so it takes its own domain and the board prints the ratio it measured. The
 * threshold is a measurement rather than a taste, which is why it is named here
 * once instead of being decided panel by panel.
 */
export const RATE_AXIS_RATIO_LIMIT = 20;

/** A median and a maximum on one track, against a domain the caller owns. */
function rangeMark(
	middle: number | null,
	highest: number | null,
	scale: number
): RangeMark {
	if (middle === null && highest === null) {
		return { median: null, max: null, medianWidth: '0%', notchWidth: '0%', empty: true };
	}
	const fraction = (value: number | null) =>
		value === null || scale <= 0 ? 0 : Math.min(value / scale, 1);
	return {
		median: middle,
		max: highest,
		medianWidth: percentOf(fraction(middle)),
		notchWidth: percentOf(fraction(highest)),
		empty: false
	};
}

function swapStateOf(total: number | null): SwapState {
	if (total === null) return 'unrecorded';
	return total > 0 ? 'measured' : 'none';
}

/** One run as one row per shard, ranked by the clock the timeout applies to.
 *
 * Ranked by the job clock rather than by model seconds, because the job clock
 * is the one the platform kills a shard on: the row at the top is the shard
 * that would be killed first.
 *
 * `chartWidth` is `console.chart_width`, and it decides one thing only: whether
 * the smaller half of a shard's reading-against-writing split is wide enough to
 * be a band rather than a legend key with no mark.
 */
export function shardBoard(
	run: MachineRun | null,
	timeoutSeconds: number | null,
	chartWidth: number
): ShardBoardView {
	if (run === null || run.reported.length === 0) {
		return {
			runId: run?.runId ?? '',
			date: run?.date ?? '',
			rows: [],
			shards: run?.shards ?? null,
			readSpread: null,
			scaleSeconds: 0,
			rateScale: 0,
			writeRateScale: 0,
			rateRatio: null,
			ratesShareAxis: true,
			memoryScaleBytes: RUNNER_MEMORY_BYTES,
			timeoutSeconds,
			cpuKnown: 0,
			swapKnown: 0,
			empty: true
		};
	}

	const totals = run.reported
		.map(modelSeconds)
		.filter((value): value is number => value !== null);
	// The queue bars are drawn on this scale too, so it has to reach the longest
	// wait as well as the heaviest model clock. A shard that queued longer than it
	// computed then draws a longer bar, which is the sentence the pair exists to
	// let a reader read.
	const waits = run.reported
		.map((shard) => shard.queueMaxSeconds)
		.filter((value): value is number => value !== null);
	const clocks = [...totals, ...waits];
	const scaleSeconds = clocks.length === 0 ? 0 : Math.max(...clocks);

	// Both domains come from the values drawn. The memory one takes the runner's
	// ceiling in beside them rather than as its maximum, so a shard that went
	// past 16 GiB still draws past the line instead of stopping on it.
	const readRates = run.reported
		.map((shard) => shard.readTokensPerSecond)
		.filter((value): value is number => value !== null);
	const writeRates = run.reported
		.map((shard) => shard.writeTokensPerSecond)
		.filter((value): value is number => value !== null);
	const readTop = readRates.length === 0 ? 0 : Math.max(...readRates);
	const writeTop = writeRates.length === 0 ? 0 : Math.max(...writeRates);
	const larger = Math.max(readTop, writeTop);
	const smaller = Math.min(readTop, writeTop);
	const rateRatio = smaller > 0 ? larger / smaller : null;
	const ratesShareAxis = rateRatio === null || rateRatio < RATE_AXIS_RATIO_LIMIT;
	const rateScale = larger;
	const writeRateScale = ratesShareAxis ? larger : writeTop;

	const memoryMarks = run.reported.flatMap((shard) =>
		[shard.rssMedianBytes, shard.peakRssBytes].filter((value): value is number => value !== null)
	);
	const memoryScaleBytes = Math.max(RUNNER_MEMORY_BYTES, ...memoryMarks);

	// A band this narrow is a legend entry with no mark on the track.
	const leastVisible = chartWidth > 0 ? 1 / chartWidth : 0;

	const ordered = [...run.reported].sort((a, b) => {
		// A shard with no clock has no rank. It goes last, in shard order, rather
		// than being sorted as though its clock were zero.
		if (a.jobSeconds === null && b.jobSeconds === null) return a.shard - b.shard;
		if (a.jobSeconds === null) return 1;
		if (b.jobSeconds === null) return -1;
		return b.jobSeconds - a.jobSeconds;
	});

	const rows: BoardRow[] = ordered.map((shard) => {
		const readShare = scaleSeconds > 0 ? (shard.readSeconds ?? 0) / scaleSeconds : 0;
		const writeShare = scaleSeconds > 0 ? (shard.writeSeconds ?? 0) / scaleSeconds : 0;
		// Only a band that is there at all has to be wide enough to see. A shard
		// that spent no seconds writing has a real zero, not an invisible band.
		const bands = [readShare, writeShare].filter((share) => share > 0);
		return {
			shard: shard.shard,
			items: shard.items,
			readSeconds: shard.readSeconds,
			writeSeconds: shard.writeSeconds,
			modelSeconds: modelSeconds(shard),
			readWidth: percentOf(readShare),
			writeWidth: percentOf(writeShare),
			splitDrawn: bands.every((share) => share >= leastVisible),
			readTokensPerSecond: shard.readTokensPerSecond,
			writeTokensPerSecond: shard.writeTokensPerSecond,
			readRateWidth: percentOf(
				rateScale > 0 ? (shard.readTokensPerSecond ?? 0) / rateScale : 0
			),
			writeRateWidth: percentOf(
				writeRateScale > 0 ? (shard.writeTokensPerSecond ?? 0) / writeRateScale : 0
			),
			cpuModel: shard.cpuModel,
			cpuBusyPct: shard.cpuBusyPct,
			memory: rangeMark(shard.rssMedianBytes, shard.peakRssBytes, memoryScaleBytes),
			cpu: rangeMark(shard.cpuBusyMedianPct, shard.cpuBusyMaxPct, 100),
			stolen: rangeMark(shard.cpuStolenMedianPct, shard.cpuStolenMaxPct, 100),
			stolenItems: shard.cpuStolenItems,
			loadMax: shard.loadMax,
			cores: shard.cores,
			load: targetMarks(shard.loadMax, shard.cores ?? 0, 'lower-is-better'),
			swapFreeBytes: shard.swapFreeMinBytes,
			swapTotalBytes: shard.swapTotalBytes,
			swapState: swapStateOf(shard.swapTotalBytes),
			modelLoadMs: shard.modelLoadMs,
			unclaimedSeconds: shard.unclaimedSeconds,
			clocksDisagreed: shard.clocksDisagreed,
			clockedItems: shard.clockedItems,
			queue: rangeMark(shard.queueMedianSeconds, shard.queueMaxSeconds, scaleSeconds),
			queueMedianSeconds: shard.queueMedianSeconds,
			queueMaxSeconds: shard.queueMaxSeconds,
			jobSeconds: shard.jobSeconds,
			job: targetMarks(shard.jobSeconds, timeoutSeconds ?? 0, 'lower-is-better')
		};
	});

	return {
		runId: run.runId,
		date: run.date,
		rows,
		shards: run.shards,
		readSpread: run.readSpread.value,
		scaleSeconds,
		rateScale,
		writeRateScale,
		rateRatio,
		ratesShareAxis,
		memoryScaleBytes,
		timeoutSeconds,
		cpuKnown: run.cpuModels.from,
		swapKnown: run.reported.filter((shard) => shard.swapTotalBytes !== null).length,
		empty: false
	};
}

// ---------------------------------------------------------------------------
// Reading against writing
// ---------------------------------------------------------------------------

// The split is drawn once per machine and lives in `machine-split.ts`. It was
// one pooled figure over every shard of a run until 2026-09-17, and measured
// over the committed ledger that figure averaged two or more different machines
// on 86 of the 90 runs that name a processor.

// ---------------------------------------------------------------------------
// The prompt cache
// ---------------------------------------------------------------------------

export interface CacheDay {
	date: string;
	/** Prompt tokens the server actually read. */
	read: number;
	/** Prompt tokens it reused instead of reading. */
	cached: number;
	/** Cached over every prompt token the day needed, whole percent. Null where
	 * the day needed none. */
	cachedPct: number | null;
	/** Runs the day's figures were summed over. The denominator. */
	runs: number;
}

/** Absolute tokens per day, never a share.
 *
 * The decision this answers is "would a bigger cache save wall clock", and a
 * share over a shrinking prompt is not that: a day that read half as much and
 * cached the same fraction draws an identical bar. The share is printed beside
 * the bar because it is worth knowing, and it is never the geometry.
 */
export function cacheByDay(runs: readonly MachineRun[]): CacheDay[] {
	const byDate = new Map<string, { read: number; cached: number; runs: number }>();
	for (const run of runs) {
		if (run.promptTokens.value === null || run.cachedTokens.value === null) continue;
		const bucket = byDate.get(run.date) ?? { read: 0, cached: 0, runs: 0 };
		bucket.read += run.promptTokens.value;
		bucket.cached += run.cachedTokens.value;
		bucket.runs += 1;
		byDate.set(run.date, bucket);
	}
	return [...byDate.entries()]
		.map(([date, bucket]) => ({
			date,
			read: bucket.read,
			cached: bucket.cached,
			cachedPct:
				bucket.read + bucket.cached > 0
					? Math.round((bucket.cached / (bucket.read + bucket.cached)) * 100)
					: null,
			runs: bucket.runs
		}))
		.sort((a, b) => a.date.localeCompare(b.date));
}

/** The cache as a stacked column a day. No threshold marker and no health tint:
 * nobody has agreed a floor, and a tint would invent one and publish it.
 *
 * The same array draws as two lines, which is the other half of the question:
 * stacked says how many prompt tokens the day needed, lines say whether the
 * read half fell while the cached half rose. Nothing is re-shaped between them.
 */
export function cacheChart(days: readonly CacheDay[], shape: StackShape = 'bars') {
	const plot = stacked(
		// The same date grammar the hand-written axes print. `2026-08-25` is how
		// the ledger spells a day, and a ledger spelling is not a label.
		days.map((day) => dayMonth(day.date)),
		[
			{ label: 'Read', token: '--chart-1', values: days.map((day) => day.read) },
			{ label: 'Served from cache', token: '--chart-3', values: days.map((day) => day.cached) }
		],
		shape
	);
	// A day here reaches seven digits, which is two more than the shared inset
	// was drawn for. The gutter is returned as well as applied, so the readout
	// strip's column centres are computed from the same number the engine laid
	// the plot out with rather than from a copy that can drift.
	const grid = { left: valueGutter(Math.max(0, ...plot.totals)), right: 12 };
	if (!plot.empty) plot.option.grid = { ...plot.option.grid, ...grid };
	return { ...plot, grid };
}

/** Both halves of one day's prompt tokens, for the strip under the chart. */
export function cacheColumns(days: readonly CacheDay[]): DayReadout[] {
	return days.map((day) => ({
		x: 0,
		date: day.date,
		rows: [
			{ label: 'Read', value: grouped(day.read), colour: 'var(--chart-1)' },
			{ label: 'Served from cache', value: grouped(day.cached), colour: 'var(--chart-3)' }
		]
	}));
}

// ---------------------------------------------------------------------------
// Peak memory, per shard and in one number
// ---------------------------------------------------------------------------

/** One shard's own memory high-water mark, against the runner's. */
export interface ShardMemory {
	shard: number;
	bytes: number;
	marks: TargetMarks;
}

/** What one run did to the runner's 16 GB.
 *
 * The aggregate is a MAXIMUM and never a sum. Shards are separate jobs on
 * separate hosts, so adding four of them reports a machine that never existed -
 * and it would read as 50 GB on a box that has 16.
 */
export interface MemoryView {
	runId: string;
	date: string;
	/** Ascending by shard index. Only shards that reported the cell. */
	shards: ShardMemory[];
	/** The largest of those. Null where no shard reported one. */
	highWater: number | null;
	/** That figure against `RUNNER_MEMORY_BYTES`, whole percent. */
	pctOfRunner: number | null;
	marks: TargetMarks;
	/** Shards that reported the cell, and shards the run split into. */
	from: number;
	/** Null where the run's manifest recorded no shard count, which is unknown
	 * and is drawn as unknown - never as the count of who answered. */
	outOf: number | null;
	empty: boolean;
}

/** The run's own memory high-water mark, and every shard behind it.
 *
 * The item ledger's `llama_rss_peak_bytes` landed on 2026-08-30, so most
 * committed rows are blank in
 * it. A blank is drawn as absence: this returns only the shards that reported,
 * and carries the run's shard count beside them so the page can say how much of
 * the run the figure covers rather than treating an unmeasured shard as a shard
 * that used no memory.
 */
export function peakMemory(run: MachineRun | null): MemoryView {
	const reported =
		run === null
			? []
			: run.reported
					.filter((shard): shard is ShardCounters & { peakRssBytes: number } =>
						shard.peakRssBytes !== null
					)
					.sort((a, b) => a.shard - b.shard);
	const highWater = reported.length === 0 ? null : Math.max(...reported.map((s) => s.peakRssBytes));
	return {
		runId: run?.runId ?? '',
		date: run?.date ?? '',
		shards: reported.map((shard) => ({
			shard: shard.shard,
			bytes: shard.peakRssBytes,
			// Every bar is read against the same ceiling, so the four of them are
			// one picture rather than four differently scaled ones.
			marks: targetMarks(shard.peakRssBytes, RUNNER_MEMORY_BYTES, MEMORY_POLARITY)
		})),
		highWater,
		pctOfRunner: highWater === null ? null : Math.round((highWater / RUNNER_MEMORY_BYTES) * 100),
		marks: targetMarks(highWater, RUNNER_MEMORY_BYTES, MEMORY_POLARITY),
		from: reported.length,
		outOf: run?.shards ?? null,
		empty: highWater === null
	};
}

// ---------------------------------------------------------------------------
// Memory and load, at the item grain
// ---------------------------------------------------------------------------

/** How far the machine's own MemTotal may sit from the runner's 16 GiB and
 * still be read as that runner.
 *
 * `/proc/meminfo` is not namespaced, so inside a container MemTotal reports the
 * HOST rather than the job. That makes it the one cell that can say the other
 * five OS cells are about the wrong machine. A tolerance is needed because
 * MemTotal excludes the memory the kernel reserved at boot, which is a low
 * single-digit percent of a 16 GiB box - so ten percent is wide enough never to
 * fire on a healthy runner and narrow enough to catch a host twice or half the
 * size. Stated once here for the same reason `CLOCKS_AGREE_WITHIN_PCT` is.
 */
export const MEM_TOTAL_AGREES_WITHIN_PCT = 10;

/** Which of the three grains the panel is drawing. */
export type MemoryGrain = 'item' | 'shard' | 'span';

/** What one item left the kernel, at its worst moment and at its last.
 *
 * Two ends and not one, because the pair separates two states nothing else on
 * this site can tell apart. A machine whose floor falls and whose end also
 * falls is leaking; one whose floor falls and whose end recovers was only
 * working hard. The floor alone reads the same on both.
 */
export interface HeadroomMark {
	/** The lowest MemAvailable seen while the model worked on this item. */
	floorBytes: number | null;
	/** MemAvailable when the item ended. */
	endBytes: number | null;
	floorWidth: string;
	endWidth: string;
	/** What the item gave back between those two. Null with either end missing,
	 * and negative where the item ended lower than its own recorded floor. */
	recoveredBytes: number | null;
	empty: boolean;
}

/** One item of one run: what it held, what it left, and what it queued. */
export interface ItemMemory {
	itemId: string;
	shard: number;
	/** The clock the run order is taken from. Empty where the row carried none,
	 * which puts the item last rather than first. */
	startedAt: string;
	/** llama-server's own high-water mark over this item. The figure a per-shard
	 * maximum hides, and the one that reaches five sixths of the ceiling. */
	peakBytes: number | null;
	/** The worker process when the item ended. A second process on the same box,
	 * and never added to the figure above without saying what the sum is. */
	workerBytes: number | null;
	peakWidth: string;
	workerWidth: string;
	headroom: HeadroomMark;
	/** The one-minute load when the item ended. Past the core count it is a
	 * queue, which is a different fact from a busy processor. */
	load: number | null;
	loadWidth: string;
	/** Processor busy over the item's model window, trough as fill and peak as
	 * notch. Near 100 on every row, which is why load is drawn beside it. */
	busy: RangeMark;
	/** True on the one item that owns the run's memory maximum. */
	worst: boolean;
}

/** Memory and machine load over one run, at every grain the panel offers.
 *
 * **A break panel.** It takes the extreme and the item that owns it, over every
 * item of one run. The verdict reading - how near the ceiling the run got - is
 * the shard grain, and it is here as the second grain rather than as a second
 * panel, because one measurement asked two questions is one panel.
 */
export interface MemoryBoardView {
	runId: string;
	date: string;
	/** One entry an item, in run order. The x every track here shares. */
	items: ItemMemory[];
	/** The shard grain, exactly as the peak-memory bars drew it. */
	shard: MemoryView;
	/** The largest any single item took the model server to. */
	itemHighWater: number | null;
	itemHighWaterPct: number | null;
	/** The item that owns that figure, by name. */
	worstItemId: string | null;
	/** The largest worker reading over the same items. */
	workerHighWater: number | null;
	/** The two maxima added. */
	bothHighWater: number | null;
	bothHighWaterPct: number | null;
	/** True only where both maxima fall on the SAME item. False makes the sum an
	 * upper bound rather than a reading, and the panel says which it is. */
	coPeak: boolean;
	/** What every byte figure here is drawn against. */
	ceilingBytes: number;
	/** The byte domain every byte track shares: the ceiling and every drawn
	 * value, so a reading past the ceiling draws past the line rather than
	 * stopping on it, and the grains stay comparable across the switch. */
	scaleBytes: number;
	/** The machine's own MemTotal, where the rows carried one. */
	measuredTotalBytes: number | null;
	/** Every distinct MemTotal the drawn rows carried, ascending. More than one
	 * entry is a run that drew two machine sizes, which is itself a finding. */
	totalsSeen: number[];
	/** Whether that total reads as the runner we believe we are on. Null where
	 * no row carried one, which is unknown rather than agreement. */
	totalAgrees: boolean | null;
	/** The highest load any item of the run ended under. */
	loadHigh: number | null;
	/** Cores the run's hosts let the jobs see. The smaller where they disagree,
	 * for the same reason the memory denominator takes the smaller. */
	cores: number | null;
	load: TargetMarks;
	/** Processor busy across the whole run, trough to peak. */
	busySpan: RangeMark;
	/** Items that carried a memory reading, and items the run's shards counted.
	 * Null where no shard recorded its own item count. */
	from: number;
	outOf: number | null;
	/** Items that carried each of the three tracks. A track no item measured is
	 * a sentence rather than a row of marks with nothing in them. */
	heldFrom: number;
	headroomFrom: number;
	loadFrom: number;
	itemsEmpty: boolean;
	loadEmpty: boolean;
	empty: boolean;
}

function numberCell(row: Record<string, string>, name: string): number | null {
	const text = (row[name] ?? '').trim();
	if (text === '') return null;
	const value = Number(text);
	return Number.isFinite(value) ? value : null;
}

function smallest(values: readonly (number | null)[]): number | null {
	const known = values.filter((value): value is number => value !== null);
	return known.length === 0 ? null : Math.min(...known);
}

function widthOf(value: number | null, scale: number): string {
	return percentOf(value === null || scale <= 0 ? 0 : Math.min(value / scale, 1));
}

/** One run's memory and load, item by item, with the shard grain beside it.
 *
 * `health` is the item ledger, bounded by the caller; only the handed run's own
 * rows are read. The denominator is the machine's own MemTotal where the rows
 * carried one and the runner's 16 GiB where they did not - and the two are
 * printed together, because a MemTotal that disagrees with the runner is the
 * tell that every other OS cell is about a different machine.
 *
 * The domain takes the ceiling in beside the drawn values rather than as its
 * maximum, so an item past the ceiling still draws past the line.
 */
export function memoryBoard(
	run: MachineRun | null,
	health: readonly Record<string, string>[]
): MemoryBoardView {
	const shard = peakMemory(run);
	const runId = run?.runId ?? '';
	const rows = runId === '' ? [] : health.filter((row) => (row.run_id ?? '') === runId);

	// The smaller of two totals, per decision 8: a run that drew two machine
	// sizes is read against the smaller of them, because the smaller is the one
	// that could have run out.
	const totalsSeen = [
		...new Set(rows.map((row) => numberCell(row, 'os_mem_total_bytes')).filter((v): v is number => v !== null))
	].sort((left, right) => left - right);
	const measuredTotalBytes = totalsSeen[0] ?? null;
	const totalAgrees =
		measuredTotalBytes === null
			? null
			: Math.abs(measuredTotalBytes - RUNNER_MEMORY_BYTES) / RUNNER_MEMORY_BYTES <=
				MEM_TOTAL_AGREES_WITHIN_PCT / 100;
	const denominator = measuredTotalBytes ?? RUNNER_MEMORY_BYTES;

	const drawn = rows.filter(
		(row) =>
			numberCell(row, 'llama_rss_peak_bytes') !== null ||
			numberCell(row, 'python_rss_bytes') !== null ||
			numberCell(row, 'os_mem_available_min_bytes') !== null ||
			numberCell(row, 'os_mem_available_bytes') !== null
	);
	// Run order, from the item's own clock. A row with no clock has no place in
	// that order, so it follows the ones that have rather than opening the strip.
	const ordered = [...drawn].sort((left, right) => {
		const leftAt = (left.item_started_at ?? '').trim();
		const rightAt = (right.item_started_at ?? '').trim();
		if (leftAt === '' && rightAt === '') return (left.item_id ?? '').localeCompare(right.item_id ?? '');
		if (leftAt === '') return 1;
		if (rightAt === '') return -1;
		return leftAt.localeCompare(rightAt);
	});

	const peaks = ordered
		.map((row) => numberCell(row, 'llama_rss_peak_bytes'))
		.filter((value): value is number => value !== null);
	const workers = ordered
		.map((row) => numberCell(row, 'python_rss_bytes'))
		.filter((value): value is number => value !== null);
	const floors = ordered
		.map((row) => numberCell(row, 'os_mem_available_min_bytes'))
		.filter((value): value is number => value !== null);
	const ends = ordered
		.map((row) => numberCell(row, 'os_mem_available_bytes'))
		.filter((value): value is number => value !== null);

	const itemHighWater = peaks.length === 0 ? null : Math.max(...peaks);
	const workerHighWater = workers.length === 0 ? null : Math.max(...workers);
	const worstRow =
		itemHighWater === null
			? null
			: (ordered.find((row) => numberCell(row, 'llama_rss_peak_bytes') === itemHighWater) ?? null);
	const worstItemId = worstRow === null ? null : (worstRow.item_id ?? '').trim() || null;
	// The two maxima added is a reading only where one item held both. Anywhere
	// else it is arithmetic over two moments that never met.
	const coPeak =
		worstRow !== null &&
		workerHighWater !== null &&
		numberCell(worstRow, 'python_rss_bytes') === workerHighWater;

	// Every byte track on the panel runs to this, ceiling included, so a reading
	// past the ceiling draws past the line rather than stopping on it.
	const scaleBytes = Math.max(denominator, ...peaks, ...workers, ...floors, ...ends);

	const loads = ordered
		.map((row) => numberCell(row, 'load_1m'))
		.filter((value): value is number => value !== null);
	const loadHigh = loads.length === 0 ? null : Math.max(...loads);
	const cores = run === null ? null : smallest(run.reported.map((one) => one.cores));
	const loadScale = Math.max(loadHigh ?? 0, cores ?? 0);
	const busyLow = smallest(ordered.map((row) => numberCell(row, 'cpu_busy_min')));
	const busyHighs = ordered
		.map((row) => numberCell(row, 'cpu_busy_max'))
		.filter((value): value is number => value !== null);

	const items: ItemMemory[] = ordered.map((row) => {
		const floorBytes = numberCell(row, 'os_mem_available_min_bytes');
		const endBytes = numberCell(row, 'os_mem_available_bytes');
		const peakBytes = numberCell(row, 'llama_rss_peak_bytes');
		const workerBytes = numberCell(row, 'python_rss_bytes');
		const load = numberCell(row, 'load_1m');
		return {
			itemId: (row.item_id ?? '').trim(),
			shard: numberCell(row, 'shard') ?? 0,
			startedAt: (row.item_started_at ?? '').trim(),
			peakBytes,
			workerBytes,
			peakWidth: widthOf(peakBytes, scaleBytes),
			workerWidth: widthOf(workerBytes, scaleBytes),
			headroom: {
				floorBytes,
				endBytes,
				floorWidth: widthOf(floorBytes, scaleBytes),
				endWidth: widthOf(endBytes, scaleBytes),
				recoveredBytes: floorBytes === null || endBytes === null ? null : endBytes - floorBytes,
				empty: floorBytes === null && endBytes === null
			},
			load,
			loadWidth: widthOf(load, loadScale),
			busy: rangeMark(numberCell(row, 'cpu_busy_min'), numberCell(row, 'cpu_busy_max'), 100),
			// The one row, not every row that ties with it. Two items that reached
			// the same byte are a tie the panel names once, because "the item that
			// owns the maximum" has to be an item a reader can go and look at.
			worst: row === worstRow
		};
	});

	const bothHighWater =
		itemHighWater === null || workerHighWater === null ? null : itemHighWater + workerHighWater;
	const share = (value: number | null) =>
		value === null ? null : Math.round((value / denominator) * 100);
	// Items the shards said they had, which is a different number from the items
	// that carried a reading. One count a shard, summed over the shards that
	// recorded one - never the largest, which would report one shard's work as
	// the run's. Null where no shard counted, because an unknown total is not
	// the count of who answered.
	const planned = new Map<number, number>();
	for (const row of rows) {
		const count = numberCell(row, 'shard_item_count');
		const at = numberCell(row, 'shard');
		if (count !== null && at !== null) planned.set(at, count);
	}

	return {
		runId,
		date: run?.date ?? '',
		items,
		shard,
		itemHighWater,
		itemHighWaterPct: share(itemHighWater),
		worstItemId,
		workerHighWater,
		bothHighWater,
		bothHighWaterPct: share(bothHighWater),
		coPeak,
		ceilingBytes: denominator,
		scaleBytes,
		measuredTotalBytes,
		totalsSeen,
		totalAgrees,
		loadHigh,
		cores,
		load: targetMarks(loadHigh, cores ?? 0, 'lower-is-better'),
		busySpan: rangeMark(busyLow, busyHighs.length === 0 ? null : Math.max(...busyHighs), 100),
		from: items.length,
		outOf: planned.size === 0 ? null : sum([...planned.values()]),
		heldFrom: peaks.length,
		headroomFrom: items.filter((one) => !one.headroom.empty).length,
		loadFrom: loads.length,
		itemsEmpty: items.length === 0,
		loadEmpty: loadHigh === null && busyLow === null && busyHighs.length === 0,
		empty: items.length === 0 && shard.empty
	};
}

// ---------------------------------------------------------------------------
// The two clocks, compared
// ---------------------------------------------------------------------------

export interface ClockPair {
	/** `shard 2` where the item ledger carries a shard, the run id otherwise. */
	label: string;
	/** Prompt tokens a second, as the item ledger counted them. */
	ledger: number | null;
	/** The same, as llama-server counted them. */
	server: number | null;
	/** How far the ledger sits from the server, as a percent of the server. */
	gapPct: number | null;
	/** Null where nothing was compared. Never `false` by default. */
	agrees: boolean | null;
}

export interface ClockView {
	/** Which grain the ledger allowed. */
	grain: 'shard' | 'run';
	pairs: ClockPair[];
	/** Item rows that carry a shard, and item rows in the set. The sentence the
	 * panel prints about its own grain is derived from these two. */
	shardRows: number;
	itemRows: number;
	tolerancePct: number;
	/** Pairs that disagree by more than the tolerance. */
	disagreeing: number;
	empty: boolean;
}

/** One item row's read tokens and read milliseconds, or nothing.
 *
 * `input_tokens - cached_tokens` is the definition, and it is defined HERE
 * rather than in the reader so there is exactly one of it: the runtime reused
 * the cached ones instead of reading them, so leaving them in reports a rate
 * the machine never ran at. `poolLedger` in `$lib/server/machine-counters.ts`
 * calls this, which is why that module imports a chart module rather than the
 * other way round for this one function.
 *
 * neither direction, so it is skipped rather than counted as an item that read
 * nothing.
 */
export function itemRead(
	row: Record<string, string>
): { tokens: number; ms: number } | null {
	const ms = cell(row.prefill_ms);
	const input = cell(row.input_tokens);
	if (ms === null || input === null) return null;
	return { tokens: input - (cell(row.cached_tokens) ?? 0), ms };
}

/** An empty cell is absent, never zero. The same rule the reader applies. */
function cell(value: string | undefined): number | null {
	if (value === undefined || value === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

/** Prompt tokens a second over a set of item rows, summed and then divided.
 *
 * Sum over sum, never a mean of per-item rates: a rate is a ratio, and
 * averaging ratios weighs a release note like a feature.
 */
export function pooledReadRate(rows: readonly Record<string, string>[]): number | null {
	const reads = rows
		.map(itemRead)
		.filter((read): read is { tokens: number; ms: number } => read !== null);
	const ms = sum(reads.map((read) => read.ms));
	return ms > 0 ? sum(reads.map((read) => read.tokens)) / (ms / 1000) : null;
}

/** The two instruments, side by side, at the finest grain the ledgers allow.
 *
 * The runtime ledger was created for exactly this check and nothing performed
 * it on a screen. Both sides count prompt tokens actually read, so a gap is one
 * of the two instruments being wrong rather than the two measuring different
 * things.
 */
export function clockAgreement(
	run: MachineRun | null,
	health: readonly Record<string, string>[],
	tolerancePct: number
): ClockView {
	if (run === null) {
		return {
			grain: 'run',
			pairs: [],
			shardRows: 0,
			itemRows: 0,
			tolerancePct,
			disagreeing: 0,
			empty: true
		};
	}
	const mine = health.filter((row) => row.run_id === run.runId);
	const withShard = mine.filter((row) => (row.shard ?? '') !== '');
	const grain: ClockView['grain'] =
		withShard.length === mine.length && mine.length > 0 ? 'shard' : 'run';

	const pairs: ClockPair[] =
		grain === 'shard'
			? run.reported.map((shard) => {
					const rows = withShard.filter((row) => Number(row.shard) === shard.shard);
					return pair(
						`shard ${shard.shard}`,
						pooledReadRate(rows),
						shard.readTokensPerSecond,
						tolerancePct
					);
				})
			: [pair(run.runId, run.clocks.ledger.rate, run.clocks.server.rate, tolerancePct)];

	return {
		grain,
		pairs,
		shardRows: withShard.length,
		itemRows: mine.length,
		tolerancePct,
		disagreeing: pairs.filter((entry) => entry.agrees === false).length,
		empty: pairs.every((entry) => entry.gapPct === null)
	};
}

function pair(
	label: string,
	ledger: number | null,
	server: number | null,
	tolerancePct: number
): ClockPair {
	if (ledger === null || server === null || server <= 0) {
		return { label, ledger, server, gapPct: null, agrees: null };
	}
	const gapPct = (Math.abs(ledger - server) / server) * 100;
	return { label, ledger, server, gapPct, agrees: gapPct <= tolerancePct };
}

/** Two bars side by side, never stacked: they are two readings of one quantity,
 * and stacking would add a number to itself.
 *
 * No legend: the strip under the plot names both instruments in the colours
 * they are drawn in, at the column the reader is on. */
export function clocksChart(pairs: readonly ClockPair[]): {
	option: EChartsOption;
	empty: boolean;
} {
	const drawn = pairs.filter((entry) => entry.ledger !== null && entry.server !== null);
	if (drawn.length === 0) return { option: {}, empty: true };
	const bar = (name: string, token: ChartToken, pick: (entry: ClockPair) => number | null) => ({
		name,
		type: 'bar' as const,
		barMaxWidth: 22,
		itemStyle: { color: paint(token) },
		data: drawn.map((entry) => Number((pick(entry) ?? 0).toFixed(2)))
	});
	return {
		empty: false,
		option: {
			animation: false,
			grid: { left: 48, right: 12, top: 8, bottom: 26, containLabel: false },
			tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
			xAxis: {
				type: 'category',
				data: drawn.map((entry) => entry.label),
				axisLine: { lineStyle: { color: paint('--chart-axis') } },
				axisTick: { show: false },
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11, hideOverlap: true }
			},
			yAxis: {
				type: 'value',
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11 },
				splitLine: { lineStyle: { color: paint('--chart-grid') } }
			},
			series: [
				bar('Item ledger', '--chart-1', (entry) => entry.ledger),
				bar('Model server', '--chart-4', (entry) => entry.server)
			]
		}
	};
}

// ---------------------------------------------------------------------------
// The percentile curve
// ---------------------------------------------------------------------------

/** Both instruments at one column, for the strip under the clock chart.
 *
 * The panel exists to compare two readings of one quantity, and reading two
 * bars off a shared axis by eye is the thing it was built to stop.
 */
export function clockColumns(pairs: readonly ClockPair[]): DayReadout[] {
	return pairs
		.filter((pair) => pair.ledger !== null && pair.server !== null)
		.map((pair) => ({
			x: 0,
			date: pair.label,
			rows: [
				{
					label: 'Item ledger',
					value: `${(pair.ledger ?? 0).toFixed(2)} tok/s`,
					colour: 'var(--chart-1)'
				},
				{
					label: 'Model server',
					value: `${(pair.server ?? 0).toFixed(2)} tok/s`,
					colour: 'var(--chart-4)'
				},
				{ label: 'Apart', value: `${(pair.gapPct ?? 0).toFixed(2)}%`, colour: '' }
			]
		}));
}

/** One run's whole distribution, as the small multiples draw it.
 *
 * `ms` is one entry per `PERCENTILES`, in that order. An array rather than an
 * object because five charts read it by position and the page carries one of
 * these per run in the widest window.
 */
export interface LatencyRun {
	runId: string;
	date: string;
	items: number;
	ms: number[];
}

export interface LatencyHistory {
	/** Oldest first, so the newest run is the last mark on every multiple. */
	runs: LatencyRun[];
	/** Runs with too few items to quote a p99, and how few. Printed, never
	 * drawn: a p99 over four items is the fourth item. */
	tooFew: { runId: string; date: string; items: number }[];
	floor: number;
}

/** Every run's distribution, across every day the ledger holds.
 *
 * Never pooled between runs: two runs of one day draw different processors, and
 * the whole reason to plot a distribution rather than quote a p95 is that a tail
 * can change shape while every headline number holds still. The value is
 * `summarize_ms`, which is the whole model call for one item.
 */
export function percentileHistory(
	health: readonly Record<string, string>[],
	floor: number
): LatencyHistory {
	const byRun = new Map<string, { date: string; ms: number[] }>();
	for (const row of health) {
		const ms = Number(row.summarize_ms);
		if (row.summarize_ms === '' || !Number.isFinite(ms) || ms <= 0) continue;
		const runId = row.run_id ?? '';
		const bucket = byRun.get(runId) ?? { date: row.date ?? '', ms: [] };
		bucket.ms.push(ms);
		byRun.set(runId, bucket);
	}

	const runs: LatencyRun[] = [];
	const tooFew: { runId: string; date: string; items: number }[] = [];
	// Run ids are `<date>-<n>`, so a plain string sort orders a day's runs and
	// orders the days too.
	for (const runId of [...byRun.keys()].sort()) {
		const bucket = byRun.get(runId) as { date: string; ms: number[] };
		const values = [...bucket.ms].sort((a, b) => a - b);
		if (values.length < floor) {
			tooFew.push({ runId, date: bucket.date, items: values.length });
			continue;
		}
		runs.push({
			runId,
			date: bucket.date,
			items: values.length,
			// Whole milliseconds. The interpolation gives a fraction of one, and a
			// fraction of a millisecond is finer than anything this is printed at -
			// it would only be seventeen digits carried into the document.
			ms: PERCENTILES.map((percentile) => Math.round(quantile(values, percentile / 100)))
		});
	}

	return {
		runs,
		tooFew,
		floor
	};
}

/** Every percentile of one run, for the strip under the small multiples.
 *
 * No colour on any row. The five multiples are one measure at five quantiles
 * and are drawn in one colour, so a swatch would name a distinction that is not
 * on the plot.
 */
export function latencyColumns(runs: readonly LatencyRun[]): DayReadout[] {
	return runs.map((run) => ({
		x: 0,
		date: run.runId,
		rows: [
			...PERCENTILES.map((percentile, at) => ({
				label: `p${percentile}`,
				value: seconds((run.ms[at] ?? 0) / 1000),
				colour: ''
			})),
			{ label: 'Items timed', value: grouped(run.items), colour: '' }
		]
	}));
}

// ---------------------------------------------------------------------------
// What a run reads against what it writes, and what it would have cost
// ---------------------------------------------------------------------------

/** The two currencies a run's model work can be counted in. */
export type WorkUnit = 'tokens' | 'seconds';

/** Which unit the panel opens on, read by the server that draws the first
 * paint and by the browser that redraws it, so the two can never disagree.
 *
 * Seconds, because it is the true reading. Reading is batched prefill and
 * writing is sequential decode, so the taller token bar is the cheaper half of
 * the run - a panel that opens in tokens states the wrong answer first and
 * waits for the reader to find the switch. */
export const DEFAULT_WORK_UNIT: WorkUnit = 'seconds';

/** Past this, the smaller series draws under 5 percent and reads as zero, so
 * it takes its own row on a shared x rather than a sliver on a shared axis. */
export const SHARED_AXIS_LIMIT = 20;

export interface RunWork {
	runId: string;
	date: string;
	/** Every prompt token the run sent, cached ones included: a provider bills
	 * for the prompt it was given, not for the part its own cache missed. */
	input: number;
	output: number;
	/** Prefill and decode over the SAME item rows the two token counts came
	 * from. Null where none of those rows timed the model call: a run that was
	 * not timed did not take no time. */
	prefillMs: number | null;
	decodeMs: number | null;
	/** Items that reported both token counts. The denominator, and the row set
	 * both units are summed over. */
	items: number;
	/** Of those, the ones that also timed both halves of the model call. */
	timed: number;
}

export interface ReadWriteSummary {
	/** Runs carrying a duration. Zero is the seconds grain's absent state. */
	timedRuns: number;
	/** Larger over smaller, per unit, over every run drawn. Null where the unit
	 * has no reading or the smaller side is zero. */
	ratio: Record<WorkUnit, number | null>;
	/** Which side of the comparison is the taller one, per unit. The two
	 * disagreeing is the finding this panel exists to deliver. */
	taller: Record<WorkUnit, 'read' | 'written' | null>;
	/** Where that ratio passed `SHARED_AXIS_LIMIT` and the smaller series takes
	 * its own row. Measured rather than assumed. */
	split: Record<WorkUnit, boolean>;
}

export interface ReadWriteView extends ReadWriteSummary {
	runs: RunWork[];
}

/** What a run read against what it wrote, counted twice over one row set.
 *
 * **One call returns both units, and the row set is decided once.** A row
 * qualifies on its token counts; the durations are then summed over exactly
 * those rows. Two independent filters would let the two grains cover different
 * runs, and a panel whose grains disagree about what they measured cannot be
 * recovered by reading it harder.
 */
export function readAgainstWritten(health: readonly Record<string, string>[]): ReadWriteView {
	const byRun = new Map<
		string,
		{
			date: string;
			input: number;
			output: number;
			prefillMs: number;
			decodeMs: number;
			items: number;
			timed: number;
		}
	>();
	for (const row of health) {
		const input = cell(row.input_tokens);
		const output = cell(row.output_tokens);
		if (input === null || output === null) continue;
		const runId = row.run_id ?? '';
		const bucket = byRun.get(runId) ?? {
			date: row.date ?? '',
			input: 0,
			output: 0,
			prefillMs: 0,
			decodeMs: 0,
			items: 0,
			timed: 0
		};
		bucket.input += input;
		bucket.output += output;
		bucket.items += 1;
		const prefill = cell(row.prefill_ms);
		const decode = cell(row.decode_ms);
		if (prefill !== null && decode !== null) {
			bucket.prefillMs += prefill;
			bucket.decodeMs += decode;
			bucket.timed += 1;
		}
		byRun.set(runId, bucket);
	}
	const runs: RunWork[] = [...byRun.entries()]
		.map(([runId, bucket]) => ({
			runId,
			date: bucket.date,
			input: bucket.input,
			output: bucket.output,
			prefillMs: bucket.timed === 0 ? null : bucket.prefillMs,
			decodeMs: bucket.timed === 0 ? null : bucket.decodeMs,
			items: bucket.items,
			timed: bucket.timed
		}))
		.filter((run) => run.items > 0)
		.sort((a, b) => a.runId.localeCompare(b.runId));

	const total = (pick: (run: RunWork) => number | null): number | null => {
		const drawn = runs.map(pick).filter((value): value is number => value !== null);
		return drawn.length === 0 ? null : drawn.reduce((carry, value) => carry + value, 0);
	};
	const pair = (read: number | null, written: number | null) => {
		if (read === null || written === null) {
			return { ratio: null, taller: null, split: false } as const;
		}
		const high = Math.max(read, written);
		const low = Math.min(read, written);
		const ratio = low === 0 ? null : high / low;
		return {
			ratio,
			taller: (read === written ? null : read > written ? 'read' : 'written') as
				| 'read'
				| 'written'
				| null,
			split: ratio !== null && ratio > SHARED_AXIS_LIMIT
		};
	};
	const counted = pair(total((run) => run.input), total((run) => run.output));
	const clocked = pair(total((run) => run.prefillMs), total((run) => run.decodeMs));
	return {
		runs,
		timedRuns: runs.filter((run) => run.timed > 0).length,
		ratio: { tokens: counted.ratio, seconds: clocked.ratio },
		taller: { tokens: counted.taller, seconds: clocked.taller },
		split: { tokens: counted.split, seconds: clocked.split }
	};
}

/** What one run's two sides measure in the open unit, or nothing.
 *
 * Milliseconds leave as seconds here and nowhere else, so the axis, the strip
 * and the readout are one conversion rather than three.
 */
export function workValues(
	run: RunWork,
	unit: WorkUnit
): { read: number | null; written: number | null } {
	if (unit === 'tokens') return { read: run.input, written: run.output };
	return {
		read: run.prefillMs === null ? null : run.prefillMs / 1000,
		written: run.decodeMs === null ? null : run.decodeMs / 1000
	};
}

/** One group a run: what it read beside what it wrote, in the open unit.
 *
 * **Two bars a group and one linear domain, because the comparison IS the
 * panel.** Two plots with a domain each let both series fill their own box, and
 * a reader who wants to know which half of the run costs more learns nothing
 * from two full boxes.
 *
 * **Past `SHARED_AXIS_LIMIT` the smaller series takes its own row on a shared
 * x.** Two grids, same categories, larger on top - the ratio is measured before
 * the shape is picked, and the page prints the ratio it measured. On the
 * committed ledger neither unit reaches the limit, so this is the degradation
 * and not the panel.
 *
 * The axis carries the run's DAY and not its run id. A run id is now
 * `<date>-<workflow run>`, and turned 45 degrees, measured 2026-09-01 on the
 * built console, seventeen of them made fourteen overlapping pairs at 1440 -
 * the worst two sat 67.9px on top of each other - and every one of them hung
 * 60.6px below the chart's own box. `hideOverlap` kept them all, because the
 * engine measures a turned label along the axis and not across the box it
 * actually draws. Horizontal short dates cost nothing a reader wanted: the run
 * id is in the strip below at the bar the pointer is on, in full.
 *
 * The engine's own `hideOverlap` does the thinning here rather than `dayTicks`,
 * and that is the difference between the two kinds of axis. `dayTicks` measures
 * against pixels we own; an engine relays out its own axis at every width, so a
 * label set computed at the authored width would be the wrong set at all the
 * others.
 */
export function workChart(
	runs: readonly RunWork[],
	summary: ReadWriteSummary,
	unit: WorkUnit
): { option: EChartsOption; empty: boolean; grid: { left: number; right: number } } {
	const values = runs.map((run) => workValues(run, unit));
	const read = values.map((value) => value.read);
	const written = values.map((value) => value.written);
	const drawn = [...read, ...written].filter((value): value is number => value !== null);
	const grid = { left: valueGutter(Math.max(0, ...drawn)), right: 12 };
	if (drawn.length === 0) return { option: {}, empty: true, grid };

	const name = unit === 'tokens' ? 'tokens' : 'seconds';
	const dates = runs.map((run) => dayMonth(run.date));
	const category = (extra: Record<string, unknown>) => ({
		type: 'category' as const,
		data: dates,
		axisLine: { lineStyle: { color: paint('--chart-axis') } },
		axisTick: { show: false },
		axisLabel: {
			color: paint('--color-text-tertiary'),
			fontSize: 10,
			hideOverlap: true
		},
		...extra
	});
	const value = (title: string, extra: Record<string, unknown>) => ({
		type: 'value' as const,
		name: title,
		nameTextStyle: { color: paint('--color-text-tertiary'), fontSize: 11 },
		axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11 },
		splitLine: { lineStyle: { color: paint('--chart-grid') } },
		...extra
	});
	const bar = (title: string, token: ChartToken, data: (number | null)[], at: number) => ({
		name: title,
		type: 'bar' as const,
		barMaxWidth: 24,
		itemStyle: { color: paint(token) },
		xAxisIndex: at,
		yAxisIndex: at,
		data
	});
	const READ = { title: 'Read', token: '--chart-1' as ChartToken, data: read };
	const WRITTEN = { title: 'Written', token: '--chart-4' as ChartToken, data: written };

	if (!summary.split[unit]) {
		return {
			empty: false,
			grid,
			option: {
				animation: false,
				// 30 at the top for the axis name, 26 at the bottom now that no label
				// is turned. The 14px that buys goes back to the plot.
				grid: { ...grid, top: 30, bottom: 26, containLabel: false },
				tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
				xAxis: category({}),
				yAxis: value(name, {}),
				series: [
					bar(READ.title, READ.token, READ.data, 0),
					bar(WRITTEN.title, WRITTEN.token, WRITTEN.data, 0)
				]
			}
		};
	}

	const readTotal = read.reduce<number>((carry, entry) => carry + (entry ?? 0), 0);
	const writtenTotal = written.reduce<number>((carry, entry) => carry + (entry ?? 0), 0);
	const [top, below] = readTotal >= writtenTotal ? [READ, WRITTEN] : [WRITTEN, READ];
	return {
		empty: false,
		grid,
		option: {
			animation: false,
			// Percentages rather than pixels: the renderer is handed a height and
			// the two rows have to divide whatever it is.
			grid: [
				{ ...grid, top: 30, height: '34%', containLabel: false },
				{ ...grid, top: '62%', bottom: 26, containLabel: false }
			],
			tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
			// One pointer over both rows, so a run is read on both at once.
			axisPointer: { link: [{ xAxisIndex: 'all' }] },
			// The top row borrows the bottom row's labels rather than printing the
			// same dates twice.
			xAxis: [
				category({ gridIndex: 0, axisLabel: { show: false } }),
				category({ gridIndex: 1 })
			],
			yAxis: [
				value(`${top.title.toLowerCase()}, ${name}`, { gridIndex: 0 }),
				value(`${below.title.toLowerCase()}, ${name}`, { gridIndex: 1 })
			],
			series: [
				bar(top.title, top.token, top.data, 0),
				bar(below.title, below.token, below.data, 1)
			]
		}
	};
}

/** A price per million tokens, and the currency it is quoted in. */
export interface CostRate {
	currency: string;
	inputPerMillion: number;
	outputPerMillion: number;
}

/** What a run's tokens would have cost at somebody else's price.
 *
 * A counterfactual and never a bill: nothing bills us, because Actions minutes
 * are free on a public repository (Guardrail #2). What this answers is the question
 * the wall clock cannot - whether four hours of runner time was a good trade -
 * and CLAUDE.md Guardrail #10 carries the owner's carve-out for it, on the condition
 * that the rate and its source are printed beside the figure.
 */
export function costOf(tokens: { input: number; output: number }, rate: CostRate): number {
	return (
		(tokens.input * rate.inputPerMillion + tokens.output * rate.outputPerMillion) / 1_000_000
	);
}

/** Money as digits and an ISO code, never a symbol.
 *
 * `toLocaleString` reads the machine's locale and two builds have to agree, and
 * a currency symbol in front of a number is exactly the shape a bill takes.
 *
 * **A real cost never prints as zero.** An amount above nothing that rounds away
 * at the decimals asked for comes back as `<0.01 USD`, the same rule the console
 * already applies to a millisecond total: a `0` there would say the work was
 * free, and the work was not free.
 */
export function money(amount: number, currency: string, decimals = 2): string {
	const floor = Math.pow(10, -decimals);
	if (amount > 0 && amount < floor / 2) return `<${floor.toFixed(decimals)} ${currency}`;
	const rounded = amount.toFixed(decimals);
	const [whole, fraction] = rounded.split('.');
	const separated = grouped(Number(whole));
	return `${fraction === undefined ? separated : `${separated}.${fraction}`} ${currency}`;
}
