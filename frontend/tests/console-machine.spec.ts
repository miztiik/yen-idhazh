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
import {
	clockAgreement,
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
	SHARED_AXIS_LIMIT,
	type RunWork
} from '../src/lib/charts/machine';
import {
	costChart,
	costColumns,
	costLabel,
	costOverDays,
	COST_SHAPES,
	DEFAULT_COST_SHAPE
} from '../src/lib/charts/cost';
import {
	carriesServerCounters,
	machineCounters,
	machineLimits,
	type MachineLimits,
	type MachineRun
} from '../src/lib/server/machine-counters';
import { contextCost } from '../src/lib/console/machine/context-cost';
import { articleCost } from '../src/lib/console/machine/article-cost';
import { processorLostOverDays } from '../src/lib/console/machine/processor-lost';
import { diskReads } from '../src/lib/console/machine/disk-reads';
import { promptReuse } from '../src/lib/console/machine/prompt-reuse';
import { describeRefusedRuns } from '../src/lib/console/machine/refused-runs';
import { describeServerCounters, type ServerCounterNotes } from '../src/lib/server/server-counter-notes';
import { hostRow, ledgers, plan, type ShardReading } from './support/machine-rows';
import { observabilityConfig, runConfig, type ObservabilityConfig } from '../src/lib/server/config';

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

/** The three clocks the board draws that nothing on the site read before.
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

	const board = shardBoard(onlyRun(CLOCKED), LIMITS.jobTimeoutSeconds, CHART_WIDTH);
	const rowFor = (shard: number) => board.rows.find((row) => row.shard === shard)!;

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
		const view = shardBoard(
			onlyRun([{ shard: 0, jobSeconds: 600 }, { shard: 1, jobSeconds: 300 }]),
			LIMITS.jobTimeoutSeconds,
			CHART_WIDTH
		);
		expect(view.rows[0].unclaimedSeconds).toBeNull();
		expect(view.rows[0].clockedItems).toBe(0);
		expect(view.rows[0].queue.empty).toBe(true);
		expect(view.rows[0].queueMaxSeconds).toBeNull();
	});

	test('the queue is a typical item and the worst one, never the two added up', () => {
		// Each item's wait covers the queue ahead of it, so 1 s + 5 s is not 6 s of
		// shard time - it is one item that waited a second and one that waited five.
		const row = rowFor(0);
		expect(row.queueMedianSeconds).toBeCloseTo(3, 6);
		expect(row.queueMaxSeconds).toBeCloseTo(5, 6);
		expect(row.queue.median).toBeCloseTo(3, 6);
		expect(row.queue.max).toBeCloseTo(5, 6);
	});

	test('the queue bars are on the clock scale, so their lengths compare with it', () => {
		// Shard 0 spent 400 seconds in the model and shard 1 spent 300, so the
		// model clocks alone would scale to 400. Shard 1 waited 60 seconds at
		// worst, which is inside that - the scale stays the heaviest clock.
		expect(board.scaleSeconds).toBe(400);
		expect(Number(rowFor(1).queue.notchWidth.replace('%', ''))).toBeCloseTo((60 / 400) * 100, 3);

		// A shard that queued longer than anything computed widens the scale rather
		// than being clipped at the end of the track.
		const queued = shardBoard(
			onlyRun([
				{ ...CLOCKED[0], queueWaitMs: 900_000 },
				CLOCKED[1],
				CLOCKED[2]
			]),
			LIMITS.jobTimeoutSeconds,
			CHART_WIDTH
		);
		expect(queued.scaleSeconds).toBe(900);
		expect(queued.rows.find((row) => row.shard === 0)?.queue.notchWidth).toBe('100.0000%');
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
			...cells
		});
	const refusedRows = [
		article(REFUSED, 0, {
			input_tokens: 4000,
			output_tokens: 300,
			prefill_ms: 8000,
			decode_ms: 30_000,
			summary_input_tokens: 4000,
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
		const options = { percentile: 99, cutOffReason: 'length' };
		const accepted = contextCost(acceptedRows, options).span;
		expect([accepted.rowsRead, accepted.items, accepted.largest]).toEqual([2, 2, 2200]);
		expect([accepted.unusedPct, accepted.cutOff, accepted.calls]).toEqual([73, 0, 2]);
		const both = contextCost(bothRuns, options).span;
		expect([both.rowsRead, both.items, both.largest]).toEqual([4, 4, 6300]);
		// The headline moves: the refused run's article is the one that used most
		// of the limit, and both of its calls ran out of room.
		expect([both.unusedPct, both.cutOff, both.calls]).toEqual([23, 2, 4]);
	});

	test('the cost of one article counts it', () => {
		// The route joins the machine record's processor counts with no run left
		// out, so the refused run's shard names its processors too.
		const processors = [REFUSED, ACCEPTED].map((runId) => ({
			date: '2026-09-04',
			run_id: runId,
			shard: 0,
			threads: 4
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
			{ date: '2026-09-04', run_id: REFUSED, shard: 0, threads: 4 },
			{ date: '2026-09-04', run_id: REFUSED, shard: 0, threads: 8 }
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
		const accepted = processorLostOverDays(acceptedRows, thresholds);
		expect([accepted.from, accepted.outOf, accepted.days[0].worstPct]).toEqual([2, 2, 0.5]);
		expect(accepted.named).toBeNull();
		const both = processorLostOverDays(bothRuns, thresholds);
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
		const columns = Object.keys(bothRuns[0]);
		const accepted = promptReuse(acceptedRows, columns);
		expect([accepted.rowsRead, accepted.items, accepted.floor?.pct]).toEqual([2, 2, 80]);
		const both = promptReuse(bothRuns, columns);
		expect([both.rowsRead, both.items, both.floor?.pct]).toEqual([4, 4, 0]);
		expect(both.requests[0].read).toEqual({ low: 10, median: 26, high: 45, from: 4 });
	});

	test("the box says what leaves the run out and what still counts it, in Reader's words", () => {
		const { runs, refused } = machineCounters(
			hosts,
			bothRuns,
			plan([REFUSED, 2], [ACCEPTED, 1]),
			LIMITS
		);
		// "The run count above" is the route's first line, over the runs the
		// counters keep: one run, though two filed rows. "Figures that pick
		// articles by date" are the six cases above, and each one counts it.
		const open = { days: 7, start: '2026-08-29', end: '2026-09-04' };
		const firstLine = describeServerCounters({
			runs,
			refused,
			ran: ['2026-09-04'],
			articleDays: ['2026-09-04'],
			machineRead: {
				state: 'read',
				through: '2026-09-04',
				first: '2026-09-04',
				lastRows: { period: 'daily', covers: '2026-09-04' },
				lostDays: [],
				setAside: {}
			},
			from: open.start,
			open,
			offered: [open],
			observability: {
				cost_currency: 'USD',
				cost_input_per_million: 0.2,
				cost_output_per_million: 0.6,
				evaluation_enabled: true,
				host_fingerprint: true,
				host_fingerprint_bandwidth_cache_multiple: 2,
				sample_rate: 1
			}
		}).intro;
		expect(firstLine).toBe(
			'1 run in these 7 days, with figures from the model server itself. 2026-08-29 to 2026-09-04.'
		);
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

test.describe("a refused run is a run the server's figures were written down for, where its records hold them", () => {
	// One run a day, on shard 0, in the 7 days that end on 15 Jun 2030. A run is kept where its
	// records fit together, and refused where shard 0 filed two machine records that disagree: about
	// the server's two cells, or only about the machine. Each case hands the lines what the route
	// hands them: the kept and refused runs of one `machineCounters` call, every day with a run from
	// either record, and the article record's days.
	const OPEN = { days: 7, start: '2030-06-09', end: '2030-06-15' };
	const OBSERVABILITY: ObservabilityConfig = {
		cost_currency: 'USD',
		cost_input_per_million: 0.2,
		cost_output_per_million: 0.6,
		evaluation_enabled: true,
		host_fingerprint: true,
		host_fingerprint_bandwidth_cache_multiple: 2,
		sample_rate: 1
	};
	/** Shard 0's machine record for the run on `date`: the probe and the clock, and the server's two
	 *  cells where `prompt` is a number. */
	const machine = (date: string, prompt: number | '' = 900, fingerprint = 'f00d') =>
		hostRow({
			date,
			runId: `${date}-1`,
			shard: 0,
			fingerprint,
			jobSeconds: 600,
			serverPromptTokens: prompt,
			serverPromptSeconds: prompt === '' ? '' : prompt / 100
		});
	/** Two machine records shard 0 of the run on `date` filed that disagree: about the server's
	 *  figures, both holding them, or with `server` false only about the machine, neither holding them. */
	const disagreeing = (date: string, server: boolean) =>
		server ? [machine(date, 900), machine(date, 901)] : [machine(date, ''), machine(date, '', 'beef')];
	/** An article that shard 0 of the run on `date` summarised. */
	const article = (date: string) =>
		healthRow({ date, run_id: `${date}-1`, item_id: `${date}-item`, machine_shard: 0 });
	/** What Hardware says about the server's figures over `open`, from the rows built. The read is
	 *  the 7 days, whichever window is open. */
	const hardware = (
		hosts: Record<string, string>[],
		articleDays: string[],
		{ recording = true, open = OPEN }: { recording?: boolean; open?: typeof OPEN } = {}
	) => {
		const { runs, refused } = machineCounters(hosts, articleDays.map(article), plan(), LIMITS);
		return describeServerCounters({
			runs,
			refused,
			ran: [...new Set([...runs.map((run) => run.date), ...articleDays])].sort(),
			articleDays,
			machineRead: {
				state: 'read',
				through: OPEN.end,
				first: OPEN.start,
				lastRows: { period: 'daily', covers: hosts.map((row) => row.date).sort().at(-1) ?? OPEN.start },
				lostDays: [],
				setAside: {}
			},
			from: OPEN.start,
			open,
			offered: [...new Set([open, OPEN])],
			observability: { ...OBSERVABILITY, host_fingerprint: recording }
		});
	};
	/** Every line printed about the server's figures, apart from the first line. */
	const printed = (notes: ServerCounterNotes): string[] =>
		[notes.measurementOff, ...Object.values(notes.recording)].filter((line): line is string => line !== null);

	test("a day whose only run was refused, while its records hold the server's figures, is not named; a day of article rows alone still is", () => {
		// 10 Jun's run carried the server's figures. 12 Jun's only run was refused: shard 0 filed two
		// machine records that disagree, both holding them. 13 Jun's run is article rows alone.
		const notes = hardware(
			[machine('2030-06-10'), ...disagreeing('2030-06-12', true)],
			['2030-06-10', '2030-06-12', '2030-06-13']
		);
		// The first line counts only the runs the counters keep; the box names the refused one.
		expect(notes.intro).toBe(
			'2 runs in these 7 days, 1 of them with figures from the model server itself. 2030-06-09 to 2030-06-15.'
		);
		expect(printed(notes)).toEqual([
			'No server figures were written down for 13 Jun 2030. The speed figures for that day come from the summariser, not the server.'
		]);
	});

	test('a day whose only run was refused, with no server figure in its records, is still named', () => {
		// 12 Jun's only run was refused because shard 0's two records name two machines. Neither
		// holds a cell the server wrote, so no server figures were written down that day.
		const notes = hardware(
			[machine('2030-06-10'), ...disagreeing('2030-06-12', false)],
			['2030-06-10', '2030-06-12']
		);
		expect(printed(notes)).toEqual([
			'No server figures were written down for 12 Jun 2030. The speed figures for that day come from the summariser, not the server.'
		]);
	});

	test("the server's figures start on a refused day whose records hold them, which is not counted as a day without them", () => {
		// Runs of article rows alone on 9, 10, 11 and 13 Jun. 12 Jun's only run was refused with the
		// server's figures in both records, and 14 Jun's run carried them.
		const notes = hardware(
			[...disagreeing('2030-06-12', true), machine('2030-06-14')],
			['2030-06-09', '2030-06-10', '2030-06-11', '2030-06-12', '2030-06-13', '2030-06-14']
		);
		expect(notes.intro).toBe(
			'5 runs in these 7 days, 1 of them with figures from the model server itself. 2030-06-09 to 2030-06-15.'
		);
		expect(printed(notes)).toEqual([
			'Server figures started on 12 Jun 2030. Earlier in this window, 3 days had a run but no server figures.',
			'No server figures were written down for 13 Jun 2030. The speed figures for that day come from the summariser, not the server.'
		]);
	});

	test("with measurement off, the newest day recorded is a refused day whose records hold the server's figures", () => {
		// Switched off after 12 Jun, whose only run was refused with the server's figures in both
		// records. Article rows kept forming runs on 13 and 14 Jun.
		const notes = hardware(
			[machine('2030-06-10'), ...disagreeing('2030-06-12', true)],
			['2030-06-10', '2030-06-12', '2030-06-13', '2030-06-14'],
			{ recording: false }
		);
		expect(printed(notes)).toEqual([
			'Measurement is off. Nothing has been recorded since 12 Jun 2030. Turn it on in config/idhazh.json.'
		]);
	});

	test("a window whose only run was refused counts 0 runs, in Reader's words, and has no run on record only where the box names none", () => {
		// 12 Jun's only run was refused, with the server's figures in both records. The box under the
		// first line names it, and calls that line "the run count above".
		const refusedOnly = disagreeing('2030-06-12', true);
		expect(hardware(refusedOnly, ['2030-06-12']).intro).toBe('0 runs in these 7 days. 2030-06-09 to 2030-06-15.');
		expect(
			hardware(refusedOnly, ['2030-06-12'], { open: { days: 1, start: '2030-06-12', end: '2030-06-12' } }).intro
		).toBe('This one day had 0 runs. 2030-06-12.');
		// A run refused on 5 Jun is outside the window, so the box names no run in it.
		expect(hardware(disagreeing('2030-06-05', true), ['2030-06-05']).intro).toBe(
			'No run in these 7 days is on record. 2030-06-09 to 2030-06-15.'
		);
	});
});

test.describe('the counterfactual cost, once it has a shape', () => {
	const RATE = { currency: 'USD', inputPerMillion: 0.2, outputPerMillion: 0.6 };
	const SIZE = { heightPx: CHART_HEIGHT };

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
		const shapes = costOverDays(RUNS, RATE, SIZE);
		const bars = shapes.days.reduce((carry, day) => carry + day.read + day.written, 0);
		expect(shapes.runningTotal).toBeCloseTo(bars, 12);

		// And the same figure the four numbers above the chart print, which is the
		// second way the two could have drifted.
		const totals = RUNS.reduce(
			(carry, run) => ({ input: carry.input + run.input, output: carry.output + run.output }),
			{ input: 0, output: 0 }
		);
		expect(shapes.runningTotal).toBeCloseTo(costOf(totals, RATE), 12);

		// Recomputed by hand rather than from the module: 3.5 million prompt tokens
		// at 0.20 is 0.70, and 0.7 million written at 0.60 is 0.42.
		expect(shapes.runningTotal).toBeCloseTo(1.12, 12);
	});

	test('the line is the bars added up in order, point by point', () => {
		const shapes = costOverDays(RUNS, RATE, SIZE);
		let carry = 0;
		for (const day of shapes.days) {
			carry += day.read + day.written;
			expect(day.running).toBeCloseTo(carry, 12);
			expect(day.total).toBeCloseTo(day.read + day.written, 12);
		}
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
			RATE,
			SIZE
		);
		expect(shapes.days).toHaveLength(1);
		expect(shapes.days[0].items).toBe(6);
		expect(shapes.days[0].read).toBeCloseTo(0.3, 12);
		expect(shapes.days[0].written).toBeCloseTo(0.18, 12);
	});

	test('reading is the bottom band and writing the top, in the drawing and in the key', () => {
		const shapes = costOverDays(RUNS, RATE, SIZE);
		const drawn = costChart(shapes, 'daily', RATE.currency).option;
		// A stack draws its first series at the bottom. Read below, write above,
		// on every stacked chart on this console.
		expect((drawn.series as { name: string; stack?: string }[]).map((one) => one.name)).toEqual([
			'Reading the prompts',
			'Writing the answers'
		]);
		expect((drawn.series as { stack?: string }[]).every((one) => one.stack === 'cost')).toBe(true);
		// The strip is the key, so it carries the same two in the same order.
		expect(costColumns(shapes, 'daily', RATE.currency).series.map((one) => one.label)).toEqual([
			'Reading the prompts',
			'Writing the answers'
		]);
	});

	test('the axis names the counterfactual, never the currency on its own', () => {
		// A currency code alone on an axis is the shape a bill takes. The word is
		// on the label a reader meets before any of the numbers, so it travels
		// with the drawing rather than sitting in a sentence near it.
		const shapes = costOverDays(RUNS, RATE, SIZE);
		for (const shape of ['daily', 'running'] as const) {
			const name = (costChart(shapes, shape, RATE.currency).option.yAxis as { name: string })
				.name;
			expect(name).toContain('Counterfactual cost');
			expect(name).toContain(RATE.currency);
			expect(name).not.toMatch(/[$\u00a3\u20ac]/);
			// And again for a reader who gets the description rather than the axis.
			const spoken = costLabel(shape, 30);
			expect(spoken).toContain('counterfactual cost');
			expect(spoken).toContain('never an amount owed');
		}
		expect(costChart(shapes, 'running', RATE.currency).option.yAxis).toHaveProperty(
			'name',
			`Counterfactual cost so far, ${RATE.currency}`
		);
		// Two named states a reader can see both of, and the default is one of them.
		expect(COST_SHAPES.map((one) => one.value)).toContain(DEFAULT_COST_SHAPE);
	});

	test('the running shape is one line over the same days the bars drew', () => {
		const shapes = costOverDays(RUNS, RATE, SIZE);
		const line = costChart(shapes, 'running', RATE.currency).option;
		const series = line.series as { type: string; data: number[] }[];
		expect(series).toHaveLength(1);
		expect(series[0].type).toBe('line');
		expect(series[0].data.at(-1)).toBeCloseTo(shapes.runningTotal, 12);
		// Same categories in both shapes, so the switch moves the reading and not
		// the days it is taken over.
		const bars = costChart(shapes, 'daily', RATE.currency).option;
		expect((line.xAxis as { data: string[] }).data).toEqual(
			(bars.xAxis as { data: string[] }).data
		);
	});

	test('a band under a pixel is printed rather than drawn as a band', () => {
		// Measured against the tallest column, because that is what sets the axis.
		// The committed rate leaves the writing half above a quarter of every day,
		// so this branch is reached by an operator who prices writing at almost
		// nothing - which the rate control allows.
		const thin = costOverDays(RUNS, { ...RATE, outputPerMillion: 0.000_01 }, SIZE);
		expect(thin.splitTooThin).toBe(true);
		const whole = costChart(thin, 'daily', RATE.currency).option;
		expect((whole.series as unknown[]).length).toBe(1);
		expect((whole.series as { name: string }[])[0].name).toBe('Counterfactual, that day');
		// The split does not vanish with the band: it is a measured figure the
		// panel prints, and the number is on the view for the page to print it.
		const plot = CHART_HEIGHT - 30 - 26;
		expect(thin.thinnestShare ?? 0).toBeGreaterThan(0);
		expect((thin.thinnestShare ?? 0) * plot).toBeLessThan(1);

		// At the committed rate both halves are bands, and the measurement says so.
		const drawn = costOverDays(RUNS, RATE, SIZE);
		expect(drawn.splitTooThin).toBe(false);
		expect((drawn.thinnestShare ?? 0) * plot).toBeGreaterThan(1);
	});

	test('no day is an absence, not an empty plot', () => {
		const nothing = costOverDays([], RATE, SIZE);
		expect(nothing.days).toEqual([]);
		expect(nothing.runningTotal).toBe(0);
		expect(nothing.thinnestShare).toBeNull();
		expect(costChart(nothing, 'daily', RATE.currency).empty).toBe(true);
		expect(costChart(nothing, 'running', RATE.currency).empty).toBe(true);
		// A run with no date cannot be laid on a time axis and is not a day.
		const undated = costOverDays([work('', 1_000, 200)], RATE, SIZE);
		expect(undated.days).toEqual([]);
	});

	test('the shape the panel opens on is named once, and both readers take it from there', () => {
		// The server draws this shape and the page checks its radio at it. Two
		// literals would eventually be two shapes.
		expect(['daily', 'running']).toContain(DEFAULT_COST_SHAPE);
		expect(DEFAULT_COST_SHAPE).toBe('daily');
	});
});

test.describe('the committed ledger, read as the page reads it', () => {
	const limits = machineLimits();

	test('the ceilings come from config, and the runner memory from the platform', () => {
		expect(limits.contextWindow).toBe(MODELS.summarizer.server['--ctx-size']);
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
