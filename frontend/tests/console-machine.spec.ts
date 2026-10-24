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
import { closestToMemory, contextReadings, countersFrom, fingerprints, processors, textRows, labelHeldMedian, reuseChecks, shardCounts, slowestArticles, slowerMachines } from '../src/lib/console/machine/records';
import { machineCards } from '../src/lib/charts/machine-cards';
import { fleetJobs } from '../src/lib/charts/fleet';
import { machineKeys } from '../src/lib/charts/machine-colour';
import {
	clockAgreement,
	clocksChart,
	costOf,
	itemRead,
	percentileHistory,
	pooledReadRate,
	quantile,
	readAgainstWritten,
	workSeries,
	workValues,
	PERCENTILES,
	type RunWork
} from '../src/lib/charts/machine';
import { costOverDays } from '../src/lib/charts/cost';
import {
	carriesServerCounters,
	machineCounters,
	type MachineLimits,
	type MachineRun
} from '../src/lib/console/machine/counters';
import { dateSeries, money, numberFormat } from './support/number-format';
import { frame } from '../src/lib/charts/frame';
import { articleCost, runnerHourSeconds } from '../src/lib/console/machine/article-cost';
import { processorLostOverDays } from '../src/lib/console/machine/processor-lost';
import { diskReads } from '../src/lib/console/machine/disk-reads';
import { describeRefusedRuns } from '../src/lib/console/machine/refused-runs';
import { hostRow, ledgers, plan, type ShardReading } from './support/machine-rows';
import { observabilityConfig } from '../src/lib/server/config';

/** `config/idhazh.json` read straight off disk, so a test's expectation comes
 * from the committed file rather than from the reader it is checking. */
const CONFIG = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')
) as {
	run: { shard_timeout_minutes: number };
	models_file: string;
	observability: {
		cost_currency: string;
		cost_input_per_million: number;
		cost_output_per_million: number;
	};
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

	test('the read rate is the shard rate, and the spread is the two of them', () => {
		// 8,000 tokens over 200 seconds is 40; 2,000 over 200 is 10; 40/10 is 4.
		expect(run.reported.find((row) => row.shard === 0)?.readTokensPerSecond).toBeCloseTo(40, 6);
		expect(run.reported.find((row) => row.shard === 1)?.readTokensPerSecond).toBeCloseTo(10, 6);
		expect(run.readSpread.value).toBeCloseTo(4, 6);
	});

	test('the job clock is measured against the configured timeout, not a literal', () => {
		expect(run.reported[1].jobUsedPct).toBe(Math.round(1200 / (CONFIG.run.shard_timeout_minutes * 60) * 100));
		const { hosts, health } = ledgers(TWO_SHARDS.map(shardOf));
		const tighter = machineCounters(hosts, health, plan(['2026-09-04-1', 2]),
			{ ...LIMITS, jobTimeoutSeconds: 1500 }).runs[0];
		expect(tighter.reported[1].jobUsedPct).toBe(80);
	});

	test('a shard that reported no clock is unknown, not zero', () => {
		const mixed = onlyRun([TWO_SHARDS[0], { shard: 1, serverPromptTokens: 10 }]);
		expect(mixed.reported[1].jobSeconds).toBeNull();
		expect(mixed.reported[1].jobUsedPct).toBeNull();
		expect(mixed.reported[1].cpuModel).toBeNull();
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

	test('the unclaimed figure is the stored column added up, and never a difference', () => {
		// 4,321 ms and -2,500 ms are the two cells the fixture wrote. Their sum is
		// 1,821 ms, which is 1.821 seconds - and no arithmetic over the rest of
		// these rows produces it, because they carry no stage clock to subtract.
		expect(rowFor(0).unclaimedSeconds).toBeCloseTo(1.821, 6);
		expect(rowFor(1).unclaimedSeconds).toBeCloseTo(-9, 6);
	});

	test('a shard below zero reads as a disagreement and not as a zero', () => {
		// The one state the committed archive has never held. Clamping it would
		// hide the fault the signed column exists to show.
		const row = rowFor(1);
		expect(row.unclaimedSeconds).toBeLessThan(0);
		expect(row.clocksDisagreed).toBe(1);
		expect(row.clockedItems).toBe(1);
	});

	test('the count of disagreements survives a sum that cancels', () => {
		// Shard 0 adds to a positive 1.821 seconds, and one of its two items is
		// still below zero. A page that only carried the sum would print a healthy
		// shard and lose the item that disagreed.
		const row = rowFor(0);
		expect(row.unclaimedSeconds).toBeGreaterThan(0);
		expect(row.clocksDisagreed).toBe(1);
		expect(row.clockedItems).toBe(2);
	});

	test('a shard that recorded no unclaimed time draws an absence, not a zero', () => {
		const view = onlyRun([{ shard: 0, jobSeconds: 600 }, { shard: 1, jobSeconds: 300 }]);
		expect(view.reported[0].unclaimedSeconds).toBeNull();
		expect(view.reported[0].clockedItems).toBe(0);
		expect(view.reported[0].queueMedianSeconds).toBeNull();
		expect(view.reported[0].queueMaxSeconds).toBeNull();
	});

	test('the queue is a typical item and the worst one, never the two added up', () => {
		// Each item's wait covers the queue ahead of it, so 1 s + 5 s is not 6 s of
		// shard time - it is one item that waited a second and one that waited five.
		const row = rowFor(0);
		expect(row.queueMedianSeconds).toBeCloseTo(3, 6);
		expect(row.queueMaxSeconds).toBeCloseTo(5, 6);
	});
});

test.describe('do the two clocks agree', () => {
	/** Four items a shard, whose summed tokens and milliseconds put the ledger's
	 * rate exactly on the server's 40 and 10 tokens a second. */
	function items(shard: number, tokens: number, prefillMs: number) {
		return Array.from({ length: 4 }, (_, index) =>
			healthRow({
				item_id: `s${shard}-${index}`,
				machine_shard: shard,
				input_tokens: tokens + 50,
				cached_tokens: 50,
				prefill_ms: prefillMs
			})
		);
	}

	test('per shard where the ledger names one, and the gap is a percentage', () => {
		// Shard 0: 4 x 2,000 read tokens over 4 x 50,000 ms is 8,000 over 200 s -
		// 40 a second, the server's own figure. Shard 1: 4 x 500 over the same time
		// is 2,000 over 200 s, or 10, likewise.
		const health = [...items(0, 2000, 50_000), ...items(1, 500, 50_000)];
		const view = clockAgreement(onlyRun(TWO_SHARDS), health, 5);
		expect(view.grain).toBe('shard');
		expect(view.pairs.map((pair) => pair.label)).toEqual(['shard 0', 'shard 1']);
		expect(view.pairs[0].ledger).toBeCloseTo(40, 6);
		expect(view.pairs[0].server).toBeCloseTo(40, 6);
		expect(view.pairs[1].ledger).toBeCloseTo(10, 6);
		expect(view.pairs[1].server).toBeCloseTo(10, 6);
		expect(view.pairs[0].gapPct).toBeCloseTo(0, 6);
		expect(view.pairs.every((pair) => pair.agrees)).toBe(true);
		expect(view.disagreeing).toBe(0);
	});

	test('a disagreement is reported as one, not rounded away', () => {
		// Half the tokens in the same time is half the rate, which is 50 percent
		// below the server and ten times the tolerance. Only shard 0 is moved, so
		// the count of disagreeing shards is a count and not a total.
		const health = [...items(0, 1000, 50_000), ...items(1, 500, 50_000)];
		const view = clockAgreement(onlyRun(TWO_SHARDS), health, 5);
		expect(view.pairs[0].gapPct).toBeCloseTo(50, 6);
		expect(view.pairs[0].agrees).toBe(false);
		expect(view.pairs[1].agrees).toBe(true);
		expect(view.disagreeing).toBe(1);
	});

	test('native ranked gaps keep the independent readings, rule and unknown state', () => {
		const view = clockAgreement(onlyRun(TWO_SHARDS),
			[...items(0, 1000, 50_000), ...items(1, 500, 50_000)], 5);
		const geometry = clocksChart(view.pairs, 5, numberFormat);
		expect(geometry?.rows.map((row) => row.value)).toEqual([50, 0]);
		expect(geometry?.rules.map((rule) => [rule.at, rule.label])).toEqual([[5, 'Allowed disagreement']]);
		expect(geometry?.rows[0].row).toMatchObject({
			status: 'disagrees', context: 'item ledger 20; server 40 tokens a second'
		});
		expect(clocksChart([{ label: 'shard 0', ledger: null, server: 40, gapPct: null, agrees: null }], 5, numberFormat)).toBeNull();
	});

	test('a ledger with no shard falls back to the run and says which grain it used', () => {
		const health = Array.from({ length: 4 }, (_, index) =>
			healthRow({ item_id: `i${index}`, input_tokens: 1050, cached_tokens: 50, prefill_ms: 50_000 })
		);
		const view = clockAgreement(onlyRun(TWO_SHARDS), health, 5);
		expect(view.grain).toBe('run');
		expect(view.pairs).toHaveLength(1);
		expect(view.shardRows).toBe(0);
		expect(view.itemRows).toBe(4);
	});

	test('the read count takes the cache out, because the machine did not read it', () => {
		const row = healthRow({ input_tokens: 1000, cached_tokens: 400, prefill_ms: 2000 });
		expect(itemRead(row)).toEqual({ tokens: 600, ms: 2000 });
		expect(pooledReadRate([row, row])).toBeCloseTo(1200 / 4, 6);
		// A row that predates token capture is evidence in neither direction.
		expect(itemRead(healthRow({ prefill_ms: 2000 }))).toBeNull();
		expect(pooledReadRate([healthRow({})])).toBeNull();
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

	test('the taller bar inverts between the two units, and that is the finding', () => {
		// Reads outnumber writes 5 to 1; decode outlasts prefill 3 to 1.
		const view = readAgainstWritten(health);
		expect(workValues(view.runs[0], 'tokens')).toEqual({ read: 1_500_000, written: 300_000 });
		expect(workValues(view.runs[0], 'seconds')).toEqual({ read: 60, written: 180 });
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

	test('input and output are priced apart, at the rate per million', () => {
		const rate = { currency: 'USD', inputPerMillion: 0.2, outputPerMillion: 0.6 };
		// 1.5 million prompt tokens at 0.20 is 0.30; 0.3 million written at 0.60 is
		// 0.18; together 0.48.
		expect(costOf({ input: 1_500_000, output: 300_000 }, rate)).toBeCloseTo(0.48, 12);
		// One blended rate cannot reproduce that, which is why there are two.
		expect(costOf({ input: 1_500_000, output: 0 }, rate)).toBeCloseTo(0.3, 12);
		expect(costOf({ input: 0, output: 300_000 }, rate)).toBeCloseTo(0.18, 12);
		expect(costOf({ input: 0, output: 0 }, rate)).toBe(0);
	});

	test('the default rate comes from the committed config and not from a literal', () => {
		const configured = observabilityConfig();
		expect(configured.cost_currency).toBe(CONFIG.observability.cost_currency);
		expect(configured.cost_input_per_million).toBe(CONFIG.observability.cost_input_per_million);
		expect(configured.cost_output_per_million).toBe(CONFIG.observability.cost_output_per_million);
		// Named rather than assumed: a bare number behind a symbol is the shape a
		// bill takes, and this figure is not one.
		expect(configured.cost_currency).toMatch(/^[A-Z]{3}$/);
	});

	test('money is digits and an ISO code, and never reads the machine locale', () => {
		expect(money(1234.5, 'USD')).toBe('1,230 USD');
		expect(money(0.0123, 'USD')).toBe('0.0123 USD');
		expect(money(0, 'EUR')).toBe('0 EUR');
		expect(money(0.0027, 'USD')).toBe('0.0027 USD');
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

	test('the counters refuse one run and keep the other', () => {
		const { runs, refused } = machineCounters(
			hosts,
			bothRuns,
			plan([REFUSED, 2], [ACCEPTED, 1]),
			LIMITS
		);
		expect(refused.map((run) => run.runId)).toEqual([REFUSED]);
		expect(refused[0].why).toContain('shard 1');
		expect(runs.map((run) => run.runId)).toEqual([ACCEPTED]);
	});

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

	test('what a run reads against what it writes counts it', () => {
		expect(readAgainstWritten(acceptedRows).runs.map((run) => run.runId)).toEqual([ACCEPTED]);
		const view = readAgainstWritten(bothRuns);
		expect(view.runs.map((run) => run.runId)).toEqual([REFUSED, ACCEPTED]);
		expect(view.runs[0]).toEqual({
			runId: REFUSED,
			date: '2026-09-04',
			input: 10_000,
			output: 600,
			prefillMs: 20_000,
			decodeMs: 60_000,
			items: 2,
			timed: 2
		});
	});

	test('the reading limit counts it', () => {
		const accepted = contextReadings(acceptedRows);
		expect(accepted.summary).toEqual([1000, 2000]);
		expect(accepted.limits).toEqual([8192]);
		const both = contextReadings(bothRuns);
		expect(both.summary).toEqual([4000, 6000, 1000, 2000]);
		expect(both.limits).toEqual([8192]);
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

	test('THE ORACLE: a refused shard whose records disagree about the processors leaves its time out', () => {
		// Shard 0 of the refused run filed two machine records that disagree: one
		// names 4 logical processors, the other 8. articleCost is handed the same
		// shard's one article row (busy 50%, 40s total) with the two records in
		// one order, then in the other. Picking whichever record came last would
		// price the shard at 160 processor-seconds (50% of 8 over 40s) with 8
		// named last, and 80 with 4 named last. The shard is left out in both
		// orders and counted in `outOf`.
		const shardArticle = [refusedRows[0]];
		const namedLast8 = [
			{ date: '2026-09-04', run_id: REFUSED, shard: 0, cpu_logical_processors: 4 },
			{ date: '2026-09-04', run_id: REFUSED, shard: 0, cpu_logical_processors: 8 }
		];
		const namedLast4 = [...namedLast8].reverse();
		const forward = articleCost(shardArticle, namedLast8);
		const backward = articleCost(shardArticle, namedLast4);
		for (const cost of [forward, backward]) {
			expect(cost.processorSeconds.from).toBe(0);
			expect(cost.processorSeconds.mid).toBeNull();
			expect(cost.processorSeconds.outOf).toBe(1);
			expect(cost.processors).toEqual([]);
		}
	});

	test('the processor lost to other tenants counts it', () => {
		const thresholds = { marked: 1, named: 10 };
		const accepted = processorLostOverDays(acceptedRows, thresholds, numberFormat);
		expect([accepted.from, accepted.outOf, accepted.days[0].worstPct]).toEqual([2, 2, 0.5]);
		expect(accepted.named).toBeNull();
		const both = processorLostOverDays(bothRuns, thresholds, numberFormat);
		expect([both.from, both.outOf, both.days[0].worstPct]).toEqual([4, 4, 12]);
		// The day is named for a share only the refused run's article lost.
		expect(both.named?.key).toBe('2026-09-04');
	});

	test('the waits for the disk count it', () => {
		const marks = { marked: 1, named: 1 };
		const accepted = diskReads(acceptedRows, marks);
		expect([accepted.days[0].reads, accepted.days[0].counted, accepted.days[0].excluded]).toEqual([
			0, 1, 1
		]);
		expect(accepted.pinning).toEqual({ held: 1, loose: 0, silent: 0 });
		expect(accepted.worst).toBeNull();
		const both = diskReads(bothRuns, marks);
		expect([both.days[0].reads, both.days[0].counted, both.days[0].excluded]).toEqual([
			4100, 2, 2
		]);
		expect(both.pinning).toEqual({ held: 1, loose: 1, silent: 0 });
		expect(both.worst?.date).toBe('2026-09-04');
	});

	test('the prompt reuse counts it', () => {
		const accepted = reuseChecks(acceptedRows).find((one) => one.call === 'summary')!;
		// Native independent percentages use the upper middle of [80, 90].
		expect([accepted.count, accepted.server]).toEqual([2, 90]);
		expect(accepted.ours).toBeCloseTo(100 * 2600 / 3000, 12);
		const both = reuseChecks(bothRuns).find((one) => one.call === 'summary')!;
		expect([both.count, both.server]).toEqual([4, 80]);
		expect(both.ours).toBeCloseTo(100 * 2800 / 13000, 12);
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

test.describe('the native daily counterfactual cost', () => {
	const RATE = { currency: 'USD', inputPerMillion: 0.2, outputPerMillion: 0.6 };

	function work(date: string, input: number, output: number, items = 1): RunWork {
		return {
			runId: `${date}-1`,
			date,
			input,
			output,
			prefillMs: null,
			decodeMs: null,
			items,
			timed: 0
		};
	}

	/** Three days, the middle one twice the first and the last one half of it. */
	const RUNS = [
		work('2026-09-01', 1_000_000, 200_000, 4),
		work('2026-09-02', 2_000_000, 400_000, 8),
		work('2026-09-03', 500_000, 100_000, 2)
	];

	test('one call returns both shapes, and the line ends where the bars add up', () => {
		// The oracle of this panel. Two builder calls could hand a reader a line
		// and a stack that disagree, with nothing on screen saying which to
		// believe - which is the whole reason the no-re-shaping rule exists.
		const shapes = costOverDays(RUNS, RATE);
		const bars = shapes.days.reduce((carry, day) => carry + day.read + day.written, 0);
		expect(shapes.runningTotal).toBeCloseTo(bars, 12);

		// Recomputed by hand rather than from the module: 3.5 million prompt tokens
		// at 0.20 is 0.70, and 0.7 million written at 0.60 is 0.42.
		expect(shapes.runningTotal).toBeCloseTo(1.12, 12);
	});

	test('the line is the bars added up in order, point by point', () => {
		const shapes = costOverDays(RUNS, RATE);
		const expected = [
			[0.2, 0.12, 0.32, 0.32],
			[0.4, 0.24, 0.64, 0.96],
			[0.1, 0.06, 0.16, 1.12]
		];
		shapes.days.forEach((day, at) => {
			for (const [column, value] of [day.read, day.written, day.total, day.running].entries()) {
				expect(value).toBeCloseTo(expected[at][column], 12);
			}
		});
		// A running total never falls, because a day cannot cost less than nothing.
		const climbs = shapes.days.map((day) => day.running);
		expect(climbs).toEqual([...climbs].sort((left, right) => left - right));
	});

	test('two runs on one date are one column, because the panel asks what a day cost', () => {
		const shapes = costOverDays(
			[
				work('2026-09-01', 1_000_000, 200_000, 4),
				{ ...work('2026-09-01', 500_000, 100_000, 2), runId: '2026-09-01-2' }
			],
			RATE
		);
		expect(shapes.days).toHaveLength(1);
		expect(shapes.days[0].items).toBe(6);
		expect(shapes.days[0].read).toBeCloseTo(0.3, 12);
		expect(shapes.days[0].written).toBeCloseTo(0.18, 12);
	});

	test('no day is an absence, not an empty plot', () => {
		const nothing = costOverDays([], RATE);
		expect(nothing.days).toEqual([]);
		expect(nothing.runningTotal).toBe(0);
		// A run with no date cannot be laid on a time axis and is not a day.
		const undated = costOverDays([work('', 1_000, 200)], RATE);
		expect(undated.days).toEqual([]);
	});

	test('changing either operator-owned price recomputes the same dated cohort', () => {
		const shapes = costOverDays(RUNS, { ...RATE, inputPerMillion: 0.4, outputPerMillion: 0.3 });
		expect(shapes.days.map((day) => [day.date, day.items])).toEqual([
			['2026-09-01', 4], ['2026-09-02', 8], ['2026-09-03', 2]
		]);
		expect(shapes.runningTotal).toBeCloseTo(1.61, 12);
	});
});

test.describe('the native counters, read as the page reads them', () => {
	const limits = LIMITS;

	test('a run the reader refuses is named, never quietly dropped', () => {
		// Two machine records for one shard, each naming a different server, is a
		// run whose rows cannot be made into one run. The page prints the reason;
		// this asserts the reason exists and is words.
		const { hosts, health } = ledgers(
			[
				...TWO_SHARDS,
				{ shard: 1, serverPromptTokens: 1, serverPromptSeconds: 1 }
			].map(shardOf)
		);
		const { refused } = machineCounters(hosts, health, plan(['2026-09-04-1', 2]), limits);
		expect(refused).toHaveLength(1);
		// Six, because each of the three readings states one machine row and one item
		// row, and the count a refusal reports is what it could not read.
		expect(refused[0].rows).toBe(6);
		expect(refused[0].why.length).toBeGreaterThan(20);
		expect(refused[0].why).toContain('shard 1');
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
			{ run_id: '2026-09-01-10', item_id: 'new', item_total_ms: 4000, fetch_ms: 1000, extract_ms: 1000,
				summarize_ms: 1000, faithfulness_ms: 2000, stage_gap_ms: -1000, queue_wait_ms: 500 }
		], numberFormat);
		expect(actual.run).toBe('2026-09-01-10');
		expect(actual.rows).toHaveLength(1);
		expect(actual.rows[0]).toMatchObject({ value: 4, context: 'waited 0.5 s first; stages overlapped by 1 s' });
		expect(actual.rows[0]).not.toHaveProperty('segments');
	});

	test('numeric run suffixes beyond safe integers retain their actual order', () => {
		const older = '2026-09-01-9007199254740992';
		const newer = '2026-09-01-9007199254740993';
		expect(slowestArticles([
			{ run_id: newer, item_id: 'new', item_total_ms: 1000 },
			{ run_id: older, item_id: 'old', item_total_ms: 9000 }
		], numberFormat).run).toBe(newer);
	});

	test('positive gaps close the elapsed stack; queue wait stays outside it and missing stages stay absent', () => {
		const row = { run_id: '2026-09-01-1', item_id: 'one', item_total_ms: 5000,
			fetch_ms: 1000, extract_ms: 1000, summarize_ms: 1000, faithfulness_ms: 1000,
			stage_gap_ms: 1000, queue_wait_ms: 2000 };
		const measured = slowestArticles([row], numberFormat).rows[0];
		expect(measured.value).toBe(5);
		expect(measured.segments?.map((segment) => segment.value)).toEqual([1, 1, 1, 1, 1]);
		expect(measured.context).toBe('waited 2 s first');
		expect(slowestArticles([{ ...row, extract_ms: null }], numberFormat).rows[0]).not.toHaveProperty('segments');
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

	test('a card never fabricates a job, shard or private unasked field', () => {
		const row = { version: '2026-10-10', date: '2026-09-01', run_id: '2026-09-01-1', job: 'work',
			shard: 2, fingerprint: '0123456789abcdef', fingerprint_version: 2 };
		expect(fingerprints([{ ...row, shard: null }, { ...row, job: null }])).toEqual([]);
		for (const shard of ['', 'not-a-shard', -1, 0.5]) {
			expect(fingerprints([{ ...row, shard }])).toEqual([]);
		}
		expect(fingerprints([{ ...row, shard: 0 }])[0].shard).toBe(0);
		const held = fingerprints([row]);
		expect(held[0]).toMatchObject({ job: 'work', shard: 2, fingerprint: row.fingerprint });
		expect(held[0]).toMatchObject({ version: row.version, fingerprint_version: 2 });
		expect(held[0]).not.toHaveProperty('runner_name');
		expect(held[0]).not.toHaveProperty('measured_at');
		expect(held[0]).not.toHaveProperty('cores');
	});

	test('held memory is total less the low-water available, with a total endpoint, never a process total', () => {
		const rows = closestToMemory([
			{ item_id: 'a', source_id: 's', os_mem_total_bytes: 16 * 2 ** 30, os_mem_available_min_bytes: 6 * 2 ** 30 },
			{ item_id: 'missing', os_mem_total_bytes: 16 * 2 ** 30, os_mem_available_min_bytes: null },
			{ item_id: 'invalid', os_mem_total_bytes: 16 * 2 ** 30, os_mem_available_min_bytes: -1 }
		]);
		expect(rows).toHaveLength(1);
		expect(rows[0]).toMatchObject({ value: 10, ends: { end: 16 } });
		const repeated = closestToMemory([
			{ date: '2026-09-01', item_id: 'same', os_mem_total_bytes: 16 * 2 ** 30, os_mem_available_min_bytes: 6 * 2 ** 30 },
			{ date: '2026-09-01', item_id: 'same', os_mem_total_bytes: 16 * 2 ** 30, os_mem_available_min_bytes: 4 * 2 ** 30 },
			{ date: '2026-09-02', item_id: 'same', os_mem_total_bytes: 16 * 2 ** 30, os_mem_available_min_bytes: 3 * 2 ** 30 }
		]);
		expect(repeated.map((row) => row.value)).toEqual([12, 13]);
	});

	test('context rules use the smallest per-slot limit and the middle label reading among cut rows', () => {
		const actual = contextReadings([
			{ n_ctx_configured: 8192, n_parallel: 2, label_input_tokens: 100, summary_input_tokens: 200, truncation_cap_tokens: 500 },
			{ n_ctx_configured: 4096, n_parallel: 2, label_input_tokens: 300, summary_input_tokens: 400, truncation_cap_tokens: 500 }
		]);
		expect(actual.limits).toEqual([2048, 4096]);
		expect(actual.rules.map((rule) => rule.at)).toEqual([2048, 300]);
	});

	test('cache share pairs cells on the same article; equal counts cannot pair two different missing rows', () => {
		const actual = reuseChecks([
			{ label_input_tokens: 100, label_cached_tokens: null },
			{ label_input_tokens: null, label_cached_tokens: 80 },
			{ label_input_tokens: 200, label_cached_tokens: 50, label_cache_pct: 40 }
		]);
		expect(actual[0]).toMatchObject({ ours: 25, server: 40, count: 1 });
	});

	test('the held-text lede quotes the middle request, not a median of unequal daily medians', () => {
		expect(labelHeldMedian([
			{ date: '2026-09-01', label_cached_tokens: 1000 },
			...([10, 20, 30].map((label_cached_tokens) => ({ date: '2026-09-02', label_cached_tokens }))),
			{ date: '2026-09-02', label_cached_tokens: null }
		])).toBe(30);
		expect(labelHeldMedian([{ label_cached_tokens: null }])).toBeNull();
		expect(labelHeldMedian([{ label_cached_tokens: 0 }])).toBe(0);
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
		const options = { watchedFlags: ['avx2'], colour: { stops: 5, floor: 0.4 }, numberFormat, recording: true, cacheMargin: 2 };
		test('physical, logical, allowed, quota and frozen readings stay separate from whole-host cost', () => {
			const held = countersFrom([modern], [], [{ run_id: 'one', shards: 1 }], limits);
			expect(held.refused).toEqual([]);
			expect(held.runs[0].reported[0]).toMatchObject({ logicalProcessors: 8, fingerprintVersion: 2, readTokensPerSecond: 0 });
			const card = machineCards(held.runs[0], fingerprints([modern]), options).cards[0];
			expect(card).toMatchObject({ physicalCores: 4, logicalProcessors: 8, allowedProcessors: 2,
				quotaCores: 0.5, quotaState: 'finite', targetMeasuredAt: modern.cpu_target_measured_at,
				observedMhz: 2800, reportedMaxMhz: 3200 });
			const cost = articleCost(textRows([busy]), processors([modern]));
			expect(cost.processorSeconds).toMatchObject({ from: 1, outOf: 1, mid: 8 });
			expect(runnerHourSeconds(cost.processors)).toBe(28800);
			for (const cpu_quota_state of ['unlimited', 'unavailable', null]) {
				const row = { ...modern, cpu_quota_state, cpu_quota_cores: null, cpu_target_measured_at: null };
				expect(machineCards(held.runs[0], fingerprints([row]), options).cards[0]).toMatchObject({
					quotaState: cpu_quota_state, quotaCores: null, targetMeasuredAt: null
				});
			}
			const unknown = { ...modern, cpu_logical_processors: null };
			expect(articleCost(textRows([busy]), processors([unknown])).processorSeconds).toMatchObject({ from: 0, outOf: 1, mid: null });
		});
		test('a class card keeps one source snapshot rather than borrowing another target', () => {
			const run = countersFrom([modern], [], [{ run_id: 'one', shards: 1 }], limits).runs[0];
			const first = { ...modern, cpu_allowed_processors: null, cpu_quota_cores: null,
				cpu_quota_state: null, cpu_target_measured_at: null };
			const second = { ...modern, job: 'plan', cpu_logical_processors: 16, flags: null };
			const card = machineCards(run, fingerprints([first, second]), options).cards[0];
			expect(card).toMatchObject({ logicalProcessors: 8, allowedProcessors: null, quotaCores: null,
				quotaState: null, targetMeasuredAt: null });
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
			expect(fingerprints([legacy])[0]).toMatchObject({ cpu_physical_cores: null, cpu_logical_processors: null,
				cpu_allowed_processors: null, cpu_quota_cores: null, cpu_quota_state: null,
				cpu_target_measured_at: null, cpu_observed_mhz: 2400, cpu_reported_max_mhz: null, fingerprint_version: 1 });
			expect(articleCost(textRows([{ ...busy, machine_shard: 1 }]), processors([legacy])).processorSeconds)
				.toMatchObject({ from: 0, outOf: 1, mid: null });
			const jobs = fleetJobs(textRows(rows));
			const keys = machineKeys(jobs);
			expect(keys(jobs[0]).key).not.toBe(keys(jobs[1]).key);
			expect(machineCards(known.runs[0], fingerprints(rows), options).cards).toHaveLength(2);
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
				expect(fingerprints([{ ...modern, shard }])).toEqual([]);
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
