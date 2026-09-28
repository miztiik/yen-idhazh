import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { COMPACT_INDEX_STAMP, readIndex, type CompactEntry } from '../src/lib/data/compact-index';
import { nodeEngine } from '../src/lib/data/engine';
import { fetchedBytes, type Fetcher } from '../src/lib/data/fetched-bytes';
import { daysBetween, filesFor } from '../src/lib/data/slice';
import { cellOf, SliceValueError, statementFor } from '../src/lib/data/slice-query';
import { indexPath, readSlice, type EngineOpener } from '../src/lib/data/slice-reader';
import { checkedRequest, SliceRequestError, type SliceOptions, type SliceResult } from '../src/lib/data/slice-shapes';
import { sliceFromDisk } from '../src/lib/server/ledger-disk';

/**
 * THE ORACLE for the query door: a request is answered through exactly the
 * files it needs, one file a day, and every way it can fail comes back as the
 * state a panel draws rather than as an error it has to inspect.
 *
 * The door is driven through its core and its disk entry point, never through
 * `ledger.ts`, which imports `$app/paths` and so cannot load in plain Node. The
 * browser's byte source is exercised with recorded responses: every request is
 * answered from the fixture files under `tests/fixtures/ledger-door/`, read
 * inside the test that asks, and a case that needs a 404, a short body, a
 * refused fetch or a different stamp says so by path. Nothing here touches the
 * network.
 *
 * The fixture holds a monthly file for 2026-08, daily files for 2026-08-31,
 * 09-01, 09-02 and 09-05, a zero-row day on 09-03, and a hole on 09-04.
 * 2026-08-31 is named by both indexes, and the two files hold different jobs for
 * it, so a reader that opens both, or the wrong one, returns a row it should not.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const STATE = path.resolve(here, '..', '..', 'tests', 'fixtures', 'ledger-door', 'state');
const LEDGER = 'host-fingerprint' as const;
const PREFIX = 'https://pages.test/yen-idhazh';
const DAILY_INDEX = indexPath(LEDGER, 'daily');
const MONTHLY_INDEX = indexPath(LEDGER, 'monthly');
const resolver = createRequire(import.meta.url);
const locate = (specifier: string): string => resolver.resolve(specifier);

type Answer = { status: number; body?: Uint8Array } | 'throw';
type Rule = Answer | ((onDisk: Uint8Array) => Answer);

interface Asked {
	path: string;
	version: string | null;
	cache: RequestCache | undefined;
}

/** Answers from the fixture files, unless `rules` names the path. */
function recorded(rules: Record<string, Rule> = {}): { fetcher: Fetcher; asked: Asked[] } {
	const asked: Asked[] = [];
	const root = `${PREFIX}/state/`;
	const fetcher: Fetcher = async (url, init) => {
		expect(url.startsWith(root), `${url} is not under ${root}`).toBe(true);
		const address = new URL(url);
		const relative = decodeURIComponent(address.pathname.slice(new URL(root).pathname.length));
		asked.push({ path: relative, version: address.searchParams.get('v'), cache: init.cache });
		const file = path.join(STATE, ...relative.split('/'));
		const onDisk = existsSync(file) ? new Uint8Array(readFileSync(file)) : null;
		const rule = rules[relative];
		const answer: Answer =
			typeof rule === 'function'
				? rule(onDisk ?? new Uint8Array())
				: (rule ?? (onDisk === null ? { status: 404 } : { status: 200, body: onDisk }));
		if (answer === 'throw') throw new TypeError('Failed to fetch');
		return new Response(answer.body === undefined ? null : answer.body.slice().buffer, { status: answer.status });
	};
	return { fetcher, asked };
}

const decoded = (bytes: Uint8Array): Record<string, unknown> => JSON.parse(new TextDecoder().decode(bytes));
const encoded = (value: unknown): Uint8Array => new TextEncoder().encode(JSON.stringify(value));

/** The index as the fixture holds it, with some fields replaced. */
const reshaped =
	(change: Record<string, unknown>): Rule =>
	(onDisk) => ({ status: 200, body: encoded({ ...decoded(onDisk), ...change }) });

/** An engine opener that counts how often the door reached for the engine. */
function counted(): { open: EngineOpener; opened: () => number } {
	let count = 0;
	return {
		open: () => {
			count += 1;
			return nodeEngine(locate);
		},
		opened: () => count
	};
}

/** Every console warning `work` prints, and its result. */
async function warnings<T>(work: () => Promise<T>): Promise<{ result: T; warned: string[] }> {
	const warned: string[] = [];
	const original = console.warn;
	console.warn = (...parts: unknown[]) => {
		warned.push(parts.map(String).join(' '));
	};
	try {
		return { result: await work(), warned };
	} finally {
		console.warn = original;
	}
}

function fixtureEntries(period: 'daily' | 'monthly'): CompactEntry[] {
	const text = readFileSync(path.join(STATE, ...indexPath(LEDGER, period).split('/')), 'utf8');
	const reading = readIndex(JSON.parse(text), LEDGER, period);
	if (!('index' in reading)) throw new Error(`the fixture's ${period} index is refused: ${JSON.stringify(reading)}`);
	return reading.index.entries;
}

const columns = ['date', 'run_id', 'job', 'shard', 'cores'] as const;
const ask = (from: string, to: string, extra: Partial<SliceOptions> = {}): SliceOptions => ({
	columns,
	from,
	to,
	...extra
});
const dataAsked = (asked: Asked[]): string[] => asked.filter((one) => one.path.endsWith('.parquet')).map((one) => one.path);

test.describe('which files a range needs', () => {
	test('each day is read through the coarsest period that holds it, one file a day', () => {
		const selection = filesFor('2026-08-30', '2026-09-01', fixtureEntries('daily'), fixtureEntries('monthly'));
		expect('files' in selection).toBe(true);
		if (!('files' in selection)) return;
		expect(selection.files.map((file) => [file.period, file.entry.covers, file.firstDay])).toEqual([
			['monthly', '2026-08', '2026-08-30'],
			['daily', '2026-09-01', '2026-09-01']
		]);
	});

	test('the first day neither index names comes back instead of a file set', () => {
		expect(filesFor('2026-09-02', '2026-09-05', fixtureEntries('daily'), fixtureEntries('monthly'))).toEqual({
			hole: '2026-09-04'
		});
	});

	test('a range crosses a month end one UTC day at a time', () => {
		expect(daysBetween('2026-08-30', '2026-09-02')).toEqual(['2026-08-30', '2026-08-31', '2026-09-01', '2026-09-02']);
	});
});

test.describe('the four states, before the engine is needed', () => {
	test('a ledger with no daily index is missing, and nothing else is asked', async () => {
		const { fetcher, asked } = recorded({ [DAILY_INDEX]: { status: 404 } });
		const engine = counted();
		expect(await readSlice(fetchedBytes(PREFIX, fetcher), engine.open, LEDGER, ask('2026-09-01', '2026-09-02'))).toEqual({
			state: 'missing',
			rows: []
		});
		expect(asked.map((one) => one.path)).toEqual([DAILY_INDEX]);
		expect(engine.opened()).toBe(0);
	});

	test('a span of zero-row days is quiet, fetches no data file and starts no engine', async () => {
		const { fetcher, asked } = recorded();
		const engine = counted();
		expect(await readSlice(fetchedBytes(PREFIX, fetcher), engine.open, LEDGER, ask('2026-09-03', '2026-09-03'))).toEqual({
			state: 'quiet',
			rows: [],
			through: '2026-09-05'
		});
		expect(asked.map((one) => one.path)).toEqual([DAILY_INDEX]);
		expect(engine.opened()).toBe(0);
	});

	test('a span wholly after the newest compacted day is quiet, and says how far the data reaches', async () => {
		const { fetcher, asked } = recorded();
		expect(await readSlice(fetchedBytes(PREFIX, fetcher), counted().open, LEDGER, ask('2026-09-06', '2026-09-10'))).toEqual({
			state: 'quiet',
			rows: [],
			through: '2026-09-05'
		});
		expect(asked.map((one) => one.path)).toEqual([DAILY_INDEX]);
	});

	test('a day past the newest compacted day is clamped away rather than asked for', async () => {
		const { fetcher, asked } = recorded();
		await readSlice(fetchedBytes(PREFIX, fetcher), counted().open, LEDGER, ask('2026-09-05', '2026-09-10'));
		expect(dataAsked(asked)).toEqual(['compact/host-fingerprint/daily/2026/09/05.parquet']);
	});

	test('a hole is unreachable at that day, and no data file is fetched', async () => {
		const { fetcher, asked } = recorded();
		const engine = counted();
		const { result, warned } = await warnings(() =>
			readSlice(fetchedBytes(PREFIX, fetcher), engine.open, LEDGER, ask('2026-09-02', '2026-09-05'))
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-09-04' });
		expect(dataAsked(asked)).toEqual([]);
		expect(engine.opened()).toBe(0);
		expect(warned.join('\n')).toContain('2026-09-04 is named by neither index');
	});

	test('monthly.json is asked for only when the span starts before the oldest daily day', async () => {
		const later = recorded();
		await readSlice(fetchedBytes(PREFIX, later.fetcher), counted().open, LEDGER, ask('2026-08-31', '2026-09-01'));
		expect(later.asked.map((one) => one.path)).not.toContain(MONTHLY_INDEX);
		const earlier = recorded();
		await readSlice(fetchedBytes(PREFIX, earlier.fetcher), counted().open, LEDGER, ask('2026-08-30', '2026-09-01'));
		expect(earlier.asked.map((one) => one.path)).toContain(MONTHLY_INDEX);
	});

	test('a day both indexes name is fetched once, from the month', async () => {
		const { fetcher, asked } = recorded();
		await readSlice(fetchedBytes(PREFIX, fetcher), counted().open, LEDGER, ask('2026-08-30', '2026-09-01'));
		expect(dataAsked(asked)).toEqual([
			'compact/host-fingerprint/monthly/2026/08.parquet',
			'compact/host-fingerprint/daily/2026/09/01.parquet'
		]);
	});

	test('with no monthly.json, a day before the oldest daily day is a hole', async () => {
		const { fetcher } = recorded({ [MONTHLY_INDEX]: { status: 404 } });
		const { result } = await warnings(() =>
			readSlice(fetchedBytes(PREFIX, fetcher), counted().open, LEDGER, ask('2026-08-30', '2026-09-01'))
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-08-30' });
	});

	test('an index stamped newer than this build is refused: both stamps on the console, no data fetched', async () => {
		const { fetcher, asked } = recorded({ [DAILY_INDEX]: reshaped({ version: '2099-01-01' }) });
		const { result, warned } = await warnings(() =>
			readSlice(fetchedBytes(PREFIX, fetcher), counted().open, LEDGER, ask('2026-08-30', '2026-09-02'))
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-08-30' });
		expect(asked.map((one) => one.path)).toEqual([DAILY_INDEX]);
		expect(warned.join('\n')).toContain('2099-01-01');
		expect(warned.join('\n')).toContain(COMPACT_INDEX_STAMP);
	});

	test('an index stamped older than this build is read', async () => {
		const { fetcher } = recorded({ [DAILY_INDEX]: reshaped({ version: '2026-09-01' }) });
		expect(await readSlice(fetchedBytes(PREFIX, fetcher), counted().open, LEDGER, ask('2026-09-03', '2026-09-03'))).toEqual({
			state: 'quiet',
			rows: [],
			through: '2026-09-05'
		});
	});

	test('a monthly index stamped newer than this build is refused too', async () => {
		const { fetcher } = recorded({ [MONTHLY_INDEX]: reshaped({ version: '2099-01-01' }) });
		const { result } = await warnings(() =>
			readSlice(fetchedBytes(PREFIX, fetcher), counted().open, LEDGER, ask('2026-08-30', '2026-09-01'))
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-08-30' });
	});

	const unreadable: [string, Rule][] = [
		['not JSON', { status: 200, body: new TextEncoder().encode('{"entries": [') }],
		['another ledger', reshaped({ ledger: 'scores' })],
		['entries out of order', reshaped({ entries: [{ covers: '2026-09-02', rows: 1, bytes: 1 }, { covers: '2026-09-01', rows: 1, bytes: 1 }] })],
		['a month in a daily index', reshaped({ entries: [{ covers: '2026-09', rows: 1, bytes: 1 }] })],
		['a refused fetch', 'throw'],
		['a server error', { status: 500 }]
	];
	for (const [what, rule] of unreadable) {
		test(`a daily index that is ${what} is unreachable from the first day asked`, async () => {
			const { fetcher, asked } = recorded({ [DAILY_INDEX]: rule });
			const { result, warned } = await warnings(() =>
				readSlice(fetchedBytes(PREFIX, fetcher), counted().open, LEDGER, ask('2026-09-01', '2026-09-02'))
			);
			expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-09-01' });
			expect(dataAsked(asked)).toEqual([]);
			expect(warned.join('\n')).toContain('daily.json');
		});
	}

	test('a named file that is not there is unreachable at the first day it covers in the span', async () => {
		const { fetcher } = recorded({ 'compact/host-fingerprint/daily/2026/09/02.parquet': { status: 404 } });
		const engine = counted();
		const { result } = await warnings(() =>
			readSlice(fetchedBytes(PREFIX, fetcher), engine.open, LEDGER, ask('2026-09-01', '2026-09-02'))
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-09-02' });
		expect(engine.opened()).toBe(0);
	});

	test('a file whose decoded length is not its entry bytes is unreachable, and the engine never sees it', async () => {
		const { fetcher } = recorded({
			'compact/host-fingerprint/monthly/2026/08.parquet': (onDisk) => ({ status: 200, body: onDisk.slice(0, -1) })
		});
		const engine = counted();
		const { result, warned } = await warnings(() =>
			readSlice(fetchedBytes(PREFIX, fetcher), engine.open, LEDGER, ask('2026-08-30', '2026-09-01'))
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-08-30' });
		expect(engine.opened()).toBe(0);
		const month = fixtureEntries('monthly').find((entry) => entry.covers === '2026-08');
		expect(month, 'the fixture names no 2026-08 month file').toBeDefined();
		expect(warned.join('\n')).toContain(`arrived as ${(month?.bytes ?? 0) - 1} bytes and its entry says ${month?.bytes}`);
	});

	test('an index is asked for fresh, and a data file under the version its entry names', async () => {
		const { fetcher, asked } = recorded();
		await readSlice(fetchedBytes(PREFIX, fetcher), counted().open, LEDGER, ask('2026-08-30', '2026-09-01'));
		const entries = new Map([...fixtureEntries('daily'), ...fixtureEntries('monthly')].map((entry) => [entry.covers, entry]));
		for (const one of asked) {
			if (one.path.endsWith('.json')) {
				expect(one, one.path).toMatchObject({ cache: 'no-store', version: null });
			} else {
				const covers = one.path.includes('/monthly/') ? '2026-08' : '2026-09-01';
				const entry = entries.get(covers);
				expect(one.version, one.path).toBe(`${entry?.rows}-${entry?.bytes}`);
				expect(one.cache, one.path).toBeUndefined();
			}
		}
	});

	test('an engine that does not start is unreachable from the first day asked, and the console says why', async () => {
		const { fetcher } = recorded();
		const { result, warned } = await warnings(() =>
			readSlice(
				fetchedBytes(PREFIX, fetcher),
				() => Promise.reject(new Error('this browser has no WebAssembly exception handling')),
				LEDGER,
				ask('2026-09-01', '2026-09-02')
			)
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-09-01' });
		expect(warned.join('\n')).toContain('no WebAssembly exception handling');
	});
});

test.describe('a request the door refuses before it fetches anything', () => {
	const refused: [string, SliceOptions][] = [
		['no columns', { columns: [], from: '2026-09-01', to: '2026-09-02' }],
		['a column that is not a name', { columns: ['date"; drop table x; --'], from: '2026-09-01', to: '2026-09-02' }],
		['a filter on a column that is not a name', { ...ask('2026-09-01', '2026-09-02'), where: [{ column: 'Shard', op: '=', value: 1 }] }],
		['"from" after "to"', ask('2026-09-02', '2026-09-01')],
		['a day that is not a day', ask('2026-9-1', '2026-09-02')],
		['a day that does not exist', ask('2026-02-30', '2026-03-01')],
		['an empty "in" list', { ...ask('2026-09-01', '2026-09-02'), where: [{ column: 'job', op: 'in', value: [] }] }]
	];
	for (const [what, options] of refused) {
		test(`it refuses ${what} by name`, async () => {
			const { fetcher, asked } = recorded();
			await expect(readSlice(fetchedBytes(PREFIX, fetcher), counted().open, LEDGER, options)).rejects.toThrow(SliceRequestError);
			expect(asked).toEqual([]);
		});
	}

	test('it refuses a ledger outside the closed set', async () => {
		const { fetcher, asked } = recorded();
		await expect(
			readSlice(fetchedBytes(PREFIX, fetcher), counted().open, 'state/../../secrets' as typeof LEDGER, ask('2026-09-01', '2026-09-02'))
		).rejects.toThrow(SliceRequestError);
		expect(asked).toEqual([]);
	});
});

test.describe('the statement, and the values it hands back', () => {
	test('every caller value is bound, every name is quoted, and an absent column reads as null', () => {
		const request = checkedRequest({
			columns: ['date', 'shard', 'absent'],
			from: '2026-09-01',
			to: '2026-09-02',
			where: [
				{ column: 'job', op: 'in', value: ["work'); drop table x; --", 'plan'] },
				{ column: 'shard', op: '>=', value: 1 }
			]
		});
		const { sql, params } = statementFor("['slice1-0.parquet']", new Set(['date', 'shard', 'job']), request, '2026-09-02');
		expect(sql).toBe(
			`SELECT "date", "shard", NULL AS "absent" FROM read_parquet(['slice1-0.parquet'], union_by_name = true) ` +
				`WHERE "date" >= ? AND "date" <= ? AND "job" IN (?, ?) AND "shard" >= ? ORDER BY ALL`
		);
		expect(params).toEqual(['2026-09-01', '2026-09-02', "work'); drop table x; --", 'plan', 1]);
		expect(sql).not.toContain('drop table');
	});

	test('a 64-bit integer comes back as a number, and one a number cannot hold exactly is refused by name', () => {
		expect(cellOf('shard', 3n)).toBe(3);
		expect(cellOf('rows', BigInt(Number.MAX_SAFE_INTEGER))).toBe(Number.MAX_SAFE_INTEGER);
		expect(() => cellOf('rows', BigInt(Number.MAX_SAFE_INTEGER) + 1n)).toThrow(SliceValueError);
		expect(() => cellOf('flags', ['avx2'])).toThrow(/holds a value of type object/);
		expect(cellOf('vm_zone', null)).toBeNull();
		expect(cellOf('mhz_max', 3529.5)).toBe(3529.5);
	});
});

test.describe('THE ORACLE through the engine, at both entry points', () => {
	/** The same request through the browser's byte source and through the disk. */
	async function bothWays(options: SliceOptions): Promise<{ browser: SliceResult; disk: SliceResult; warned: string[] }> {
		const { fetcher } = recorded();
		const { result: browser, warned } = await warnings(() =>
			readSlice(fetchedBytes(PREFIX, fetcher), () => nodeEngine(locate), LEDGER, options)
		);
		const { result: disk, warned: more } = await warnings(() => sliceFromDisk(STATE, LEDGER, options));
		return { browser, disk, warned: [...warned, ...more] };
	}

	test('exactly the requested columns for exactly the requested days, the same rows both ways', async () => {
		const { browser, disk, warned } = await bothWays(ask('2026-09-01', '2026-09-02'));
		expect(disk, warned.join('\n')).toMatchObject({ state: 'ok', through: '2026-09-05' });
		expect(browser).toEqual(disk);
		if (disk.state !== 'ok') return;
		for (const row of disk.rows) expect(Object.keys(row)).toEqual([...columns]);
		const perDay: Record<string, number> = {};
		for (const row of disk.rows) perDay[String(row.date)] = (perDay[String(row.date)] ?? 0) + 1;
		expect(perDay).toEqual({ '2026-09-01': 3, '2026-09-02': 2 });
		expect(disk.rows.every((row) => typeof row.shard === 'number' && typeof row.cores === 'number')).toBe(true);
	});

	test('a day both indexes name is read from the month file alone', async () => {
		const { disk, warned } = await bothWays(ask('2026-08-30', '2026-09-01', { columns: ['date', 'run_id', 'shard'] }));
		expect(disk, warned.join('\n')).toMatchObject({ state: 'ok' });
		if (disk.state !== 'ok') return;
		expect(disk.rows.filter((row) => row.date === '2026-08-31')).toEqual([
			{ date: '2026-08-31', run_id: '2026-08-31-17810000001', shard: 0 }
		]);
		expect(disk.rows).toHaveLength(6);
	});

	test('a filter narrows the rows, and a filter that matches nothing is quiet rather than an empty ok', async () => {
		const narrowed = await bothWays(ask('2026-09-01', '2026-09-05', { where: [{ column: 'job', op: '=', value: 'plan' }] }));
		expect(narrowed.disk, narrowed.warned.join('\n')).toMatchObject({ state: 'ok' });
		if (narrowed.disk.state === 'ok') expect(narrowed.disk.rows.map((row) => row.job)).toEqual(['plan']);
		const nothing = await bothWays(ask('2026-09-01', '2026-09-05', { where: [{ column: 'shard', op: '>', value: 9 }] }));
		expect(nothing.disk, nothing.warned.join('\n')).toEqual({ state: 'quiet', rows: [], through: '2026-09-05' });
		expect(nothing.browser).toEqual(nothing.disk);
	});
});
