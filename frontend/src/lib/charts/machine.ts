/** What the native machine charts read from the independent clocks and article rows.
 *
 * An empty cell is unknown and never zero. The counters hand absence through
 * as null and so does this module: a zero is a measurement.
 */

import { rankedList, type RankedGeometry } from './d3/rankedList';
import type { MachineRun } from '$lib/console/machine/counters';
import type { SeriesInput } from './d3/dateSeries';
import { compareRuns } from '../console/queries/shared';
import { readoutOf, type Readout, type ReadoutInput } from './readout';
import { grouped } from './series';

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
 * the machine never ran at. `poolLedger` in the native machine counters
 * calls this, which is why that module imports a chart module rather than the
 * other way round for this one function.
 *
 * A row without either instrument is skipped, not counted as reading nothing.
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
	const withShard = mine.filter((row) => (row.machine_shard ?? '') !== '');
	const grain: ClockView['grain'] =
		withShard.length === mine.length && mine.length > 0 ? 'shard' : 'run';

	const pairs: ClockPair[] =
		grain === 'shard'
			? run.reported.map((shard) => {
					const rows = withShard.filter((row) => Number(row.machine_shard) === shard.shard);
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

/** Rank each measured gap against the rule, retaining both independent readings. */
export function clocksChart(pairs: readonly ClockPair[], tolerancePct: number): RankedGeometry | null {
	return rankedList(pairs.flatMap((pair) => pair.gapPct === null ? [] : [{
		label: pair.label,
		value: pair.gapPct,
		context: `item ledger ${pair.ledger?.toFixed(2)}; server ${pair.server?.toFixed(2)} tokens a second`,
		...(pair.agrees === false ? { status: 'disagrees' } : {})
	}]), { rules: [{ at: tolerancePct, label: 'Allowed disagreement' }] });
}

// ---------------------------------------------------------------------------
// The percentile curve
// ---------------------------------------------------------------------------

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
	for (const runId of [...byRun.keys()].sort(compareRuns)) {
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
export function latencyColumns(
	runs: readonly LatencyRun[],
	events?: ReadoutInput['events']
): Readout {
	return readoutOf({
		type: 'dateSeries',
		columns: runs.map((run) => run.runId),
		series: [
			...PERCENTILES.map((percentile, at) => ({
				label: `p${percentile}`,
				swatch: null,
				values: runs.map((run) => run.ms[at] ?? 0),
				format: (ms: number) => seconds(ms / 1000)
			})),
			{
				label: 'Items timed',
				swatch: null,
				values: runs.map((run) => run.items),
				format: (value: number) => grouped(value)
			}
		],
		...(events === undefined ? {} : { events }),
		notMeasured: 'This run timed no item',
		resting: 'last'
	});
}

// ---------------------------------------------------------------------------
// What a run reads against what it writes, and what it would have cost
// ---------------------------------------------------------------------------

/** The two currencies a run's model work can be counted in. */
export type WorkUnit = 'tokens' | 'seconds';

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

export interface ReadWriteView {
	runs: RunWork[];
}

/** What a run read against what it wrote, counted twice over one row set.
 *
 * One call returns both units, and the row set is decided once. A row
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

	return { runs };
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

/** Dated totals over the same qualified runs, with unmeasured seconds left unknown. */
export function workSeries(runs: readonly RunWork[], unit: WorkUnit): SeriesInput[] {
	const days = new Map<string, { read: number | null; written: number | null }>();
	for (const run of runs) {
		const values = workValues(run, unit);
		const day = days.get(run.date) ?? { read: null, written: null };
		if (values.read !== null) day.read = (day.read ?? 0) + values.read;
		if (values.written !== null) day.written = (day.written ?? 0) + values.written;
		days.set(run.date, day);
	}
	const dated = [...days].sort(([left], [right]) => left.localeCompare(right));
	return [
		{ label: `Read ${unit}`, token: '--chart-6',
			points: dated.map(([date, values]) => ({ date, value: values.read })) },
		{ label: `Written ${unit}`, token: '--chart-7',
			points: dated.map(([date, values]) => ({ date, value: values.written })) }
	];
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
 * A real cost never prints as zero. An amount above nothing that rounds away
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
