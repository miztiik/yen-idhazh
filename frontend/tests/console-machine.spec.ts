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

import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
	cacheByDay,
	clockAgreement,
	contextHeadroom,
	costOf,
	itemRead,
	money,
	percentileHistory,
	pooledReadRate,
	quantile,
	readAgainstWritten,
	shardBoard,
	workChart,
	workValues,
	DEFAULT_WORK_UNIT,
	PERCENTILES,
	RUNNER_MEMORY_BYTES,
	SHARED_AXIS_LIMIT
} from '../src/lib/charts/machine';
import {
	machineCounters,
	machineLimits,
	type MachineLimits,
	type MachineRun
} from '../src/lib/server/machine-counters';
import { ledgers, plan, type ShardReading } from './support/machine-rows';
import { observabilityConfig, runConfig } from '../src/lib/server/config';

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

/** `console.chart_width`, off the committed file for the same reason. It
 * decides one thing on the board: whether the smaller half of a shard's split
 * is wide enough to be a band. */
const CHART_WIDTH = (
	JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
	) as { console: { chart_width: number } }
).console.chart_width;

/** The active model, reached through the pointer and never by filename. */
const MODELS = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', CONFIG.models_file), 'utf8')
) as { summarize: { inference: { n_ctx: number } } };

const LIMITS: MachineLimits = {
	contextWindow: MODELS.summarize.inference.n_ctx,
	jobTimeoutSeconds: CONFIG.run.shard_timeout_minutes * 60
};

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
		shard: ''
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

test.describe('the shard board', () => {
	const run = onlyRun(TWO_SHARDS);
	const board = shardBoard(run, LIMITS.jobTimeoutSeconds, CHART_WIDTH);

	test('rows are ranked by the clock the platform kills a shard on', () => {
		// Shard 1 took 1,200 seconds against shard 0's 600, so it is the one that
		// would be killed first and it goes on top.
		expect(board.rows.map((row) => row.shard)).toEqual([1, 0]);
		expect(board.rows.map((row) => row.jobSeconds)).toEqual([1200, 600]);
	});

	test('every bar sums to that shard, and the scale is the heaviest of them', () => {
		// Hand-computed: shard 0 spent 200 + 200 = 400 seconds in the model and
		// shard 1 spent 200 + 400 = 600, so 600 is the scale both bars share.
		expect(board.scaleSeconds).toBe(600);
		for (const row of board.rows) {
			expect(row.modelSeconds).toBe((row.readSeconds ?? 0) + (row.writeSeconds ?? 0));
			// The two segments are fractions of the shared scale, not of the row, so
			// a short row means a short shard.
			const read = Number((row.readWidth ?? '0%').replace('%', ''));
			const write = Number((row.writeWidth ?? '0%').replace('%', ''));
			expect(read).toBeCloseTo(((row.readSeconds ?? 0) / 600) * 100, 3);
			expect(write).toBeCloseTo(((row.writeSeconds ?? 0) / 600) * 100, 3);
		}
	});

	test('the read rate is the shard rate, and the spread is the two of them', () => {
		// 8,000 tokens over 200 seconds is 40; 2,000 over 200 is 10; 40/10 is 4.
		expect(board.rows.find((row) => row.shard === 0)?.readTokensPerSecond).toBeCloseTo(40, 6);
		expect(board.rows.find((row) => row.shard === 1)?.readTokensPerSecond).toBeCloseTo(10, 6);
		expect(board.readSpread).toBeCloseTo(4, 6);
	});

	test('the job clock is measured against the configured timeout, not a literal', () => {
		// The value is what the geometry is a fraction of, so driving the same run
		// with a different ceiling has to move the fill. A test that only asserted
		// the marker would pass against a constant, because the marker sits at the
		// same place for every value under its target.
		expect(board.timeoutSeconds).toBe(CONFIG.run.shard_timeout_minutes * 60);
		expect(machineLimits().jobTimeoutSeconds).toBe(CONFIG.run.shard_timeout_minutes * 60);
		const tighter = shardBoard(run, 1500, CHART_WIDTH);
		expect(tighter.rows[0].job.valueFraction).not.toBeCloseTo(
			board.rows[0].job.valueFraction,
			4
		);
	});

	test('a shard that reported no clock is last and is not read as zero', () => {
		const mixed = onlyRun([TWO_SHARDS[0], { shard: 1, serverPromptTokens: 10 }]);
		const view = shardBoard(mixed, LIMITS.jobTimeoutSeconds, CHART_WIDTH);
		expect(view.rows.map((row) => row.shard)).toEqual([0, 1]);
		expect(view.rows[1].jobSeconds).toBeNull();
		expect(view.rows[1].job.empty).toBe(true);
		expect(view.rows[1].cpuModel).toBeNull();
	});

	test('a run nothing reported draws nothing and says so', () => {
		const view = shardBoard(null, LIMITS.jobTimeoutSeconds, CHART_WIDTH);
		expect(view.empty).toBe(true);
		expect(view.rows).toEqual([]);
		expect(view.readSpread).toBeNull();
	});
});

/** The one question this panel exists to answer: was the slow shard slow
 * because of the WORK it was handed, or because of the HOST it landed on?
 *
 * Two runs below have the same shape - a shard on 600 seconds beside one on
 * 1,200 - and differ only in why. An operator has to part them without leaving
 * the panel, so every fact that parts them is on the row.
 */
const GIB = 1024 * 1024 * 1024;

/** One shard as however many item rows it ran, with the machine record's cells
 * on the first of them.
 *
 * The record is one row a shard and a second copy would have to agree cell for
 * cell, so it is stated once. The item cells repeat, because a median over one
 * reading is that reading and the fold has to be given something to sort.
 */
function shardOfItems(
	items: number,
	host: Partial<ShardReading>,
	machine: Partial<ShardReading>
): ShardReading[] {
	return Array.from({ length: items }, (_, index) => ({
		shard: host.shard ?? 0,
		...(index === 0 ? host : { shard: host.shard ?? 0 }),
		cachedTokens: 0,
		writtenTokens: 100,
		writeSeconds: 20,
		longestSequence: 500,
		peakRssBytes: 8 * GIB,
		cpuBusyPct: 94,
		cpuBusyMax: 97,
		...machine
	}));
}

/** A machine with room to spare: load inside its cores, swap barely touched. */
const CALM: Partial<ShardReading> = { load: 3, swapFree: 4 * GIB, swapTotal: 4 * GIB };

/** A machine in trouble: load past its four cores, and a sixteenth of its swap
 * left. Read rate collapses here, and the shard walks towards its timeout. */
const STRAINED: Partial<ShardReading> = {
	load: 6.5,
	swapFree: GIB / 4,
	swapTotal: 4 * GIB,
	cpuBusyPct: 62,
	cpuBusyMax: 71
};

const HOST_JOB = { cores: 4, cpuModel: 'AMD EPYC 7763 64-Core Processor', modelLoadMs: 2400 };

/** Shard 1 took twice shard 0's clock on the same two items, reading at a
 * quarter of its rate on a host that is queueing and swapping. */
const HOST_SLOW: ShardReading[] = [
	...shardOfItems(
		2,
		{ shard: 0, ...HOST_JOB, serverPromptTokens: 8000, serverPromptSeconds: 200, jobSeconds: 600 },
		CALM
	),
	...shardOfItems(
		2,
		{ shard: 1, ...HOST_JOB, serverPromptTokens: 2000, serverPromptSeconds: 200, jobSeconds: 1200 },
		STRAINED
	)
];

/** Shard 1 took twice shard 0's clock reading at exactly its rate, because it
 * was handed three times the items on a host with room to spare. */
const WORK_SLOW: ShardReading[] = [
	...shardOfItems(
		2,
		{ shard: 0, ...HOST_JOB, serverPromptTokens: 8000, serverPromptSeconds: 200, jobSeconds: 600 },
		CALM
	),
	...shardOfItems(
		6,
		{
			shard: 1,
			...HOST_JOB,
			serverPromptTokens: 24000,
			serverPromptSeconds: 600,
			jobSeconds: 1200
		},
		CALM
	)
];

function boardOf(readings: ShardReading[]) {
	return shardBoard(onlyRun(readings), LIMITS.jobTimeoutSeconds, CHART_WIDTH);
}

test.describe('work or the host, decided on the row', () => {
	const host = boardOf(HOST_SLOW);
	const work = boardOf(WORK_SLOW);

	test('the two runs look the same on the clock alone', () => {
		// The state the panel has to break out of: the ranking cannot part them,
		// because the clock is identical on both boards.
		expect(host.rows.map((row) => row.shard)).toEqual([1, 0]);
		expect(work.rows.map((row) => row.shard)).toEqual([1, 0]);
		expect(host.rows.map((row) => row.jobSeconds)).toEqual(
			work.rows.map((row) => row.jobSeconds)
		);
	});

	test('the host-slow shard names the host on its own row', () => {
		const [slow, fast] = host.rows;
		// Hand-computed: 8,000 over 200 is 40 and 2,000 over 200 is 10.
		expect(fast.readTokensPerSecond).toBeCloseTo(40, 6);
		expect(slow.readTokensPerSecond).toBeCloseTo(10, 6);
		// Same work, a quarter of the rate. That is the machine, not the queue.
		expect(slow.items).toBe(fast.items);
		expect(slow.readTokensPerSecond).toBeCloseTo((fast.readTokensPerSecond ?? 0) / 4, 6);
		// Load past the cores the host reported is a queue, and the target bar
		// says so rather than leaving the reader to divide.
		expect(slow.cores).toBe(4);
		expect(slow.loadMax).toBeCloseTo(6.5, 6);
		expect(slow.load.band).toBe('past');
		expect(fast.load.band).not.toBe('past');
		// A sixteenth of the swap left, with the total beside it so the reading
		// is not confused with a box that has no swap at all.
		expect(slow.swapState).toBe('measured');
		expect(slow.swapFreeBytes).toBe(GIB / 4);
		expect(slow.swapTotalBytes).toBe(4 * GIB);
		expect(fast.swapFreeBytes).toBe(4 * GIB);
	});

	test('the work-slow shard names the work on its own row', () => {
		const [slow, fast] = work.rows;
		// 24,000 over 600 is 40, the same rate its neighbour read at.
		expect(slow.readTokensPerSecond).toBeCloseTo(fast.readTokensPerSecond ?? 0, 6);
		expect(slow.items).toBe(fast.items * 3);
		expect(slow.loadMax).toBeLessThan(slow.cores ?? 0);
		expect(slow.load.band).not.toBe('past');
		expect(slow.swapFreeBytes).toBe(4 * GIB);
	});

	test('the value domain adapts to the 4x rather than clipping it', () => {
		// Every rate bar is drawn against the largest rate on the board, so the
		// shard reading at a quarter draws at a quarter. A fixed domain would put
		// both bars against a round number somebody picked, and a domain that
		// clipped would draw the two at the same length.
		expect(host.rateScale).toBeCloseTo(40, 6);
		expect(host.rows[0].readRateWidth).toBe('25.0000%');
		expect(host.rows[1].readRateWidth).toBe('100.0000%');
		// The same run against a wider board draws the same fractions: the domain
		// is the data, never the pixels.
		expect(boardOf(HOST_SLOW).rateScale).toBe(host.rateScale);
	});

	test('reading and writing share one scale while they are inside 20x', () => {
		// Hand-computed: 200 written tokens over 40 seconds is 5 a second on both
		// shards, against a fastest read of 40. That is 8x, inside the 20 at
		// which the smaller draws under a twentieth of the track.
		expect(host.rateRatio).toBeCloseTo(8, 6);
		expect(host.ratesShareAxis).toBe(true);
		expect(host.writeRateScale).toBe(host.rateScale);

		// Past 20x the write series takes its own domain, so a rate nothing can
		// see is not drawn as a rate of zero. 8,000 over 200 against 100 written
		// tokens over 400 seconds is 0.25 a second, which is 160x.
		const wide = boardOf([
			...shardOfItems(
				1,
				{
					shard: 0,
					...HOST_JOB,
					serverPromptTokens: 8000,
					serverPromptSeconds: 200,
					jobSeconds: 600
				},
				{ ...CALM, writtenTokens: 100, writeSeconds: 400 }
			)
		]);
		expect(wide.rateRatio).toBeCloseTo(160, 6);
		expect(wide.ratesShareAxis).toBe(false);
		expect(wide.writeRateScale).toBeCloseTo(0.25, 6);
		expect(wide.rows[0].writeRateWidth).toBe('100.0000%');
	});

	test('a range mark is the middle item filled and the worst one notched', () => {
		// Three items on one shard, so the median is a real middle rather than the
		// only reading: 8, 9 and 14 GiB has a median of 9 and a maximum of 14.
		const view = boardOf([
			{ shard: 0, ...HOST_JOB, serverPromptTokens: 8000, serverPromptSeconds: 200, jobSeconds: 600, cachedTokens: 0, writtenTokens: 100, writeSeconds: 20, longestSequence: 500, peakRssBytes: 8 * GIB, cpuBusyPct: 50, cpuBusyMax: 55, ...CALM },
			{ shard: 0, cachedTokens: 0, writtenTokens: 100, writeSeconds: 20, longestSequence: 500, peakRssBytes: 9 * GIB, cpuBusyPct: 60, cpuBusyMax: 91, ...CALM },
			{ shard: 0, cachedTokens: 0, writtenTokens: 100, writeSeconds: 20, longestSequence: 500, peakRssBytes: 14 * GIB, cpuBusyPct: 70, cpuBusyMax: 75, ...CALM }
		]);
		const memory = view.rows[0].memory;
		expect(memory.median).toBe(9 * GIB);
		expect(memory.max).toBe(14 * GIB);
		// The runner's own ceiling joins the figures rather than capping them, so
		// the scale is 16 GiB and the notch sits at fourteen sixteenths of it.
		expect(view.memoryScaleBytes).toBe(RUNNER_MEMORY_BYTES);
		expect(memory.medianWidth).toBe('56.2500%');
		expect(memory.notchWidth).toBe('87.5000%');
		// A share runs nought to a hundred, so the CPU mark needs no scale of its
		// own: 60 percent typical, 91 percent at its worst.
		expect(view.rows[0].cpu.median).toBe(60);
		expect(view.rows[0].cpu.max).toBe(91);
		expect(view.rows[0].cpu.medianWidth).toBe('60.0000%');
		expect(view.rows[0].cpu.notchWidth).toBe('91.0000%');
	});

	test('a band under one pixel is printed rather than drawn', () => {
		// The write side is a thousandth of the read side, so at 760px the smaller
		// band is 0.76px and a browser paints nothing. The bar draws whole and
		// both seconds stay on the row.
		const thin = boardOf([
			{
				shard: 0,
				...HOST_JOB,
				serverPromptTokens: 8000,
				serverPromptSeconds: 600,
				jobSeconds: 900,
				cachedTokens: 0,
				writtenTokens: 100,
				writeSeconds: 0.6,
				longestSequence: 500,
				...CALM
			}
		]);
		expect(1 / CHART_WIDTH).toBeGreaterThan(0.6 / 600.6);
		expect(thin.rows[0].splitDrawn).toBe(false);
		// The seconds themselves are untouched. The rule takes the band away, not
		// the fact.
		expect(thin.rows[0].writeSeconds).toBeCloseTo(0.6, 6);
		expect(host.rows[0].splitDrawn).toBe(true);
	});

	test('a run that recorded no swap says so rather than reading as zero', () => {
		const silent = boardOf(TWO_SHARDS);
		expect(silent.swapKnown).toBe(0);
		for (const row of silent.rows) {
			expect(row.swapState).toBe('unrecorded');
			expect(row.swapFreeBytes).toBeNull();
		}
		// A host that really has no swap is a third state, and not an emergency.
		const none = boardOf(
			shardOfItems(
				1,
				{
					shard: 0,
					...HOST_JOB,
					serverPromptTokens: 8000,
					serverPromptSeconds: 200,
					jobSeconds: 600
				},
				{ load: 3, swapFree: 0, swapTotal: 0 }
			)
		);
		expect(none.rows[0].swapState).toBe('none');
		expect(none.swapKnown).toBe(1);
	});

	test('the weights load lands as a cell on the shard that paid it', () => {
		expect(host.rows[0].modelLoadMs).toBe(2400);
		expect(boardOf(TWO_SHARDS).rows.map((row) => row.modelLoadMs)).toEqual([4000, 3000]);
	});
});

test.describe('the prompt cache', () => {
	test('a day is the sum of its runs, in absolute tokens, with its own share', () => {
		const second = TWO_SHARDS.map((reading) => ({
			...reading,
			runId: '2026-09-04-2',
			serverPromptTokens: 1000,
			cachedTokens: 1000
		}));
		const { runs } = runsOf(
			[...TWO_SHARDS, ...second],
			[
				['2026-09-04-1', 2],
				['2026-09-04-2', 2]
			]
		);
		const [day] = cacheByDay(runs);
		// Run one read 8,000 + 2,000 and cached 2,000 + 2,000; run two read 1,000
		// twice and cached 1,000 twice.
		expect(day.read).toBe(10_000 + 2000);
		expect(day.cached).toBe(4000 + 2000);
		expect(day.runs).toBe(2);
		expect(day.cachedPct).toBe(Math.round((6000 / 18_000) * 100));
	});

	test('a run that reported neither count is left out rather than counted as nothing', () => {
		expect(cacheByDay(runsOf([{ shard: 0 }], [['2026-09-04-1', 1]]).runs)).toEqual([]);
	});
});

test.describe('context headroom', () => {
	test('the longest sequence is a maximum over shards, against the window', () => {
		const [bar] = contextHeadroom([onlyRun(TWO_SHARDS)], MODELS.summarize.inference.n_ctx);
		expect(bar.longest).toBe(4096);
		expect(bar.spare).toBe(MODELS.summarize.inference.n_ctx - 4096);
		expect(bar.usedPct).toBe(Math.round((4096 / MODELS.summarize.inference.n_ctx) * 100));
		expect(bar.from).toBe(2);
	});

	test('no window means no share, and the sequence still prints', () => {
		const [bar] = contextHeadroom([onlyRun(TWO_SHARDS)], null);
		expect(bar.usedPct).toBeNull();
		expect(bar.spare).toBeNull();
		// The counter survives its missing ceiling. A share is what cannot be
		// computed, and inventing one would be inventing the ceiling.
		expect(bar.longest).toBe(4096);
	});
});

test.describe('do the two clocks agree', () => {
	/** Four items a shard, whose summed tokens and milliseconds put the ledger's
	 * rate exactly on the server's 40 and 10 tokens a second. */
	function items(shard: number, tokens: number, prefillMs: number) {
		return Array.from({ length: 4 }, (_, index) =>
			healthRow({
				item_id: `s${shard}-${index}`,
				shard,
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
		PERCENTILES.forEach((percentile, at) => {
			// Whole milliseconds, and the interpolation rule is still the stated
			// one: the rounding happens after it, not instead of it.
			expect(view.runs[0].ms[at]).toBe(Math.round(quantile(ms, percentile / 100)));
		});
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
		expect(view.taller.tokens).toBe('read');
		expect(view.taller.seconds).toBe('written');
		expect(view.ratio.tokens).toBeCloseTo(5.0, 12);
		expect(view.ratio.seconds).toBeCloseTo(3.0, 12);
	});

	test('a run nobody timed draws no seconds and still draws its tokens', () => {
		const view = readAgainstWritten([
			healthRow({ item_id: 'x', input_tokens: 1000, output_tokens: 200 })
		]);
		expect(view.runs[0].input).toBe(1000);
		expect(view.runs[0].prefillMs).toBeNull();
		expect(view.runs[0].decodeMs).toBeNull();
		// Zero timed runs is the seconds grain's absent state, and it is the
		// figure the page branches on.
		expect(view.timedRuns).toBe(0);
		expect(view.ratio.seconds).toBeNull();
		expect(view.taller.seconds).toBeNull();
		expect(workChart(view.runs, view, 'seconds').empty).toBe(true);
		expect(workChart(view.runs, view, 'tokens').empty).toBe(false);
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

	test('one axis under the measured limit, and the smaller series takes a row past it', () => {
		const view = readAgainstWritten(health);
		expect(view.split.tokens).toBe(false);
		expect(view.split.seconds).toBe(false);
		const shared = workChart(view.runs, view, 'tokens').option;
		expect(Array.isArray(shared.grid)).toBe(false);
		expect(shared.series).toHaveLength(2);

		// Past the limit the smaller side draws under 5 percent of a shared axis
		// and reads as zero, so it gets its own row on the same categories.
		const lopsided = readAgainstWritten([
			healthRow({
				item_id: 'x',
				input_tokens: 1_000_000,
				output_tokens: 1000,
				prefill_ms: 10,
				decode_ms: 20
			})
		]);
		expect(lopsided.ratio.tokens).toBeGreaterThan(SHARED_AXIS_LIMIT);
		expect(lopsided.split.tokens).toBe(true);
		expect(lopsided.split.seconds).toBe(false);
		const rows = workChart(lopsided.runs, lopsided, 'tokens').option;
		expect(Array.isArray(rows.grid)).toBe(true);
		expect((rows.grid as unknown[]).length).toBe(2);
		// Larger on top, smaller below, on one set of categories.
		expect((rows.series as { name: string }[]).map((series) => series.name)).toEqual([
			'Read',
			'Written'
		]);
		expect((rows.xAxis as { data: string[] }[])[0].data).toEqual(
			(rows.xAxis as { data: string[] }[])[1].data
		);
	});

	test('the unit the panel opens on is named once, and both readers take it from there', () => {
		// The server draws this unit and the page checks its radio at it. Two
		// literals would eventually be two units.
		expect(['tokens', 'seconds']).toContain(DEFAULT_WORK_UNIT);
		expect(DEFAULT_WORK_UNIT).toBe('seconds');
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
		expect(money(1234.5, 'USD', 2)).toBe('1,234.50 USD');
		expect(money(0.0123, 'USD', 4)).toBe('0.0123 USD');
		expect(money(0, 'EUR', 2)).toBe('0.00 EUR');
		// A real cost never prints as zero. The work was not free.
		expect(money(0.0027, 'USD', 2)).toBe('<0.01 USD');
	});
});

test.describe('the committed ledger, read as the page reads it', () => {
	const limits = machineLimits();

	test('the ceilings come from config, and the runner memory from the platform', () => {
		expect(limits.contextWindow).toBe(MODELS.summarize.inference.n_ctx);
		expect(limits.jobTimeoutSeconds).toBe(runConfig().shard_timeout_minutes * 60);
		// CLAUDE.md Guardrail #2: a stock ubuntu-latest runner has 16 GB.
		expect(RUNNER_MEMORY_BYTES).toBe(16 * 1024 * 1024 * 1024);
	});

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
