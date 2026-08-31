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
	percentileCurves,
	pooledReadRate,
	quantile,
	readingAgainstWriting,
	shardBoard,
	tokensByRun,
	PERCENTILES,
	RUNNER_MEMORY_BYTES
} from '../src/lib/charts/machine';
import {
	machineCounters,
	machineLimits,
	type MachineLimits,
	type RunCounters
} from '../src/lib/server/runtime-counters';
import { observabilityConfig, runConfig } from '../src/lib/server/config';

/** `config/idhazh.json` read straight off disk, so a test's expectation comes
 * from the committed file rather than from the reader it is checking. */
const CONFIG = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')
) as {
	run: { shard_timeout_minutes: number };
	models: { inference: { n_ctx: number } };
	observability: {
		cost_currency: string;
		cost_input_per_million: number;
		cost_output_per_million: number;
	};
};

const LIMITS: MachineLimits = {
	contextWindow: CONFIG.models.inference.n_ctx,
	jobTimeoutSeconds: CONFIG.run.shard_timeout_minutes * 60
};

/** Every cell the counters ledger carries, so a fixture row is a whole row. */
function counterRow(cells: Partial<Record<string, string | number>>): Record<string, string> {
	const blank: Record<string, string> = {
		version: '2026-08-31',
		date: '2026-09-04',
		run_id: '2026-09-04-1',
		shard: '0',
		shards: '2',
		scraped_at: '2026-09-04T10:00:00Z',
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
const TWO_SHARDS = [
	counterRow({
		shard: 0,
		prompt_tokens_total: 8000,
		prompt_tokens_cached_total: 2000,
		prompt_seconds_total: 200,
		tokens_predicted_total: 1000,
		tokens_predicted_seconds_total: 200,
		n_decode_total: 1010,
		n_tokens_max: 4096,
		n_busy_slots_per_decode: 1.0,
		job_seconds: 600,
		cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C',
		cpu_busy_pct: 95,
		peak_rss_bytes: 8_000_000_000,
		model_load_ms: 3000
	}),
	counterRow({
		shard: 1,
		prompt_tokens_total: 2000,
		prompt_tokens_cached_total: 2000,
		prompt_seconds_total: 200,
		tokens_predicted_total: 1000,
		tokens_predicted_seconds_total: 400,
		n_decode_total: 1010,
		n_tokens_max: 2048,
		n_busy_slots_per_decode: 1.0,
		job_seconds: 1200,
		cpu_model: 'AMD EPYC 7763 64-Core Processor',
		cpu_busy_pct: 88,
		peak_rss_bytes: 9_000_000_000,
		model_load_ms: 4000
	})
];

function onlyRun(rows: Record<string, string>[]): RunCounters {
	const { runs, refused } = machineCounters(rows, [], LIMITS);
	expect(refused, 'the fixture was refused').toEqual([]);
	expect(runs).toHaveLength(1);
	return runs[0];
}

test.describe('the shard board', () => {
	const run = onlyRun(TWO_SHARDS);
	const board = shardBoard(run, LIMITS.jobTimeoutSeconds);

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
		const tighter = shardBoard(run, 1500);
		expect(tighter.rows[0].job.valueFraction).not.toBeCloseTo(
			board.rows[0].job.valueFraction,
			4
		);
	});

	test('a shard that reported no clock is last and is not read as zero', () => {
		const mixed = onlyRun([TWO_SHARDS[0], counterRow({ shard: 1, prompt_tokens_total: 10 })]);
		const view = shardBoard(mixed, LIMITS.jobTimeoutSeconds);
		expect(view.rows.map((row) => row.shard)).toEqual([0, 1]);
		expect(view.rows[1].jobSeconds).toBeNull();
		expect(view.rows[1].job.empty).toBe(true);
		expect(view.rows[1].cpuModel).toBeNull();
	});

	test('a run nothing reported draws nothing and says so', () => {
		const view = shardBoard(null, LIMITS.jobTimeoutSeconds);
		expect(view.empty).toBe(true);
		expect(view.rows).toEqual([]);
		expect(view.readSpread).toBeNull();
	});
});

test.describe('reading against writing', () => {
	const split = readingAgainstWriting(onlyRun(TWO_SHARDS));

	test('the two rows disagree, and that disagreement is the panel', () => {
		// Seconds: 400 reading against 600 writing, so reading is 40 percent.
		// Tokens: 10,000 read against 2,000 written, so reading is 83 percent.
		const [seconds, tokens] = split.rows;
		expect(seconds.readValue).toBe(400);
		expect(seconds.writeValue).toBe(600);
		expect(seconds.readPct).toBe(40);
		expect(tokens.readValue).toBe(10_000);
		expect(tokens.writeValue).toBe(2000);
		expect(tokens.readPct).toBe(Math.round((10_000 / 12_000) * 100));
	});

	test('the rates are summed and then divided, never averaged', () => {
		// 10,000 tokens over 400 seconds is 25; 2,000 over 600 is 3.333...
		expect(split.readTokensPerSecond).toBeCloseTo(25, 6);
		expect(split.writeTokensPerSecond).toBeCloseTo(2000 / 600, 6);
		expect(split.writeCostRatio).toBeCloseTo(25 / (2000 / 600), 6);
		expect(split.from).toBe(2);
		expect(split.outOf).toBe(2);
	});

	test('a run with no complete shard splits nothing rather than splitting zero', () => {
		const bare = onlyRun([counterRow({ shard: 0 }), counterRow({ shard: 1 })]);
		const view = readingAgainstWriting(bare);
		expect(view.empty).toBe(true);
		expect(view.rows).toEqual([]);
		expect(view.writeCostRatio).toBeNull();
	});
});

test.describe('the prompt cache', () => {
	test('a day is the sum of its runs, in absolute tokens, with its own share', () => {
		const second = TWO_SHARDS.map((row) =>
			counterRow({ ...row, run_id: '2026-09-04-2', prompt_tokens_total: 1000, prompt_tokens_cached_total: 1000 })
		);
		const { runs } = machineCounters([...TWO_SHARDS, ...second], [], LIMITS);
		const [day] = cacheByDay(runs);
		// Run one read 8,000 + 2,000 and cached 2,000 + 2,000; run two read 1,000
		// twice and cached 1,000 twice.
		expect(day.read).toBe(10_000 + 2000);
		expect(day.cached).toBe(4000 + 2000);
		expect(day.runs).toBe(2);
		expect(day.cachedPct).toBe(Math.round((6000 / 18_000) * 100));
	});

	test('a run that reported neither count is left out rather than counted as nothing', () => {
		expect(cacheByDay(machineCounters([counterRow({ shards: 1 })], [], LIMITS).runs)).toEqual([]);
	});
});

test.describe('context headroom', () => {
	test('the longest sequence is a maximum over shards, against the window', () => {
		const [bar] = contextHeadroom([onlyRun(TWO_SHARDS)], CONFIG.models.inference.n_ctx);
		expect(bar.longest).toBe(4096);
		expect(bar.spare).toBe(CONFIG.models.inference.n_ctx - 4096);
		expect(bar.usedPct).toBe(Math.round((4096 / CONFIG.models.inference.n_ctx) * 100));
		expect(bar.from).toBe(2);
	});

	test('no window means no share, and the bar draws empty rather than full', () => {
		const [bar] = contextHeadroom([onlyRun(TWO_SHARDS)], null);
		expect(bar.usedPct).toBeNull();
		expect(bar.spare).toBeNull();
		expect(bar.marks.empty).toBe(true);
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

	test('one curve a run, and every point is the hand-computed quantile', () => {
		const ms = [10, 20, 30, 40, 50, 60];
		const health = ms.map((value, index) =>
			healthRow({ item_id: `a${index}`, summarize_ms: value })
		);
		const view = percentileCurves(health, '2026-09-04', 5);
		expect(view.curves).toHaveLength(1);
		expect(view.curves[0].items).toBe(6);
		expect(view.curves[0].points.map((point) => point.percentile)).toEqual([...PERCENTILES]);
		for (const point of view.curves[0].points) {
			expect(point.ms).toBeCloseTo(quantile(ms, point.percentile / 100), 9);
		}
	});

	test('a run under the floor prints its count and draws no curve', () => {
		const health = [10, 20, 30].map((value, index) =>
			healthRow({ item_id: `b${index}`, summarize_ms: value })
		);
		const view = percentileCurves(health, '2026-09-04', 5);
		expect(view.curves).toEqual([]);
		expect(view.tooFew).toEqual([{ runId: '2026-09-04-1', items: 3 }]);
		expect(view.empty).toBe(true);
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
		const view = percentileCurves(health, '2026-09-04', 5);
		expect(view.curves.map((curve) => curve.runId)).toEqual(['2026-09-04-1', '2026-09-04-2']);
		// A pooled p50 over all ten would be 75. Neither curve says that.
		expect(view.curves[0].points[0].ms).toBe(30);
		expect(view.curves[1].points[0].ms).toBe(300);
	});
});

test.describe('tokens, and what they would have cost somewhere else', () => {
	const health = [
		healthRow({ item_id: 'x', input_tokens: 1_000_000, output_tokens: 200_000 }),
		healthRow({ item_id: 'y', input_tokens: 500_000, output_tokens: 100_000 }),
		healthRow({ item_id: 'z', run_id: '2026-09-04-2', input_tokens: 2000, output_tokens: 400 }),
		healthRow({ item_id: 'w', input_tokens: 999, output_tokens: '' })
	];

	test('a run is the sum of the items that reported both counts', () => {
		const runs = tokensByRun(health);
		expect(runs.map((run) => run.runId)).toEqual(['2026-09-04-1', '2026-09-04-2']);
		// `w` reported no output, so it is not an item that wrote nothing.
		expect(runs[0]).toEqual({
			runId: '2026-09-04-1',
			date: '2026-09-04',
			input: 1_500_000,
			output: 300_000,
			items: 2
		});
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
		expect(limits.contextWindow).toBe(CONFIG.models.inference.n_ctx);
		expect(limits.jobTimeoutSeconds).toBe(runConfig().shard_timeout_minutes * 60);
		// CLAUDE.md Rule #2: a stock ubuntu-latest runner has 16 GB.
		expect(RUNNER_MEMORY_BYTES).toBe(16 * 1024 * 1024 * 1024);
	});

	test('a run the reader refuses is named, never quietly dropped', () => {
		// The committed ledger holds at least one run whose rows cannot be made
		// into one run - two workflow runs computed the same id. The page prints
		// the reason; this asserts the reason exists and is words.
		const { refused } = machineCounters(
			[
				...TWO_SHARDS,
				counterRow({
					shard: 1,
					prompt_tokens_total: 1,
					prompt_seconds_total: 1,
					scraped_at: '2026-09-04T11:00:00Z'
				})
			],
			[],
			limits
		);
		expect(refused).toHaveLength(1);
		expect(refused[0].rows).toBe(3);
		expect(refused[0].why.length).toBeGreaterThan(20);
		expect(refused[0].why).toContain('shard 1');
	});
});
