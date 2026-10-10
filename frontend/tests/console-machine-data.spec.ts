/** The build-time reader for the machine record and the item ledger.
 *
 * Two files meet in that reader and neither is derived from the other, so every
 * figure below is stated once as a shard reading and split across both by
 * `support/machine-rows.ts`. Each oracle recomputes its figure from the fixture
 * readings here in the test, never off the module's own output - otherwise the
 * assertion only proves the module agrees with itself. Where an oracle needs the
 * two to be independent, it writes each ledger's rows on its own.
 *
 * Pure functions over rows written here, in every section but the last, and the
 * readers over records a test builds. No browser, no SvelteKit alias, no `$app`
 * import: a spec that reaches one fails the whole suite at load rather than
 * failing one test. The last sections drive a browser, because what they measure
 * is where the board's strings landed on a phone, and how the panels draw what
 * the page holds; no amount of arithmetic answers that, and none of it is checked
 * against a figure the canary holds.
 */

import { expect, test } from './support/door-page';
import { mkdirSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	clockAgreement,
	latencyColumns,
	percentileHistory,
	PERCENTILES
} from '../src/lib/charts/machine';
import {
	contextColumns,
	contextCost,
	highLabel,
	type ContextOptions
} from '../src/lib/console/machine/context-cost';
import {
	CLOCKS_AGREE_WITHIN_PCT,
	machineCounters,
	machineLimits,
	type MachineLimits,
	type MachineRun
} from '../src/lib/server/machine-counters';
import { machineRecord } from '../src/lib/server/host-fingerprint';
import { itemHealthRows } from '../src/lib/server/ledger-rows';
import { buildLedger } from './support/ledger-lifecycle';
import { hostRow, itemRow, ledgers, plan, type ShardReading } from './support/machine-rows';

const HERE = dirname(fileURLToPath(import.meta.url));

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
 * comparison can only pass. This one writes the two ledgers apart: the machine
 * record's server counters for one shard, 1,000 prompt tokens read in 100
 * seconds, against three items the item ledger timed on that shard, 300 tokens
 * in 44 seconds, 300 in 45 and 400 in 10 - 1,000 tokens in 99 seconds, 1.01
 * percent off the server - and then takes one item's cost away.
 *
 * Blanking the five cost cells of one row is the defect this panel exists for:
 * a prompt the server read and was paid for, and the item ledger never
 * recorded. One clock cannot see it, because one clock has nothing to differ
 * from. Two must, and the panel must turn: without the third item the ledger
 * reads 600 tokens in 89 seconds, 32.6 percent off.
 */
test.describe('THE ORACLE: one item cost, taken away', () => {
	/** The item whose cost goes missing, and the five cells `summarize.py` failed
	 * to carry before 2026-09-13. */
	const REFUSED = 'ai-09';
	const COST = ['prefill_ms', 'decode_ms', 'input_tokens', 'output_tokens', 'cached_tokens'];
	const RUN = '2030-06-15-1';
	const shard = { date: '2030-06-15', runId: RUN, shard: 0 };
	const hosts = [hostRow({ ...shard, serverPromptTokens: 1000, serverPromptSeconds: 100 })];
	const item = (itemId: string, prompt: number, seconds: number) =>
		itemRow({ ...shard, itemId, longestSequence: prompt + 50, writtenTokens: 50, cachedTokens: 0, ledgerReadSeconds: seconds, writeSeconds: 5 });
	const whole = [item('ai-01', 300, 44), item('ai-02', 300, 45), item(REFUSED, 400, 10)];
	const blanked = whole.map((row) =>
		row.item_id === REFUSED ? { ...row, ...Object.fromEntries(COST.map((cell) => [cell, ''])) } : row
	);

	function verdict(machines: Record<string, string>[], health: Record<string, string>[]) {
		const counters = machineCounters(machines, health, plan([RUN, 1]), LIMITS);
		expect(counters.refused, 'the reader refused the run').toEqual([]);
		const run = only(counters.runs, RUN);
		return { run, view: clockAgreement(run, health, CLOCKS_AGREE_WITHIN_PCT) };
	}

	test('the two ledgers agree, and disagree once one row cost goes missing', () => {
		const before = verdict(hosts, whole);
		expect(before.run.clocks.agrees).toBe(true);
		expect(before.run.clocks.gapPct, '1,000 tokens in 99 seconds against 1,000 in 100').toBeCloseTo(1.0101, 3);
		expect(before.view.grain).toBe('shard');
		expect(before.view.disagreeing).toBe(0);
		expect(before.view.pairs.every((pair) => pair.agrees === true)).toBe(true);

		const after = verdict(hosts, blanked);
		expect(after.run.clocks.agrees).toBe(false);
		expect(after.run.clocks.gapPct, '600 tokens in 89 seconds against 1,000 in 100').toBeCloseTo(32.584, 2);
		expect(after.view.disagreeing).toBeGreaterThan(0);
		expect(after.view.pairs.some((pair) => pair.agrees === false)).toBe(true);

		// And back. The red state is the missing cost and nothing about the order
		// the two readings were taken in.
		expect(verdict(hosts, whole).run.clocks.agrees).toBe(true);
	});

	test('the server counters are what turn it, and not the item rows alone', () => {
		// The same blanked ledger, read against a machine record that recorded no
		// server counters at all. Nothing is left to disagree with, so the panel
		// must say it compared nothing rather than report a gap it cannot know.
		const blind = hosts.map((row) => ({ ...row, server_prompt_tokens: '', server_prompt_seconds: '' }));
		const { run } = verdict(blind, blanked);
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

test.describe('two machine records for one shard', () => {
	const SHARD: ShardReading = FULL[0];
	const RUN_ID = SHARD.runId ?? '';

	test('that disagree are refused by name, never read one over the other', () => {
		// Packing keeps one row per job, so the door never hands over two rows for
		// one shard. The reader still refuses them if it is ever handed two: read
		// off whichever came first, the run would describe a machine by chance.
		const { hosts, health } = ledgers([SHARD]);
		const second = {
			...hosts[0],
			cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C',
			job_seconds: '720'
		};
		const { runs, refused } = machineCounters(
			[...hosts, second],
			health,
			plan([RUN_ID, 1]),
			LIMITS
		);
		expect(runs).toEqual([]);
		expect(refused.map((run) => run.runId)).toEqual([RUN_ID]);
		expect(refused[0].why).toContain('two machine records that disagree');
	});
});

test.describe('the ledgers this reads, over a record written here', () => {
	const limits = machineLimits();
	/** Two runs: `FULL`, whose two shards both reported, and one whose rows name
	 * two shards where its manifest planned one, which the reader refuses. */
	const counted = () => {
		const { hosts, health } = ledgers([
			...FULL,
			row({ runId: '2026-09-02-5', shard: 0 }),
			row({ runId: '2026-09-02-5', shard: 1 })
		]);
		return machineCounters(hosts, health, plan(['2026-09-02-1', 2], ['2026-09-02-5', 1]), limits);
	};

	test('the ceilings come from config and not from a literal', () => {
		const config = JSON.parse(
			readFileSync(join(HERE, '..', '..', 'config', 'idhazh.json'), 'utf8')
		) as {
			models_file: string;
			run: { shard_timeout_minutes: number };
		};
		const models = JSON.parse(
			readFileSync(join(HERE, '..', '..', 'config', config.models_file), 'utf8')
		) as { summarizer: { server: { '--ctx-size': number } } };
		expect(limits.contextWindow).toBe(models.summarizer.server['--ctx-size']);
		expect(limits.jobTimeoutSeconds).toBe(config.run.shard_timeout_minutes * 60);
	});

	test('the record reads as one run and one refused run', () => {
		// Guards the rest of this block: every assertion below passes over an
		// empty record and would say nothing.
		const { runs, refused } = counted();
		expect(runs.map((run) => run.runId)).toEqual(['2026-09-02-1']);
		expect(refused.map((run) => run.runId)).toEqual(['2026-09-02-5']);
	});

	test('nothing derived off them is impossible', () => {
		for (const run of counted().runs) {
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
		for (const run of counted().refused) {
			expect(run.runId).not.toBe('');
			expect(run.why.length).toBeGreaterThan(10);
			expect(run.why).toContain('shards');
		}
	});

	test('an absent ledger is an empty read, never a throw', () => {
		expect(machineCounters([], [], new Map(), limits)).toEqual({ runs: [], refused: [] });
	});
});

test.describe('ledger readers respect the fixture root', () => {
	test('an empty root cannot fall back to the populated canary or the archive', async () => {
		// A root the test builds holds both records, two rows a day on 14 and 15 Jun
		// 2030; an empty root beside it holds nothing at all.
		const state = test.info().outputPath('state');
		for (const ledger of ['host-fingerprint', 'item-health'] as const) {
			await buildLedger(state, { ledger, pinned: '2030-06-15', days: [{ ago: 1, rows: 2 }, { ago: 0, rows: 2 }] });
		}
		const empty = test.info().outputPath('empty');
		mkdirSync(empty, { recursive: true });
		const window = { start: '2030-06-14', end: '2030-06-15' };
		for (const read of [machineRecord, itemHealthRows]) {
			const built = await read(window, state);
			expect(built.read.state).toBe('read');
			expect(built.rows).toHaveLength(4);
			const nothing = await read(window, empty);
			expect(nothing.rows).toEqual([]);
			expect(nothing.read.state).not.toBe('read');
			const again = await read(window, state);
			expect(again.rows).toEqual(built.rows);
		}
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

const WIDEST = Math.max(...CONSOLE.window_presets);

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

	/** A record written here, under one limit of 8,192 tokens, read at a percentile
	 * written here too, so every figure below is worked out by hand.
	 *
	 * The first run of 14 Jun 2030 holds three articles whose peaks are 1,024,
	 * 2,048 and 4,096 tokens - the last a label call of 1,000 and a summary call of
	 * 4,096, so the larger call is the peak and never the two added. The first run
	 * of 15 Jun holds one of 3,072 beside a row that recorded no limit, and the
	 * second run of 15 Jun names a row and measures nothing.
	 */
	const AT_90: ContextOptions = { percentile: 90, cutOffReason: CONSOLE.context_cut_off_reason };
	const RECORD: Record<string, string>[] = [
		{ run_id: '2030-06-14-1', date: '2030-06-14', n_ctx_configured: '8192', summary_input_tokens: '1000', summary_output_tokens: '24' },
		{ run_id: '2030-06-14-1', date: '2030-06-14', n_ctx_configured: '8192', summary_input_tokens: '2000', summary_output_tokens: '48' },
		{
			run_id: '2030-06-14-1',
			date: '2030-06-14',
			n_ctx_configured: '8192',
			label_input_tokens: '900',
			label_output_tokens: '100',
			summary_input_tokens: '4000',
			summary_output_tokens: '96'
		},
		{ run_id: '2030-06-15-1', date: '2030-06-15', n_ctx_configured: '8192', summary_input_tokens: '3000', summary_output_tokens: '72' },
		{ run_id: '2030-06-15-1', date: '2030-06-15', summary_input_tokens: '500', summary_output_tokens: '20' },
		{ run_id: '2030-06-15-2', date: '2030-06-15' }
	];

	test('THE ORACLE: the unused share is the largest article recomputed off the ledger', () => {
		const { span } = contextCost(RECORD, AT_90);
		expect(span.limits, 'the record ran under more than one limit').toEqual([8192]);
		expect(span.rowsRead).toBe(6);
		expect(span.items, 'the reader measured a different set of articles').toBe(4);
		expect(span.largest, 'the largest article is not the largest in the record').toBe(4096);
		expect(span.largestPct).toBe(50);
		// The headline. Unused is what the WORST article left behind, so it is the
		// slack that is there even in the case the setting exists for.
		expect(span.unusedPct, 'the unused share is not the largest article inverted').toBe(50);
		// Halfway between 2,048 and 3,072, and the limit is 3.2 times that.
		expect(span.median).toBe(2560);
		expect(span.timesMedian).toBe(3.2);
		// Seven tenths of the way from 3,072 to 4,096: 3,788.8, to the whole token.
		expect(span.high).toBe(3789);
		expect(span.percentile).toBe(90);
	});

	test('THE ORACLE: every run mark carries both ends, not one', () => {
		const { runs } = contextCost(RECORD, AT_90);
		expect(runs).toEqual([
			// Eight tenths of the way from 2,048 to 4,096: 3,686.4, which is 45 percent of the limit.
			{ runId: '2030-06-14-1', date: '2030-06-14', items: 3, high: 3686, largest: 4096, highPct: 45, largestPct: 50 },
			// One article is both ends, and 3,072 is 37.5 percent of the limit, rounded up.
			{ runId: '2030-06-15-1', date: '2030-06-15', items: 1, high: 3072, largest: 3072, highPct: 38, largestPct: 38 },
			// A run the ledger names but never measured keeps its column, as an absence and never a zero.
			{ runId: '2030-06-15-2', date: '2030-06-15', items: 0, high: null, largest: null, highPct: null, largestPct: null }
		]);
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

	test('no rows at all is an absence the panel can name, never a zero', () => {
		// The state a fresh clone and a wiped ledger are both in. Every figure is
		// null rather than 0: a limit nothing ran under has no share, and a zero
		// share would read as a limit nothing needs.
		const { runs, span } = contextCost([], OPTIONS);
		expect(runs).toEqual([]);
		expect(span.rowsRead).toBe(0);
		expect(span.items).toBe(0);
		expect(span.limits).toEqual([]);
		expect(span.largest).toBeNull();
		expect(span.unusedPct, 'an unread limit reported a share').toBeNull();
		expect(span.timesMedian).toBeNull();
		expect(span.calls).toBe(0);
		expect(span.cutOff).toBe(0);
		expect(span.reasons).toEqual([]);
	});

	test('the strip prints both ends and names the percentile in words', () => {
		const { runs } = contextCost(RECORD, AT_90);
		const strip = contextColumns(runs, 8192, AT_90.percentile);
		expect(strip.columns).toEqual(['2030-06-14-1', '2030-06-15-1', '2030-06-15-2']);
		const said = (label: string) => strip.series.find((one) => one.label === label)?.values ?? null;
		// A run that measured nothing prints the not-measured words, which is the one
		// reading that is not a number the chart could have drawn.
		expect(said('The longest article')).toEqual(['4,096 tokens - 50% of 8,192', '3,072 tokens - 38% of 8,192', null]);
		expect(said(highLabel(90))).toEqual(['3,686 tokens - 45% of 8,192', '3,072 tokens - 38% of 8,192', null]);
		expect(said('Articles measured')).toEqual(['3', '1', '0']);
		// `p99` is a subsystem term. The strip says it in words a reader who has
		// never met one still understands, and the words follow the knob.
		expect(highLabel(90)).toBe('All but the longest 10 in 100');
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
		// Which runs there are, and how far each reached, is the record's own
		// arithmetic, pinned above over rows written here. What the page owes is to
		// draw both ends of every run that measured an article, in date order, under
		// the limit, and to print the numbers it draws.
		const runs = drawn!.runs;
		const measured = runs.filter((run) => run.largest !== '');
		expect(measured.length, 'no run in the window measured an article').toBeGreaterThan(0);
		// Both ends, one mark each a run that measured something. One series alone is
		// the state this row replaced: a single mark cannot say both what an ordinary
		// article takes and what the worst one takes. A run that measured nothing
		// keeps its column and draws no mark, so the two counts differ.
		expect(drawn!.largestMarks, 'the chart drew no worst-case mark').toBe(measured.length);
		expect(drawn!.highMarks, 'the chart drew only one end a run').toBe(measured.length);
		for (const run of runs) {
			if (run.largest === '') {
				expect(run.said, `${run.runId} was dropped instead of drawn as an absence`).toContain(
					'no article recorded'
				);
				continue;
			}
			expect(Number(run.high), `${run.runId} drew its second end above its largest`).toBeLessThanOrEqual(
				Number(run.largest)
			);
			expect(run.said, `${run.runId} prints no denominator`).toMatch(/over \d+ articles?/);
		}
		// Date order, oldest first: a run id is `<date>-<n>`, so a plain sort is
		// the order the chart must be in.
		expect(runs.map((run) => run.runId)).toEqual([...runs.map((run) => run.runId)].sort());
		// The rule is the limit the rows ran under, and it sits above every mark,
		// which is the geometry that makes it a limit rather than a series.
		const limit = Number(drawn!.limit);
		expect(limit, 'the rule names no limit').toBeGreaterThan(0);
		expect(drawn!.markYs.length).toBeGreaterThan(0);
		expect(
			Math.min(...drawn!.markYs),
			'a mark is drawn above the limit it cannot exceed'
		).toBeGreaterThanOrEqual(drawn!.ruleY as number);

		// THE ORACLE: the printed unused share is the largest article the page draws,
		// against the limit it draws.
		const largest = Math.max(...measured.map((run) => Number(run.largest)));
		expect(drawn!.unused, 'the printed unused share is not the drawn largest article inverted').toBe(
			String(100 - Math.round((largest / limit) * 100))
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

test.describe('one plot a percentile, on one shared scale', () => {
	/** Three runs written here, at a floor of three items, so every figure below is
	 * worked out by hand: five items on 14 Jun 2030 that took 1, 2, 3, 4 and 10
	 * seconds; two on the first run of 15 Jun, too few to quote a tail; and three on
	 * its second run, of 0.5, 1.5 and 2.5 seconds, beside a row that timed nothing. */
	const FLOOR = 3;
	const timed = (runId: string, ms: string) => ({ run_id: runId, date: runId.slice(0, 10), summarize_ms: ms });
	const health = [
		...['1000', '2000', '3000', '4000', '10000'].map((ms) => timed('2030-06-14-1', ms)),
		...['900', '1100'].map((ms) => timed('2030-06-15-1', ms)),
		...['500', '1500', '2500', ''].map((ms) => timed('2030-06-15-2', ms))
	];
	const history = percentileHistory(health, FLOOR);

	test('THE ORACLE: one value per configured percentile, per readable run', () => {
		expect(PERCENTILES).toEqual([50, 75, 90, 95, 99]);
		// Between the two nearest ranks: the 90th percentile of the first run is six
		// tenths of the way from 4 seconds to 10.
		expect(history.runs).toEqual([
			{ runId: '2030-06-14-1', date: '2030-06-14', items: 5, ms: [3000, 4000, 7600, 8800, 9760] },
			{ runId: '2030-06-15-2', date: '2030-06-15', items: 3, ms: [1500, 2000, 2300, 2400, 2480] }
		]);
		// A run under the floor is printed, never drawn.
		expect(history.tooFew).toEqual([{ runId: '2030-06-15-1', date: '2030-06-15', items: 2 }]);
	});

	test('THE ORACLE: the strip under the plots prints the newest run own ladder', () => {
		const newest = history.runs.at(-1);
		expect(newest?.runId, 'no run to read').toBe('2030-06-15-2');
		const strip = latencyColumns(newest === undefined ? [] : [newest]);
		expect(strip.columns).toEqual(['2030-06-15-2']);
		expect(strip.series.slice(0, PERCENTILES.length).map((one) => [one.label, one.values[0]])).toEqual([
			['p50', '1.5 s'],
			['p75', '2.0 s'],
			['p90', '2.3 s'],
			['p95', '2.4 s'],
			['p99', '2.5 s']
		]);
	});

	test('THE ORACLE: the printed spread is the newest run slowest over its middle', async ({
		page
	}) => {
		await page.goto('/console/machine/');
		await expect(page.locator(`[data-window-preset="${WIDEST}"] input`)).toBeEnabled();
		await widen(page, WIDEST);

		const printed = page.locator('[data-latency-spread]');
		await expect(printed, 'the trend panel printed no spread at all').toHaveCount(1);
		// The ladder behind it is pinned above, over runs written here. On the page
		// the slowest articles can never have taken less time than the middle one,
		// and the sentence carries the number rather than leaving it in an attribute
		// only a test can read.
		const spread = Number(await printed.getAttribute('data-latency-spread'));
		expect(spread).toBeGreaterThanOrEqual(1);
		await expect(printed).toContainText(`${spread.toFixed(1)} times as long`);
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
