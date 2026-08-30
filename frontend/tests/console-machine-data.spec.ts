/** The build-time reader for `state/runtime-counters.csv`.
 *
 * The ledger has been committed since 2026-08-27 and nothing read a cell of it
 * until this module, so every figure it produces is new and none of it has ever
 * been checked on a screen. Each oracle below recomputes its figure from the
 * fixture rows here in the test, never off the module's own output - otherwise
 * the assertion only proves the module agrees with itself.
 *
 * Pure functions and committed ledgers only. No browser, no SvelteKit alias, no
 * `$app` import: a spec that reaches one fails the whole suite at load rather
 * than failing one test.
 */

import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	CLOCKS_AGREE_WITHIN_PCT,
	machineCounters,
	machineLimits,
	runtimeCounterRows,
	type MachineLimits,
	type RunCounters
} from '../src/lib/server/runtime-counters';

const HERE = dirname(fileURLToPath(import.meta.url));

/** 150 minutes, the committed `run.shard_timeout_minutes`, as seconds. */
const LIMITS: MachineLimits = { contextWindow: 8192, jobTimeoutSeconds: 9000 };

/** Every cell the ledger carries, so a fixture row is a whole row. */
function row(cells: Partial<Record<string, string | number>>): Record<string, string> {
	const blank: Record<string, string> = {
		version: '2026-08-30',
		date: '2026-09-02',
		run_id: '2026-09-02-1',
		shard: '0',
		shards: '2',
		scraped_at: '2026-09-02T10:00:00Z',
		prompt_tokens_total: '',
		prompt_tokens_cached_total: '',
		prompt_seconds_total: '',
		tokens_predicted_total: '',
		tokens_predicted_seconds_total: '',
		n_decode_total: '',
		n_tokens_max: '',
		n_busy_slots_per_decode: '',
		job_seconds: '',
		cpu_model: '',
		cpu_busy_pct: '',
		peak_rss_bytes: '',
		model_load_ms: ''
	};
	for (const [name, value] of Object.entries(cells)) blank[name] = String(value);
	return blank;
}

/** A run of two shards, every cell populated, with values chosen so that every
 * derived figure lands on a number a person can check by hand. */
const FULL = [
	row({
		shard: 0,
		prompt_tokens_total: 1000,
		prompt_tokens_cached_total: 250,
		prompt_seconds_total: 100,
		tokens_predicted_total: 400,
		tokens_predicted_seconds_total: 50,
		n_decode_total: 404,
		n_tokens_max: 4096,
		n_busy_slots_per_decode: 1.0,
		job_seconds: 600,
		cpu_model: 'AMD EPYC 7763 64-Core Processor',
		cpu_busy_pct: 99.5,
		peak_rss_bytes: 6_000_000_000,
		model_load_ms: 12000
	}),
	row({
		shard: 1,
		prompt_tokens_total: 3000,
		prompt_tokens_cached_total: 1000,
		prompt_seconds_total: 100,
		tokens_predicted_total: 600,
		tokens_predicted_seconds_total: 150,
		n_decode_total: 606,
		n_tokens_max: 2048,
		n_busy_slots_per_decode: 1.0,
		job_seconds: 900,
		cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C',
		cpu_busy_pct: 88,
		peak_rss_bytes: 7_000_000_000,
		model_load_ms: 9000
	})
];

/** Four items whose summed timings put the ledger's rate on the server's. */
function healthRows(runId: string, items: number, tokens: number, prefillMs: number) {
	return Array.from({ length: items }, (_, index) => ({
		run_id: runId,
		item_id: `item-${index}`,
		input_tokens: String(tokens + 100),
		cached_tokens: '100',
		prefill_ms: String(prefillMs),
		decode_ms: '1000'
	}));
}

function only(runs: RunCounters[], runId: string): RunCounters {
	const found = runs.find((run) => run.runId === runId);
	expect(found, `no run ${runId}`).toBeTruthy();
	return found as RunCounters;
}

test.describe('every figure, recomputed by hand', () => {
	const { runs, refused } = machineCounters(FULL, [], LIMITS);
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
		expect(run.slotsPerDecode).toEqual({ value: 1, from: 2, outOf: 2 });
	});
});

test.describe('the two clocks, checked against each other', () => {
	test('an agreeing run reports the gap it agreed by', () => {
		// Four items, 1,000 read tokens each after cache, 50,000 ms each. That is
		// 4,000 tokens over 200 seconds - exactly what the two shards counted.
		const health = healthRows('2026-09-02-1', 4, 1000, 50_000);
		const run = only(machineCounters(FULL, health, LIMITS).runs, '2026-09-02-1');
		expect(run.clocks.ledger).toEqual({ tokens: 4000, seconds: 200, parts: 4, rate: 20 });
		expect(run.clocks.server).toEqual({ tokens: 4000, seconds: 200, parts: 2, rate: 20 });
		expect(run.clocks.gapPct).toBe(0);
		expect(run.clocks.agrees).toBe(true);
	});

	test('a disagreeing run says so rather than rounding it away', () => {
		// The same tokens over 300 seconds instead of 200: 13.33 a second against
		// the server's 20, which is 33 percent apart.
		const health = healthRows('2026-09-02-1', 4, 1000, 75_000);
		const run = only(machineCounters(FULL, health, LIMITS).runs, '2026-09-02-1');
		const expected = ((20 - 4000 / 300) / 20) * 100;
		expect(run.clocks.gapPct).toBeCloseTo(expected, 6);
		expect(run.clocks.gapPct as number).toBeGreaterThan(CLOCKS_AGREE_WITHIN_PCT);
		expect(run.clocks.agrees).toBe(false);
	});

	test('nothing to compare is null, never a disagreement', () => {
		const run = only(machineCounters(FULL, [], LIMITS).runs, '2026-09-02-1');
		expect(run.clocks.ledger.parts).toBe(0);
		expect(run.clocks.gapPct).toBeNull();
		expect(run.clocks.agrees).toBeNull();
	});

	test('an item missing either timing cell is left out of both sums', () => {
		// A row that predates token capture is evidence in neither direction, so
		// counting it as an item that read nothing would drag the rate down.
		const health = [
			...healthRows('2026-09-02-1', 4, 1000, 50_000),
			{ run_id: '2026-09-02-1', item_id: 'older', input_tokens: '', cached_tokens: '', prefill_ms: '' }
		];
		const run = only(machineCounters(FULL, health, LIMITS).runs, '2026-09-02-1');
		expect(run.clocks.ledger.parts).toBe(4);
		expect(run.clocks.gapPct).toBe(0);
	});
});

test.describe('an empty cell is unknown and never zero', () => {
	/** The same run with the machine cells blank - which is 86 percent of the
	 * committed ledger, because three columns landed on 2026-08-29 and three
	 * more on 2026-08-30. */
	const partial = [
		row({
			run_id: '2026-09-02-2',
			shards: 4,
			shard: 0,
			prompt_tokens_total: 1000,
			prompt_tokens_cached_total: 250,
			prompt_seconds_total: 100,
			tokens_predicted_total: 400,
			tokens_predicted_seconds_total: 50,
			n_tokens_max: 4096
		})
	];

	test('a cell no shard reported reads as absent, with a denominator of zero', () => {
		const run = only(machineCounters(partial, [], LIMITS).runs, '2026-09-02-2');
		for (const [name, reading] of [
			['slowestJobSeconds', run.slowestJobSeconds],
			['jobUsedPct', run.jobUsedPct],
			['lowestCpuBusyPct', run.lowestCpuBusyPct],
			['peakRssBytes', run.peakRssBytes],
			['slowestModelLoadMs', run.slowestModelLoadMs],
			['slotsPerDecode', run.slotsPerDecode]
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
		const filled = [{ ...partial[0], job_seconds: '600', cpu_busy_pct: '99.5' }];
		const run = only(machineCounters(filled, [], LIMITS).runs, '2026-09-02-2');
		expect(run.slowestJobSeconds).toEqual({ value: 600, from: 1, outOf: 4 });
		expect(run.lowestCpuBusyPct).toEqual({ value: 99.5, from: 1, outOf: 4 });
	});

	test('a figure from one shard of four carries the four out of the module', () => {
		const run = only(machineCounters(partial, [], LIMITS).runs, '2026-09-02-2');
		expect(run.reported).toHaveLength(1);
		expect(run.readSeconds).toEqual({ value: 100, from: 1, outOf: 4 });
		expect(run.readTokensPerSecond).toEqual({ value: 10, from: 1, outOf: 4 });
		// One shard cannot spread against itself, and 1.00x would read as "the
		// hosts agreed" rather than "nothing was compared".
		expect(run.readSpread.value).toBeNull();
	});

	test('a measurement of zero is a measurement and survives as one', () => {
		const zeroed = [{ ...partial[0], cpu_busy_pct: '0' }];
		const run = only(machineCounters(zeroed, [], LIMITS).runs, '2026-09-02-2');
		expect(run.lowestCpuBusyPct).toEqual({ value: 0, from: 1, outOf: 4 });
	});

	test('no ceiling means no share, and the counter still prints', () => {
		const run = only(
			machineCounters(partial, [], { contextWindow: null, jobTimeoutSeconds: null }).runs,
			'2026-09-02-2'
		);
		expect(run.longestSequence.value).toBe(4096);
		expect(run.contextUsedPct.value).toBeNull();
	});
});

test.describe('a shard is a set and never a count', () => {
	/** Two workflow runs computed the same `run_id`, `actions/checkout` pinned
	 * each to a frozen SHA, and `merge=union` concatenated both. */
	const twice = [
		row({ run_id: '2026-09-02-3', shard: 0, prompt_seconds_total: 100, prompt_tokens_total: 1000 }),
		row({ run_id: '2026-09-02-3', shard: 0, prompt_seconds_total: 100, prompt_tokens_total: 1000 }),
		row({ run_id: '2026-09-02-3', shard: 1, prompt_seconds_total: 300, prompt_tokens_total: 3000 })
	];

	test('one scrape written twice is counted once', () => {
		const run = only(machineCounters(twice, [], LIMITS).runs, '2026-09-02-3');
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
		const disagree = [
			twice[0],
			{ ...twice[1], prompt_seconds_total: '250', scraped_at: '2026-09-02T11:00:00Z' },
			twice[2]
		];
		const { runs, refused } = machineCounters(disagree, [], LIMITS);
		expect(runs.map((run) => run.runId)).not.toContain('2026-09-02-3');
		expect(refused).toHaveLength(1);
		expect(refused[0].runId).toBe('2026-09-02-3');
		expect(refused[0].rows).toBe(3);
		expect(refused[0].why).toContain('shard 0');
	});

	test('a run is refused rather than reported half', () => {
		// Shard 1 is clean in the fixture above. Reporting it on its own would put
		// a figure on the page that reads as the run.
		const { runs } = machineCounters(
			[twice[0], { ...twice[1], prompt_seconds_total: '250' }, twice[2]],
			[],
			LIMITS
		);
		expect(runs).toEqual([]);
	});

	test('more shards than the run says it had is refused', () => {
		const impossible = [
			row({ run_id: '2026-09-02-5', shards: 1, shard: 0 }),
			row({ run_id: '2026-09-02-5', shards: 1, shard: 1 })
		];
		const { runs, refused } = machineCounters(impossible, [], LIMITS);
		expect(runs).toEqual([]);
		expect(refused[0].why).toContain('shards');
	});

	test('rows that disagree about the day are not one run', () => {
		const split = [
			row({ run_id: '2026-09-02-6', shard: 0, date: '2026-09-02' }),
			row({ run_id: '2026-09-02-6', shard: 1, date: '2026-09-03' })
		];
		const { runs, refused } = machineCounters(split, [], LIMITS);
		expect(runs).toEqual([]);
		expect(refused[0].why).toContain('not one run');
	});

	test('a row that does not say which shard it is refuses the run', () => {
		const nameless = [row({ run_id: '2026-09-02-7', shard: '' })];
		const { runs, refused } = machineCounters(nameless, [], LIMITS);
		expect(runs).toEqual([]);
		expect(refused[0].why).toContain('which shard');
	});
});

test.describe('the ledger this reads is the committed one', () => {
	const limits = machineLimits();
	const { rows } = runtimeCounterRows();
	const { runs, refused } = machineCounters(rows, [], limits);

	test('the ceilings come from config and not from a literal', () => {
		const config = JSON.parse(
			readFileSync(join(HERE, '..', '..', 'config', 'idhazh.json'), 'utf8')
		) as { models: { inference: { n_ctx: number } }; run: { shard_timeout_minutes: number } };
		expect(limits.contextWindow).toBe(config.models.inference.n_ctx);
		expect(limits.jobTimeoutSeconds).toBe(config.run.shard_timeout_minutes * 60);
	});

	test('the committed ledger still has rows to read', () => {
		// Guards the rest of this block: every assertion below passes over an
		// empty ledger and would say nothing.
		expect(rows.length).toBeGreaterThan(0);
		expect(runs.length + refused.length).toBeGreaterThan(0);
	});

	test('nothing derived off it is impossible', () => {
		for (const run of runs) {
			expect(run.reported.length, `${run.runId} reported more shards than it had`).toBeLessThanOrEqual(
				run.shards
			);
			expect(new Set(run.reported.map((shard) => shard.shard)).size).toBe(run.reported.length);
			for (const reading of [run.readSeconds, run.writeSeconds, run.promptTokens, run.cachedTokens]) {
				if (reading.value !== null) expect(reading.value).toBeGreaterThanOrEqual(0);
			}
			// The fastest shard cannot be slower than the slowest one.
			if (run.readSpread.value !== null) expect(run.readSpread.value).toBeGreaterThanOrEqual(1);
			// A sequence longer than the window is a scrape that read the wrong
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
		expect(machineCounters([], [], limits)).toEqual({ runs: [], refused: [] });
	});
});

test.describe('the module cannot reach a browser', () => {
	const source = readFileSync(join(HERE, '..', 'src', 'lib', 'server', 'runtime-counters.ts'), 'utf8');

	test('it imports no SvelteKit alias, so no client graph can pull it in', () => {
		// `$lib/server/` is what stops the bundler; this is what stops the module
		// growing a dependency that only resolves inside one. It is also what
		// lets this spec load it in plain Node - a spec that reaches `$app` fails
		// the whole browser suite at load rather than failing one test.
		for (const alias of ["from '$app", "from '$lib", 'import("$app', "import('$app"]) {
			expect(source, `imports ${alias}`).not.toContain(alias);
		}
	});

	test('it reads the ledger through STATE_ROOT, so a fixture tree can replace it', () => {
		// The canary suite builds a site out of fixture runs by pointing
		// `STATE_ROOT` at a copy. A path built any other way reads the real ledger
		// anyway, and the canary silently measures the wrong tree.
		expect(source).toContain("join(STATE_ROOT, 'runtime-counters.csv')");
	});
});
