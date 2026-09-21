/** The build-time reader for the machine record and the item ledger.
 *
 * Two files meet in that reader and neither is derived from the other, so every
 * figure below is stated once as a shard reading and split across both by
 * `support/machine-rows.ts`. Each oracle recomputes its figure from the fixture
 * readings here in the test, never off the module's own output - otherwise the
 * assertion only proves the module agrees with itself.
 *
 * Pure functions and committed ledgers only, in every section but the last. No
 * browser, no SvelteKit alias, no `$app` import: a spec that reaches one fails
 * the whole suite at load rather than failing one test. The last section drives
 * a browser, because what it measures is where the board's strings landed on a
 * phone, and no amount of arithmetic answers that.
 */

import { expect, test } from '@playwright/test';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	clockAgreement,
	curveOf,
	latencyColumns,
	peakMemory,
	percentileHistory,
	quantile,
	PERCENTILES,
	RUNNER_MEMORY_BYTES
} from '../src/lib/charts/machine';
import {
	contextColumns,
	contextCost,
	highLabel,
	type ContextOptions
} from '../src/lib/console/machine/context-cost';
import { readDayShards } from '../src/lib/server/payload';
import {
	CLOCKS_AGREE_WITHIN_PCT,
	hostRows,
	loadMachineCounters,
	machineCounters,
	machineLimits,
	plannedShards,
	type MachineLimits,
	type MachineRun
} from '../src/lib/server/machine-counters';
import { ledgers, plan, type ShardReading } from './support/machine-rows';

const HERE = dirname(fileURLToPath(import.meta.url));

/** The canary tree the browser suite is built from. The three oracles below
 * that drive a page read THIS ledger, never the committed one: the page under
 * the browser was built from it, and reading the other tree would compare a
 * drawing of one ledger against the arithmetic of another. */
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'state');

/** The canary's machine records, read the way the page's server reads them. */
function canaryHosts(): Record<string, string>[] {
	return readDayShards(join(CANARY, 'host-fingerprint'), -1).rows;
}

/** The canary's item rows, over every day file.
 *
 * Through `readDayShards`, the reader the page's own server uses, so a grain
 * change in the store cannot leave this comparing the page against an empty set.
 */
function canaryHealth(): Record<string, string>[] {
	return readDayShards(join(CANARY, 'item-health'), -1).rows;
}

/** What the canary's own run manifests planned, read where the page reads it. */
function canaryPlan(): Map<string, number> {
	return plannedShards(-1, resolve(CANARY, '..', 'digest'));
}

/** A fixed 150-minute job timeout as seconds, not read from config, so these
 * fixtures' expectations do not move when `run.shard_timeout_minutes` does. The
 * committed value is asserted against config further down. */
const LIMITS: MachineLimits = { contextWindow: 8192, jobTimeoutSeconds: 9000 };

/** One shard's figures, under the fixture's day and run. */
function row(reading: ShardReading): ShardReading {
	return { date: '2026-09-02', runId: '2026-09-02-1', shard: 0, ...reading };
}

/** A run of two shards, every figure stated, with values chosen so that every
 * derived figure lands on a number a person can check by hand. */
const FULL: ShardReading[] = [
	row({
		shard: 0,
		serverPromptTokens: 1000,
		serverPromptSeconds: 100,
		cachedTokens: 250,
		writtenTokens: 400,
		writeSeconds: 50,
		longestSequence: 4096,
		jobSeconds: 600,
		cpuModel: 'AMD EPYC 7763 64-Core Processor',
		cpuBusyPct: 99.5,
		peakRssBytes: 6_000_000_000,
		modelLoadMs: 12000
	}),
	row({
		shard: 1,
		serverPromptTokens: 3000,
		serverPromptSeconds: 100,
		cachedTokens: 1000,
		writtenTokens: 600,
		writeSeconds: 150,
		longestSequence: 2048,
		jobSeconds: 900,
		cpuModel: 'INTEL(R) XEON(R) PLATINUM 8573C',
		cpuBusyPct: 88,
		peakRssBytes: 7_000_000_000,
		modelLoadMs: 9000
	})
];

/** The two ledgers and the plan for a set of shard readings. */
function readerInput(readings: ShardReading[], planned?: [string, number][]) {
	const { hosts, health } = ledgers(readings.map(row));
	const byRun = new Map<string, number>();
	for (const reading of readings) {
		const runId = reading.runId ?? '2026-09-02-1';
		byRun.set(runId, (byRun.get(runId) ?? 0) + 1);
	}
	return { hosts, health, planned: planned === undefined ? byRun : plan(...planned) };
}

/** The reader driven over shard readings.
 *
 * `planned` defaults to one shard a reading, which is what a fixture that
 * states every shard of its run means. A case about a plan the shards did not
 * fill states it.
 */
function read(
	readings: ShardReading[],
	options: {
		planned?: [string, number][];
		/** Item rows beyond the one a reading builds, for the clock cases. */
		health?: Record<string, string>[];
		limits?: MachineLimits;
	} = {}
) {
	const input = readerInput(readings, options.planned);
	return machineCounters(
		input.hosts,
		[...input.health, ...(options.health ?? [])],
		input.planned,
		options.limits ?? LIMITS
	);
}

/** Four items whose summed timings put the ledger's rate on the server's. */
function healthRows(runId: string, items: number, tokens: number, prefillMs: number) {
	return Array.from({ length: items }, (_, index) => ({
		// The day, because the reader refuses a run whose rows disagree about which
		// day it belongs to and a blank cell is a second answer.
		date: runId.slice(0, 10),
		run_id: runId,
		item_id: `item-${index}`,
		input_tokens: String(tokens + 100),
		cached_tokens: '100',
		prefill_ms: String(prefillMs),
		decode_ms: '1000'
	}));
}

function only(runs: MachineRun[], runId: string): MachineRun {
	const found = runs.find((run) => run.runId === runId);
	expect(found, `no run ${runId}`).toBeTruthy();
	return found as MachineRun;
}

test.describe('every figure, recomputed by hand', () => {
	const { runs, refused } = read(FULL);
	const run = only(runs, '2026-09-02-1');

	test('nothing was refused and both shards were read', () => {
		expect(refused).toEqual([]);
		expect(run.shards).toBe(2);
		expect(run.reported.map((shard) => shard.shard)).toEqual([0, 1]);
	});

	test('reading and writing are two clocks and never one', () => {
		// 100 + 100 seconds reading against 50 + 150 writing.
		expect(run.readSeconds).toEqual({ value: 200, from: 2, outOf: 2 });
		expect(run.writeSeconds).toEqual({ value: 200, from: 2, outOf: 2 });
		expect(run.readPct).toEqual({ value: 50, from: 2, outOf: 2 });
		// 4,000 tokens over 200 seconds, and 1,000 over 200. Sum over sum, so the
		// slow shard is not given the same weight as the fast one.
		expect(run.readTokensPerSecond).toEqual({ value: 20, from: 2, outOf: 2 });
		expect(run.writeTokensPerSecond).toEqual({ value: 5, from: 2, outOf: 2 });
	});

	test('the spread between shards is carried, not averaged away', () => {
		// 1,000 over 100 seconds is 10 a second; 3,000 over 100 is 30. The run
		// average of 20 says nothing about either end, which is the whole reason
		// this module exists.
		expect(run.reported[0].readTokensPerSecond).toBe(10);
		expect(run.reported[1].readTokensPerSecond).toBe(30);
		expect(run.readSpread).toEqual({ value: 3, from: 2, outOf: 2 });
	});

	test('the cache share is of every token the prompt needed', () => {
		expect(run.promptTokens).toEqual({ value: 4000, from: 2, outOf: 2 });
		expect(run.cachedTokens).toEqual({ value: 1250, from: 2, outOf: 2 });
		// 1,250 of 5,250, not 1,250 of 4,000: the denominator is what the shard
		// needed, read or reused.
		expect(run.cachedPct).toEqual({ value: Math.round((1250 / 5250) * 100), from: 2, outOf: 2 });
		expect(run.cachedPct.value).toBe(24);
	});

	test('the longest sequence is read against the window, and is a maximum', () => {
		expect(run.longestSequence).toEqual({ value: 4096, from: 2, outOf: 2 });
		expect(run.contextUsedPct).toEqual({ value: 50, from: 2, outOf: 2 });
		expect(run.reported[1].contextUsedPct).toBe(25);
	});

	test('the job clock is the slowest shard, read against the timeout', () => {
		expect(run.slowestJobSeconds).toEqual({ value: 900, from: 2, outOf: 2 });
		// 900 of 9,000 seconds is 10 percent, and 600 of 9,000 is 7.
		expect(run.jobUsedPct).toEqual({ value: 10, from: 2, outOf: 2 });
		expect(run.reported[0].jobUsedPct).toBe(7);
	});

	test('the machine cells that landed on 2026-08-29 and 2026-08-30', () => {
		expect(run.cpuModels.value).toEqual([
			'AMD EPYC 7763 64-Core Processor',
			'INTEL(R) XEON(R) PLATINUM 8573C'
		]);
		expect(run.cpuModels.from).toBe(2);
		// The lowest busy figure is the signal: it names the shard that spent its
		// job waiting rather than computing.
		expect(run.lowestCpuBusyPct).toEqual({ value: 88, from: 2, outOf: 2 });
		expect(run.peakRssBytes).toEqual({ value: 7_000_000_000, from: 2, outOf: 2 });
		expect(run.slowestModelLoadMs).toEqual({ value: 12000, from: 2, outOf: 2 });
	});
});

test.describe('the two clocks, checked against each other', () => {
	test('an agreeing run reports the gap it agreed by', () => {
		// Four items, 1,000 read tokens each after cache, 50,000 ms each. That is
		// 4,000 tokens over 200 seconds - exactly what the two shards counted.
		const health = healthRows('2026-09-02-1', 4, 1000, 50_000);
		const run = only(read(FULL, { health }).runs, '2026-09-02-1');
		expect(run.clocks.ledger).toEqual({ tokens: 4000, seconds: 200, parts: 4, rate: 20 });
		expect(run.clocks.server).toEqual({ tokens: 4000, seconds: 200, parts: 2, rate: 20 });
		expect(run.clocks.gapPct).toBe(0);
		expect(run.clocks.agrees).toBe(true);
	});

	test('a disagreeing run says so rather than rounding it away', () => {
		// The same tokens over 300 seconds instead of 200: 13.33 a second against
		// the server's 20, which is 33 percent apart.
		const health = healthRows('2026-09-02-1', 4, 1000, 75_000);
		const run = only(read(FULL, { health }).runs, '2026-09-02-1');
		const expected = ((20 - 4000 / 300) / 20) * 100;
		expect(run.clocks.gapPct).toBeCloseTo(expected, 6);
		expect(run.clocks.gapPct as number).toBeGreaterThan(CLOCKS_AGREE_WITHIN_PCT);
		expect(run.clocks.agrees).toBe(false);
	});

	test('nothing to compare is null, never a disagreement', () => {
		const run = only(read(FULL).runs, '2026-09-02-1');
		expect(run.clocks.ledger.parts).toBe(0);
		expect(run.clocks.gapPct).toBeNull();
		expect(run.clocks.agrees).toBeNull();
	});

	test('an item missing either timing cell is left out of both sums', () => {
		// A row that predates token capture is evidence in neither direction, so
		// counting it as an item that read nothing would drag the rate down.
		const health = [
			...healthRows('2026-09-02-1', 4, 1000, 50_000),
			{ runId: '2026-09-02-1', item_id: 'older', input_tokens: '', cached_tokens: '', prefill_ms: '' }
		];
		const run = only(read(FULL, { health }).runs, '2026-09-02-1');
		expect(run.clocks.ledger.parts).toBe(4);
		expect(run.clocks.gapPct).toBe(0);
	});
});

/** THE ORACLE: the red state only a second instrument can enter.
 *
 * Every check above states one shard reading and splits it across both ledgers,
 * so the two sides are the same expression over the same numbers and the
 * comparison can only pass. This one reads the two canary files as they were
 * written - the item ledger's own rows against the machine record's server
 * counters, built 1.0 to 1.1 percent apart on purpose - and then takes one
 * item's cost away.
 *
 * Blanking the five cost cells of one row is the defect this panel exists for:
 * a prompt the server read and was paid for, and the item ledger never
 * recorded. One clock cannot see it, because one clock has nothing to differ
 * from. Two must, and the panel must turn.
 */
test.describe('THE ORACLE: one item cost, taken away', () => {
	/** The refused row `build-canary.mjs` writes for this, and the five cells
	 * `summarize.py` failed to carry before 2026-09-13. */
	const REFUSED = 'ai-09';
	const COST = ['prefill_ms', 'decode_ms', 'input_tokens', 'output_tokens', 'cached_tokens'];

	function verdict(health: Record<string, string>[]) {
		const counters = machineCounters(canaryHosts(), health, canaryPlan(), LIMITS);
		expect(counters.runs.length, 'the canary records no machine run at all').toBeGreaterThan(0);
		const run = counters.runs[0];
		return { run, view: clockAgreement(run, health, CLOCKS_AGREE_WITHIN_PCT) };
	}

	test('the canary agrees, and disagrees once one row cost goes missing', () => {
		const whole = canaryHealth();
		expect(
			whole.filter((row) => row.item_id === REFUSED).length,
			`the canary writes no ${REFUSED} row, so this oracle has nothing to blank`
		).toBe(1);

		const before = verdict(whole);
		expect(before.run.clocks.agrees).toBe(true);
		expect(before.run.clocks.gapPct as number).toBeLessThan(CLOCKS_AGREE_WITHIN_PCT);
		expect(before.run.clocks.gapPct, 'equal figures would pass a check that never ran').not.toBe(0);
		expect(before.view.grain).toBe('shard');
		expect(before.view.disagreeing).toBe(0);
		expect(before.view.pairs.every((pair) => pair.agrees === true)).toBe(true);

		const blanked = whole.map((row) =>
			row.item_id === REFUSED
				? { ...row, ...Object.fromEntries(COST.map((cell) => [cell, ''])) }
				: row
		);
		const after = verdict(blanked);
		expect(after.run.runId, 'the blanked row moved which run is newest').toBe(before.run.runId);
		expect(after.run.clocks.agrees).toBe(false);
		expect(after.run.clocks.gapPct as number).toBeGreaterThan(CLOCKS_AGREE_WITHIN_PCT);
		expect(after.view.disagreeing).toBeGreaterThan(0);
		expect(after.view.pairs.some((pair) => pair.agrees === false)).toBe(true);

		// And back. The red state is the missing cost and nothing about the order
		// the two readings were taken in.
		expect(verdict(whole).run.clocks.agrees).toBe(true);
	});

	test('the server counters are what turn it, and not the item rows alone', () => {
		// The same blanked ledger, read against a machine record that recorded no
		// server counters at all. Nothing is left to disagree with, so the panel
		// must say it compared nothing rather than report a gap it cannot know.
		const blind = canaryHosts().map((row) => ({
			...row,
			server_prompt_tokens: '',
			server_prompt_seconds: ''
		}));
		const health = canaryHealth().map((row) =>
			row.item_id === REFUSED
				? { ...row, ...Object.fromEntries(COST.map((cell) => [cell, ''])) }
				: row
		);
		const run = machineCounters(blind, health, canaryPlan(), LIMITS).runs[0];
		expect(run.clocks.server.rate).toBeNull();
		expect(run.clocks.agrees).toBeNull();
		expect(run.clocks.agrees).not.toBe(false);
	});
});

test.describe('an empty cell is unknown and never zero', () => {
	/** The same run with the machine cells blank - which is 86 percent of the
	 * committed ledger, because three columns landed on 2026-08-29 and three
	 * more on 2026-08-30. */
	const partial = [
		row({
			runId: '2026-09-02-2',
			shard: 0,
			serverPromptTokens: 1000,
			cachedTokens: 250,
			serverPromptSeconds: 100,
			writtenTokens: 400,
			writeSeconds: 50,
			longestSequence: 4096
		})
	];

	/** The run planned four shards and one of them reported. */
	const PLANNED: [string, number][] = [['2026-09-02-2', 4]];

	test('a cell no shard reported reads as absent, with a denominator of zero', () => {
		const run = only(read(partial, { planned: PLANNED }).runs, '2026-09-02-2');
		for (const [name, reading] of [
			['slowestJobSeconds', run.slowestJobSeconds],
			['jobUsedPct', run.jobUsedPct],
			['lowestCpuBusyPct', run.lowestCpuBusyPct],
			['peakRssBytes', run.peakRssBytes],
			['slowestModelLoadMs', run.slowestModelLoadMs]
		] as const) {
			expect(reading.value, `${name} invented a value`).toBeNull();
			expect(reading.value, `${name} read a blank cell as zero`).not.toBe(0);
			expect(reading.from, `${name} counted a shard that said nothing`).toBe(0);
			expect(reading.outOf, `${name} lost the run's shard count`).toBe(4);
		}
		expect(run.cpuModels.value).toBeNull();
		expect(run.cpuModels.from).toBe(0);
	});

	test('the same run with the cell filled proves the absence was the cell', () => {
		// The bite. If a blank read as zero, the run above would already carry
		// `value: 0, from: 1` and this pair would be indistinguishable from it.
		const filled = [{ ...partial[0], jobSeconds: 600, cpuBusyPct: 99.5 }];
		const run = only(read(filled, { planned: PLANNED }).runs, '2026-09-02-2');
		expect(run.slowestJobSeconds).toEqual({ value: 600, from: 1, outOf: 4 });
		expect(run.lowestCpuBusyPct).toEqual({ value: 99.5, from: 1, outOf: 4 });
	});

	test('a figure from one shard of four carries the four out of the module', () => {
		const run = only(read(partial, { planned: PLANNED }).runs, '2026-09-02-2');
		expect(run.reported).toHaveLength(1);
		expect(run.readSeconds).toEqual({ value: 100, from: 1, outOf: 4 });
		expect(run.readTokensPerSecond).toEqual({ value: 10, from: 1, outOf: 4 });
		// One shard cannot spread against itself, and 1.00x would read as "the
		// hosts agreed" rather than "nothing was compared".
		expect(run.readSpread.value).toBeNull();
	});

	test('a measurement of zero is a measurement and survives as one', () => {
		const zeroed = [{ ...partial[0], cpuBusyPct: 0 }];
		const run = only(read(zeroed, { planned: PLANNED }).runs, '2026-09-02-2');
		expect(run.lowestCpuBusyPct).toEqual({ value: 0, from: 1, outOf: 4 });
	});

	test('no ceiling means no share, and the counter still prints', () => {
		const run = only(
			read(partial, { limits: { contextWindow: null, jobTimeoutSeconds: null } }).runs,
			'2026-09-02-2'
		);
		expect(run.longestSequence.value).toBe(4096);
		expect(run.contextUsedPct.value).toBeNull();
	});
});

test.describe('a shard is a set and never a count', () => {
	/** Two workflow runs computed the same `run_id`, `actions/checkout` pinned
	 * each to a frozen SHA, and a union merge concatenated both. */
	const twice = [
		row({ runId: '2026-09-02-3', shard: 0, serverPromptSeconds: 100, serverPromptTokens: 1000 }),
		row({ runId: '2026-09-02-3', shard: 0, serverPromptSeconds: 100, serverPromptTokens: 1000 }),
		row({ runId: '2026-09-02-3', shard: 1, serverPromptSeconds: 300, serverPromptTokens: 3000 })
	];

	test('one record written twice is counted once', () => {
		const run = only(read(twice, { planned: [['2026-09-02-3', 2]] }).runs, '2026-09-02-3');
		expect(run.reported.map((shard) => shard.shard)).toEqual([0, 1]);
		// 400, not the 500 a naive sum of three rows gives.
		expect(run.readSeconds).toEqual({ value: 400, from: 2, outOf: 2 });
		expect(run.promptTokens).toEqual({ value: 4000, from: 2, outOf: 2 });
		expect(run.readTokensPerSecond).toEqual({ value: 10, from: 2, outOf: 2 });
	});

	test('two servers answering for one shard refuse the run rather than sum it', () => {
		// This is the case that produced -394 seconds against the item ledger. The
		// counters are cumulative for one server process, so two processes cannot
		// be added and neither can be picked over the other.
		const disagree = [twice[0], { ...twice[1], serverPromptSeconds: 250 }, twice[2]];
		const { runs, refused } = read(disagree, { planned: [['2026-09-02-3', 2]] });
		expect(runs.map((run) => run.runId)).not.toContain('2026-09-02-3');
		expect(refused).toHaveLength(1);
		expect(refused[0].runId).toBe('2026-09-02-3');
		// Six, because each of the three readings states one machine row and one item
		// row, and the count a refusal reports is what it could not read.
		expect(refused[0].rows).toBe(6);
		expect(refused[0].why).toContain('shard 0');
	});

	test('a run is refused rather than reported half', () => {
		// Shard 1 is clean in the fixture above. Reporting it on its own would put
		// a figure on the page that reads as the run.
		const { runs } = read([twice[0], { ...twice[1], serverPromptSeconds: 250 }, twice[2]], {
			planned: [['2026-09-02-3', 2]]
		});
		expect(runs).toEqual([]);
	});

	test('more shards than the run says it had is refused', () => {
		const impossible = [
			row({ runId: '2026-09-02-5', shard: 0 }),
			row({ runId: '2026-09-02-5', shard: 1 })
		];
		const { runs, refused } = read(impossible, { planned: [['2026-09-02-5', 1]] });
		expect(runs).toEqual([]);
		expect(refused[0].why).toContain('shards');
	});

	test('rows that disagree about the day are not one run', () => {
		const split = [
			row({ runId: '2026-09-02-6', shard: 0, date: '2026-09-02' }),
			row({ runId: '2026-09-02-6', shard: 1, date: '2026-09-03' })
		];
		const { runs, refused } = read(split);
		expect(runs).toEqual([]);
		expect(refused[0].why).toContain('which day');
	});

	test('a row that does not say which shard it is refuses the run', () => {
		const nameless = [{ ...row({ runId: '2026-09-02-7' }), shard: undefined }];
		const { hosts, health } = ledgers(nameless);
		const { runs, refused } = machineCounters(
			hosts.map((host) => ({ ...host, shard: '' })),
			health,
			plan(['2026-09-02-7', 1]),
			LIMITS
		);
		expect(runs).toEqual([]);
		expect(refused[0].why).toContain('which shard');
	});
});

test.describe('the ledgers this reads are the committed ones', () => {
	const limits = machineLimits();
	const rows = hostRows();
	const { runs, refused } = loadMachineCounters();

	test('the ceilings come from config and not from a literal', () => {
		const config = JSON.parse(
			readFileSync(join(HERE, '..', '..', 'config', 'idhazh.json'), 'utf8')
		) as {
			models_file: string;
			run: { shard_timeout_minutes: number };
		};
		const models = JSON.parse(
			readFileSync(join(HERE, '..', '..', 'config', config.models_file), 'utf8')
		) as { summarize: { inference: { n_ctx: number } } };
		expect(limits.contextWindow).toBe(models.summarize.inference.n_ctx);
		expect(limits.jobTimeoutSeconds).toBe(config.run.shard_timeout_minutes * 60);
	});

	test('the committed ledgers still have rows to read', () => {
		// Guards the rest of this block: every assertion below passes over an
		// empty ledger and would say nothing.
		expect(rows.length).toBeGreaterThan(0);
		expect(runs.length + refused.length).toBeGreaterThan(0);
	});

	test('nothing derived off them is impossible', () => {
		for (const run of runs) {
			if (run.shards !== null) {
				expect(
					run.reported.length,
					`${run.runId} reported more shards than it had`
				).toBeLessThanOrEqual(run.shards);
			}
			expect(new Set(run.reported.map((shard) => shard.shard)).size).toBe(run.reported.length);
			for (const reading of [run.readSeconds, run.writeSeconds, run.promptTokens, run.cachedTokens]) {
				if (reading.value !== null) expect(reading.value).toBeGreaterThanOrEqual(0);
			}
			// The fastest shard cannot be slower than the slowest one.
			if (run.readSpread.value !== null) expect(run.readSpread.value).toBeGreaterThanOrEqual(1);
			// A sequence longer than the window is a record that read the wrong
			// series, not a server that exceeded its own context.
			if (run.contextUsedPct.value !== null) expect(run.contextUsedPct.value).toBeLessThanOrEqual(100);
		}
	});

	test('a run the reader refuses says which run and why', () => {
		for (const run of refused) {
			expect(run.runId).not.toBe('');
			expect(run.why.length).toBeGreaterThan(10);
		}
	});

	test('an absent ledger is an empty read, never a throw', () => {
		expect(machineCounters([], [], new Map(), limits)).toEqual({ runs: [], refused: [] });
	});
});

test.describe('the module cannot reach a browser', () => {
	const source = readFileSync(
		join(HERE, '..', 'src', 'lib', 'server', 'machine-counters.ts'),
		'utf8'
	);

	test('it imports no SvelteKit alias, so no client graph can pull it in', () => {
		// `$lib/server/` is what stops the bundler; this is what stops the module
		// growing a dependency that only resolves inside one. It is also what
		// lets this spec load it in plain Node - a spec that reaches `$app` fails
		// the whole browser suite at load rather than failing one test.
		for (const alias of ["from '$app", "from '$lib", 'import("$app', "import('$app"]) {
			expect(source, `imports ${alias}`).not.toContain(alias);
		}
	});

	test('it reads the ledgers through STATE_ROOT, so a fixture tree can replace them', () => {
		// The canary suite builds a site out of fixture runs by pointing
		// `STATE_ROOT` at a copy. A path built any other way reads the real ledger
		// anyway, and the canary silently measures the wrong tree.
		expect(source).toContain("join(STATE_ROOT, 'host-fingerprint')");
		// And the item side through the shared reader, which is rooted the same way.
		expect(source).toContain('itemHealthRows(days)');
	});
});

// ---------------------------------------------------------------------------
// The board on a phone
//
// The rest of this file is arithmetic and needs no browser. This last section
// does, because what it measures is geometry: how many lines a string was drawn
// over, how wide the box that held it was, and whether two of them landed on the
// same pixels. None of that can be read off the module, and none of it can be
// reasoned about from the CSS - a two-column grid holding five children puts the
// last three wherever the auto-placement algorithm decides, and only a browser
// says where that is.
// ---------------------------------------------------------------------------

/** How few characters a line may hold before the box it is in is too narrow.
 *
 * The declared bound the row asks for: a text node of `n` characters may take at
 * most `ceil(n / 12)` lines. Twelve is well under what any string in a card
 * actually gets - measured 2026-09-01 at 360px, the widest line in a card holds
 * about 48 characters - so the rule fires on a squeezed box and never on an
 * ordinary wrap.
 *
 * What it is written against, measured 2026-09-01 at 360px on the build before
 * this row: `1 h 28 m` was drawn over four lines in a 20px box, one character to
 * a line; `of the 150-minute timeout - 59 percent` took six lines in 41px;
 * `prompt tokens a second` took three lines in 45px; and `Shard 2 job clock`
 * took three lines in 36px.
 */
const AT_LEAST_CHARS_A_LINE = 12;

const PHONE = { width: 360, height: 800 };
const DESKTOP = { width: 1440, height: 1000 };

/** Every visible text node in the board, with the lines it was drawn over and
 * the rectangles it was drawn in. */
const READ_BOARD = () => {
	const board = document.querySelector('[data-shard-board]');
	if (board === null) return null;

	const boxes: {
		text: string;
		lines: number;
		width: number;
		inCard: boolean;
		rects: { x: number; y: number; w: number; h: number }[];
	}[] = [];
	const walker = document.createTreeWalker(board, NodeFilter.SHOW_TEXT);
	let node: Node | null;
	while ((node = walker.nextNode()) !== null) {
		const text = (node.textContent ?? '').replace(/\s+/g, ' ').trim();
		const parent = node.parentElement;
		if (text === '' || parent === null) continue;
		// The screen-reader list repeats every figure as one sentence. It is not
		// drawn, so it has no geometry to check.
		if (parent.closest('.sr-only') !== null) continue;
		const range = document.createRange();
		range.selectNodeContents(node);
		const rects = [...range.getClientRects()].filter((r) => r.width > 0 && r.height > 0);
		if (rects.length === 0) continue;
		boxes.push({
			text,
			// Distinct tops, not raw rect count: one line reports two rectangles
			// when an inline element splits it.
			lines: new Set(rects.map((r) => Math.round(r.top))).size,
			width: Math.round(range.getBoundingClientRect().width),
			inCard: parent.closest('[data-shard-row]') !== null,
			rects: rects.map((r) => ({
				x: Math.round(r.x),
				y: Math.round(r.y),
				w: Math.round(r.width),
				h: Math.round(r.height)
			}))
		});
	}

	const rows = [...board.querySelectorAll('[data-shard-row]')].map((row) => {
		const clock = row.querySelector('[data-shard-cell="clock"]');
		const bar = clock?.querySelector('[data-target-bar]') ?? null;
		return {
			shard: row.getAttribute('data-shard-row') ?? '',
			figures: [...row.querySelectorAll('[data-shard-figure]')].map((cell) => ({
				name: cell.getAttribute('data-shard-figure') ?? '',
				value: (cell.textContent ?? '').replace(/\s+/g, ' ').trim(),
				named: (() => {
					const label = row.querySelector(
						`[data-shard-name="${cell.getAttribute('data-shard-figure')}"]`
					);
					if (label === null) return '';
					const drawn = label.getBoundingClientRect();
					if (drawn.width < 1 || drawn.height < 1) return '';
					return (label.textContent ?? '').replace(/\s+/g, ' ').trim();
				})()
			})),
			// The bar prints its own name at every width, so it needs no cell
			// label - but it still has to be printed, not just declared.
			clockName: bar?.getAttribute('data-target-bar') ?? '',
			clockPrinted: (clock?.textContent ?? '').replace(/\s+/g, ' ').trim(),
			clockValue: (
				clock?.querySelector('[data-target-cell="value"]')?.textContent ?? ''
			).trim()
		};
	});

	const wide = [board, ...board.querySelectorAll('[data-shard-row]')]
		.map((el) => ({
			what: el.getAttribute('data-shard-row') ?? 'board',
			scroll: el.scrollWidth,
			client: el.clientWidth
		}))
		.filter((el) => el.scroll > el.client + 1);

	return { boxes, rows, wide, spelled: board.querySelectorAll('[data-shard-values] li').length };
};

test.describe('the shard board survives a phone', () => {
	test('THE ORACLE: at 360px no string in the board is squeezed onto more lines than it has characters for', async ({
		page
	}) => {
		await page.setViewportSize(PHONE);
		await page.goto('/console/machine/');
		await page.evaluate(() => document.fonts.ready.then(() => true));
		const board = await page.evaluate(READ_BOARD);

		expect(board, 'no shard board on the page').not.toBeNull();
		expect(board!.boxes.length, 'the board drew no text - the scan is broken').toBeGreaterThan(10);
		expect(board!.rows.length, 'the board drew no shard').toBeGreaterThan(0);

		const squeezed = board!.boxes
			.map((box) => ({
				box,
				// A string in the note is prose broken up by inline elements, so one
				// wrap can land inside it without the box being narrow. A string in a
				// card owns its whole line and gets no such allowance.
				allowed: Math.ceil(box.text.length / AT_LEAST_CHARS_A_LINE) + (box.inCard ? 0 : 1)
			}))
			.filter((one) => one.box.lines > one.allowed)
			.map(
				(one) =>
					`"${one.box.text}" took ${one.box.lines} lines in ${one.box.width}px, and ${one.allowed} is its bound`
			);

		expect(squeezed, 'these strings were drawn in a box too narrow to read them in').toEqual([]);
	});

	test('every value on a phone carries a name a reader can see', async ({ page }) => {
		// The head is the only thing naming a column on a desktop, and it is gone
		// below the breakpoint. A value whose only name went with it is a number
		// nobody can act on.
		await page.setViewportSize(PHONE);
		await page.goto('/console/machine/');
		await page.evaluate(() => document.fonts.ready.then(() => true));
		const board = await page.evaluate(READ_BOARD);

		const orphans: string[] = [];
		for (const row of board!.rows) {
			expect(row.figures.length, `shard ${row.shard} drew no figure`).toBeGreaterThan(3);
			for (const figure of row.figures) {
				if (figure.named === '') orphans.push(`shard ${row.shard}: ${figure.name} = ${figure.value}`);
			}
			expect(row.clockName, `shard ${row.shard}: the job clock has no name`).not.toBe('');
			expect(
				row.clockPrinted,
				`shard ${row.shard}: the job clock's name is declared but not printed`
			).toContain(row.clockName);
		}

		expect(orphans, 'these values are drawn with no visible name beside them').toEqual([]);
		// And the one reading a screen reader gets is still whole.
		expect(board!.spelled).toBe(board!.rows.length);
	});

	test('the board holds the same figures at 360 as it holds at 1440', async ({ page }) => {
		// A smaller table is a table. A table with a column dropped to make it fit
		// is a different instrument, and the phone would answer a question the
		// desktop does not.
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/machine/');
		await page.evaluate(() => document.fonts.ready.then(() => true));
		const wide = await page.evaluate(READ_BOARD);

		await page.setViewportSize(PHONE);
		await page.goto('/console/machine/');
		await page.evaluate(() => document.fonts.ready.then(() => true));
		const narrow = await page.evaluate(READ_BOARD);

		const figures = (board: NonNullable<typeof wide>) =>
			board.rows.map((row) => ({
				shard: row.shard,
				clockValue: row.clockValue,
				figures: row.figures.map((figure) => `${figure.name}=${figure.value}`)
			}));

		expect(figures(narrow!)).toEqual(figures(wide!));
	});

	test('nothing in the board scrolls sideways at 360, and no two strings share a pixel', async ({
		page
	}) => {
		await page.setViewportSize(PHONE);
		await page.goto('/console/machine/');
		await page.evaluate(() => document.fonts.ready.then(() => true));
		const board = await page.evaluate(READ_BOARD);

		expect(board!.wide, 'these parts of the board are wider than the room they have').toEqual([]);

		// Per drawn line, not per bounding box: a string that wraps has a box
		// covering its neighbours on every line it touches, and comparing those
		// reports an overlap on every ordinary paragraph.
		const collisions: string[] = [];
		for (let a = 0; a < board!.boxes.length; a += 1) {
			for (let b = a + 1; b < board!.boxes.length; b += 1) {
				for (const one of board!.boxes[a].rects) {
					for (const other of board!.boxes[b].rects) {
						const across = Math.min(one.x + one.w, other.x + other.w) - Math.max(one.x, other.x);
						const down = Math.min(one.y + one.h, other.y + other.h) - Math.max(one.y, other.y);
						if (across > 1 && down > 1) {
							collisions.push(
								`"${board!.boxes[a].text}" over "${board!.boxes[b].text}" by ${across}x${down}px`
							);
						}
					}
				}
			}
		}
		expect(collisions, 'these strings are drawn on top of each other').toEqual([]);
	});
});

// ---------------------------------------------------------------------------
// Context headroom, peak memory, and the shape of a run's latency
//
// Three panels, three oracles, and each one has a case that recomputes its
// figure from the ledger the page was built from and a case that measures what
// the page actually drew. Neither case alone is enough: arithmetic that never
// reaches a screen is a function nobody looks at, and a mark count off a page
// says nothing about whether the number under it is right.
// ---------------------------------------------------------------------------

const CONSOLE = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
).console as {
	window_presets: number[];
	min_attempts_for_rate: number;
	context_high_percentile: number;
	context_cut_off_reason: string;
};
const INFERENCE = JSON.parse(
	readFileSync(
		resolve(
			process.cwd(),
			'..',
			'config',
			(
				JSON.parse(
					readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')
				) as { models_file: string }
			).models_file
		),
		'utf8'
	)
).summarize.inference as { n_ctx: number };

const WIDEST = Math.max(...CONSOLE.window_presets);

/** The limit every canary item ran under. The canary writes the committed
 * `inference.n_ctx`, so a fixture that disagreed with the config would draw a
 * share no run ever had. */
const CANARY_LIMIT = INFERENCE.n_ctx;

/** Drive the shared control to a preset and wait for the page to hold it. */
async function widen(page: import('@playwright/test').Page, days: number) {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

test.describe('Row #21 - the context panel says what the limit already costs', () => {
	/** The knobs the page reads, off the committed config rather than typed here:
	 * a percentile pinned in a test is a percentile the config can no longer
	 * move. */
	const OPTIONS: ContextOptions = {
		percentile: CONSOLE.context_high_percentile,
		cutOffReason: CONSOLE.context_cut_off_reason
	};

	/** Every item's own peak, read straight off the canary ledger rather than off
	 * the module.
	 *
	 * The limit bounds ONE call, and a pipeline that carries an earlier call
	 * forward into a later prompt makes the calls added together a length the
	 * server never held. So the peak is the LARGEST filled call slot and never
	 * their sum - and nothing here counts the slots, which is a config value
	 * rather than a property of the pipeline.
	 *
	 * A run the ledger names keys an entry even when nothing on it is measurable,
	 * because the panel draws an absence rather than dropping the run.
	 */
	function peaksByRun(rows: readonly Record<string, string>[]): Map<string, number[]> {
		const found = new Map<string, number[]>();
		for (const row of rows) {
			const runId = row.run_id ?? '';
			if (runId === '') continue;
			const here = found.get(runId) ?? [];
			found.set(runId, here);
			const limit = Number(row.n_ctx_configured);
			if (row.n_ctx_configured === '' || !Number.isFinite(limit)) continue;
			let peak: number | null = null;
			for (const slot of ['label', 'summary']) {
				const prompt = row[`${slot}_input_tokens`];
				const wrote = row[`${slot}_output_tokens`];
				if (prompt === undefined || prompt === '' || wrote === undefined || wrote === '') continue;
				peak = Math.max(peak ?? 0, Number(prompt) + Number(wrote));
			}
			if (peak !== null) here.push(peak);
		}
		return found;
	}

	test('THE ORACLE: the unused share is the largest article recomputed off the ledger', () => {
		const rows = canaryHealth();
		const expected = [...peaksByRun(rows).values()].flat();
		expect(expected.length, 'the canary ledger measures no article at all').toBeGreaterThan(1);

		const { span } = contextCost(rows, OPTIONS);
		expect(span.limits, 'the canary ran under more than one limit').toEqual([CANARY_LIMIT]);
		expect(span.items, 'the reader measured a different set of articles').toBe(expected.length);
		expect(span.rowsRead).toBe(rows.length);

		const sorted = [...expected].sort((left, right) => left - right);
		const largest = sorted[sorted.length - 1];
		expect(span.largest, 'the largest article is not the ledger\u2019s largest').toBe(largest);
		expect(span.largestPct).toBe(Math.round((largest / CANARY_LIMIT) * 100));
		// The headline. Unused is what the WORST article left behind, so it is the
		// slack that is there even in the case the setting exists for.
		expect(span.unusedPct, 'the unused share is not the largest article inverted').toBe(
			100 - Math.round((largest / CANARY_LIMIT) * 100)
		);
		const median = Math.round(quantile(sorted, 0.5));
		expect(span.median).toBe(median);
		expect(span.timesMedian).toBe(Math.round((CANARY_LIMIT / median) * 10) / 10);
		expect(span.high).toBe(Math.round(quantile(sorted, OPTIONS.percentile / 100)));
		expect(span.percentile).toBe(OPTIONS.percentile);
	});

	test('THE ORACLE: every run mark carries both ends, not one', () => {
		const expected = peaksByRun(canaryHealth());
		const { runs } = contextCost(canaryHealth(), OPTIONS);
		expect(runs.map((run) => run.runId)).toEqual([...expected.keys()].sort());
		expect(
			runs.filter((run) => run.items === 0).length,
			'a run the ledger names but never measured was dropped from the axis'
		).toBeGreaterThan(0);
		for (const run of runs) {
			const peaks = [...(expected.get(run.runId) ?? [])].sort((left, right) => left - right);
			expect(run.items, `${run.runId} measured a different number of articles`).toBe(peaks.length);
			if (peaks.length === 0) {
				// An absence, never a zero: this run recorded nothing to draw.
				expect(run.largest, `${run.runId} drew a peak off no article at all`).toBeNull();
				expect(run.high).toBeNull();
				continue;
			}
			expect(run.largest, `${run.runId} drew a peak the ledger does not hold`).toBe(
				peaks[peaks.length - 1]
			);
			expect(run.high, `${run.runId} drew no second end`).toBe(
				Math.round(quantile(peaks, OPTIONS.percentile / 100))
			);
			// Two ends means two readings. A run whose high equals its largest is
			// legitimate - it has few enough articles that the percentile lands on
			// the top one - but both have to be there.
			expect(run.highPct).not.toBeNull();
			expect(run.largestPct).not.toBeNull();
			expect(run.high as number).toBeLessThanOrEqual(run.largest as number);
		}
	});

	test('a row that recorded no limit is not measured, and a total across calls is not a peak', () => {
		// Two rows the reader must refuse, each for its own reason. A row with no
		// limit has no denominator; a row that recorded one total across its calls
		// recorded a length nothing ever held.
		const rows: Record<string, string>[] = [
			{ run_id: '2026-09-02-1', date: '2026-09-02', label_input_tokens: '900', label_output_tokens: '100' },
			{ run_id: '2026-09-02-1', date: '2026-09-02', n_ctx_configured: '8192', input_tokens: '4000', output_tokens: '500' },
			{ run_id: '2026-09-02-1', date: '2026-09-02', n_ctx_configured: '8192', summary_input_tokens: '1900', summary_output_tokens: '148' }
		];
		const { span, runs } = contextCost(rows, OPTIONS);
		expect(span.rowsRead).toBe(3);
		expect(span.items, 'a row with no limit or no call cells was measured').toBe(1);
		expect(span.largest).toBe(2048);
		expect(span.largestPct).toBe(25);
		expect(span.unusedPct).toBe(75);
		expect(runs[0].items).toBe(1);
	});

	test('the peak is the largest call and never the calls added', () => {
		// The correction this panel was rebuilt for. The later call replays the
		// earlier one, so 1,000 + 2,050 is a length the server never held and 2,050
		// is what the slot actually carried.
		const row: Record<string, string> = {
			run_id: '2026-09-02-1',
			date: '2026-09-02',
			n_ctx_configured: '8192',
			label_input_tokens: '900',
			label_output_tokens: '100',
			summary_input_tokens: '1950',
			summary_output_tokens: '100'
		};
		const { span } = contextCost([row], OPTIONS);
		expect(span.largest, 'the reader added the calls together').toBe(2050);
		expect(span.largest).not.toBe(3050);
	});

	test('a limit that moved inside the span leaves the token figures unshared', () => {
		// Two limits means no single token figure is about the span, so the shares
		// go and the limits are named. Drawing one anyway would be a percentage of
		// a number half the rows never ran under.
		const rows: Record<string, string>[] = [
			{ run_id: '2026-09-02-1', date: '2026-09-02', n_ctx_configured: '8192', summary_input_tokens: '1000', summary_output_tokens: '48' },
			{ run_id: '2026-09-03-1', date: '2026-09-03', n_ctx_configured: '65536', summary_input_tokens: '2000', summary_output_tokens: '48' }
		];
		const { span } = contextCost(rows, OPTIONS);
		expect(span.limits).toEqual([8192, 65536]);
		expect(span.largest, 'the token figure survives a limit that moved').toBe(2048);
		expect(span.largestPct, 'a share was taken against one of two limits').toBeNull();
		expect(span.unusedPct).toBeNull();
		expect(span.timesMedian).toBeNull();
		// Each run still has its own share, because each ran under one limit.
		expect(span.items).toBe(2);
	});

	test('a cut-off reply is counted and an unrecorded one is not called a clean stop', () => {
		const clean = { label_finish_reason: 'stop', summary_finish_reason: 'stop' };
		const cut = { label_finish_reason: 'stop', summary_finish_reason: CONSOLE.context_cut_off_reason };
		const { span } = contextCost([clean, cut, {}], OPTIONS);
		expect(span.calls, 'a row that named no reason was counted as a call').toBe(4);
		expect(span.cutOff).toBe(1);
		expect(span.reasons).toEqual([
			{ reason: 'stop', calls: 3 },
			{ reason: CONSOLE.context_cut_off_reason, calls: 1 }
		]);
	});

	test('the strip prints both ends and names the percentile in words', () => {
		const { runs } = contextCost(canaryHealth(), OPTIONS);
		const columns = contextColumns(runs, CANARY_LIMIT, OPTIONS.percentile);
		expect(columns).toHaveLength(runs.length);
		columns.forEach((column, at) => {
			const run = runs[at];
			const said = Object.fromEntries(column.rows.map((row) => [row.label, row.value]));
			expect(column.date).toBe(run.runId);
			// A run that measured nothing prints a dash, which is the one reading
			// that is not a number the chart could have drawn.
			expect(said['The longest article'].replace(/,/g, '')).toContain(
				run.largest === null ? '-' : String(run.largest)
			);
			expect(said[highLabel(OPTIONS.percentile)].replace(/,/g, '')).toContain(
				run.high === null ? '-' : String(run.high)
			);
			expect(said['Articles measured']).toBe(String(run.items));
		});
		// `p99` is a subsystem term. The strip says it in words a reader who has
		// never met one still understands, and the words follow the knob.
		expect(highLabel(99)).toBe('All but the longest 1 in 100');
		expect(highLabel(95)).toBe('All but the longest 5 in 100');
	});

	test('THE ORACLE: the built page draws both ends a run, in date order, under the rule', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		await expect(page.locator(`[data-window-preset="${WIDEST}"] input`)).toBeEnabled();
		await widen(page, WIDEST);

		const drawn = await page.evaluate(() => {
			const panel = document.querySelector('[data-windowed="machine-context"]');
			if (panel === null) return null;
			const svg = panel.querySelector('svg');
			const rule = panel.querySelector('[data-context-limit]');
			const marksOf = (name: string) =>
				svg === null ? [] : [...svg.querySelectorAll(`[data-context-series="${name}"] circle`)];
			return {
				runs: [...panel.querySelectorAll('[data-context-run]')].map((li) => ({
					runId: li.getAttribute('data-context-run') ?? '',
					largest: li.getAttribute('data-context-largest') ?? '',
					high: li.getAttribute('data-context-high') ?? '',
					said: (li.textContent ?? '').replace(/\s+/g, ' ').trim()
				})),
				largestMarks: marksOf('largest').length,
				highMarks: marksOf('high').length,
				limit: rule?.getAttribute('data-context-limit') ?? '',
				ruleY: rule === null ? null : Number(rule.getAttribute('y1')),
				markYs: marksOf('largest').map((mark) => Number(mark.getAttribute('cy'))),
				unused: panel.querySelector('[data-context-cost]')?.getAttribute('data-context-unused-pct') ?? '',
				cost: (panel.querySelector('[data-context-cost]')?.textContent ?? '').replace(/\s+/g, ' ').trim(),
				cutOff: panel.querySelector('[data-context-cutoff]')?.getAttribute('data-context-cutoff-calls') ?? ''
			};
		});

		expect(drawn, 'no context panel on the page').not.toBeNull();
		const expected = peaksByRun(canaryHealth());
		expect(drawn!.runs.map((run) => run.runId), 'the panel names a different set of runs').toEqual(
			[...expected.keys()].sort()
		);
		// Both ends, one mark each a run the ledger measured. One series alone is
		// the state this row replaced: a single mark cannot say both what an
		// ordinary article takes and what the worst one takes. A run that measured
		// nothing keeps its column and draws no mark, so the two counts differ.
		const measured = drawn!.runs.filter((run) => run.largest !== '').length;
		expect(measured, 'no run on the canary measured an article').toBeGreaterThan(0);
		expect(drawn!.largestMarks, 'the chart drew no worst-case mark').toBe(measured);
		expect(drawn!.highMarks, 'the chart drew only one end a run').toBe(measured);
		for (const run of drawn!.runs) {
			const peaks = [...(expected.get(run.runId) ?? [])].sort((left, right) => left - right);
			if (peaks.length === 0) {
				expect(run.largest, `${run.runId} drew a peak off no article at all`).toBe('');
				expect(run.said, `${run.runId} was dropped instead of drawn as an absence`).toContain(
					'no article recorded'
				);
				continue;
			}
			expect(run.largest, `${run.runId} drew a peak the ledger does not hold`).toBe(
				String(peaks[peaks.length - 1])
			);
			expect(run.said, `${run.runId} prints no denominator`).toMatch(/over \d+ articles?/);
		}
		// Date order, oldest first: a run id is `<date>-<n>`, so a plain sort is
		// the order the chart must be in.
		expect(drawn!.runs.map((run) => run.runId)).toEqual(
			[...drawn!.runs.map((run) => run.runId)].sort()
		);
		// The rule is the limit the rows ran under, and it sits above every mark,
		// which is the geometry that makes it a limit rather than a series.
		expect(drawn!.limit).toBe(String(CANARY_LIMIT));
		expect(drawn!.markYs.length).toBeGreaterThan(0);
		expect(
			Math.min(...drawn!.markYs),
			'a mark is drawn above the limit it cannot exceed'
		).toBeGreaterThanOrEqual(drawn!.ruleY as number);

		// THE ORACLE: the printed unused share is the ledger's own arithmetic.
		const all = [...expected.values()].flat().sort((left, right) => left - right);
		const largest = all[all.length - 1];
		const unused = 100 - Math.round((largest / CANARY_LIMIT) * 100);
		expect(drawn!.unused, 'the printed unused share is not the ledger recomputed').toBe(
			String(unused)
		);
		expect(drawn!.cost, 'the page prints a share without saying what it means').toContain(
			'went spare every time'
		);
		// The canary carries one cut-off reply, which no committed day has ever
		// produced, so the state a shrinking budget reaches is drawn rather than
		// argued about.
		expect(Number(drawn!.cutOff), 'the page counted no cut-off reply').toBeGreaterThan(0);
	});

	test('THE ORACLE: hovering a run prints that run own numbers', async ({ page }) => {
		await page.goto('/console/machine/');
		await expect(page.locator(`[data-window-preset="${WIDEST}"] input`)).toBeEnabled();
		await widen(page, WIDEST);

		const panel = page.locator('[data-windowed="machine-context"]');
		// Go to the panel, not to the plot inside it. `hydrate` observes
		// intersection, so a chart more than a screen down has no `svg` until
		// somebody goes to it, and waiting on that `svg` first waits for the one
		// thing only this scroll produces.
		await panel.evaluate((node) => node.scrollIntoView({ behavior: 'instant', block: 'center' }));
		const plot = panel.locator('svg').first();
		await expect(plot, 'the context chart drew nothing after scrolling to it').toBeVisible({
			timeout: 15000
		});
		const box = await plot.boundingBox();
		expect(box, 'the context chart has no box to point at').not.toBeNull();

		const runs = await panel
			.locator('[data-context-run]')
			.evaluateAll((nodes) => nodes.map((n) => n.getAttribute('data-context-run') ?? ''));

		await page.mouse.move(box!.x + 4, box!.y + box!.height / 2);
		await page.waitForTimeout(150);
		const first = await panel.locator('[data-readout="context"] [data-readout-day]').innerText();
		await page.mouse.move(box!.x + box!.width - 4, box!.y + box!.height / 2);
		await page.waitForTimeout(150);
		const last = await panel.locator('[data-readout="context"] [data-readout-day]').innerText();

		// The strip names the run it is on, and the two ends are two runs.
		expect(first.trim()).toBe(runs[0]);
		expect(last.trim()).toBe(runs[runs.length - 1]);
		expect(first).not.toBe(last);
		// And the numbers under that heading are the ones the list prints for it.
		// The last column is the newest run, which the canary measures; a run it
		// did not measure prints a dash and there would be no number to compare.
		const said = await panel.locator('[data-readout="context"]').innerText();
		const listed = await panel
			.locator(`[data-context-run="${runs[runs.length - 1]}"]`)
			.getAttribute('data-context-largest');
		expect(listed, 'the newest run measured no article, so the readout has no number').not.toBe('');
		expect(said.replace(/,/g, '')).toContain(String(listed));
	});
});

test.describe('Row #20 - peak memory is a maximum and never a sum', () => {
	const highest = 7_000_000_000;

	test('THE ORACLE: the run figure is the largest shard, not their total', () => {
		const run = only(read(FULL).runs, '2026-09-02-1');
		const view = peakMemory(run);
		// 6 GB and 7 GB. A sum would report 13 GB on a machine that has 16.
		expect(view.shards.map((shard) => [shard.shard, shard.bytes])).toEqual([
			[0, 6_000_000_000],
			[1, highest]
		]);
		expect(view.highWater, 'the aggregate is not the maximum').toBe(highest);
		expect(view.highWater, 'the aggregate summed the shards').not.toBe(13_000_000_000);
		expect(view.from).toBe(2);
		expect(view.outOf).toBe(2);
		expect(view.pctOfRunner).toBe(Math.round((highest / RUNNER_MEMORY_BYTES) * 100));
		// Every bar runs to the same ceiling, so their lengths compare.
		const tracks = new Set(view.shards.map((shard) => shard.marks.track));
		expect(tracks.size, 'the per-shard bars are drawn on different tracks').toBe(1);
		expect(view.marks.sense, 'the polarity is decided at the paint site').toBe('lower-is-better');
	});

	test('THE ORACLE: a run the reader refuses contributes nothing to either', () => {
		// Two servers answered for shard 0 of `2026-08-29-3`, so the run cannot be
		// made into one run. It is in the ledger below and must be in neither the
		// per-shard bars nor the aggregate - not as a shard, and not as a zero.
		const refusedRun = [
			row({
				runId: '2026-08-29-3',
				date: '2026-08-29',
				shard: 0,
				peakRssBytes: 15_000_000_000,
				serverPromptSeconds: 100
			}),
			row({
				runId: '2026-08-29-3',
				date: '2026-08-29',
				shard: 0,
				peakRssBytes: 15_000_000_000,
				serverPromptSeconds: 250
			}),
			row({ runId: '2026-08-29-3', date: '2026-08-29', shard: 1, peakRssBytes: 9_000_000_000 })
		];
		const { runs, refused } = read([...FULL, ...refusedRun]);
		expect(refused.map((one) => one.runId)).toEqual(['2026-08-29-3']);
		expect(runs.map((run) => run.runId)).not.toContain('2026-08-29-3');

		// The page reads the newest run the READER handed over, which is the clean
		// one - the refused run's 15 GB is nowhere.
		for (const run of runs) {
			const view = peakMemory(run);
			expect(view.runId).not.toBe('2026-08-29-3');
			expect(view.highWater, 'the refused run reached the aggregate').not.toBe(15_000_000_000);
			expect(view.shards.map((shard) => shard.bytes)).not.toContain(15_000_000_000);
		}
	});

	test('a shard that recorded nothing is left out, never drawn as no memory', () => {
		const partial = [
			row({ runId: '2026-09-02-9', shard: 0, peakRssBytes: 5_000_000_000 }),
			row({ runId: '2026-09-02-9', shard: 1 })
		];
		const view = peakMemory(
			only(read(partial, { planned: [['2026-09-02-9', 4]] }).runs, '2026-09-02-9')
		);
		expect(view.shards.map((shard) => shard.shard)).toEqual([0]);
		expect(view.from).toBe(1);
		expect(view.outOf).toBe(4);
		expect(view.highWater).toBe(5_000_000_000);
	});

	test('no shard recorded it at all is an empty panel, never a zero', () => {
		const view = peakMemory(only(read([row({ shard: 0 })], { planned: [['2026-09-02-1', 2]] }).runs, '2026-09-02-1'));
		expect(view.empty).toBe(true);
		expect(view.highWater).toBeNull();
		expect(view.highWater).not.toBe(0);
	});

	test('THE ORACLE: the built page prints the ledger own bytes, and no sum', async ({ page }) => {
		await page.goto('/console/machine/');
		// The per-shard bars are the shard grain of the merged memory panel, so
		// the grain has to be the one on screen before they are in the document.
		await page
			.locator('[data-shape-switch="memory-grain"] [data-shape-option="shard"]')
			.click();

		const drawn = await page.evaluate(() => {
			const panel = document.querySelector('[data-peak-memory]');
			if (panel === null) return null;
			return {
				runId: panel.getAttribute('data-peak-memory') ?? '',
				highWater: Number(
					panel.querySelector('[data-memory-high-water]')?.getAttribute('data-memory-high-water')
				),
				shards: [...panel.querySelectorAll('[data-memory-shard]')].map((node) => ({
					shard: Number(node.getAttribute('data-memory-shard')),
					bytes: Number(node.getAttribute('data-memory-bytes'))
				}))
			};
		});
		expect(drawn, 'no peak-memory panel on the page').not.toBeNull();

		// Recomputed from the canary item ledger, not from the module. One figure a
		// shard: the highest any of that shard's items reached.
		const byShard = new Map<number, number>();
		for (const row of canaryHealth()) {
			if (row.run_id !== drawn!.runId || row.llama_rss_peak_bytes === '') continue;
			const value = Number(row.llama_rss_peak_bytes);
			if (!Number.isFinite(value)) continue;
			const shard = Number(row.shard);
			byShard.set(shard, Math.max(byShard.get(shard) ?? 0, value));
		}
		const bytes = [...byShard.values()];
		expect(bytes.length, 'the newest canary run records no memory').toBeGreaterThan(0);
		expect(drawn!.shards.map((shard) => shard.bytes).sort()).toEqual([...bytes].sort());
		expect(drawn!.highWater, 'the page drew something other than the maximum').toBe(
			Math.max(...bytes)
		);
		const total = bytes.reduce((carry, value) => carry + value, 0);
		if (bytes.length > 1) {
			expect(drawn!.highWater, 'the page summed the shards').not.toBe(total);
		}
		// The figure the panel exists for, in the unit the runner's limit is quoted
		// in, beside the limit itself.
		await expect(page.locator('[data-peak-memory]')).toContainText(/GiB/);
		await expect(page.locator('[data-peak-memory]')).toContainText(
			`of the runner's ${(RUNNER_MEMORY_BYTES / 1024 / 1024 / 1024).toFixed(2)} GiB`
		);
	});
});

test.describe('Row #21 - one plot a percentile, and one across them', () => {
	let health: Record<string, string>[] = [];
	let history: ReturnType<typeof percentileHistory>;
	test.beforeAll(() => {
		health = canaryHealth();
		history = percentileHistory(health, CONSOLE.min_attempts_for_rate);
	});

	test('THE ORACLE: one value per configured percentile, per readable run', () => {
		// Recomputed here from the rows, so the module never checks itself.
		const timed = new Map<string, number[]>();
		for (const row of health) {
			const ms = Number(row.summarize_ms);
			if (row.summarize_ms === '' || !Number.isFinite(ms) || ms <= 0) continue;
			timed.set(row.run_id ?? '', [...(timed.get(row.run_id ?? '') ?? []), ms]);
		}
		const readable = [...timed.entries()].filter(
			([, values]) => values.length >= CONSOLE.min_attempts_for_rate
		);
		expect(readable.length, 'the canary times too few items to draw anything').toBeGreaterThan(0);

		expect(history.runs.map((run) => run.runId).sort()).toEqual(
			readable.map(([runId]) => runId).sort()
		);
		for (const run of history.runs) {
			expect(run.ms, `${run.runId} drew a different number of percentiles`).toHaveLength(
				PERCENTILES.length
			);
			// Non-decreasing, because a percentile ladder that dips is a sort that
			// did not happen.
			expect([...run.ms], `${run.runId}: the ladder is not in order`).toEqual(
				[...run.ms].sort((a, b) => a - b)
			);
		}
		// A run under the floor is printed, never drawn.
		for (const few of history.tooFew) {
			expect(few.items).toBeLessThan(CONSOLE.min_attempts_for_rate);
			expect(history.runs.map((run) => run.runId)).not.toContain(few.runId);
		}
	});

	test('THE ORACLE: the aggregate reads the newest run own values, at every percentile', () => {
		const newest = history.runs.at(-1);
		expect(newest, 'no run to aggregate').toBeTruthy();
		const curve = curveOf(newest!);
		expect(curve.points.map((point) => point.percentile)).toEqual([...PERCENTILES]);
		PERCENTILES.forEach((percentile, at) => {
			expect(
				curve.points[at].ms,
				`the aggregate and the p${percentile} plot disagree about the newest run`
			).toBe(newest!.ms[at]);
		});
		// And the strip under the plots prints the same ladder.
		const column = latencyColumns([newest!])[0];
		expect(column.date).toBe(newest!.runId);
		expect(column.rows.slice(0, PERCENTILES.length).map((row) => row.label)).toEqual(
			PERCENTILES.map((percentile) => `p${percentile}`)
		);
	});

	test('THE ORACLE: the built page draws a plot a percentile on one shared scale', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		await expect(page.locator(`[data-window-preset="${WIDEST}"] input`)).toBeEnabled();
		await widen(page, WIDEST);

		const drawn = await page.evaluate(() => {
			const panel = document.querySelector('[data-windowed="machine-latency"]');
			if (panel === null) return null;
			const svg = panel.querySelector('svg');
			if (svg === null) return { plots: [], tops: [], runs: 0, empty: true };
			return {
				plots: [...svg.querySelectorAll('[data-latency-series]')].map((group) => ({
					name: group.getAttribute('data-latency-series') ?? '',
					marks: group.querySelectorAll('circle').length,
					// The vertical span the line covers, in the plot own pixels.
					points: (group.querySelector('polyline')?.getAttribute('points') ?? '')
						.split(' ')
						.filter(Boolean)
						.map((pair) => Number(pair.split(',')[1]))
				})),
				tops: [...svg.querySelectorAll('[data-latency-top]')].map((node) =>
					node.getAttribute('data-latency-top')
				),
				runs: Number(svg.getAttribute('data-latency-runs')),
				empty: false
			};
		});

		expect(drawn, 'no latency panel on the page').not.toBeNull();
		expect(drawn!.empty, 'the widest preset drew no latency plot at all').toBe(false);
		// One plot a configured percentile, and each draws one mark a run.
		expect(drawn!.plots.map((plot) => plot.name)).toEqual(
			PERCENTILES.map((percentile) => `p${percentile}`)
		);
		expect(drawn!.runs, 'the panel drew no run').toBeGreaterThan(0);
		for (const plot of drawn!.plots) {
			expect(plot.marks, `${plot.name} drew a different number of marks from the runs`).toBe(
				drawn!.runs
			);
		}
		// ONE domain across all five. Five plots on five domains would each label
		// their own maximum, and the five labels would differ.
		expect(new Set(drawn!.tops).size, 'the five plots are not on one scale').toBe(1);
		expect(drawn!.tops.length, 'a plot draws no scale at all').toBe(PERCENTILES.length);

		// And the shared scale is what makes the heights comparable: with the same
		// domain and the same cell height, a bigger value sits nearer its own plot's
		// top. p99 is the biggest, so within its own cell it sits highest.
		const CELL = 96 + 12;
		const within = (plot: { points: number[] }, at: number, index: number) =>
			plot.points[at] - index * CELL;
		const last = drawn!.runs - 1;
		expect(
			within(drawn!.plots[PERCENTILES.length - 1], last, PERCENTILES.length - 1),
			'p99 does not sit higher in its own plot than p50 does in its'
		).toBeLessThan(within(drawn!.plots[0], last, 0));
	});
});
