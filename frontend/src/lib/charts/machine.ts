/** What the machine did, drawn from what the model server itself counted.
 *
 * `$lib/server/runtime-counters.ts` reads `state/runtime-counters.csv` and hands
 * back one figure per shard and per run. This module turns those figures into
 * the six things an operator can act on: which shard was slow and why, whether
 * the seconds went on reading or on writing, whether the prompt cache is
 * earning its keep, how much of the context window a run actually used, whether
 * the two clocks agree, and what a run's tokens would have cost somewhere else.
 *
 * Every function here is pure and every one takes its ceiling as an argument,
 * so a test drives it from a fixture ledger and Rule #6 keeps the knobs in
 * `config/`. Nothing reaches the disk and nothing reaches the network.
 *
 * **An empty cell is unknown and never zero.** The reader hands absence through
 * as `null` and so does this module: a figure that did not run leaves here as
 * `null` and a component prints a dash or a sentence. A zero is a measurement.
 */

import type { EChartsOption } from 'echarts';
import type { RunCounters, ShardCounters } from '$lib/server/runtime-counters';
import { dayMonth } from '../format';
import type { DayReadout } from './frame';
import { percentOf } from './rank';
import { grouped } from './series';
import { stacked, type StackShape } from './stacked';
import { targetMarks, type TargetMarks } from './targetbar';
import { paint, type ChartToken } from './theme';

/** The runner's memory, from CLAUDE.md Rule #2: 4 vCPU, 16 GB RAM, no GPU.
 *
 * A constant and not a `config/` knob, for the same reason `PAGES_CAP_BYTES` in
 * `glance.ts` is a constant: it is a property of the platform we run on, not a
 * preference anybody may tune. Turning it into a knob would let a run that no
 * longer fits be made to look as though it did.
 */
export const RUNNER_MEMORY_BYTES = 16 * 1024 * 1024 * 1024;

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
	readSeconds: number | null;
	writeSeconds: number | null;
	/** The two together. Null unless the shard reported both. */
	modelSeconds: number | null;
	/** CSS lengths for the two segments, against the heaviest shard's total, so
	 * a short row means a short shard rather than a differently scaled bar. */
	readWidth: string;
	writeWidth: string;
	readTokensPerSecond: number | null;
	/** The processor, as the text `/proc/cpuinfo` printed. Null on a shard that
	 * ran before the cell existed - which is absence, not an unknown machine. */
	cpuModel: string | null;
	cpuBusyPct: number | null;
	jobSeconds: number | null;
	/** The job clock against `run.shard_timeout_minutes`. */
	job: TargetMarks;
}

export interface ShardBoardView {
	runId: string;
	date: string;
	/** Ranked by job clock, slowest first. A shard with no clock cannot be
	 * ranked, so it follows in shard order rather than being dropped. */
	rows: BoardRow[];
	/** Shards the run split into. `rows.length` is short of it when a shard's
	 * job died before it scraped. */
	shards: number;
	/** The fastest reader over the slowest. Null with fewer than two readers -
	 * one shard cannot spread against itself. */
	readSpread: number | null;
	/** The seconds the widest bar stands for. Every row shares it. */
	scaleSeconds: number;
	/** What the job clock is measured against, in seconds. Null unconfigured. */
	timeoutSeconds: number | null;
	/** Shards that named a processor, and shards the run had. */
	cpuKnown: number;
	empty: boolean;
}

function modelSeconds(shard: ShardCounters): number | null {
	return shard.readSeconds === null || shard.writeSeconds === null
		? null
		: shard.readSeconds + shard.writeSeconds;
}

/** One run as one row per shard, ranked by the clock the timeout applies to.
 *
 * Ranked by the job clock rather than by model seconds, because the job clock
 * is the one the platform kills a shard on: the row at the top is the shard
 * that would be killed first.
 */
export function shardBoard(
	run: RunCounters | null,
	timeoutSeconds: number | null
): ShardBoardView {
	if (run === null || run.reported.length === 0) {
		return {
			runId: run?.runId ?? '',
			date: run?.date ?? '',
			rows: [],
			shards: run?.shards ?? 0,
			readSpread: null,
			scaleSeconds: 0,
			timeoutSeconds,
			cpuKnown: 0,
			empty: true
		};
	}

	const totals = run.reported
		.map(modelSeconds)
		.filter((value): value is number => value !== null);
	const scaleSeconds = totals.length === 0 ? 0 : Math.max(...totals);

	const ordered = [...run.reported].sort((a, b) => {
		// A shard with no clock has no rank. It goes last, in shard order, rather
		// than being sorted as though its clock were zero.
		if (a.jobSeconds === null && b.jobSeconds === null) return a.shard - b.shard;
		if (a.jobSeconds === null) return 1;
		if (b.jobSeconds === null) return -1;
		return b.jobSeconds - a.jobSeconds;
	});

	const rows: BoardRow[] = ordered.map((shard) => ({
		shard: shard.shard,
		readSeconds: shard.readSeconds,
		writeSeconds: shard.writeSeconds,
		modelSeconds: modelSeconds(shard),
		readWidth: percentOf(scaleSeconds > 0 ? (shard.readSeconds ?? 0) / scaleSeconds : 0),
		writeWidth: percentOf(scaleSeconds > 0 ? (shard.writeSeconds ?? 0) / scaleSeconds : 0),
		readTokensPerSecond: shard.readTokensPerSecond,
		cpuModel: shard.cpuModel,
		cpuBusyPct: shard.cpuBusyPct,
		jobSeconds: shard.jobSeconds,
		job: targetMarks(shard.jobSeconds, timeoutSeconds ?? 0, 'lower-is-better')
	}));

	return {
		runId: run.runId,
		date: run.date,
		rows,
		shards: run.shards,
		readSpread: run.readSpread.value,
		scaleSeconds,
		timeoutSeconds,
		cpuKnown: run.cpuModels.from,
		empty: false
	};
}

// ---------------------------------------------------------------------------
// Reading against writing
// ---------------------------------------------------------------------------

/** One 100-percent row: what share of a quantity went to reading. */
export interface SplitRow {
	/** `Seconds` or `Tokens`. */
	label: string;
	readValue: number;
	writeValue: number;
	readWidth: string;
	writeWidth: string;
	/** Reading's share, whole percent. */
	readPct: number;
	/** The absolute total, already formatted with its unit. */
	totalText: string;
	readText: string;
	writeText: string;
}

export interface SplitView {
	runId: string;
	rows: SplitRow[];
	readTokensPerSecond: number | null;
	writeTokensPerSecond: number | null;
	/** How many read tokens one written token costs. Null unless both rates are
	 * known - a ratio against an absent rate is not a ratio. */
	writeCostRatio: number | null;
	/** Shards that reported all four cells, and shards the run had. */
	from: number;
	outOf: number;
	empty: boolean;
}

/** The two rows whose disagreement is the whole panel.
 *
 * Reading and writing are two different machines: measured on this ledger read
 * speed varies more than 4x inside one run and write speed barely moves. One
 * bar showing "model seconds" hides that, so nothing on this site ever draws
 * one. Both rows come off the same shard set, so the mismatch between them is a
 * fact about the model rather than about which shards answered which question.
 */
export function readingAgainstWriting(run: RunCounters | null): SplitView {
	const whole =
		run === null
			? []
			: run.reported.filter(
					(shard) =>
						shard.readSeconds !== null &&
						shard.writeSeconds !== null &&
						shard.promptTokens !== null &&
						shard.writtenTokens !== null
				);
	if (run === null || whole.length === 0) {
		return {
			runId: run?.runId ?? '',
			rows: [],
			readTokensPerSecond: null,
			writeTokensPerSecond: null,
			writeCostRatio: null,
			from: 0,
			outOf: run?.shards ?? 0,
			empty: true
		};
	}

	const readSeconds = sum(whole.map((shard) => shard.readSeconds ?? 0));
	const writeSeconds = sum(whole.map((shard) => shard.writeSeconds ?? 0));
	const readTokens = sum(whole.map((shard) => shard.promptTokens ?? 0));
	const writeTokens = sum(whole.map((shard) => shard.writtenTokens ?? 0));

	const row = (
		label: string,
		read: number,
		write: number,
		unit: (value: number) => string
	): SplitRow => {
		const total = read + write;
		const fraction = total > 0 ? read / total : 0;
		return {
			label,
			readValue: read,
			writeValue: write,
			readWidth: percentOf(fraction),
			writeWidth: percentOf(1 - fraction),
			readPct: Math.round(fraction * 100),
			totalText: unit(total),
			readText: unit(read),
			writeText: unit(write)
		};
	};

	// Sum over sum, never a mean of per-shard rates: averaging ratios weighs a
	// shard that read 20 items like one that read 40.
	const readRate = readSeconds > 0 ? readTokens / readSeconds : null;
	const writeRate = writeSeconds > 0 ? writeTokens / writeSeconds : null;

	return {
		runId: run.runId,
		rows: [
			row('Seconds', readSeconds, writeSeconds, (value) => seconds(value)),
			row('Tokens', readTokens, writeTokens, (value) => `${grouped(Math.round(value))} tokens`)
		],
		readTokensPerSecond: readRate,
		writeTokensPerSecond: writeRate,
		writeCostRatio: readRate !== null && writeRate !== null && writeRate > 0 ? readRate / writeRate : null,
		from: whole.length,
		outOf: run.shards,
		empty: false
	};
}

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
export function cacheByDay(runs: readonly RunCounters[]): CacheDay[] {
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
	return stacked(
		// The same date grammar the hand-written axes print. `2026-08-25` is how
		// the ledger spells a day, and a ledger spelling is not a label.
		days.map((day) => dayMonth(day.date)),
		[
			{ label: 'Read', token: '--chart-1', values: days.map((day) => day.read) },
			{ label: 'Served from cache', token: '--chart-3', values: days.map((day) => day.cached) }
		],
		shape
	);
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
// Context headroom
// ---------------------------------------------------------------------------

export interface ContextBar {
	runId: string;
	date: string;
	/** The longest sequence any shard of the run saw, prompt plus generation. */
	longest: number | null;
	usedPct: number | null;
	spare: number | null;
	marks: TargetMarks;
	from: number;
	outOf: number;
}

/** The longest thing a run read, against the window it was given.
 *
 * A counter without its ceiling is not a measurement: 4,925 says nothing until
 * 8,192 sits beside it. This is also the one panel that says whether raising
 * the truncation cap is even possible.
 */
export function contextHeadroom(
	runs: readonly RunCounters[],
	contextWindow: number | null
): ContextBar[] {
	// The share is computed from the window handed in, never from the one the
	// reader happened to hold: a test that drives a different ceiling has to see a
	// different share, or the argument is decoration.
	const share = (longest: number | null): number | null =>
		longest === null || contextWindow === null || contextWindow <= 0
			? null
			: Math.round((longest / contextWindow) * 100);
	return runs.map((run) => ({
		runId: run.runId,
		date: run.date,
		longest: run.longestSequence.value,
		usedPct: share(run.longestSequence.value),
		spare:
			run.longestSequence.value === null || contextWindow === null
				? null
				: contextWindow - run.longestSequence.value,
		marks: targetMarks(run.longestSequence.value, contextWindow ?? 0, 'lower-is-better'),
		from: run.longestSequence.from,
		outOf: run.longestSequence.outOf
	}));
}

// ---------------------------------------------------------------------------
// Do the two clocks agree
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
 * the machine never ran at. `poolLedger` in `$lib/server/runtime-counters.ts`
 * calls this, which is why that module imports a chart module rather than the
 * other way round for this one function.
 *
 * A row missing either required cell predates token capture and is evidence in
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
	run: RunCounters | null,
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

export interface PercentilePoint {
	percentile: number;
	ms: number;
}

export interface PercentileCurve {
	runId: string;
	items: number;
	points: PercentilePoint[];
}

export interface PercentileView {
	/** The day the curves came off. Null where the ledger held none. */
	date: string | null;
	curves: PercentileCurve[];
	/** Runs with too few items to quote a p99, and how few. Printed, never drawn:
	 * a p99 over four items is the fourth item. */
	tooFew: { runId: string; items: number }[];
	floor: number;
	/** Item rows of that day carrying a shard, and item rows of that day. */
	shardRows: number;
	itemRows: number;
	empty: boolean;
}

/** One curve a run, across the percentiles, never pooled between runs.
 *
 * Pooling would average a host lottery: two runs of one day draw different
 * processors, and the whole reason to plot a distribution rather than quote a
 * p95 is that a tail can change shape while every headline number holds still.
 * The value is `summarize_ms`, which is the whole model call for one item.
 */
export function percentileCurves(
	health: readonly Record<string, string>[],
	date: string | null,
	floor: number
): PercentileView {
	if (date === null) {
		return {
			date: null,
			curves: [],
			tooFew: [],
			floor,
			shardRows: 0,
			itemRows: 0,
			empty: true
		};
	}
	const day = health.filter((row) => row.date === date);
	const byRun = new Map<string, number[]>();
	for (const row of day) {
		const ms = Number(row.summarize_ms);
		if (row.summarize_ms === '' || !Number.isFinite(ms) || ms <= 0) continue;
		byRun.set(row.run_id ?? '', [...(byRun.get(row.run_id ?? '') ?? []), ms]);
	}

	const curves: PercentileCurve[] = [];
	const tooFew: { runId: string; items: number }[] = [];
	for (const runId of [...byRun.keys()].sort()) {
		const values = [...(byRun.get(runId) ?? [])].sort((a, b) => a - b);
		if (values.length < floor) {
			tooFew.push({ runId, items: values.length });
			continue;
		}
		curves.push({
			runId,
			items: values.length,
			points: PERCENTILES.map((percentile) => ({
				percentile,
				ms: quantile(values, percentile / 100)
			}))
		});
	}

	return {
		date,
		curves,
		tooFew,
		floor,
		shardRows: day.filter((row) => (row.shard ?? '') !== '').length,
		itemRows: day.length,
		empty: curves.length === 0
	};
}

/** Every point labelled with its value. A curve with unlabelled points is a
 * shape nobody can quote.
 *
 * No legend: the strip under the plot names every run in the colour its curve
 * is drawn in. The top inset is the room a point's own label needs, not the
 * room a legend took. */
export function percentileChart(curves: readonly PercentileCurve[]): {
	option: EChartsOption;
	empty: boolean;
} {
	if (curves.length === 0) return { option: {}, empty: true };
	const tokens: ChartToken[] = ['--chart-1', '--chart-2', '--chart-3', '--chart-4', '--chart-5'];
	return {
		empty: false,
		option: {
			animation: false,
			grid: { left: 60, right: 44, top: 20, bottom: 26, containLabel: false },
			tooltip: { trigger: 'axis' },
			xAxis: {
				type: 'category',
				data: PERCENTILES.map((percentile) => `p${percentile}`),
				axisLine: { lineStyle: { color: paint('--chart-axis') } },
				axisTick: { show: false },
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11 }
			},
			yAxis: {
				type: 'value',
				name: 'seconds',
				nameTextStyle: { color: paint('--color-text-tertiary'), fontSize: 11 },
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11 },
				splitLine: { lineStyle: { color: paint('--chart-grid') } }
			},
			series: curves.map((curve, index) => ({
				name: curve.runId,
				type: 'line' as const,
				symbolSize: 7,
				lineStyle: { color: paint(tokens[index % tokens.length]), width: 2 },
				itemStyle: { color: paint(tokens[index % tokens.length]) },
				label: {
					show: true,
					position: 'top' as const,
					fontSize: 10,
					color: paint('--color-text-tertiary'),
					// A template rather than a callback: the value is already in seconds
					// and one decimal, so there is nothing left to compute.
					formatter: '{c}s'
				},
				data: curve.points.map((point) => Number((point.ms / 1000).toFixed(1)))
			}))
		}
	};
}

// ---------------------------------------------------------------------------
// Tokens, and what they would have cost somewhere else
// ---------------------------------------------------------------------------

/** Every run's reading at one percentile, for the strip under the curves.
 *
 * Two curves that cross are the fact this panel was drawn for, and a crossing
 * is exactly where reading one curve at a time stops working.
 */
export function percentileColumns(curves: readonly PercentileCurve[]): DayReadout[] {
	const tokens: ChartToken[] = ['--chart-1', '--chart-2', '--chart-3', '--chart-4', '--chart-5'];
	return PERCENTILES.map((percentile, at) => ({
		x: 0,
		date: `p${percentile}`,
		rows: curves.map((curve, index) => ({
			label: curve.runId,
			value: seconds(curve.points[at]?.ms === undefined ? null : curve.points[at].ms / 1000),
			colour: `var(${tokens[index % tokens.length]})`
		}))
	}));
}

export interface RunTokens {
	runId: string;
	date: string;
	/** Every prompt token the run sent, cached ones included: a provider bills
	 * for the prompt it was given, not for the part its own cache missed. */
	input: number;
	output: number;
	/** Items that reported both counts. The denominator. */
	items: number;
}

export function tokensByRun(health: readonly Record<string, string>[]): RunTokens[] {
	const byRun = new Map<string, { date: string; input: number; output: number; items: number }>();
	for (const row of health) {
		if (row.input_tokens === '' || row.output_tokens === '') continue;
		const input = Number(row.input_tokens);
		const output = Number(row.output_tokens);
		if (!Number.isFinite(input) || !Number.isFinite(output)) continue;
		const runId = row.run_id ?? '';
		const bucket = byRun.get(runId) ?? { date: row.date ?? '', input: 0, output: 0, items: 0 };
		bucket.input += input;
		bucket.output += output;
		bucket.items += 1;
		byRun.set(runId, bucket);
	}
	return [...byRun.entries()]
		.map(([runId, bucket]) => ({ runId, ...bucket }))
		.filter((run) => run.items > 0)
		.sort((a, b) => a.runId.localeCompare(b.runId));
}

/** One bar a run. Input and output are separate charts because they are
 * separate quantities with separate prices, and a shared axis would flatten
 * whichever of them is smaller into nothing. */
export function tokenChart(
	runs: readonly RunTokens[],
	pick: (run: RunTokens) => number,
	label: string,
	token: ChartToken
): { option: EChartsOption; empty: boolean } {
	if (runs.length === 0) return { option: {}, empty: true };
	return {
		empty: false,
		option: {
			animation: false,
			grid: { left: 62, right: 12, top: 16, bottom: 40, containLabel: false },
			tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
			xAxis: {
				type: 'category',
				data: runs.map((run) => run.runId),
				axisLine: { lineStyle: { color: paint('--chart-axis') } },
				axisTick: { show: false },
				axisLabel: {
					color: paint('--color-text-tertiary'),
					fontSize: 10,
					hideOverlap: true,
					rotate: 45
				}
			},
			yAxis: {
				type: 'value',
				name: label,
				nameTextStyle: { color: paint('--color-text-tertiary'), fontSize: 11 },
				axisLabel: { color: paint('--color-text-tertiary'), fontSize: 11 },
				splitLine: { lineStyle: { color: paint('--chart-grid') } }
			},
			series: [
				{
					name: label,
					type: 'bar' as const,
					barMaxWidth: 24,
					itemStyle: { color: paint(token) },
					data: runs.map((run) => pick(run))
				}
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
 * are free on a public repository (Rule #2). What this answers is the question
 * the wall clock cannot - whether four hours of runner time was a good trade -
 * and CLAUDE.md Rule #10 carries the owner's carve-out for it, on the condition
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
