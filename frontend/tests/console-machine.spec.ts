/** Every figure the Machine route draws, recomputed by hand.
 *
 * Each oracle below computes its expected value from the fixture rows in this
 * file, never from the module's own output - otherwise the assertion only
 * proves the module agrees with itself. Where a figure is read off the
 * committed ledger, the assertion is a structural one (segments sum to their
 * total, a ceiling comes from config) rather than a literal, because the
 * pipeline publishes several times a day and a literal would rot by morning.
 *
 * Pure functions and committed ledgers only. No browser, no SvelteKit alias, no
 * `$app` import: a spec that reaches one fails the whole suite at load rather
 * than failing one test.
 */

import { expect, test } from './support/browser';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { contextReadings, countersFrom, processors, textRows, shardCounts, slowerMachines } from '../src/lib/console/machine/records';
import { reuseDays } from '../src/lib/console/machine/prompt-reuse';
import { slowestArticles } from '../src/lib/console/pipelines/slowest-articles';
import { rankedList } from '../src/lib/charts/d3/rankedList';
import { fleetJobs } from '../src/lib/charts/fleet';
import { machineKeys } from '../src/lib/charts/machine-colour';
import { machineRamp } from '../src/lib/charts/machine-colour';
import { shardPhases } from '../src/lib/console/machine/shard-phases';
import { machinePhases } from '../src/lib/console/machine/machine-phases';
import {
	percentileHistory,
	quantile,
	readAgainstWritten,
	workSeries,
	workValues,
	PERCENTILES,
	type RunWork
} from '../src/lib/charts/machine';
import {
	carriesServerCounters,
	machineCounters,
	type MachineLimits,
	type MachineRun
} from '../src/lib/console/machine/counters';
import { dateSeries, numberFormat } from './support/number-format';
import { frame } from '../src/lib/charts/frame';
import { articleCost, runnerHourSeconds } from '../src/lib/console/machine/article-cost';
import { describeRefusedRuns } from '../src/lib/console/machine/refused-runs';
import { hostRow, ledgers, plan, type ShardReading } from './support/machine-rows';

/** `config/idhazh.json` read straight off disk, so a test's expectation comes
 * from the committed file rather than from the reader it is checking. */
const CONFIG = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')
) as {
	run: { shard_timeout_minutes: number };
	models_file: string;
};

/** The native chart's width and height, from the same configuration it reads. */
const CHART_WIDTH = (
	JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
	) as { chart: { width_px: number } }
).chart.width_px;

/** `chart.height_px`, which is what a stacked band's height is a share of. */
const CHART_HEIGHT = (
	JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
	) as { chart: { height_px: number } }
).chart.height_px;

/** The active model, reached through the pointer and never by filename. */
const MODELS = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', CONFIG.models_file), 'utf8')
) as { summarizer: { server: { '--ctx-size': number } } };

const LIMITS: MachineLimits = {
	contextWindow: MODELS.summarizer.server['--ctx-size'],
	jobTimeoutSeconds: CONFIG.run.shard_timeout_minutes * 60
};

test('phase totals and weighted rates keep shards separate and exclude incomplete identities or timings', () => {
	const row = { date: '2026-11-01', run_id: '2026-11-01-1', machine_job: 'work', machine_shard: 0,
		cpu_model: 'cpu-a', input_tokens: 300, cached_tokens: 100, output_tokens: 100, prefill_ms: 1000, decode_ms: 2000 };
	const work = shardPhases([
		row,
		{ ...row, input_tokens: 500, output_tokens: 200, prefill_ms: 4000, decode_ms: 1000 },
		{ ...row, machine_shard: 1, prefill_ms: 4000, decode_ms: 4000 },
		{ ...row, run_id: '2026-11-01-2' },
		{ ...row, cached_tokens: null },
		{ ...row, prefill_ms: 0 },
		{ ...row, machine_shard: null }
	], []);
	expect(work.excluded).toBe(3);
	expect(work.shards).toHaveLength(3);
	expect(work.shards.find((shard) => shard.label.endsWith('shard 1'))).toMatchObject({
		articles: 1, prefill: 4, decode: 4, total: 8, prefillTps: 50, decodeTps: 25, prefillShare: 50
	});
	expect(work.shards.find((shard) => shard.articles === 2)).toMatchObject({
		articles: 2, prefill: 5, decode: 3, prefillTps: 120, decodeTps: 100, prefillShare: 62.5
	});
	expect(shardPhases([{ ...row, decode_ms: null }], []).shards).toEqual([]);
});

test('shard hardware joins by date, run, task and shard; unknown and conflicting L3 never borrow a CPU peer reading', () => {
	const item = { date: '2026-11-01', run_id: '2026-11-01-1', machine_job: 'work', machine_shard: 0,
		machine_pipeline_name: 'digest', machine_task_name: 'summarize', cpu_model: 'same-cpu',
		input_tokens: 300, cached_tokens: 100, output_tokens: 100, prefill_ms: 1000, decode_ms: 2000 };
	const host = { date: item.date, run_id: item.run_id, job: 'work', shard: 0,
		pipeline_name: 'digest', task_name: 'summarize', cpu_model: 'Intel(R) Xeon(R) measured', l3_cache_bytes: 0 };
	const hosts = [
		host, { ...host, l3_cache_bytes: null }, { ...host, run_id: '2026-11-01-2', l3_cache_bytes: 99 },
		{ ...host, date: '2026-11-02', l3_cache_bytes: 100 }, { ...host, shard: 1, l3_cache_bytes: 101 },
		{ ...host, pipeline_name: 'other', l3_cache_bytes: 102 },
		{ ...host, task_name: 'judge', cpu_model: 'AMD measured', l3_cache_bytes: 128 },
		{ ...host, task_name: 'judge', cpu_model: 'AMD measured', l3_cache_bytes: 256 }
	];
	const work = shardPhases([item, { ...item, machine_task_name: 'judge' }, { ...item, machine_shard: 2 }], hosts);
	expect(work.shards.find((shard) => shard.label.includes('digest/summarize') && shard.label.endsWith('shard 0')))
		.toMatchObject({ cpuModels: ['Intel(R) Xeon(R) measured'], l3CacheBytes: [0] });
	expect(work.shards.find((shard) => shard.label.includes('digest/judge')))
		.toMatchObject({ cpuModels: ['AMD measured'], l3CacheBytes: [128, 256] });
	expect(work.shards.find((shard) => shard.label.endsWith('shard 2')))
		.toMatchObject({ cpuModels: ['same-cpu'], l3CacheBytes: [] });
});

test('hardware phase means weight articles, not shards or runs, and phase rates weight measured seconds', () => {
	const item = { date: '2026-11-01', run_id: '2026-11-01-1', machine_job: 'work', machine_shard: 0,
		cpu_model: 'cpu-a', input_tokens: 300, cached_tokens: 100, output_tokens: 100, prefill_ms: 1000, decode_ms: 2000 };
	const work = machinePhases([
		item,
		{ ...item, input_tokens: 500, output_tokens: 200, prefill_ms: 4000, decode_ms: 1000 },
		{ ...item, machine_shard: 1, prefill_ms: 4000, decode_ms: 4000 },
		{ ...item, run_id: '2026-11-01-2' },
		{ ...item, decode_ms: null }
	], []);
	expect(work.excluded).toBe(1);
	expect(work.machines).toHaveLength(1);
	expect(work.machines[0]).toMatchObject({
		cpuModels: ['cpu-a'], l3CacheBytes: [], articles: 4, shards: 3,
		prefill: 2.5, decode: 2.25, total: 4.75, prefillTps: 100
	});
	expect(work.machines[0].decodeTps).toBeCloseTo(500 / 9);
	expect(work.machines[0].prefillShare).toBeCloseTo(100 * 10 / 19);
	expect(machinePhases([{ ...item, prefill_ms: 0 }], []).machines).toEqual([]);
});

test('hardware phase groups keep CPU models and distinct, zero, missing or conflicting L3 readings separate', () => {
	const item = { date: '2026-11-01', run_id: '2026-11-01-1', machine_job: 'work',
		cpu_model: 'cpu-a', input_tokens: 300, cached_tokens: 100, output_tokens: 100, prefill_ms: 1000, decode_ms: 2000 };
	const host = { date: item.date, run_id: item.run_id, job: 'work', cpu_model: 'cpu-a' };
	const work = machinePhases([
		...[0, 1, 2, 3, 4, 5].map((machine_shard) => ({ ...item, machine_shard })),
		{ ...item, machine_shard: 6, cpu_model: 'cpu-b' }
	], [
		{ ...host, shard: 0, l3_cache_bytes: 128 },
		{ ...host, shard: 1, l3_cache_bytes: 128 },
		{ ...host, shard: 2, l3_cache_bytes: 256 },
		{ ...host, shard: 3, l3_cache_bytes: 0 },
		{ ...host, shard: 5, l3_cache_bytes: 128 },
		{ ...host, shard: 5, l3_cache_bytes: 256 },
		{ ...host, shard: 6, cpu_model: 'cpu-b', l3_cache_bytes: 128 }
	]);
	expect(work.machines).toHaveLength(6);
	expect(work.machines.find((machine) => machine.cpuModels[0] === 'cpu-a' &&
		machine.l3CacheBytes.length === 1 && machine.l3CacheBytes[0] === 128))
		.toMatchObject({ articles: 2, shards: 2, total: 3 });
	expect(work.machines.map((machine) => [machine.cpuModels, machine.l3CacheBytes])).toEqual(expect.arrayContaining([
		[['cpu-a'], [256]], [['cpu-a'], [0]], [['cpu-a'], []], [['cpu-a'], [128, 256]], [['cpu-b'], [128]]
	]));
});

function drawingOptions(stacked = false) {
	return {
		frame: frame(CHART_WIDTH, CHART_HEIGHT), stacked,
		density: 5, valueTicks: 4, padding: 0.2,
		rule: { declined: 'This compares recorded work, not a settings change.' }
	};
}

/** One shard of the fixture run, with the day and run every figure sits under. */
function shardOf(reading: ShardReading): ShardReading {
	return { date: '2026-09-04', runId: '2026-09-04-1', ...reading };
}

function healthRow(cells: Partial<Record<string, string | number>>): Record<string, string> {
	const blank: Record<string, string> = {
		date: '2026-09-04',
		run_id: '2026-09-04-1',
		item_id: 'item-0',
		stage: 'summarize',
		summarize_ms: '',
		prefill_ms: '',
		decode_ms: '',
		input_tokens: '',
		output_tokens: '',
		cached_tokens: '',
		machine_shard: ''
	};
	for (const [name, value] of Object.entries(cells)) blank[name] = String(value);
	return blank;
}

/** Two shards whose figures were chosen so every derived number can be checked
 * with a pencil: shard 0 reads 4x as fast as shard 1 and finishes sooner. */
const TWO_SHARDS: ShardReading[] = [
	{
		shard: 0,
		serverPromptTokens: 8000,
		serverPromptSeconds: 200,
		cachedTokens: 2000,
		writtenTokens: 1000,
		writeSeconds: 200,
		longestSequence: 4096,
		jobSeconds: 600,
		cpuModel: 'INTEL(R) XEON(R) PLATINUM 8573C',
		cpuBusyPct: 95,
		peakRssBytes: 8_000_000_000,
		modelLoadMs: 3000
	},
	{
		shard: 1,
		serverPromptTokens: 2000,
		serverPromptSeconds: 200,
		cachedTokens: 2000,
		writtenTokens: 1000,
		writeSeconds: 400,
		longestSequence: 2048,
		jobSeconds: 1200,
		cpuModel: 'AMD EPYC 7763 64-Core Processor',
		cpuBusyPct: 88,
		peakRssBytes: 9_000_000_000,
		modelLoadMs: 4000
	}
];

function runsOf(readings: ShardReading[], planned: [string, number][] = [['2026-09-04-1', 2]]) {
	const { hosts, health } = ledgers(readings.map(shardOf));
	return machineCounters(hosts, health, plan(...planned), LIMITS);
}

function onlyRun(readings: ShardReading[]): MachineRun {
	const { runs, refused } = runsOf(readings);
	expect(refused, 'the fixture was refused').toEqual([]);
	expect(runs).toHaveLength(1);
	return runs[0];
}

test.describe('native shard counter arithmetic', () => {
	const run = onlyRun(TWO_SHARDS);

	test('the job clock is measured against the configured timeout, not a literal', () => {
		expect(run.reported[1].jobUsedPct).toBe(Math.round(1200 / (CONFIG.run.shard_timeout_minutes * 60) * 100));
		const { hosts, health } = ledgers(TWO_SHARDS.map(shardOf));
		const tighter = machineCounters(hosts, health, plan(['2026-09-04-1', 2]),
			{ ...LIMITS, jobTimeoutSeconds: 1500 }).runs[0];
		expect(tighter.reported[1].jobUsedPct).toBe(80);
	});
});

/** The native counters read stored gaps separately from queue waits.
 *
 * The unclaimed figure is the one that matters. It is `stage_gap_ms` added over
 * the shard's items and nothing else - a page that worked it out from the stage
 * clocks would agree with them by construction, so it could never flag the one
 * thing the column exists to flag. The rows below carry NO stage clocks at all,
 * only the stored column, so an implementation that recomputed would have
 * nothing to recompute from and would draw an absence.
 */
test.describe('where a shard\u2019s clock went', () => {
	/** Two items on one shard, one of them with its clocks in disagreement. */
	const CLOCKED: ShardReading[] = [
		{
			shard: 0,
			itemId: 'item-0-a',
			serverPromptTokens: 8000,
			serverPromptSeconds: 200,
			cachedTokens: 2000,
			writtenTokens: 1000,
			writeSeconds: 200,
			jobSeconds: 600,
			modelLoadMs: 3000,
			unclaimedMs: 4321,
			queueWaitMs: 1000
		},
		{
			shard: 0,
			itemId: 'item-0-b',
			cachedTokens: 2000,
			writtenTokens: 1000,
			unclaimedMs: -2500,
			queueWaitMs: 5000
		},
		{
			shard: 1,
			itemId: 'item-1-a',
			serverPromptTokens: 2000,
			serverPromptSeconds: 200,
			cachedTokens: 2000,
			writtenTokens: 1000,
			writeSeconds: 100,
			jobSeconds: 1200,
			unclaimedMs: -9000,
			queueWaitMs: 60000
		}
	];

	const run = onlyRun(CLOCKED);
	const rowFor = (shard: number) => run.reported.find((row) => row.shard === shard)!;

	test('the count of disagreements survives a sum that cancels', () => {
		// Shard 0 adds to a positive 1.821 seconds, and one of its two items is
		// still below zero. A page that only carried the sum would print a healthy
		// shard and lose the item that disagreed.
		const row = rowFor(0);
		expect(row.unclaimedSeconds).toBeGreaterThan(0);
		expect(row.clocksDisagreed).toBe(1);
		expect(row.clockedItems).toBe(2);
	});
});

test.describe('the percentile curve', () => {
	test('the newest measured run follows the numeric run suffix, not lexical order', () => {
		const view = percentileHistory(['2026-09-04-10', '2026-09-04-9'].map((run_id) =>
			healthRow({ run_id, summarize_ms: run_id.endsWith('-10') ? 2000 : 1000 })), 1);
		expect(view.runs.map((run) => run.runId)).toEqual(['2026-09-04-9', '2026-09-04-10']);
		expect(view.runs.at(-1)?.ms[PERCENTILES.indexOf(90)]).toBe(2000);
	});
	test('the interpolation rule is the stated one, checked by hand', () => {
		const sorted = [1, 2, 3, 4, 5];
		// Position is (n - 1) x fraction, then linear between the two neighbours.
		expect(quantile(sorted, 0.5)).toBeCloseTo(3, 9);
		expect(quantile(sorted, 0.75)).toBeCloseTo(4, 9);
		expect(quantile(sorted, 0.9)).toBeCloseTo(4.6, 9);
		expect(quantile(sorted, 0.95)).toBeCloseTo(4.8, 9);
		expect(quantile(sorted, 0.99)).toBeCloseTo(4.96, 9);
		expect(quantile([7], 0.99)).toBe(7);
	});

	test('one row a run, and every point is the hand-computed quantile', () => {
		const ms = [10, 20, 30, 40, 50, 60];
		const health = ms.map((value, index) =>
			healthRow({ item_id: `a${index}`, summarize_ms: value })
		);
		const view = percentileHistory(health, 5);
		expect(view.runs).toHaveLength(1);
		expect(view.runs[0].items).toBe(6);
		expect(view.runs[0].ms).toHaveLength(PERCENTILES.length);
		// Positions 2.5, 3.75, 4.5, 4.75 and 4.95 interpolate to 35, 47.5,
		// 55, 57.5 and 59.5 ms; rounding follows interpolation.
		expect(view.runs[0].ms).toEqual([35, 48, 55, 58, 60]);
	});

	test('a run under the floor prints its count and draws no mark', () => {
		const health = [10, 20, 30].map((value, index) =>
			healthRow({ item_id: `b${index}`, summarize_ms: value })
		);
		const view = percentileHistory(health, 5);
		expect(view.runs).toEqual([]);
		expect(view.tooFew).toEqual([{ runId: '2026-09-04-1', date: '2026-09-04', items: 3 }]);
	});

	test('runs are never pooled together, because they drew different processors', () => {
		const health = [
			...[10, 20, 30, 40, 50].map((value, index) =>
				healthRow({ item_id: `c${index}`, summarize_ms: value })
			),
			...[100, 200, 300, 400, 500].map((value, index) =>
				healthRow({ item_id: `d${index}`, run_id: '2026-09-04-2', summarize_ms: value })
			)
		];
		const view = percentileHistory(health, 5);
		expect(view.runs.map((run) => run.runId)).toEqual(['2026-09-04-1', '2026-09-04-2']);
		// A pooled p50 over all ten would be 75. Neither run says that.
		expect(view.runs[0].ms[0]).toBe(30);
		expect(view.runs[1].ms[0]).toBe(300);
	});
});

test.describe('what a run reads against what it writes', () => {
	const health = [
		healthRow({
			item_id: 'x',
			input_tokens: 1_000_000,
			output_tokens: 200_000,
			prefill_ms: 40_000,
			decode_ms: 120_000
		}),
		healthRow({
			item_id: 'y',
			input_tokens: 500_000,
			output_tokens: 100_000,
			prefill_ms: 20_000,
			decode_ms: 60_000
		}),
		healthRow({
			item_id: 'z',
			run_id: '2026-09-04-2',
			input_tokens: 2000,
			output_tokens: 400,
			prefill_ms: 100,
			decode_ms: 300
		}),
		healthRow({ item_id: 'w', input_tokens: 999, output_tokens: '' })
	];

	test('a run is the sum of the items that reported both counts', () => {
		const view = readAgainstWritten(health);
		expect(view.runs.map((run) => run.runId)).toEqual(['2026-09-04-1', '2026-09-04-2']);
		// `w` reported no output, so it is not an item that wrote nothing.
		expect(view.runs[0]).toEqual({
			runId: '2026-09-04-1',
			date: '2026-09-04',
			input: 1_500_000,
			output: 300_000,
			prefillMs: 60_000,
			decodeMs: 180_000,
			items: 2,
			timed: 2
		});
	});

	test('both units are summed over one row set, and the row set is the token one', () => {
		// The same two rows answer both grains. A row admitted by one and refused
		// by the other would let the panel's two grains cover different runs.
		const view = readAgainstWritten(health);
		expect(view.runs.map((run) => run.items)).toEqual([2, 1]);
		expect(view.runs.map((run) => run.timed)).toEqual([2, 1]);
		// `w` is outside both: it is refused on its token counts, and its
		// durations are never reached.
		const untimed = readAgainstWritten([
			...health,
			healthRow({ item_id: 'v', input_tokens: 7, output_tokens: 3 })
		]);
		expect(untimed.runs[0].items).toBe(3);
		expect(untimed.runs[0].timed).toBe(2);
		// The extra row moves the count grain and leaves the clock alone, because
		// it carried tokens and no clock.
		expect(untimed.runs[0].input).toBe(1_500_007);
		expect(untimed.runs[0].prefillMs).toBe(60_000);
	});

	test('a run nobody timed draws no seconds and still draws its tokens', () => {
		const view = readAgainstWritten([
			healthRow({ item_id: 'x', input_tokens: 1000, output_tokens: 200 })
		]);
		expect(view.runs[0].input).toBe(1000);
		expect(view.runs[0].prefillMs).toBeNull();
		expect(view.runs[0].decodeMs).toBeNull();
		expect(view.runs[0].timed).toBe(0);
		expect(dateSeries(workSeries(view.runs, 'seconds'), drawingOptions())).toBeNull();
		expect(dateSeries(workSeries(view.runs, 'tokens'), drawingOptions())).not.toBeNull();
	});

	test('milliseconds reach the drawing as seconds, and absence stays absence', () => {
		const view = readAgainstWritten(health);
		expect(workValues(view.runs[0], 'tokens')).toEqual({ read: 1_500_000, written: 300_000 });
		expect(workValues(view.runs[0], 'seconds')).toEqual({ read: 60, written: 180 });
		const untimed = readAgainstWritten([
			healthRow({ item_id: 'x', input_tokens: 1000, output_tokens: 200 })
		]);
		expect(workValues(untimed.runs[0], 'seconds')).toEqual({ read: null, written: null });
	});

	test('native dated totals combine runs without making unmeasured seconds zero', () => {
		const runs: RunWork[] = [
			{ runId: 'one', date: '2026-09-01', input: 100, output: 20, prefillMs: 1000, decodeMs: 2000, items: 1, timed: 1 },
			{ runId: 'two', date: '2026-09-01', input: 200, output: 40, prefillMs: 3000, decodeMs: 4000, items: 1, timed: 1 },
			{ runId: 'unknown', date: '2026-09-02', input: 10, output: 2, prefillMs: null, decodeMs: null, items: 1, timed: 0 },
			{ runId: 'zero', date: '2026-09-03', input: 0, output: 0, prefillMs: 0, decodeMs: 0, items: 1, timed: 1 }
		];
		expect(workSeries(runs, 'tokens').map((series) => series.points.map((point) => point.value))).toEqual([
			[300, 10, 0], [60, 2, 0]
		]);
		expect(workSeries(runs, 'seconds').map((series) => series.points.map((point) => point.value))).toEqual([
			[4, null, 0], [6, null, 0]
		]);
	});

	test('token comparisons keep same-day runs in numeric order, including zeros and unmeasured runs', () => {
		const view = readAgainstWritten([
			healthRow({ run_id: '2026-09-04-10', item_id: 'missing' }),
			healthRow({ run_id: '2026-09-04-2', item_id: 'zero', input_tokens: 0, output_tokens: 0 }),
			healthRow({ item_id: 'measured', input_tokens: 40, output_tokens: 8 })
		]);
		expect(view.tokenRuns).toEqual([
			{ runId: '2026-09-04-1', date: '2026-09-04', total: { read: 40, written: 8 },
				median: { read: 40, written: 8 }, measured: 1, recorded: 1 },
			{ runId: '2026-09-04-2', date: '2026-09-04', total: { read: 0, written: 0 },
				median: { read: 0, written: 0 }, measured: 1, recorded: 1 },
			{ runId: '2026-09-04-10', date: '2026-09-04', total: { read: null, written: null },
				median: { read: null, written: null }, measured: 0, recorded: 1 }
		]);
		expect(view.runs.map((run) => run.runId)).toEqual(['2026-09-04-1', '2026-09-04-2']);
	});

	test('token totals and actual medians use the same paired finite nonnegative article cohort', () => {
		const view = readAgainstWritten([
			healthRow({ item_id: 'a', input_tokens: 0, cached_tokens: 0, output_tokens: 9 }),
			healthRow({ item_id: 'b', input_tokens: 4, cached_tokens: 4, output_tokens: 0 }),
			healthRow({ item_id: 'c', input_tokens: 100, cached_tokens: 90, output_tokens: 3 }),
			healthRow({ item_id: 'missing-output', input_tokens: 9999 }),
			healthRow({ item_id: 'negative-input', input_tokens: -1, output_tokens: 7 }),
			healthRow({ item_id: 'negative-output', input_tokens: 7, output_tokens: -2 }),
			healthRow({ item_id: 'infinite', input_tokens: 'Infinity', output_tokens: 8 }),
			healthRow({ item_id: 'invalid', input_tokens: 'invalid', output_tokens: 9 }),
			healthRow({ item_id: 'blank', input_tokens: '   ', output_tokens: 5 })
		]);
		expect(view.tokenRuns).toEqual([
			{ runId: '2026-09-04-1', date: '2026-09-04', total: { read: 104, written: 12 },
				median: { read: 4, written: 3 }, measured: 3, recorded: 9 }
		]);
		expect(view.runs[0]).toMatchObject({ input: 104, output: 12, items: 3 });
		expect(view.tokenRuns[0].median.read).not.toBe(104 / 3);
	});

	test('even article medians retain their half token without pooling runs or days', () => {
		const view = readAgainstWritten([
			healthRow({ item_id: 'a', input_tokens: 12344, output_tokens: 0 }),
			healthRow({ item_id: 'b', input_tokens: 12345, output_tokens: 1 }),
			healthRow({ run_id: '2026-09-04-2', item_id: 'c', input_tokens: 5, output_tokens: 3 })
		]);
		expect(view.tokenRuns.map((run) => run.median)).toEqual([
			{ read: 12344.5, written: 0.5 }, { read: 5, written: 3 }
		]);
		expect(readAgainstWritten([]).tokenRuns).toEqual([]);
	});
});

test.describe('a run the counters refuse, handed to every figure built from article rows', () => {
	// The route hands six figures every article row of the open window, chosen by
	// date alone, and `machineCounters` refuses a run where one shard filed two
	// machine records that disagree. So these cases build one refused run and one
	// accepted run on one day, hand each figure the article rows of both runs and
	// then of the accepted run alone, and record what the refused run moves. The
	// last two check the refused-runs box's words against what these find. The
	// thresholds are today's committed ones; no count below depends on them.
	const REFUSED = '2026-09-04-1';
	const ACCEPTED = '2026-09-04-2';
	const hosts = [
		hostRow({ date: '2026-09-04', runId: REFUSED, shard: 0, serverPromptTokens: 8000, serverPromptSeconds: 200 }),
		hostRow({ date: '2026-09-04', runId: REFUSED, shard: 1, serverPromptTokens: 2000, serverPromptSeconds: 200 }),
		// Shard 1 again, naming other figures: two servers answered for one shard.
		hostRow({ date: '2026-09-04', runId: REFUSED, shard: 1, serverPromptTokens: 1, serverPromptSeconds: 1 }),
		hostRow({ date: '2026-09-04', runId: ACCEPTED, shard: 0, serverPromptTokens: 3000, serverPromptSeconds: 100 })
	];
	/** One article on shard 0, carrying every cell the six figures read. */
	const article = (runId: string, index: number, cells: Partial<Record<string, string | number>>) =>
		healthRow({
			run_id: runId,
			item_id: `${runId}-${index}`,
			machine_shard: 0,
			item_index: index,
			n_ctx_configured: 8192,
			n_parallel: 1,
			...cells
		});
	const refusedRows = [
		article(REFUSED, 0, {
			input_tokens: 4000,
			output_tokens: 300,
			prefill_ms: 8000,
			decode_ms: 30_000,
			summary_input_tokens: 4000,
			summary_cached_tokens: 200,
			summary_output_tokens: 300,
			summary_finish_reason: 'length',
			cpu_busy_pct: 50,
			item_total_ms: 40_000,
			llama_rss_bytes: 6_000_000_000,
			cpu_steal_pct: 12,
			llama_major_faults: 148_000,
			os_mem_cached_bytes: 9_000_000_000,
			weights_pinned: 'False',
			summary_cache_pct: 5,
			summary_prefill_tokens_per_s: 12
		}),
		article(REFUSED, 1, {
			input_tokens: 6000,
			output_tokens: 300,
			prefill_ms: 12_000,
			decode_ms: 30_000,
			summary_input_tokens: 6000,
			summary_cached_tokens: 0,
			summary_output_tokens: 300,
			summary_finish_reason: 'length',
			cpu_busy_pct: 75,
			item_total_ms: 40_000,
			llama_rss_bytes: 6_400_000_000,
			cpu_steal_pct: 3,
			llama_major_faults: 4100,
			os_mem_cached_bytes: 6_000_000_000,
			weights_pinned: 'False',
			summary_cache_pct: 0,
			summary_prefill_tokens_per_s: 10
		})
	];
	const acceptedRows = [
		article(ACCEPTED, 0, {
			input_tokens: 1000,
			output_tokens: 200,
			prefill_ms: 2000,
			decode_ms: 20_000,
			summary_input_tokens: 1000,
			summary_cached_tokens: 800,
			summary_output_tokens: 200,
			summary_finish_reason: 'stop',
			cpu_busy_pct: 25,
			item_total_ms: 40_000,
			llama_rss_bytes: 5_000_000_000,
			cpu_steal_pct: 0.25,
			llama_major_faults: 148_000,
			os_mem_cached_bytes: 10_000_000_000,
			weights_pinned: 'True',
			summary_cache_pct: 80,
			summary_prefill_tokens_per_s: 40
		}),
		article(ACCEPTED, 1, {
			input_tokens: 2000,
			output_tokens: 200,
			prefill_ms: 3000,
			decode_ms: 20_000,
			summary_input_tokens: 2000,
			summary_cached_tokens: 1800,
			summary_output_tokens: 200,
			summary_finish_reason: 'stop',
			cpu_busy_pct: 25,
			item_total_ms: 60_000,
			llama_rss_bytes: 5_100_000_000,
			cpu_steal_pct: 0.5,
			llama_major_faults: 0,
			os_mem_cached_bytes: 10_000_000_000,
			weights_pinned: 'True',
			summary_cache_pct: 90,
			summary_prefill_tokens_per_s: 45
		})
	];
	const bothRuns = [...refusedRows, ...acceptedRows];

	test("a refused run whose machine records hold the server's own figures carries them", () => {
		// Shard 1's two records disagree, and each of them holds the server's two cells.
		const { refused } = machineCounters(hosts, bothRuns, plan([REFUSED, 2], [ACCEPTED, 1]), LIMITS);
		expect(refused.map((run) => [run.runId, run.serverCountersWritten])).toEqual([[REFUSED, true]]);
		expect(carriesServerCounters(refused[0])).toBe(true);
	});

	test('a refused run whose records disagree only about the machine carries no server figure', () => {
		// Shard 0 filed two records that name two machines, and neither holds a cell the server wrote.
		const { runs, refused } = machineCounters(
			[
				hostRow({ date: '2026-09-04', runId: REFUSED, shard: 0, fingerprint: 'f00d' }),
				hostRow({ date: '2026-09-04', runId: REFUSED, shard: 0, fingerprint: 'beef' })
			],
			refusedRows,
			plan([REFUSED, 2]),
			LIMITS
		);
		expect(runs).toEqual([]);
		expect(refused.map((run) => [run.runId, run.serverCountersWritten])).toEqual([[REFUSED, false]]);
		expect(refused[0].why).toContain('shard 0 filed two machine records that disagree');
		expect(carriesServerCounters(refused[0])).toBe(false);
	});

	test('the cost of one article counts it', () => {
		// The route joins the machine record's processor counts with no run left
		// out, so the refused run's shard names its processors too.
		const processors = [REFUSED, ACCEPTED].map((runId) => ({
			date: '2026-09-04',
			run_id: runId,
			shard: 0,
			cpu_logical_processors: 4
		}));
		const accepted = articleCost(acceptedRows, processors);
		expect(accepted.rowsRead).toBe(2);
		expect([accepted.processorSeconds.from, accepted.processorSeconds.high]).toEqual([2, 60]);
		expect([accepted.modelSeconds.from, accepted.modelSeconds.high]).toEqual([2, 23]);
		expect([accepted.addedBytes.from, accepted.addedBytes.high]).toEqual([1, 100_000_000]);
		const both = articleCost(bothRuns, processors);
		expect(both.rowsRead).toBe(4);
		expect([both.processorSeconds.from, both.processorSeconds.high]).toEqual([4, 120]);
		expect([both.modelSeconds.from, both.modelSeconds.high]).toEqual([4, 42]);
		expect([both.addedBytes.from, both.addedBytes.high]).toEqual([2, 400_000_000]);
	});

	test('the prompt reuse counts it', () => {
		const accepted = reuseDays(acceptedRows, 'summary');
		expect(accepted).toHaveLength(1);
		expect([accepted[0].input, accepted[0].cached, accepted[0].articles]).toEqual([3000, 2600, 2]);
		const both = reuseDays(bothRuns, 'summary');
		expect(both).toHaveLength(1);
		expect([both[0].input, both[0].cached, both[0].articles]).toEqual([13000, 2800, 4]);
	});

	test("the box says what leaves the run out and what still counts it, in Reader's words", () => {
		const { runs, refused } = machineCounters(
			hosts,
			bothRuns,
			plan([REFUSED, 2], [ACCEPTED, 1]),
			LIMITS
		);
		expect(runs).toHaveLength(1);
		expect(runs.filter(carriesServerCounters)).toHaveLength(1);
		expect(describeRefusedRuns(refused)).toEqual({
			head:
				'1 run has records that do not fit together. The run count above does not include it. ' +
				'Figures that pick articles by date still include the articles of this run.',
			runs: [
				{
					runId: REFUSED,
					says:
						'has 5 rows: shard 1 filed two machine records that disagree, so two servers ' +
						'answered for one shard and neither can be read over the other.'
				}
			]
		});
	});

	test('the box reads right for several runs and for a run of one row, and is absent with none', () => {
		const box = describeRefusedRuns([
			{
				runId: REFUSED,
				date: '2026-09-04',
				rows: 1,
				why: 'neither ledger holds a shard for this run',
				serverCountersWritten: false
			},
			{
				runId: '2026-09-03-1',
				date: '2026-09-03',
				rows: 4,
				why: 'its rows disagree about which day the run belongs to',
				serverCountersWritten: false
			}
		]);
		expect(box?.head).toBe(
			'2 runs have records that do not fit together. The run count above does not include them. ' +
				'Figures that pick articles by date still include the articles of these runs.'
		);
		expect(box?.runs.map((run) => run.says)).toEqual([
			'has 1 row: neither ledger holds a shard for this run.',
			'has 4 rows: its rows disagree about which day the run belongs to.'
		]);
		expect(describeRefusedRuns([])).toBeNull();
	});
});

test.describe('the Hardware browser redraws, from stated readings', () => {
	test('same-work comparisons keep reading and writing separate and omit runs without the reference', () => {
		const rows = [
			...Array.from({ length: 20 }, () => ({ run_id: 'one', cpu_model: 'A', input_tokens: 100, cached_tokens: 0, output_tokens: 10, prefill_ms: 1000, decode_ms: 1000 })),
			...Array.from({ length: 10 }, () => ({ run_id: 'one', cpu_model: 'B', input_tokens: 100, cached_tokens: 0, output_tokens: 10, prefill_ms: 2000, decode_ms: 500 })),
			{ run_id: 'two', cpu_model: 'B', input_tokens: 100, cached_tokens: 0, output_tokens: 10, prefill_ms: 9000, decode_ms: 9000 }
		];
		const actual = slowerMachines(rows);
		expect(actual.reference.cpuModel).toBe('A');
		expect(actual.reading.find((row) => row.label === 'B')).toMatchObject({ value: 2, range: { high: 2, count: 10 } });
		expect(actual.writing.find((row) => row.label === 'B')).toMatchObject({ value: 0.5, range: { high: 0.5, count: 10 } });
		expect(actual.withoutReference).toBe(1);
	});

	test('the slowest list names the newest numeric run and never stacks a negative gap', () => {
		const actual = slowestArticles([
			{ run_id: '2026-09-01-9', item_id: 'old', item_total_ms: 99000 },
			{ run_id: '2026-09-01-10', item_id: 'short', item_total_ms: 1000 },
			{ run_id: '2026-09-01-10', item_id: 'new', item_total_ms: 4000, fetch_ms: 1000, extract_ms: 1000,
				summarize_ms: 1000, faithfulness_ms: 2000, stage_gap_ms: -1000, queue_wait_ms: 500 }
		], numberFormat);
		expect(actual.run).toBe('2026-09-01-10');
		expect(actual.rows).toHaveLength(1);
		expect(actual.rows[0]).toMatchObject({ value: 4, context: 'queue wait 0.5 s; stages overlapped by 1 s' });
		expect(actual.rows[0]).not.toHaveProperty('segments');
	});

	test('the slowest list compares all measured shards before applying its row cap', () => {
		const run = '2026-09-01-10';
		const actual = slowestArticles([
			{ run_id: '2026-09-01-9', item_id: 'older', item_total_ms: 99000 },
			...[10000, 0, 2000, 5000, 1000, 2000, 2000].map((ms, shard) => ({
				run_id: run, item_id: `article-${shard}`, machine_shard: shard, item_total_ms: ms,
				queue_wait_ms: shard === 0 ? 0 : null
			})),
			{ run_id: run, item_id: 'missing', item_total_ms: null },
			{ run_id: run, item_id: 'invalid', item_total_ms: -1 }
		], numberFormat);
		expect(actual).toMatchObject({ run, medianSeconds: 2, measured: 7, unmeasured: 2 });
		expect(actual.rows.map((row) => row.value)).toEqual([10, 5]);
		expect(actual.rows[0].context).toContain('queue wait 0 s');
		expect(actual.rows[1].context).toContain('queue wait not recorded');
		const capped = rankedList(actual.rows, { max: 1 });
		expect(capped?.rows.map((row) => row.value)).toEqual([10]);
		expect(capped?.hidden).toBe(1);
	});

	test('numeric run suffixes beyond safe integers retain their actual order', () => {
		const older = '2026-09-01-9007199254740992';
		const newer = '2026-09-01-9007199254740993';
		expect(slowestArticles([
			{ run_id: newer, item_id: 'new', item_total_ms: 1000 },
			{ run_id: older, item_id: 'old', item_total_ms: 9000 }
		], numberFormat).run).toBe(newer);
	});

	test('the run median uses recorded milliseconds before converting to seconds', () => {
		const actual = slowestArticles([800, 1600].map((ms, index) => ({
			run_id: '2026-09-01-10', item_id: `article-${index}`, item_total_ms: ms
		})), numberFormat);
		expect(actual.medianSeconds).toBe(1.2);
		expect(actual.rows.map((row) => row.value)).toEqual([1.6]);
	});

	test('a newest run without a recorded clock stays unmeasured instead of falling back to an older run', () => {
		expect(slowestArticles([
			{ run_id: '2026-09-01-9', item_id: 'older', item_total_ms: 99000 },
			{ run_id: '2026-09-01-10', item_id: 'newest', item_total_ms: null }
		], numberFormat)).toEqual({ run: '2026-09-01-10', rows: [], medianSeconds: null, measured: 0, unmeasured: 1 });
		for (const times of [[0], [1000, 1000, 1000]]) {
			const actual = slowestArticles(times.map((ms, index) => ({
				run_id: '2026-09-01-10', item_id: `article-${index}`, item_total_ms: ms
			})), numberFormat);
			expect(actual).toMatchObject({
				rows: [], medianSeconds: times[0] / 1000, measured: times.length, unmeasured: 0
			});
		}
	});

	test('positive gaps close the work stack; queue wait stays outside it and missing stages stay absent', () => {
		const row = { run_id: '2026-09-01-1', item_id: 'one', item_total_ms: 5000,
			fetch_ms: 1000, extract_ms: 1000, summarize_ms: 1000, faithfulness_ms: 1000,
			stage_gap_ms: 1000, queue_wait_ms: 2000 };
		const baseline = { run_id: row.run_id, item_id: 'short', item_total_ms: 0 };
		const measured = slowestArticles([row, baseline], numberFormat).rows[0];
		expect(measured.value).toBe(5);
		expect(measured.segments?.map((segment) => segment.value)).toEqual([1, 1, 1, 1, 1]);
		expect(measured.context).toBe('queue wait 2 s');
		expect(slowestArticles([{ ...row, extract_ms: null }, baseline], numberFormat).rows[0]).not.toHaveProperty('segments');
	});

	test('native host logical, algorithm and model load conflicts preserve whole-run refusal in both orders', () => {
		const host = { version: '2026-10-10', date: '2026-09-01', run_id: '2026-09-01-1', job: 'work', shard: 0,
			fingerprint: '0123456789abcdef', fingerprint_version: 2,
			cpu_model: 'A', cpu_logical_processors: 8, model_load_ms: 1000 };
		const limits = { contextWindow: 8192, jobTimeoutSeconds: 9000 };
		for (const conflicting of [{ ...host, cpu_logical_processors: 16 }, { ...host, model_load_ms: 2000 },
			{ ...host, fingerprint_version: 1 }]) {
			for (const hosts of [[host, conflicting], [conflicting, host]]) {
			const result = countersFrom(hosts, [], [{ run_id: host.run_id, shards: 1 }], limits);
			expect(result.runs).toEqual([]);
			expect(result.refused).toHaveLength(1);
			expect(result.refused[0].why).toContain('two machine records that disagree');
			}
		}
	});

	test('context rules use the smallest per-slot limit and the middle label reading among cut rows', () => {
		const actual = contextReadings([
			{ n_ctx_configured: 8192, n_parallel: 2, label_input_tokens: 100, summary_input_tokens: 200, truncation_cap_tokens: 500 },
			{ n_ctx_configured: 4096, n_parallel: 2, label_input_tokens: 300, summary_input_tokens: 400, truncation_cap_tokens: 500 }
		]);
		expect(actual.limits).toEqual([2048, 4096]);
		expect(actual.rules.map((rule) => rule.at)).toEqual([2048, 300]);
	});

	test('count corrections must already be settled, while a null remains unknown', () => {
		expect(shardCounts([{ run_id: 'one', shards: null }]).has('one')).toBe(false);
		for (const shards of ['3', true, 1.5, 0, -1]) {
			expect(() => shardCounts([{ run_id: 'one', shards }])).toThrow('Invalid recorded shard count');
		}
		expect(() => shardCounts([{ run_id: 'one', shards: 1 }, { run_id: 'one', shards: 2 }])).toThrow('unsettled corrections');
		const hosts = [0, 1].map((shard) => ({ version: '2026-10-10', date: '2026-09-01', run_id: 'one', job: 'work', shard, cpu_model: 'A' }));
		const limits = { contextWindow: 8192, jobTimeoutSeconds: 9000 };
		expect(countersFrom(hosts, [], [{ run_id: 'one', shards: 1 }], limits).refused).toHaveLength(1);
		expect(countersFrom(hosts, [], [{ run_id: 'one', shards: null }], limits).runs[0].shards).toBeNull();
	});

	test.describe('native current-host compatibility', () => {
		const limits = { contextWindow: 8192, jobTimeoutSeconds: 9000 };
		const modern = {
			version: '2026-10-10', date: '2026-09-01', run_id: 'one', job: 'work', shard: 0,
			fingerprint: '0123456789abcdef', fingerprint_version: 2, cpu_model: 'A',
			cpu_physical_cores: 4, cpu_logical_processors: 8, cpu_allowed_processors: 2,
			cpu_quota_cores: 0.5, cpu_quota_state: 'finite', cpu_target_measured_at: '2026-09-01T01:02:03Z',
			cpu_observed_mhz: 2800, cpu_reported_max_mhz: 3200, flags: 'avx2',
			model_load_ms: 1000, job_seconds: 10, server_prompt_tokens: 0, server_prompt_seconds: 2
		};
		const busy = { date: modern.date, run_id: modern.run_id, machine_shard: 0,
			cpu_busy_pct: 50, item_total_ms: 2000 };
		test('physical, logical, allowed, quota and frozen readings stay separate from whole-host cost', () => {
			const held = countersFrom([modern], [], [{ run_id: 'one', shards: 1 }], limits);
			expect(held.refused).toEqual([]);
			expect(held.runs[0].reported[0]).toMatchObject({ logicalProcessors: 8, fingerprintVersion: 2, readTokensPerSecond: 0 });
			const cost = articleCost(textRows([busy]), processors([modern]));
			expect(cost.processorSeconds).toMatchObject({ from: 1, outOf: 1, mid: 8 });
			expect(runnerHourSeconds(cost.processors)).toBe(28800);
			const unknown = { ...modern, cpu_logical_processors: null };
			expect(articleCost(textRows([busy]), processors([unknown])).processorSeconds).toMatchObject({ from: 0, outOf: 1, mid: null });
		});
		test('legacy measurements remain unknown, observed MHz migrates and manifest coverage never comes from hosts', () => {
			const legacy = { ...modern, version: '2026-09-20', shard: 1, fingerprint_version: null,
				cores: 4, threads: 8, mhz_max: 4000, mhz_at_probe: 2400 };
			const rows = [modern, legacy];
			const known = countersFrom(rows, [], [{ run_id: 'one', shards: 4 }], limits);
			expect(known.runs[0].slowestJobSeconds).toMatchObject({ from: 2, outOf: 4 });
			expect(known.runs[0].reported[1]).toMatchObject({ logicalProcessors: null, fingerprintVersion: 1 });
			const unknown = countersFrom(rows, [], [{ run_id: 'one', shards: null }], limits);
			expect(unknown.runs[0].slowestJobSeconds).toMatchObject({ from: 2, outOf: null });
			expect(articleCost(textRows([{ ...busy, machine_shard: 1 }]), processors([legacy])).processorSeconds)
				.toMatchObject({ from: 0, outOf: 1, mid: null });
			const jobs = fleetJobs(textRows(rows));
			const keys = machineKeys(jobs);
			expect(keys(jobs[0]).key).not.toBe(keys(jobs[1]).key);
		});
		test('unsupported or inconsistent host algorithms refuse the run rather than vanish; raw day and shard faults survive', () => {
			for (const bad of [{ ...modern, version: '2099-01-01' }, { ...modern, fingerprint_version: 3 },
				{ ...modern, fingerprint: null }, { ...modern, version: null }]) {
				expect(countersFrom([modern, bad], [], [{ run_id: 'one', shards: 4 }], limits).refused[0].why).toContain('unreadable host');
			}
			const unsupported = { ...modern, version: '2099-01-01' };
			expect(countersFrom([modern, { ...unsupported, date: '2026-09-02' }], [], [], limits).refused[0].why).toContain('day');
			for (const shard of [null, '', ' ', -1, 0.5, 'bad']) {
				const held = countersFrom([{ ...unsupported, shard }], [], [], limits);
				expect(held.runs).toEqual([]);
				expect(held.refused[0].why).toContain('shard');
				expect(processors([{ ...modern, shard }])).toEqual([]);
			}
		});
		test('complementary current half-rows and equal duplicates retain zeros in either order', () => {
			const identity = { ...modern, model_load_ms: null, job_seconds: null, server_prompt_tokens: null, server_prompt_seconds: null };
			const clocks = { ...modern, fingerprint: null, fingerprint_version: null, cpu_model: null, cpu_logical_processors: null,
				model_load_ms: 0, job_seconds: 0, server_prompt_tokens: 0, server_prompt_seconds: 2 };
			for (const rows of [[identity, clocks, identity], [clocks, identity, clocks]]) {
				const held = countersFrom(rows, [], [{ run_id: 'one', shards: 1 }], limits);
				expect(held.refused).toEqual([]);
				expect(held.runs[0].reported).toHaveLength(1);
				expect(held.runs[0].reported[0]).toMatchObject({ logicalProcessors: 8, fingerprintVersion: 2,
					modelLoadMs: 0, jobSeconds: 0, promptTokens: 0, readTokensPerSecond: 0 });
			}
		});
		test('run-level model-clock refusal does not disqualify independent article cost or hide ambiguous logical coverage', () => {
			const badClock = { ...modern, model_load_ms: 2000 };
			expect(countersFrom([modern, badClock], [], [{ run_id: 'one', shards: 1 }], limits).refused).toHaveLength(1);
			expect(articleCost(textRows([busy]), processors([modern, badClock])).processorSeconds)
				.toMatchObject({ from: 1, outOf: 1, mid: 8 });
			const badCount = { ...modern, cpu_logical_processors: 16 };
			for (const rows of [[modern, badCount], [badCount, modern]]) {
				expect(countersFrom(rows, [], [{ run_id: 'one', shards: 1 }], limits).refused).toHaveLength(1);
				expect(articleCost(textRows([busy]), processors(rows)).processorSeconds)
					.toMatchObject({ from: 0, outOf: 1, mid: null });
			}
		});
	});
});
