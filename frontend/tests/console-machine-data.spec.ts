/** The build-time reader for `state/runtime-counters.csv`.
 *
 * The ledger has been committed since 2026-08-27 and nothing read a cell of it
 * until this module, so every figure it produces is new and none of it has ever
 * been checked on a screen. Each oracle below recomputes its figure from the
 * fixture rows here in the test, never off the module's own output - otherwise
 * the assertion only proves the module agrees with itself.
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
	contextColumns,
	contextHeadroom,
	curveOf,
	latencyColumns,
	peakMemory,
	percentileHistory,
	PERCENTILES,
	RUNNER_MEMORY_BYTES
} from '../src/lib/charts/machine';
import {
	CLOCKS_AGREE_WITHIN_PCT,
	machineCounters,
	machineLimits,
	runtimeCounterRows,
	type MachineLimits,
	type RunCounters
} from '../src/lib/server/runtime-counters';

const HERE = dirname(fileURLToPath(import.meta.url));

/** The canary tree the browser suite is built from. The three oracles below
 * that drive a page read THIS ledger, never the committed one: the page under
 * the browser was built from it, and reading the other tree would compare a
 * drawing of one ledger against the arithmetic of another. */
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'state');

/** The canary's counter rows, read the way the page's server reads them. */
function canaryCounters(): Record<string, string>[] {
	const text = readFileSync(join(CANARY, 'runtime-counters.csv'), 'utf8');
	const lines = text.split('\n').filter(Boolean);
	const header = lines[0].split(',');
	return lines
		.slice(1)
		.map((line) => Object.fromEntries(header.map((key, at) => [key, line.split(',')[at] ?? ''])));
}

/** The canary's item rows, over every month shard. */
function canaryHealth(): Record<string, string>[] {
	const dir = join(CANARY, 'item-health');
	const rows: Record<string, string>[] = [];
	for (const name of readdirSync(dir).filter((entry) => entry.endsWith('.csv')).sort()) {
		const lines = readFileSync(join(dir, name), 'utf8').split('\n').filter(Boolean);
		const header = lines[0].split(',');
		for (const line of lines.slice(1)) {
			const cells = line.split(',');
			rows.push(Object.fromEntries(header.map((key, at) => [key, cells[at] ?? ''])));
		}
	}
	return rows;
}

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
// Three panels, three oracles, and each one has an arm that recomputes its
// figure from the ledger the page was built from and an arm that measures what
// the page actually drew. Neither arm alone is enough: arithmetic that never
// reaches a screen is a function nobody looks at, and a mark count off a page
// says nothing about whether the number under it is right.
// ---------------------------------------------------------------------------

const CONSOLE = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
).console as { window_presets: number[]; min_attempts_for_rate: number };
const INFERENCE = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'idhazh.json'), 'utf8')
).models.inference as { n_ctx: number };

const WIDEST = Math.max(...CONSOLE.window_presets);

/** Drive the shared control to a preset and wait for the page to hold it. */
async function widen(page: import('@playwright/test').Page, days: number) {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

test.describe('Row #19 - context headroom is one chart with a limit rule', () => {
	const limits: MachineLimits = { contextWindow: INFERENCE.n_ctx, jobTimeoutSeconds: 9000 };
	let runs: RunCounters[] = [];
	test.beforeAll(() => {
		runs = machineCounters(canaryCounters(), [], limits).runs;
	});

	/** The longest sequence per run, read straight off the CSV rather than off
	 * the module - a maximum over the run's shards, blanks skipped. */
	function longestByRun(): Map<string, number> {
		const found = new Map<string, number>();
		for (const row of canaryCounters()) {
			const value = Number(row.n_tokens_max);
			if (row.n_tokens_max === '' || !Number.isFinite(value)) continue;
			const runId = row.run_id ?? '';
			found.set(runId, Math.max(found.get(runId) ?? 0, value));
		}
		return found;
	}

	test('THE ORACLE: one mark a run, and the spare series is the window less it', () => {
		const expected = longestByRun();
		expect(expected.size, 'the canary ledger records no sequence length').toBeGreaterThan(1);

		const bars = contextHeadroom(runs, limits.contextWindow);
		const window = INFERENCE.n_ctx;
		expect(bars.map((bar) => bar.runId).sort()).toEqual([...expected.keys()].sort());
		for (const bar of bars) {
			const longest = expected.get(bar.runId) as number;
			expect(bar.longest, `${bar.runId} drew a sequence the ledger does not hold`).toBe(longest);
			// The second series is derived, and this is what it is derived from.
			expect(bar.spare, `${bar.runId}: spare is not the window less the longest`).toBe(
				window - longest
			);
			expect(bar.usedPct).toBe(Math.round((longest / window) * 100));
		}
	});

	test('no ceiling means no spare series and no share, and the sequence survives', () => {
		// The bite for the clause above: a spare computed from a window nobody
		// configured would be a number invented by the chart.
		for (const bar of contextHeadroom(runs, null)) {
			expect(bar.spare).toBeNull();
			expect(bar.usedPct).toBeNull();
			expect(bar.longest).not.toBeNull();
		}
	});

	test('the strip prints the same three numbers the chart drew', () => {
		const bars = contextHeadroom(runs, limits.contextWindow);
		const columns = contextColumns(bars, limits.contextWindow);
		expect(columns).toHaveLength(bars.length);
		columns.forEach((column, at) => {
			const bar = bars[at];
			expect(column.date).toBe(bar.runId);
			const said = Object.fromEntries(column.rows.map((row) => [row.label, row.value]));
			expect(said['Longest sequence'].replace(/,/g, '')).toContain(String(bar.longest));
			expect(said['Spare'].replace(/,/g, '')).toContain(String(bar.spare));
			expect(said['Of the window']).toContain(`${bar.usedPct}%`);
		});
	});

	test('THE ORACLE: the built page draws one mark a run, in date order, under the rule', async ({
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
			return {
				runs: [...panel.querySelectorAll('[data-context-run]')].map((li) => ({
					runId: li.getAttribute('data-context-run') ?? '',
					longest: Number(li.getAttribute('data-context-longest')),
					said: (li.textContent ?? '').replace(/\s+/g, ' ').trim()
				})),
				marks: svg === null ? 0 : svg.querySelectorAll('[data-context-series="longest"] circle').length,
				spare: svg === null ? '' : (svg.querySelector('[data-context-series="spare"] polyline, polyline[data-context-series="spare"]')?.getAttribute('points') ?? ''),
				limit: rule?.getAttribute('data-context-limit') ?? '',
				ruleY: rule === null ? null : Number(rule.getAttribute('y1')),
				markYs: svg === null ? [] : [...svg.querySelectorAll('[data-context-series="longest"] circle')].map((c) => Number(c.getAttribute('cy')))
			};
		});

		expect(drawn, 'no context panel on the page').not.toBeNull();
		const expected = longestByRun();
		// One mark a run, and the runs are the ones the ledger holds.
		expect(drawn!.runs.length, 'the panel names a different set of runs').toBe(expected.size);
		expect(drawn!.marks, 'the chart drew a different number of marks from the runs it names').toBe(
			drawn!.runs.length
		);
		for (const run of drawn!.runs) {
			expect(run.longest, `${run.runId} drew a sequence the ledger does not hold`).toBe(
				expected.get(run.runId)
			);
			expect(run.said, `${run.runId} prints no denominator`).toMatch(/over \d+ of \d+ shards/);
		}
		// Date order, oldest first: a run id is `<date>-<n>`, so a plain sort is
		// the order the chart must be in.
		expect(drawn!.runs.map((run) => run.runId)).toEqual(
			[...drawn!.runs.map((run) => run.runId)].sort()
		);
		// The rule is the configured window, and it sits above every mark, which
		// is the geometry that makes it a limit rather than a series.
		expect(drawn!.limit).toBe(String(INFERENCE.n_ctx));
		expect(drawn!.markYs.length).toBeGreaterThan(0);
		expect(
			Math.min(...drawn!.markYs),
			'a mark is drawn above the window it cannot exceed'
		).toBeGreaterThanOrEqual(drawn!.ruleY as number);
		expect(drawn!.spare, 'the spare series drew nothing').not.toBe('');
	});

	test('THE ORACLE: hovering a run prints that run own three numbers', async ({ page }) => {
		await page.goto('/console/machine/');
		await expect(page.locator(`[data-window-preset="${WIDEST}"] input`)).toBeEnabled();
		await widen(page, WIDEST);

		const panel = page.locator('[data-windowed="machine-context"]');
		const plot = panel.locator('svg').first();
		await plot.scrollIntoViewIfNeeded();
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
		const said = await panel.locator('[data-readout="context"]').innerText();
		const listed = await panel
			.locator(`[data-context-run="${runs[runs.length - 1]}"]`)
			.getAttribute('data-context-longest');
		expect(said.replace(/,/g, '')).toContain(String(listed));
	});
});

test.describe('Row #20 - peak memory is a maximum and never a sum', () => {
	const highest = 7_000_000_000;

	test('THE ORACLE: the run figure is the largest shard, not their total', () => {
		const run = only(machineCounters(FULL, [], LIMITS).runs, '2026-09-02-1');
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
			row({ run_id: '2026-08-29-3', date: '2026-08-29', shard: 0, peak_rss_bytes: 15_000_000_000 }),
			row({
				run_id: '2026-08-29-3',
				date: '2026-08-29',
				shard: 0,
				peak_rss_bytes: 15_000_000_000,
				prompt_seconds_total: 250,
				scraped_at: '2026-08-29T11:00:00Z'
			}),
			row({ run_id: '2026-08-29-3', date: '2026-08-29', shard: 1, peak_rss_bytes: 9_000_000_000 })
		];
		const { runs, refused } = machineCounters([...FULL, ...refusedRun], [], LIMITS);
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
			row({ run_id: '2026-09-02-9', shards: 4, shard: 0, peak_rss_bytes: 5_000_000_000 }),
			row({ run_id: '2026-09-02-9', shards: 4, shard: 1 })
		];
		const view = peakMemory(only(machineCounters(partial, [], LIMITS).runs, '2026-09-02-9'));
		expect(view.shards.map((shard) => shard.shard)).toEqual([0]);
		expect(view.from).toBe(1);
		expect(view.outOf).toBe(4);
		expect(view.highWater).toBe(5_000_000_000);
	});

	test('no shard recorded it at all is an empty panel, never a zero', () => {
		const view = peakMemory(only(machineCounters([row({ shards: 2 })], [], LIMITS).runs, '2026-09-02-1'));
		expect(view.empty).toBe(true);
		expect(view.highWater).toBeNull();
		expect(view.highWater).not.toBe(0);
	});

	test('THE ORACLE: the built page prints the ledger own bytes, and no sum', async ({ page }) => {
		await page.goto('/console/machine/');

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

		// Recomputed from the canary ledger, not from the module.
		const mine = canaryCounters().filter((row) => row.run_id === drawn!.runId);
		const bytes = mine
			.map((row) => Number(row.peak_rss_bytes))
			.filter((value, at) => mine[at].peak_rss_bytes !== '' && Number.isFinite(value));
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
