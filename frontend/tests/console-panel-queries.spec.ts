/** Declared panel questions cross the real disk door; windows and retries never invent evidence. */
import { expect, test } from '@playwright/test';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { FLEET_COLUMNS } from '../src/lib/charts/fleet';
import { platformMixQuery } from '../src/lib/console/queries/machine';
import { modelChangeQuery, summaryLengthQuery } from '../src/lib/console/queries/model';
import { slowerOnSameWorkQuery } from '../src/lib/console/queries/pipelines';
import { compareRuns, failedRuleQuery, hostKey, joinItemHosts, newestRunRows } from '../src/lib/console/queries/shared';
import { feedsFailedQuery } from '../src/lib/console/queries/voices';
import {
	createQueryWindow, rangeFor, tallyAsks, windowRange,
	type PanelDoor, type Range, type RouteReach
} from '../src/lib/console/queries/window';
import { finiteCell, itemRates, nearestRank, qualifyingWork, referenceWork, typicalSeconds } from '../src/lib/console/rates';
import type { Row, SliceResult } from '../src/lib/data/ledger';
import type { LedgerReach } from '../src/lib/data/ledger-reach';
import { reachFromDisk, sliceFromDisk } from '../src/lib/server/ledger-disk';
import { buildRows } from './support/ledger-lifecycle';
import { readSession, renewReadSession } from '../src/lib/data/read-session';

const PRESETS = [3, 7, 30] as const;

/** A named, bounded day fixture; numeric and boolean cells really enter Parquet. */
function item(day: string, cpu = 'machine-a'): Row {
	return {
		date: day, run_id: `${day}-10`, machine_job: null, machine_shard: 0,
		cpu_model: cpu, prefill_ms: 1000, input_tokens: 300, cached_tokens: 100,
		decode_ms: 2000, output_tokens: 80,
		stage: 'fetch', outcome: 'failed', code: 'http_rate_limited', failed_rule: 'reply_shape',
		source_id: 'fixture-source', http_status: 429, source_form: 'article', tier: 1
	};
}

function host(day: string): Row {
	return {
		date: day, run_id: `${day}-10`, job: 'work', shard: 0, fingerprint: '0123456789abcdef',
		cpu_model: 'machine-a', job_seconds: 30, server_prompt_tokens: 200, server_prompt_seconds: 1
	};
}

async function writeWindowLedgers(root: string): Promise<void> {
	await buildRows(root, 'item-health', [
		{ covers: '2026-09-24', rows: [item('2026-09-24')] },
		{ covers: '2026-09-25', rows: [item('2026-09-25')] },
		{ covers: '2026-09-26', rows: [item('2026-09-26', 'machine-b')] }
	]);
	await buildRows(root, 'host-fingerprint', [
		{ covers: '2026-09-24', rows: [host('2026-09-24')] },
		{ covers: '2026-09-25', rows: [host('2026-09-25')] }
	]);
	await buildRows(root, 'summary-quality-evals', [
		{
			covers: '2026-09-25', rows: [{
				date: '2026-09-25', run_id: '2026-09-25-10', model_id: 'fixture-model',
				summary_words: 80, source_words_before_cap: 600, source_words: 400, compression: 0.2
			}]
		},
		{
			covers: '2026-09-26', rows: [{
				date: '2026-09-26', run_id: '2026-09-26-10', model_id: 'fixture-model',
				summary_words: 90, source_words_before_cap: 800, source_words: 600, compression: 0.15
			}]
		}
	]);
}

function diskDoor(root: string): PanelDoor {
	return {
		reach: (ledger) => reachFromDisk(root, ledger),
		rows: (ledger, options) => sliceFromDisk(root, ledger, options)
	};
}

function asRange(value: Range | LedgerReach): Range {
	expect('from' in value).toBe(true);
	if (!('from' in value)) throw new Error(`expected a range, got ${value.state}`);
	return value;
}

test('UTC windows are inclusive across leap days and clamp at the ledger first day', () => {
	expect(windowRange(3, '2024-03-01', '2024-02-01')).toEqual({
		from: '2024-02-28', to: '2024-03-01', days: 3, asked: 3
	});
	expect(windowRange(30, '2026-01-02', '2025-12-31')).toEqual({
		from: '2025-12-31', to: '2026-01-02', days: 3, asked: 30
	});
	for (const asked of [0, -1, 1.5, NaN, Infinity]) {
		expect(() => windowRange(asked, '2026-09-26', '2026-09-24')).toThrow('asked');
	}
	expect(() => windowRange(2, '2026-02-30', '2026-01-01')).toThrow('through');
	expect(() => windowRange(2, '2026-03-01', '2026-02-30')).toThrow('first');
	expect(() => windowRange(2, '2026-09-24', '2026-09-25')).toThrow('first');
});

test('each span uses the shared data end and widest takes the explicitly passed presets', () => {
	const reach: RouteReach = {
		through: '2026-09-26',
		ledgers: {
			'item-health': { state: 'ok', first: '2026-08-01', through: '2026-09-26', lastRows: null, fault: null },
			'summary-quality-evals': { state: 'ok', first: '2026-08-01', through: '2026-09-28', lastRows: null, fault: null }
		}
	};
	expect(rangeFor(slowerOnSameWorkQuery, 3, reach, PRESETS)).toEqual({
		from: '2026-09-24', to: '2026-09-26', days: 3, asked: 3
	});
	expect(rangeFor({ ...slowerOnSameWorkQuery, span: 'newest-day' }, 3, reach, PRESETS)).toEqual({
		from: '2026-09-26', to: '2026-09-26', days: 1, asked: 1
	});
	expect(rangeFor(modelChangeQuery, 3, reach, [7, 14])).toEqual({
		from: '2026-09-13', to: '2026-09-26', days: 14, asked: 14
	});
	expect(rangeFor(modelChangeQuery, 3, reach, [4, 21])).toEqual({
		from: '2026-09-06', to: '2026-09-26', days: 21, asked: 21
	});
	expect(() => rangeFor(modelChangeQuery, 3, reach, [])).toThrow('window_presets');
	expect(() => rangeFor(modelChangeQuery, 3, reach, [0])).toThrow('window_presets');
	expect(() => rangeFor(modelChangeQuery, 0, reach, PRESETS)).toThrow('preset');
	expect(() => rangeFor(platformMixQuery, 3, reach, PRESETS)).toThrow('host-fingerprint');
});

test('the real three-ledger door anchors at the oldest end and asks each ledger only from its first', async ({}, info) => {
	const root = info.outputPath('window-ledgers');
	await writeWindowLedgers(root);
	const reader = createQueryWindow(diskDoor(root));
	const reach = await reader.routeReach(['item-health', 'host-fingerprint', 'summary-quality-evals']);
	expect(reach.through).toBe('2026-09-25');
	const healthRange = asRange(rangeFor(slowerOnSameWorkQuery, 3, reach, PRESETS));
	const scoreRange = asRange(rangeFor(summaryLengthQuery, 3, reach, PRESETS));
	expect(healthRange).toEqual({ from: '2026-09-24', to: '2026-09-25', days: 2, asked: 3 });
	expect(scoreRange).toEqual({ from: '2026-09-25', to: '2026-09-25', days: 1, asked: 3 });
	const health = await reader.sliceOnce(slowerOnSameWorkQuery, healthRange);
	const score = await reader.sliceOnce(summaryLengthQuery, scoreRange);
	const machines = await reader.sliceOnce(platformMixQuery, asRange(rangeFor(platformMixQuery, 3, reach, PRESETS)));
	expect(health.state).toBe('ok');
	expect(health.rows).toEqual(['2026-09-24', '2026-09-25'].map((date) => ({
		date, cpu_model: 'machine-a', prefill_ms: 1000, input_tokens: 300,
		cached_tokens: 100, decode_ms: 2000, output_tokens: 80
	})));
	expect(score.rows).toEqual([{
		date: '2026-09-25', run_id: '2026-09-25-10', model_id: 'fixture-model',
		summary_words: 80, source_words_before_cap: 600, source_words: 400, compression: 0.2
	}]);
	expect(machines.rows).toEqual(['2026-09-24', '2026-09-25'].map(host));
	expect(platformMixQuery.columns).toEqual(FLEET_COLUMNS);
});

test('structured fetch predicates cross the real door rather than filtering the answer afterward', async ({}, info) => {
	const root = info.outputPath('fetch-predicate');
	await buildRows(root, 'item-health', [{
		covers: '2026-09-25',
		rows: [item('2026-09-25'), { ...item('2026-09-25'), stage: 'publish', outcome: 'ok', code: null }]
	}]);
	const reader = createQueryWindow(diskDoor(root));
	const reach = await reader.routeReach(['item-health']);
	const answer = await reader.sliceOnce(feedsFailedQuery, asRange(rangeFor(feedsFailedQuery, 3, reach, PRESETS)));
	expect(answer.rows).toEqual([{
		date: '2026-09-25', source_id: 'fixture-source', stage: 'fetch', outcome: 'failed',
		code: 'http_rate_limited', http_status: 429, source_form: 'article', tier: 1
	}]);
});

test('unavailable reaches have no day and lead to no slice; empty and missing ledgers are distinct', async ({}, info) => {
	const root = info.outputPath('unavailable-reaches');
	await buildRows(root, 'host-fingerprint', []);
	await buildRows(root, 'item-health', [{ covers: '2026-09-25', rows: [item('2026-09-25')] }]);
	const index = path.join(root, 'compact', 'item-health', 'index', 'daily.json');
	writeFileSync(index, '{not valid JSON}\n');
	let calls = 0;
	const door = diskDoor(root);
	const reader = createQueryWindow({
		reach: door.reach,
		rows: (ledger, options) => { calls += 1; return door.rows(ledger, options); }
	});
	const reach = await reader.routeReach(['item-health', 'host-fingerprint', 'summary-quality-evals']);
	expect(reach.through).toBeNull();
	expect(reach.ledgers['item-health']).toEqual({ state: 'unreachable' });
	expect(reach.ledgers['host-fingerprint']).toEqual({ state: 'quiet' });
	expect(reach.ledgers['summary-quality-evals']).toEqual({ state: 'missing', fault: 'not-packed' });
	for (const query of [slowerOnSameWorkQuery, platformMixQuery, summaryLengthQuery]) {
		const range = rangeFor(query, 3, reach, PRESETS);
		if ('from' in range) await reader.sliceOnce(query, range);
		expect(range).toEqual(reach.ledgers[query.ledger]);
		expect('at' in range).toBe(false);
	}
	expect(calls).toBe(0);
});

test('a ledger starting after the common data end is quiet rather than an inverted range', () => {
	const reach: RouteReach = {
		through: '2026-09-24',
		ledgers: { 'item-health': { state: 'ok', first: '2026-09-25', through: '2026-09-26', lastRows: null, fault: null } }
	};
	expect(rangeFor(slowerOnSameWorkQuery, 3, reach, PRESETS)).toEqual({ state: 'quiet' });
});

test('one name and range shares its promise; a new range replaces it and explicit retry asks again', async ({}, info) => {
	const root = info.outputPath('held-range');
	await writeWindowLedgers(root);
	const door = diskDoor(root);
	let calls = 0;
	const reader = createQueryWindow({
		reach: door.reach,
		rows: (ledger, options) => { calls += 1; return door.rows(ledger, options); }
	});
	const wide = windowRange(3, '2026-09-26', '2026-09-24');
	const narrow = windowRange(1, '2026-09-26', '2026-09-24');
	const first = reader.sliceOnce(slowerOnSameWorkQuery, wide);
	expect(reader.sliceOnce(slowerOnSameWorkQuery, wide)).toBe(first);
	expect((await first).rows).toHaveLength(3);
	const next = reader.sliceOnce(slowerOnSameWorkQuery, narrow);
	expect(next).not.toBe(first);
	expect((await next).rows).toHaveLength(1);
	const back = reader.sliceOnce(slowerOnSameWorkQuery, wide);
	expect(back).not.toBe(first);
	await back;
	expect(calls).toBe(3);
	reader.retryAsks([slowerOnSameWorkQuery]);
	const retried = reader.sliceOnce(slowerOnSameWorkQuery, wide);
	expect(retried).not.toBe(back);
	await retried;
	expect(calls).toBe(4);
	reader.retryAsks();
	await reader.sliceOnce(slowerOnSameWorkQuery, wide);
	expect(calls).toBe(5);
});

test('missing and unreachable slices are retried using real repaired files, not cached empty successes', async ({}, info) => {
	const root = info.outputPath('repair-ledger');
	const reader = createQueryWindow(diskDoor(root));
	const range = windowRange(1, '2026-09-25', '2026-09-25');
	const missing = reader.sliceOnce(slowerOnSameWorkQuery, range);
	expect(await missing).toEqual({ state: 'missing', rows: [], fault: 'not-packed' });
	await buildRows(root, 'item-health', [{ covers: '2026-09-25', rows: [item('2026-09-25')] }]);
	const file = path.join(root, 'compact', 'item-health', 'daily', '2026', '09', '25.parquet');
	const bytes = readFileSync(file);
	rmSync(file);
	const unreachable = reader.sliceOnce(slowerOnSameWorkQuery, range);
	expect(unreachable).not.toBe(missing);
	expect(await unreachable).toEqual({ state: 'unreachable', rows: [], at: '2026-09-25', fault: 'file-missing' });
	writeFileSync(file, bytes);
	const repaired = reader.sliceOnce(slowerOnSameWorkQuery, range);
	expect(repaired).not.toBe(unreachable);
	expect((await repaired).rows).toHaveLength(1);
	expect(reader.sliceOnce(slowerOnSameWorkQuery, range)).toBe(repaired);
	expect((await reader.routeReach(['item-health'])).through).toBe('2026-09-25');
});

test('an explicit new read session invalidates same-endpoint answers and preserves new promises against old completions', async ({}, info) => {
	const root = info.outputPath('refreshed-rows');
	await writeWindowLedgers(root);
	const door = diskDoor(root);
	const range = windowRange(1, '2026-09-26', '2026-09-24');
	let release: () => void = () => { throw new Error('no held read'); };
	let hold = false;
	let waiting = false;
	const reader = createQueryWindow({
		...door,
		currentSession: readSession,
		rows: async (ledger, options) => {
			const rows = await door.rows(ledger, options);
			if (hold) await new Promise<void>((resolve) => { release = resolve; waiting = true; });
			return rows;
		}
	});
	const first = reader.sliceOnce(slowerOnSameWorkQuery, range);
	expect((await first).rows[0].cpu_model).toBe('machine-b');
	await buildRows(root, 'item-health', [{ covers: '2026-09-26', rows: [item('2026-09-26', 'refreshed-machine')] }]);
	expect(reader.sliceOnce(slowerOnSameWorkQuery, range)).toBe(first);
	renewReadSession();
	const refreshed = reader.sliceOnce(slowerOnSameWorkQuery, range);
	expect(refreshed).not.toBe(first);
	expect((await refreshed).rows[0].cpu_model).toBe('refreshed-machine');

	reader.retryAsks();
	hold = true;
	const old = reader.sliceOnce(slowerOnSameWorkQuery, range);
	await expect.poll(() => waiting).toBe(true);
	hold = false;
	renewReadSession();
	const newSession = reader.sliceOnce(slowerOnSameWorkQuery, range);
	await newSession;
	release();
	await old;
	expect(reader.sliceOnce(slowerOnSameWorkQuery, range)).toBe(newSession);
});

test('rejected promises preserve the real I/O error and do not poison a later ask', async ({}, info) => {
	const root = info.outputPath('rejected-promise');
	await writeWindowLedgers(root);
	const required = info.outputPath('required.txt');
	const door = diskDoor(root);
	const reader = createQueryWindow({
		reach: door.reach,
		rows: async (ledger, options) => { await readFile(required); return door.rows(ledger, options); }
	});
	const range = windowRange(1, '2026-09-25', '2026-09-25');
	const rejected = reader.sliceOnce(slowerOnSameWorkQuery, range);
	await expect(rejected).rejects.toThrow('ENOENT');
	mkdirSync(path.dirname(required), { recursive: true });
	writeFileSync(required, 'ready\n');
	const repaired = reader.sliceOnce(slowerOnSameWorkQuery, range);
	expect(repaired).not.toBe(rejected);
	expect((await repaired).rows).toHaveLength(1);
});

for (const failOld of [false, true]) {
	test(`an old range completing late cannot replace or evict the new promise (${failOld ? 'I/O error' : 'answer'})`, async ({}, info) => {
		const root = info.outputPath('overlapping-ranges');
		await writeWindowLedgers(root);
		const required = info.outputPath('required.txt');
		writeFileSync(required, 'ready\n');
		let release!: () => void;
		const gate = new Promise<void>((resolve) => { release = resolve; });
		const door = diskDoor(root);
		const reader = createQueryWindow({
			reach: door.reach,
			rows: async (ledger, options) => {
				const answer = await door.rows(ledger, options);
				if (options.from === '2026-09-24') {
					await gate;
					await readFile(required);
				}
				return answer;
			}
		});
		const wide = windowRange(3, '2026-09-26', '2026-09-24');
		const narrow = windowRange(1, '2026-09-26', '2026-09-24');
		const old = reader.sliceOnce(slowerOnSameWorkQuery, wide);
		const current = reader.sliceOnce(slowerOnSameWorkQuery, narrow);
		expect((await current).rows).toEqual([{
			date: '2026-09-26', cpu_model: 'machine-b', prefill_ms: 1000,
			input_tokens: 300, cached_tokens: 100, decode_ms: 2000, output_tokens: 80
		}]);
		if (failOld) rmSync(required);
		release();
		if (failOld) await expect(old).rejects.toThrow('ENOENT');
		else expect((await old).rows).toHaveLength(3);
		expect(reader.sliceOnce(slowerOnSameWorkQuery, narrow)).toBe(current);
		expect((await current).rows[0]?.date).toBe('2026-09-26');
	});
}

test('tally precedence keeps truthful partial missing and unreachable counts even while pending', () => {
	const quiet: LedgerReach = { state: 'quiet' };
	const missing: LedgerReach = { state: 'missing', fault: 'not-packed' };
	const unreachable: LedgerReach = { state: 'unreachable' };
	const ok: SliceResult = {
		state: 'ok', rows: [item('2026-09-25')], first: '2026-09-25', through: '2026-09-25', lostDays: [], setAside: {}
	};
	expect(tallyAsks(['pending', unreachable, missing, missing])).toEqual({ state: 'loading', missing: 2, unreachable: 1 });
	expect(tallyAsks([ok, unreachable, missing])).toEqual({ state: 'unreachable', missing: 1, unreachable: 1 });
	expect(tallyAsks([ok, quiet, missing])).toEqual({ state: 'missing', missing: 1, unreachable: 0 });
	expect(tallyAsks([quiet, quiet])).toEqual({ state: 'quiet', missing: 0, unreachable: 0 });
	expect(tallyAsks([quiet, ok])).toEqual({ state: 'ok', missing: 0, unreachable: 0 });
	expect(tallyAsks([])).toEqual({ state: 'quiet', missing: 0, unreachable: 0 });
});

test('newest run is dated and numerically ordered, including run ids beyond safe JS integers', () => {
	const rows: Row[] = [
		{ run_id: '2026-09-25-999' }, { run_id: '2026-09-26-9' },
		{ run_id: '2026-09-26-10' }, { run_id: '2026-09-26-10' }
	];
	expect(newestRunRows(rows)).toEqual(rows.slice(2));
	expect(compareRuns('2026-09-26-9007199254740993', '2026-09-26-9007199254740992')).toBe(1);
	expect(compareRuns('2026-09-27-1', '2026-09-26-100')).toBe(1);
	expect(() => compareRuns('2026-02-30-1', '2026-09-26-1')).toThrow('run_id');
	expect(newestRunRows([])).toEqual([]);
});

test('item-host joins use all four host keys, default only the empty job, and count unmatched items', () => {
	const base = item('2026-09-25');
	const hosts = [
		host('2026-09-25'),
		{ ...host('2026-09-25'), job: 'assemble', server_prompt_tokens: 999 }
	];
	const items = [
		base, { ...base, machine_job: '' },
		{ ...base, machine_job: 'assemble' },
		{ ...base, machine_shard: 1 }, { ...base, machine_shard: null },
		{ ...base, date: '2026-09-26' }, { ...base, run_id: '2026-09-25-9' }
	];
	const joined = joinItemHosts(items, hosts);
	expect(joined.rows).toHaveLength(7);
	expect(joined.unmatched).toBe(4);
	expect(joined.rows.slice(0, 3).map((row) => row.host?.server_prompt_tokens)).toEqual([200, 200, 999]);
	expect(hostKey(base, true)).toBe(hostKey(hosts[0]));
	expect(() => hostKey({ ...base, machine_shard: false }, true)).toThrow('shard');
});

test('legacy itemRates keeps independent read and write evidence and its absent-cache behavior', () => {
	expect(itemRates({ prefill_ms: '1000', input_tokens: '300', cached_tokens: '100', decode_ms: '2000', output_tokens: '80' }))
		.toEqual({ read: 200, write: 40 });
	expect(itemRates({ prefill_ms: '1000', input_tokens: '300', decode_ms: '', output_tokens: '80' }))
		.toEqual({ read: 300, write: null });
	expect(itemRates({ prefill_ms: '', input_tokens: '300', cached_tokens: '100', decode_ms: '2000', output_tokens: '80' }))
		.toEqual({ read: null, write: 40 });
	expect(itemRates({ prefill_ms: 'NaN', input_tokens: '300', decode_ms: 'Infinity', output_tokens: '80' }))
		.toEqual({ read: null, write: null });
});

test('comparable rates require all five cells, finite evidence and positive fresh input and output', () => {
	const row = item('2026-09-25');
	expect(qualifyingWork(row)).toEqual({ freshInput: 200, output: 80, readMsPerToken: 5, writeMsPerToken: 25 });
	for (const column of ['prefill_ms', 'input_tokens', 'cached_tokens', 'decode_ms', 'output_tokens']) {
		for (const absent of [null, '', ' ', Infinity, NaN, false]) {
			expect(qualifyingWork({ ...row, [column]: absent })).toBeNull();
		}
	}
	expect(qualifyingWork({ ...row, cached_tokens: 300 })).toBeNull();
	expect(qualifyingWork({ ...row, output_tokens: 0 })).toBeNull();
	expect(qualifyingWork({ ...row, prefill_ms: 0, decode_ms: 0 }))
		.toEqual({ freshInput: 200, output: 80, readMsPerToken: 0, writeMsPerToken: 0 });
	expect(finiteCell('0')).toBe(0);
	expect(finiteCell('')).toBeNull();
	expect(finiteCell(false)).toBeNull();
	expect(nearestRank([1, 2, 8, 10], 0.5)).toBe(8);
	expect(nearestRank([1, 2, 8, 10], 0.9)).toBe(10);
	expect(nearestRank([], 0.5)).toBeNull();
});

test('the reference wins by qualifying count then name, and fixed median work is priced without interpolation', () => {
	const base = item('2026-09-25');
	const rows: Row[] = [
		{ ...base, cpu_model: 'z-machine', input_tokens: 200, output_tokens: 20 },
		{ ...base, cpu_model: 'a-machine', input_tokens: 300, output_tokens: 30 },
		{ ...base, cpu_model: 'z-machine', input_tokens: 500, output_tokens: 50 },
		{ ...base, cpu_model: 'a-machine', input_tokens: 900, output_tokens: 90 },
		{ ...base, cpu_model: 'z-machine', cached_tokens: null },
		{ ...base, cpu_model: null, input_tokens: 400, output_tokens: 40 }
	];
	const reference = referenceWork(rows);
	expect(reference).toEqual({
		cpuModel: 'a-machine', referenceRows: 2, qualifying: 5, unqualified: 1, unnamedMachine: 1,
		freshInput: 300, output: 40
	});
	const priced = typicalSeconds(rows, reference);
	expect(priced.from).toBe(2);
	expect(priced.outOf).toBe(6);
	expect(priced.read).toBe(1.5);
	expect(priced.write).toBeCloseTo(8 / 3);
	expect(typicalSeconds(rows.filter((row) => row.cpu_model === 'z-machine'), reference))
		.toEqual({ read: null, write: null, from: 0, outOf: 3 });
	expect(referenceWork([])).toEqual({
		cpuModel: null, referenceRows: 0, qualifying: 0, unqualified: 0, unnamedMachine: 0,
		freshInput: null, output: null
	});
	expect(failedRuleQuery.columns).toEqual(['date', 'stage', 'outcome', 'code', 'failed_rule']);
});
