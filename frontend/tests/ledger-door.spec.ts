import { expect, test } from '@playwright/test';
import { cpSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { COMPACT_INDEX_STAMP, readIndex, type CompactEntry, type Period } from '../src/lib/data/compact-index';
import { nodeEngine } from '../src/lib/data/engine';
import { fetchedBytes, type Fetcher } from '../src/lib/data/fetched-bytes';
import { readAsk, readAskCost } from '../src/lib/data/ask-reader';
import { readReach } from '../src/lib/data/ledger-reach';
import { pageKeeper, type ByteSource, type EngineOpener, type PageKeeper, type WantedFile } from '../src/lib/data/page-keeper';
import { daysBetween, filesFor, newestNamed } from '../src/lib/data/slice';
import { cellOf, SliceValueError, statementFor } from '../src/lib/data/slice-query';
import { dataPath, indexPath, rawIndexPath, readSlice } from '../src/lib/data/slice-reader';
import { checkedRequest, LEDGER_FAULTS, SliceRequestError, type SliceOptions, type SliceResult } from '../src/lib/data/slice-shapes';
import { engineExtensionRepository } from '../src/lib/server/config';
import { diskBytes, reachFromDisk, sliceFromDisk } from '../src/lib/server/ledger-disk';

/**
 * THE ORACLE for the query door: a request is answered through exactly the
 * files it needs, one file a day, and every way it can fail comes back as the
 * state a panel draws rather than as an error it has to inspect.
 *
 * The door is driven through its core and its disk entry point, never through
 * `ledger.ts`, which imports `$app/paths` and so cannot load in plain Node. A
 * browser page is a page keeper over the browser's byte source, made here the
 * way `ledger.ts` makes one. That byte source is exercised with recorded
 * responses: every request is
 * answered from the fixture files under `tests/fixtures/ledger-door/`, read
 * inside the test that asks, and a case that needs a 404, a short body, a
 * refused fetch or a different stamp says so by path. Nothing here touches the
 * network. The setup command prepares the engine's Parquet add-on in the shared
 * home cache before tests, and global setup refuses a missing cached file.
 *
 * The fixture holds a monthly file for 2026-08, daily files for 2026-08-31,
 * 09-01, 09-02 and 09-05, a zero-row day on 09-03, and a hole on 09-04.
 * 2026-08-31 is named by both indexes, and the two files hold different jobs for
 * it, so a reader that opens both, or the wrong one, returns a row it should not.
 * A second root holds the same August and September packed into one year file,
 * one row group a month, under a yearly index and one zero-row day in 2027. Each
 * root carries all three indexes, as the compaction writes them: the first
 * root's yearly index and the second root's monthly index name nothing.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.resolve(here, '..', '..', 'tests', 'fixtures', 'ledger-door');
const STATE = path.join(FIXTURE, 'state');
const YEAR_STATE = path.join(FIXTURE, 'year-state');
const LEDGER = 'host-fingerprint' as const;
const PREFIX = 'https://pages.test/yen-idhazh';
const DAILY_INDEX = indexPath(LEDGER, 'daily');
const MONTHLY_INDEX = indexPath(LEDGER, 'monthly');
const YEARLY_INDEX = indexPath(LEDGER, 'yearly');
const resolver = createRequire(import.meta.url);
const locate = (specifier: string): string => resolver.resolve(specifier);

type Answer = { status: number; body?: Uint8Array } | 'throw';
type Rule = Answer | ((onDisk: Uint8Array) => Answer);

interface Asked {
	path: string;
	version: string | null;
	cache: RequestCache | undefined;
	/** What the recorded response answered: a status, or a fetch that threw. */
	answered: number | 'throw';
}

/** Answers from the files under `state`, the first fixture root unless named, unless `rules` names the path. */
function recorded(rules: Record<string, Rule> = {}, state: string = STATE): { fetcher: Fetcher; asked: Asked[] } {
	const asked: Asked[] = [];
	const root = `${PREFIX}/state/`;
	const fetcher: Fetcher = async (url, init) => {
		expect(url.startsWith(root), `${url} is not under ${root}`).toBe(true);
		const address = new URL(url);
		const relative = decodeURIComponent(address.pathname.slice(new URL(root).pathname.length));
		const file = path.join(state, ...relative.split('/'));
		const onDisk = existsSync(file) ? new Uint8Array(readFileSync(file)) : null;
		const rule = rules[relative];
		const answer: Answer =
			typeof rule === 'function'
				? rule(onDisk ?? new Uint8Array())
				: (rule ?? (onDisk === null ? { status: 404 } : { status: 200, body: onDisk }));
		asked.push({
			path: relative,
			version: address.searchParams.get('v'),
			cache: init.cache,
			answered: answer === 'throw' ? 'throw' : answer.status
		});
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

interface CountedEngine {
	open: EngineOpener;
	/** How often the door reached for the engine. */
	opened: () => number;
	/** Every name the engine gave a file the door handed it, in order. */
	registered: string[];
	/** Every name the door asked the engine to drop, in order. */
	dropped: string[];
}

/**
 * The real Node engine, counting what the door asks of it. It is a wrapper, not
 * a stand-in: every file is registered in DuckDB and every statement runs there.
 * It takes each buffer the way a browser's engine does - moved, leaving the
 * caller's copy empty - because the Node engine copies instead, and a door that
 * handed one buffer over twice would pass on a copy here and read an empty file
 * in a browser.
 */
function counted(): CountedEngine {
	let opened = 0;
	const registered: string[] = [];
	const dropped: string[] = [];
	const open: EngineOpener = async () => {
		opened += 1;
		const engine = await nodeEngine(locate, engineExtensionRepository());
		return {
			async register(bytes) {
				const moved = structuredClone(bytes, { transfer: [bytes.buffer as ArrayBuffer] });
				const name = await engine.register(moved);
				registered.push(name);
				return name;
			},
			async drop(names) {
				dropped.push(...names);
				await engine.drop(names);
			},
			rows: (sql, params) => engine.rows(sql, params)
		};
	};
	return { open, opened: () => opened, registered, dropped };
}

/** A page that has read nothing yet: a keeper over recorded responses, as
 *  `ledger.ts` makes one over `fetch`. */
function freshPage(fetcher: Fetcher, engine: CountedEngine = counted()): PageKeeper {
	return pageKeeper(fetchedBytes(PREFIX, fetcher), engine.open);
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

function fixtureEntries(period: Period, state: string = STATE): CompactEntry[] {
	const text = readFileSync(path.join(state, ...indexPath(LEDGER, period).split('/')), 'utf8');
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

/** How many times each path was asked for. */
function askedCounts(asked: Asked[]): Record<string, number> {
	const counts: Record<string, number> = {};
	for (const one of asked) counts[one.path] = (counts[one.path] ?? 0) + 1;
	return counts;
}

/** A fixture day file's path, and its bytes read from the fixture. */
const dayFile = (covers: string): string => dataPath(LEDGER, 'daily', covers);
const bytesOf = (relative: string): Uint8Array => new Uint8Array(readFileSync(path.join(STATE, ...relative.split('/'))));
const expectedAnswer = (name: string): Record<string, string | null>[] => JSON.parse(readFileSync(path.join(FIXTURE, 'answers', `${name}.json`), 'utf8'));

test('the engine starts while a whole file is still arriving', async () => {
	const { fetcher } = recorded();
	const engine = counted();
	let releaseArrival!: () => void;
	let markRequested!: () => void;
	const pending = new Promise<void>((resolve) => { releaseArrival = resolve; });
	const requested = new Promise<void>((resolve) => { markRequested = resolve; });
	const keeper = freshPage(async (url, init) => {
		if (new URL(url).pathname.endsWith('.parquet')) {
			markRequested();
			await pending;
		}
		return fetcher(url, init);
	}, engine);
	const reading = readSlice(keeper, LEDGER, ask('2026-09-01', '2026-09-01'));
	try {
		await requested;
		expect(engine.opened(), 'engine startup must overlap the whole-file fetch').toBe(1);
		releaseArrival();
		const result = await reading;
		expect(result.state).toBe('ok');
		expect(result.rows.map((row) => [row.date, row.job, row.shard])).toEqual([
			['2026-09-01', 'plan', 0],
			['2026-09-01', 'work', 0],
			['2026-09-01', 'work', 1]
		]);
		expect(engine.registered).toHaveLength(1);
	} finally {
		releaseArrival();
		await reading;
		await keeper.release();
	}
});



test.describe('newest day any index names', () => {
	const entry = (covers: string): CompactEntry => ({ covers, rows: 1, bytes: 1 });

	test('daily, month and year entries count through the day they cover', () => {
		expect(newestNamed([entry('2026-09-02')], [], [])).toBe('2026-09-02');
		expect(newestNamed([], [entry('2026-09')], [])).toBe('2026-09-30');
		expect(newestNamed([], [], [entry('2026')])).toBe('2026-12-31');
		expect(newestNamed([entry('2026-09-02')], [entry('2026-10')], [])).toBe('2026-10-31');
		expect(newestNamed([], [entry('2028-02')], [])).toBe('2028-02-29');
		expect(newestNamed([], [], [])).toBeNull();
	});
});

test.describe('which files a range needs', () => {
	test('each day is read through the coarsest period that holds it, one file a day', () => {
		const selection = filesFor('2026-08-30', '2026-09-01', fixtureEntries('daily'), fixtureEntries('monthly'), []);
		expect('files' in selection).toBe(true);
		if (!('files' in selection)) return;
		expect(selection.files.map((file) => [file.period, file.entry.covers, file.firstDay])).toEqual([
			['monthly', '2026-08', '2026-08-30'],
			['daily', '2026-09-01', '2026-09-01']
		]);
	});

	test('a day in a packed year is read from the year file, even where its month and day are named too', () => {
		const selection = filesFor(
			'2026-08-30',
			'2026-09-01',
			fixtureEntries('daily'),
			fixtureEntries('monthly'),
			fixtureEntries('yearly', YEAR_STATE)
		);
		expect(selection).toEqual({
			files: [{ period: 'yearly', entry: fixtureEntries('yearly', YEAR_STATE)[0], firstDay: '2026-08-30' }]
		});
	});

	test('the first day no index names comes back instead of a file set', () => {
		expect(filesFor('2026-09-02', '2026-09-05', fixtureEntries('daily'), fixtureEntries('monthly'), [])).toEqual({
			hole: '2026-09-04'
		});
	});

	test('a year file sits in a folder named for its year', () => {
		expect(dataPath(LEDGER, 'yearly', '2026')).toBe('compact/host-fingerprint/yearly/2026/2026.parquet');
	});

	test('a range crosses a month end one UTC day at a time', () => {
		expect(daysBetween('2026-08-30', '2026-09-02')).toEqual(['2026-08-30', '2026-08-31', '2026-09-01', '2026-09-02']);
	});
});

test.describe('the four states, before the engine is needed', () => {
	test('a ledger with no daily index is missing, not packed, and nothing else is asked', async () => {
		const { fetcher, asked } = recorded({ [DAILY_INDEX]: { status: 404 } });
		const engine = counted();
		const { result } = await warnings(() => readSlice(freshPage(fetcher, engine), LEDGER, ask('2026-09-01', '2026-09-02')));
		expect(result).toEqual({ state: 'missing', rows: [], fault: 'not-packed' });
		expect(asked.map((one) => one.path)).toEqual([DAILY_INDEX]);
		expect(engine.opened()).toBe(0);
	});

	test('a span of zero-row days is quiet, fetches no data file and starts no engine', async () => {
		const { fetcher, asked } = recorded();
		const engine = counted();
		expect(await readSlice(freshPage(fetcher, engine), LEDGER, ask('2026-09-03', '2026-09-03'))).toEqual({
			state: 'quiet',
			rows: [],
			through: '2026-09-05'
		});
		expect(asked.map((one) => one.path)).toEqual([DAILY_INDEX]);
		expect(engine.opened()).toBe(0);
	});

	test('a span wholly after the newest compacted day is quiet, and says how far the data reaches', async () => {
		const { fetcher, asked } = recorded();
		expect(await readSlice(freshPage(fetcher), LEDGER, ask('2026-09-06', '2026-09-10'))).toEqual({
			state: 'quiet',
			rows: [],
			through: '2026-09-05'
		});
		expect(asked.map((one) => one.path)).toEqual([DAILY_INDEX]);
	});

	test('a day past the newest compacted day is clamped away rather than asked for', async () => {
		const { fetcher, asked } = recorded();
		await readSlice(freshPage(fetcher), LEDGER, ask('2026-09-05', '2026-09-10'));
		expect(dataAsked(asked)).toEqual(['compact/host-fingerprint/daily/2026/09/05.parquet']);
	});

	test('a hole is unreachable at that day, named day-missing, and no data file is fetched', async () => {
		const { fetcher, asked } = recorded();
		const engine = counted();
		const { result, warned } = await warnings(() =>
			readSlice(freshPage(fetcher, engine), LEDGER, ask('2026-09-02', '2026-09-05'))
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-09-04', fault: 'day-missing' });
		expect(dataAsked(asked)).toEqual([]);
		expect(engine.opened()).toBe(0);
		expect(warned.join('\n')).toContain('no index names 2026-09-04');
	});

	test('monthly.json is asked for only when the span starts before the oldest daily day', async () => {
		const later = recorded();
		await readSlice(freshPage(later.fetcher), LEDGER, ask('2026-08-31', '2026-09-01'));
		expect(later.asked.map((one) => one.path)).not.toContain(MONTHLY_INDEX);
		const earlier = recorded();
		await readSlice(freshPage(earlier.fetcher), LEDGER, ask('2026-08-30', '2026-09-01'));
		expect(earlier.asked.map((one) => one.path)).toContain(MONTHLY_INDEX);
	});

	test('yearly.json is asked for only when the span starts before the oldest day the other two name', async () => {
		const inside = recorded();
		await readSlice(freshPage(inside.fetcher), LEDGER, ask('2026-08-01', '2026-09-01'));
		expect(inside.asked.map((one) => one.path)).not.toContain(YEARLY_INDEX);
		const before = recorded();
		const { result } = await warnings(() => readSlice(freshPage(before.fetcher), LEDGER, ask('2026-07-31', '2026-09-01')));
		expect(before.asked.map((one) => one.path)).toContain(YEARLY_INDEX);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-07-31', fault: null });
	});

	test('a yearly index stamped newer than this build is refused, and no data is fetched', async () => {
		const { fetcher, asked } = recorded({ [YEARLY_INDEX]: reshaped({ version: '2099-01-01' }) }, YEAR_STATE);
		const { result, warned } = await warnings(() => readSlice(freshPage(fetcher), LEDGER, ask('2026-08-30', '2026-09-02')));
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-08-30', fault: null });
		expect(dataAsked(asked)).toEqual([]);
		expect(warned.join('\n')).toContain('yearly.json is stamped 2099-01-01');
	});

	test('a day both indexes name is fetched once, from the month', async () => {
		const { fetcher, asked } = recorded();
		await readSlice(freshPage(fetcher), LEDGER, ask('2026-08-30', '2026-09-01'));
		expect(dataAsked(asked)).toEqual([
			'compact/host-fingerprint/monthly/2026/08.parquet',
			'compact/host-fingerprint/daily/2026/09/01.parquet'
		]);
	});

	test('with no monthly.json, a span that starts before the oldest daily day is index-missing', async () => {
		const { fetcher } = recorded({ [MONTHLY_INDEX]: { status: 404 } });
		const { result } = await warnings(() =>
			readSlice(freshPage(fetcher), LEDGER, ask('2026-08-30', '2026-09-01'))
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-08-30', fault: 'index-missing' });
	});

	test('with no monthly.json, a span inside the daily days draws, and monthly.json is never asked for', async () => {
		const { fetcher, asked } = recorded({ [MONTHLY_INDEX]: { status: 404 } });
		const { result, warned } = await warnings(() =>
			readSlice(freshPage(fetcher), LEDGER, ask('2026-08-31', '2026-09-01'))
		);
		expect(result, warned.join('\n')).toMatchObject({ state: 'ok', through: '2026-09-05' });
		expect(asked.map((one) => one.path)).not.toContain(MONTHLY_INDEX);
		expect(warned).toEqual([]);
	});

	test('a span that starts before the oldest day any index names is unreachable, and no fault', async () => {
		// monthly.json names 2026-08 and yearly.json names no year, so the ledger starts
		// on 2026-08-01. A day before it was never packed, so "re-pack that day" would
		// send an operator to fix nothing.
		const { fetcher } = recorded();
		const { result, warned } = await warnings(() =>
			readSlice(freshPage(fetcher), LEDGER, ask('2026-07-30', '2026-08-02'))
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-07-30', fault: null });
		expect(warned.join('\n')).toContain("it starts before 2026-08-01, the oldest day any index names");
		expect(warned.join('\n')).toContain("Clamp the span to the reach's first day");
	});

	test('an index stamped newer than this build is refused: both stamps on the console, no data fetched', async () => {
		const { fetcher, asked } = recorded({ [DAILY_INDEX]: reshaped({ version: '2099-01-01' }) });
		const { result, warned } = await warnings(() =>
			readSlice(freshPage(fetcher), LEDGER, ask('2026-08-30', '2026-09-02'))
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-08-30', fault: null });
		expect(asked.map((one) => one.path)).toEqual([DAILY_INDEX]);
		expect(warned.join('\n')).toContain('2099-01-01');
		expect(warned.join('\n')).toContain(COMPACT_INDEX_STAMP);
	});

	test('an index stamped older than this build is read', async () => {
		const { fetcher } = recorded({ [DAILY_INDEX]: reshaped({ version: '2026-09-01' }) });
		expect(await readSlice(freshPage(fetcher), LEDGER, ask('2026-09-03', '2026-09-03'))).toEqual({
			state: 'quiet',
			rows: [],
			through: '2026-09-05'
		});
	});

	test('a monthly index stamped newer than this build is refused too', async () => {
		const { fetcher } = recorded({ [MONTHLY_INDEX]: reshaped({ version: '2099-01-01' }) });
		const { result } = await warnings(() =>
			readSlice(freshPage(fetcher), LEDGER, ask('2026-08-30', '2026-09-01'))
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-08-30', fault: null });
	});

	const unreadable: [string, Rule][] = [
		['not JSON', { status: 200, body: new TextEncoder().encode('{"entries": [') }],
		['another ledger', reshaped({ ledger: 'summary-quality-evals' })],
		['entries out of order', reshaped({ entries: [{ covers: '2026-09-02', rows: 1, bytes: 1 }, { covers: '2026-09-01', rows: 1, bytes: 1 }] })],
		['a month in a daily index', reshaped({ entries: [{ covers: '2026-09', rows: 1, bytes: 1 }] })],
		['a year in a daily index', reshaped({ entries: [{ covers: '2026', rows: 1, bytes: 1 }] })],
		['a refused fetch', 'throw'],
		['a server error', { status: 500 }]
	];
	for (const [what, rule] of unreadable) {
		test(`a daily index that is ${what} is unreachable from the first day asked`, async () => {
			const { fetcher, asked } = recorded({ [DAILY_INDEX]: rule });
			const { result, warned } = await warnings(() =>
				readSlice(freshPage(fetcher), LEDGER, ask('2026-09-01', '2026-09-02'))
			);
			expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-09-01', fault: null });
			expect(dataAsked(asked)).toEqual([]);
			expect(warned.join('\n')).toContain('daily.json');
		});
	}

	test('a named file that is not there is unreachable at the first day it covers in the span, named file-missing', async () => {
		const { fetcher } = recorded({ 'compact/host-fingerprint/daily/2026/09/02.parquet': { status: 404 } });
		const engine = counted();
		const { result } = await warnings(() =>
			readSlice(freshPage(fetcher, engine), LEDGER, ask('2026-09-01', '2026-09-02'))
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-09-02', fault: 'file-missing' });
		expect(engine.opened()).toBe(1);
		expect(engine.registered).toEqual([]);
	});

	test('a file whose decoded length is not its entry bytes is unreachable, and the engine never sees it', async () => {
		const { fetcher } = recorded({
			'compact/host-fingerprint/monthly/2026/08.parquet': (onDisk) => ({ status: 200, body: onDisk.slice(0, -1) })
		});
		const engine = counted();
		const { result, warned } = await warnings(() =>
			readSlice(freshPage(fetcher, engine), LEDGER, ask('2026-08-30', '2026-09-01'))
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-08-30', fault: null });
		expect(engine.opened()).toBe(1);
		expect(engine.registered).toEqual([]);
		const month = fixtureEntries('monthly').find((entry) => entry.covers === '2026-08');
		expect(month, 'the fixture names no 2026-08 month file').toBeDefined();
		expect(warned.join('\n')).toContain(`arrived as ${(month?.bytes ?? 0) - 1} bytes and its entry says ${month?.bytes}`);
	});

	test('an index is asked for fresh, and a data file under the version its entry names', async () => {
		const { fetcher, asked } = recorded();
		await readSlice(freshPage(fetcher), LEDGER, ask('2026-08-30', '2026-09-01'));
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
				pageKeeper(fetchedBytes(PREFIX, fetcher), () =>
					Promise.reject(new Error('this browser has no WebAssembly exception handling'))
				),
				LEDGER,
				ask('2026-09-01', '2026-09-02')
			)
		);
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-09-01', fault: null });
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
			await expect(readSlice(freshPage(fetcher), LEDGER, options)).rejects.toThrow(SliceRequestError);
			expect(asked).toEqual([]);
		});
	}

	test('it refuses a ledger outside the closed set', async () => {
		const { fetcher, asked } = recorded();
		await expect(
			readSlice(freshPage(fetcher), 'state/../../secrets' as typeof LEDGER, ask('2026-09-01', '2026-09-02'))
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
		const { sql, params } = statementFor("['door/1.parquet']", new Set(['date', 'shard', 'job']), request, '2026-09-02');
		expect(sql).toBe(
			`SELECT "date", "shard", NULL AS "absent" FROM read_parquet(['door/1.parquet'], union_by_name = true) ` +
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
			readSlice(freshPage(fetcher), LEDGER, options)
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

	test('a span reads the same rows from its year file as from its month and day files, both ways', async () => {
		const span = ask('2026-08-30', '2026-09-02');
		const { disk: unpacked, warned } = await bothWays(span);
		expect(unpacked, warned.join('\n')).toMatchObject({ state: 'ok', through: '2026-09-05' });
		const { fetcher, asked } = recorded({}, YEAR_STATE);
		const { result: browser, warned: more } = await warnings(() => readSlice(freshPage(fetcher), LEDGER, span));
		const { result: disk } = await warnings(() => sliceFromDisk(YEAR_STATE, LEDGER, span));
		expect(disk, more.join('\n')).toMatchObject({ state: 'ok', through: '2027-01-01' });
		expect(browser).toEqual(disk);
		if (disk.state !== 'ok' || unpacked.state !== 'ok') return;
		expect(disk.rows).toEqual(unpacked.rows);
		expect(disk.rows).toHaveLength(8);
		expect(dataAsked(asked)).toEqual([dataPath(LEDGER, 'yearly', '2026')]);
	});

	test('a filter narrows the rows, and a filter that matches nothing is quiet rather than an empty ok', async () => {
		// Up to 09-03, the zero-row day: 09-04 is the fixture's hole, and a hole is unreachable.
		const narrowed = await bothWays(ask('2026-09-01', '2026-09-03', { where: [{ column: 'job', op: '=', value: 'plan' }] }));
		expect(narrowed.disk, narrowed.warned.join('\n')).toMatchObject({ state: 'ok' });
		if (narrowed.disk.state === 'ok') expect(narrowed.disk.rows.map((row) => row.job)).toEqual(['plan']);
		expect(narrowed.browser).toEqual(narrowed.disk);
		const nothing = await bothWays(ask('2026-09-01', '2026-09-03', { where: [{ column: 'shard', op: '>', value: 9 }] }));
		expect(nothing.disk, nothing.warned.join('\n')).toEqual({ state: 'quiet', rows: [], through: '2026-09-05' });
		expect(nothing.browser).toEqual(nothing.disk);
	});
});

test.describe('what a page keeps', () => {
	test('reports which wanted files were fetched and which were already held', async () => {
		const { fetcher } = recorded();
		const engine = counted();
		const page = freshPage(fetcher, engine);
		const entry = fixtureEntries('daily').find((one) => one.covers === '2026-09-01');
		expect(entry).toBeDefined();
		const file = {
			path: dayFile('2026-09-01'),
			version: `${entry?.rows}-${entry?.bytes}`,
			bytes: bytesOf(dayFile('2026-09-01')).byteLength,
			byRange: false
		};
		const first = await page.hold([file]);
		expect(first).toMatchObject({ fetched: [true] });
		if (!('failed' in first)) await first.done();
		const second = await page.hold([file]);
		expect(second).toMatchObject({ fetched: [false] });
		if (!('failed' in second)) await second.done();
	});

	const MONTH_FILE = dataPath(LEDGER, 'monthly', '2026-08');
	/** Both indexes and every file a span from 2026-08-30 to 2026-09-02 reads, each once. */
	const ONCE_EACH = {
		[DAILY_INDEX]: 1,
		[MONTHLY_INDEX]: 1,
		[MONTH_FILE]: 1,
		[dayFile('2026-09-01')]: 1,
		[dayFile('2026-09-02')]: 1
	};

	/** The index as the fixture holds it after a deploy: each entry passed through
	 *  `change`, and an entry it answers `null` for gone. */
	const redeployed = (onDisk: Uint8Array, change: (entry: CompactEntry) => CompactEntry | null): Uint8Array => {
		const index = decoded(onDisk) as { entries: CompactEntry[] };
		const entries = index.entries.map(change).filter((entry): entry is CompactEntry => entry !== null);
		return encoded({ ...index, entries });
	};

	test('two slices over overlapping spans fetch and register each file once, and the second answers what a fresh page would', async () => {
		const { fetcher, asked } = recorded();
		const engine = counted();
		const page = freshPage(fetcher, engine);
		expect(await readSlice(page, LEDGER, ask('2026-08-30', '2026-09-01'))).toMatchObject({ state: 'ok' });
		const second = await readSlice(page, LEDGER, ask('2026-09-01', '2026-09-02'));
		expect(askedCounts(asked)).toEqual(ONCE_EACH);
		expect(engine.registered).toHaveLength(3);
		expect(new Set(engine.registered).size).toBe(3);
		// The engine took every buffer the way a browser's does, so a second slice
		// that handed one over again would have read an empty file.
		const fresh = await readSlice(freshPage(recorded().fetcher), LEDGER, ask('2026-09-01', '2026-09-02'));
		expect(fresh).toMatchObject({ state: 'ok' });
		expect(second).toEqual(fresh);
	});

	test('two slices asked at the same moment share every fetch and every registration', async () => {
		const { fetcher, asked } = recorded();
		const engine = counted();
		const page = freshPage(fetcher, engine);
		const [one, two] = await Promise.all([
			readSlice(page, LEDGER, ask('2026-08-30', '2026-09-02')),
			readSlice(page, LEDGER, ask('2026-08-30', '2026-09-02'))
		]);
		expect(one).toMatchObject({ state: 'ok' });
		expect(two).toEqual(one);
		expect(askedCounts(asked)).toEqual(ONCE_EACH);
		expect(engine.registered).toHaveLength(3);
	});

	test('a fetch that threw is not kept, so the next slice asks again', async () => {
		let indexAsks = 0;
		let fileAsks = 0;
		const { fetcher, asked } = recorded({
			[DAILY_INDEX]: (onDisk) => (++indexAsks === 1 ? 'throw' : { status: 200, body: onDisk }),
			[dayFile('2026-09-01')]: (onDisk) => (++fileAsks === 1 ? 'throw' : { status: 200, body: onDisk })
		});
		const engine = counted();
		const page = freshPage(fetcher, engine);
		const turns: { result: SliceResult; warned: string[] }[] = [];
		for (let turn = 0; turn < 3; turn += 1) {
			turns.push(await warnings(() => readSlice(page, LEDGER, ask('2026-09-01', '2026-09-02'))));
		}
		expect(turns.map(({ result }) => result.state)).toEqual(['unreachable', 'unreachable', 'ok']);
		expect(turns[0].warned.join('\n')).toContain('daily.json cannot be read: it could not be fetched');
		expect(turns[1].warned.join('\n')).toContain(`${dayFile('2026-09-01')} could not be fetched`);
		// The second slice fetched 2026-09-02 whole but could not be answered, so it
		// registered nothing, and a page keeps no bytes: the third fetches it again.
		expect(askedCounts(asked)).toEqual({ [DAILY_INDEX]: 2, [dayFile('2026-09-01')]: 2, [dayFile('2026-09-02')]: 2 });
		expect(engine.registered).toHaveLength(2);
	});

	test('a file that is not there is kept as absent, asked for once, and told to the console once', async () => {
		const { fetcher, asked } = recorded({ [dayFile('2026-09-02')]: { status: 404 } });
		const page = freshPage(fetcher);
		const told: string[] = [];
		for (let turn = 0; turn < 2; turn += 1) {
			const { result, warned } = await warnings(() => readSlice(page, LEDGER, ask('2026-09-02', '2026-09-02')));
			expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-09-02', fault: 'file-missing' });
			told.push(...warned);
		}
		expect(askedCounts(asked)).toEqual({ [DAILY_INDEX]: 1, [dayFile('2026-09-02')]: 1 });
		expect(told).toEqual([
			`[ledger] file-missing host-fingerprint state/${dayFile('2026-09-02')}: daily.json names it; it is not there. ` +
				'Reload; if it stays, re-pack that day.'
		]);
	});

	test('a file of the wrong length is neither registered nor kept, so the next slice fetches it again', async () => {
		let asks = 0;
		const { fetcher, asked } = recorded({
			[dayFile('2026-09-02')]: (onDisk) => ({ status: 200, body: ++asks === 1 ? onDisk.slice(0, -1) : onDisk })
		});
		const engine = counted();
		const page = freshPage(fetcher, engine);
		const { result } = await warnings(() => readSlice(page, LEDGER, ask('2026-09-02', '2026-09-02')));
		expect(result).toEqual({ state: 'unreachable', rows: [], at: '2026-09-02', fault: null });
		expect(engine.registered).toEqual([]);
		expect(await readSlice(page, LEDGER, ask('2026-09-02', '2026-09-02'))).toMatchObject({ state: 'ok' });
		expect(askedCounts(asked)[dayFile('2026-09-02')]).toBe(2);
		expect(engine.registered).toHaveLength(1);
	});

	test('a file whose entry names a new version is fetched and registered again by the next page, and the open page keeps what it holds', async () => {
		// A page keeps its index, so an entry can change only for the next page: a
		// reload in a browser, the next call at build time. The deploy re-packs
		// 2026-09-02 - the site serves other bytes for it, and daily.json names their
		// length. The stand-in bytes are 2026-09-05's file, so the re-packed day holds
		// no row dated 2026-09-02, which is how the two answers tell the files apart.
		const repacked = bytesOf(dayFile('2026-09-05'));
		let deployed = false;
		const { fetcher, asked } = recorded({
			[DAILY_INDEX]: (onDisk) => ({
				status: 200,
				body: deployed
					? redeployed(onDisk, (entry) => (entry.covers === '2026-09-02' ? { ...entry, bytes: repacked.byteLength } : entry))
					: onDisk
			}),
			[dayFile('2026-09-02')]: (onDisk) => ({ status: 200, body: deployed ? repacked : onDisk })
		});
		const engine = counted();
		const open = freshPage(fetcher, engine);
		const before = await readSlice(open, LEDGER, ask('2026-09-02', '2026-09-02'));
		expect(before).toMatchObject({ state: 'ok' });
		deployed = true;
		expect(await readSlice(open, LEDGER, ask('2026-09-02', '2026-09-02'))).toEqual(before);
		expect(await readSlice(freshPage(fetcher, engine), LEDGER, ask('2026-09-02', '2026-09-02'))).toEqual({
			state: 'quiet',
			rows: [],
			through: '2026-09-05'
		});
		const entry = fixtureEntries('daily').find((one) => one.covers === '2026-09-02');
		expect(asked.filter((one) => one.path === dayFile('2026-09-02')).map((one) => one.version)).toEqual([
			`${entry?.rows}-${entry?.bytes}`,
			`${entry?.rows}-${repacked.byteLength}`
		]);
		expect(engine.registered).toHaveLength(2);
		expect(new Set(engine.registered).size).toBe(2);
	});

	test('an open page answers unreachable for a day file removed or re-packed after it opened, and the next page reads the day', async () => {
		// The deploy takes 2026-08-31 into its month, so daily.json stops naming it and
		// its day file goes; and it re-packs 2026-09-05, which the open page has not
		// read yet, with other bytes.
		const repacked = bytesOf(dayFile('2026-09-02'));
		let deployed = false;
		const { fetcher } = recorded({
			[DAILY_INDEX]: (onDisk) => ({
				status: 200,
				body: deployed
					? redeployed(onDisk, (entry) => {
							if (entry.covers === '2026-08-31') return null;
							return entry.covers === '2026-09-05' ? { ...entry, bytes: repacked.byteLength } : entry;
						})
					: onDisk
			}),
			[dayFile('2026-08-31')]: (onDisk) => (deployed ? { status: 404 } : { status: 200, body: onDisk }),
			[dayFile('2026-09-05')]: (onDisk) => ({ status: 200, body: deployed ? repacked : onDisk })
		});
		const open = freshPage(fetcher);
		// The page reads daily.json before the deploy.
		expect(await readSlice(open, LEDGER, ask('2026-09-03', '2026-09-03'))).toMatchObject({ state: 'quiet' });
		deployed = true;
		const removed = await warnings(() => readSlice(open, LEDGER, ask('2026-08-31', '2026-08-31')));
		expect(removed.result).toEqual({ state: 'unreachable', rows: [], at: '2026-08-31', fault: 'file-missing' });
		expect(removed.warned.join('\n')).toContain(
			`[ledger] file-missing host-fingerprint state/${dayFile('2026-08-31')}: daily.json names it; it is not there.`
		);
		const changed = await warnings(() => readSlice(open, LEDGER, ask('2026-09-05', '2026-09-05')));
		expect(changed.result).toEqual({ state: 'unreachable', rows: [], at: '2026-09-05', fault: null });
		expect(changed.warned.join('\n')).toContain(`arrived as ${repacked.byteLength} bytes`);
		const reloaded = freshPage(fetcher);
		expect(await readSlice(reloaded, LEDGER, ask('2026-08-31', '2026-08-31', { columns: ['date', 'run_id', 'shard'] }))).toEqual({
			state: 'ok',
			rows: [{ date: '2026-08-31', run_id: '2026-08-31-17810000001', shard: 0 }],
			through: '2026-09-05'
		});
	});

	test('every file the engine holds is named door/<n>.parquet, and the engine mints the name', async () => {
		const engine = counted();
		await readSlice(freshPage(recorded().fetcher, engine), LEDGER, ask('2026-08-30', '2026-09-02'));
		expect(engine.registered).toHaveLength(3);
		for (const name of engine.registered) expect(name).toMatch(/^door\/\d+\.parquet$/);
	});

	test('only a year file is offered to the engine by byte range, and an engine that reads no host is handed it whole', async () => {
		// The Node engine has no reader for a host, so the browser's byte source hands
		// it the year file whole; `ledger-ranges.spec.ts` drives the ranges in a browser.
		const offered: WantedFile[] = [];
		const watched = (page: PageKeeper): PageKeeper => ({
			...page,
			hold: (files) => {
				offered.push(...files);
				return page.hold(files);
			}
		});
		const unpacked = recorded();
		const span = ask('2026-08-30', '2026-09-02');
		expect(await readSlice(watched(freshPage(unpacked.fetcher)), LEDGER, span)).toMatchObject({ state: 'ok' });
		const packed = recorded({}, YEAR_STATE);
		const engine = counted();
		expect(await readSlice(watched(freshPage(packed.fetcher, engine)), LEDGER, span)).toMatchObject({ state: 'ok' });
		const yearFile = dataPath(LEDGER, 'yearly', '2026');
		expect(offered.map((file) => [file.path, file.byRange])).toEqual([
			[MONTH_FILE, false],
			[dayFile('2026-09-01'), false],
			[dayFile('2026-09-02'), false],
			[yearFile, true]
		]);
		const [year] = fixtureEntries('yearly', YEAR_STATE);
		expect(packed.asked.filter((one) => one.path === yearFile).map((one) => one.version)).toEqual([`${year.rows}-${year.bytes}`]);
		expect(engine.registered).toHaveLength(1);
	});

	test('each read of a file by range gets an address no earlier read used, under the version its entry names', () => {
		// The browser keeps the parts it fetched by address, and every deploy gives every
		// file a new ETag, so a read at an earlier read's address can be sent the whole file.
		const file = dataPath(LEDGER, 'yearly', '2026');
		const page = fetchedBytes(PREFIX, recorded().fetcher);
		const reloaded = fetchedBytes(PREFIX, recorded().fetcher);
		const addresses = [page.address?.(file, '10-20449'), page.address?.(file, '10-20449'), reloaded.address?.(file, '10-20449')];
		expect(new Set(addresses).size, addresses.join('\n')).toBe(addresses.length);
		for (const address of addresses) {
			const url = new URL(address ?? '');
			expect(`${url.origin}${url.pathname}`).toBe(`${PREFIX}/state/${file}`);
			expect(url.searchParams.get('v')).toBe('10-20449');
		}
	});

	test('a page keeps its files registered, and a build-time call drops every file it registered when it ends', async () => {
		const real = await nodeEngine(locate, engineExtensionRepository());
		const held = async (): Promise<string[]> =>
			(await real.rows(`SELECT file FROM glob('door/*') ORDER BY file`, [])).map((row) => String(row.file));
		const engine = counted();
		await readSlice(freshPage(recorded().fetcher, engine), LEDGER, ask('2026-08-30', '2026-09-02'));
		expect(await held()).toEqual(expect.arrayContaining(engine.registered));
		expect(engine.dropped).toEqual([]);
		const before = await held();
		const { result, warned } = await warnings(() => sliceFromDisk(STATE, LEDGER, ask('2026-08-30', '2026-09-02')));
		expect(result, warned.join('\n')).toMatchObject({ state: 'ok' });
		expect(await held()).toEqual(before);
	});
});

test.describe('how far a ledger reaches', () => {
	test('from the first day of the oldest month to the newest day, every index asked at once, and no engine started', async () => {
		const { fetcher, asked } = recorded();
		let inFlight = 0;
		let mostInFlight = 0;
		const watched: Fetcher = async (url, init) => {
			inFlight += 1;
			mostInFlight = Math.max(mostInFlight, inFlight);
			try {
				return await fetcher(url, init);
			} finally {
				inFlight -= 1;
			}
		};
		const engine = counted();
		expect(await readReach(freshPage(watched, engine), LEDGER)).toEqual({
			state: 'ok',
			first: '2026-08-01',
			through: '2026-09-05',
			fault: null
		});
		expect(asked.map((one) => one.path).sort()).toEqual([DAILY_INDEX, MONTHLY_INDEX, YEARLY_INDEX].sort());
		expect(mostInFlight, 'the indexes were asked for one after the other').toBe(3);
		expect(engine.opened()).toBe(0);
	});

	test('from 1 January of the oldest packed year, when the ledger packs years', async () => {
		const { fetcher } = recorded({}, YEAR_STATE);
		const engine = counted();
		expect(await readReach(freshPage(fetcher, engine), LEDGER)).toEqual({
			state: 'ok',
			first: '2026-01-01',
			through: '2027-01-01',
			fault: null
		});
		expect(engine.opened()).toBe(0);
	});

	test('a yearly.json this build will not act on leaves what the other two name, and the console says why', async () => {
		const { fetcher } = recorded({ [YEARLY_INDEX]: reshaped({ version: '2099-01-01' }) }, YEAR_STATE);
		const { result, warned } = await warnings(() => readReach(freshPage(fetcher), LEDGER));
		expect(result).toEqual({ state: 'ok', first: '2027-01-01', through: '2027-01-01', fault: null });
		expect(warned.join('\n')).toMatch(/^\[ledger\] host-fingerprint: yearly\.json .*reaches back only to 2027-01-01/);
	});

	test('with no monthly.json, it reaches back to the oldest day daily.json names, and names index-missing once', async () => {
		const { fetcher } = recorded({ [MONTHLY_INDEX]: { status: 404 } });
		const { result, warned } = await warnings(() => readReach(freshPage(fetcher), LEDGER));
		expect(result).toEqual({ state: 'ok', first: '2026-08-31', through: '2026-09-05', fault: 'index-missing' });
		expect(warned).toEqual([
			`[ledger] index-missing host-fingerprint state/${MONTHLY_INDEX}: it is not there, though daily.json is. ` +
				'Run the upkeep again to write it; it lists nothing until a month is packed.'
		]);
	});

	const unread: [string, Rule][] = [
		['stamped newer than this build', reshaped({ version: '2099-01-01' })],
		['not JSON', { status: 200, body: new TextEncoder().encode('{"entries": [') }],
		['a refused fetch', 'throw']
	];
	for (const [what, rule] of unread) {
		test(`a monthly.json that is ${what} leaves the days daily.json names, and the console says why`, async () => {
			const { fetcher } = recorded({ [MONTHLY_INDEX]: rule });
			const { result, warned } = await warnings(() => readReach(freshPage(fetcher), LEDGER));
			expect(result).toEqual({ state: 'ok', first: '2026-08-31', through: '2026-09-05', fault: null });
			expect(warned.join('\n')).toMatch(/^\[ledger\] host-fingerprint: monthly\.json .*reaches back only to 2026-08-31/);
		});

		test(`a daily.json that is ${what} is unreachable, with no day, and the console says why`, async () => {
			const { fetcher } = recorded({ [DAILY_INDEX]: rule });
			const engine = counted();
			const { result, warned } = await warnings(() => readReach(freshPage(fetcher, engine), LEDGER));
			expect(result).toStrictEqual({ state: 'unreachable' });
			expect(warned.join('\n')).toMatch(/^\[ledger\] host-fingerprint: daily\.json /);
			expect(engine.opened()).toBe(0);
		});
	}

	test('a daily.json that names no day is quiet', async () => {
		const { fetcher } = recorded({ [DAILY_INDEX]: reshaped({ entries: [] }) });
		expect(await readReach(freshPage(fetcher), LEDGER)).toStrictEqual({ state: 'quiet' });
	});

	test('a ledger with no daily.json is missing, not packed', async () => {
		const { fetcher } = recorded({ [DAILY_INDEX]: { status: 404 } });
		const { result } = await warnings(() => readReach(freshPage(fetcher), LEDGER));
		expect(result).toStrictEqual({ state: 'missing', fault: 'not-packed' });
	});

	test('it refuses a ledger outside the closed set, and asks for nothing', async () => {
		const { fetcher, asked } = recorded();
		await expect(readReach(freshPage(fetcher), 'state/../../secrets' as typeof LEDGER)).rejects.toThrow(SliceRequestError);
		expect(asked).toEqual([]);
	});

	test('a slice on the same page agrees with it, and reads no index again', async () => {
		const { fetcher, asked } = recorded();
		const page = freshPage(fetcher);
		const reach = await readReach(page, LEDGER);
		expect(reach).toMatchObject({ state: 'ok' });
		if (reach.state !== 'ok') return;
		// Up to 2026-09-03: 2026-09-04 is the fixture's hole.
		expect(await readSlice(page, LEDGER, ask(reach.first, '2026-09-03'))).toMatchObject({
			state: 'ok',
			through: reach.through
		});
		expect(asked.filter((one) => one.path.endsWith('.json')).map((one) => one.path).sort()).toEqual(
			[DAILY_INDEX, MONTHLY_INDEX, YEARLY_INDEX].sort()
		);
	});

	const nothings: [SliceResult['state'], Record<string, Rule>][] = [
		['missing', { [DAILY_INDEX]: { status: 404 } }],
		['quiet', { [DAILY_INDEX]: reshaped({ entries: [] }) }],
		['unreachable', { [DAILY_INDEX]: reshaped({ version: '2099-01-01' }) }]
	];
	for (const [state, rules] of nothings) {
		test(`where a slice on the same page is ${state}, so is the reach`, async () => {
			const page = freshPage(recorded(rules).fetcher);
			const { result: reach } = await warnings(() => readReach(page, LEDGER));
			const { result: drawn } = await warnings(() => readSlice(page, LEDGER, ask('2026-09-01', '2026-09-02')));
			expect([reach.state, drawn.state]).toEqual([state, state]);
		});
	}
});

/** A copy of the fixture's state tree in a fresh temporary folder, less the files named. */
function fixtureTreeWithout(...without: string[]): string {
	const root = mkdtempSync(path.join(tmpdir(), 'idhazh-door-'));
	cpSync(STATE, root, { recursive: true });
	for (const relative of without) rmSync(path.join(root, ...relative.split('/')));
	return root;
}

test.describe('THE ORACLE for a missing file: a name, the state it draws, and one line', () => {
	/** Each fault: what the tree lacks, a span that meets it, the answer, the reach, and the path its line names. */
	const faults = [
		{
			fault: 'not-packed',
			without: [DAILY_INDEX],
			span: ['2026-09-01', '2026-09-02'],
			answer: { state: 'missing', rows: [], fault: 'not-packed' },
			reach: { state: 'missing', fault: 'not-packed' },
			names: DAILY_INDEX
		},
		{
			fault: 'index-missing',
			without: [MONTHLY_INDEX],
			span: ['2026-08-30', '2026-09-01'],
			answer: { state: 'unreachable', rows: [], at: '2026-08-30', fault: 'index-missing' },
			reach: { state: 'ok', first: '2026-08-31', through: '2026-09-05', fault: 'index-missing' },
			names: MONTHLY_INDEX
		},
		{
			fault: 'file-missing',
			without: [dayFile('2026-09-02')],
			span: ['2026-09-01', '2026-09-02'],
			answer: { state: 'unreachable', rows: [], at: '2026-09-02', fault: 'file-missing' },
			reach: { state: 'ok', first: '2026-08-01', through: '2026-09-05', fault: null },
			names: dayFile('2026-09-02')
		},
		{
			fault: 'day-missing',
			without: [],
			span: ['2026-09-02', '2026-09-05'],
			answer: { state: 'unreachable', rows: [], at: '2026-09-04', fault: 'day-missing' },
			reach: { state: 'ok', first: '2026-08-01', through: '2026-09-05', fault: null },
			names: DAILY_INDEX
		}
	] as const;

	test('the four are the whole list, in its order', () => {
		expect(faults.map((one) => one.fault)).toEqual([...LEDGER_FAULTS]);
	});

	for (const one of faults) {
		test(`${one.fault}: both entry points answer it, and a page prints its one line once`, async () => {
			const rules: Record<string, Rule> = Object.fromEntries(
				one.without.map((relative): [string, Rule] => [relative, { status: 404 }])
			);
			const page = freshPage(recorded(rules).fetcher);
			const [from, to] = one.span;
			const browser = await warnings(async () => [
				await readSlice(page, LEDGER, ask(from, to)),
				await readSlice(page, LEDGER, ask(from, to)),
				await readReach(page, LEDGER)
			]);
			expect(browser.result).toEqual([one.answer, one.answer, one.reach]);
			expect(browser.warned).toHaveLength(1);
			expect(browser.warned[0].startsWith(`[ledger] ${one.fault} ${LEDGER} state/${one.names}: `), browser.warned[0]).toBe(true);

			const root = fixtureTreeWithout(...one.without);
			try {
				const disk = await warnings(() => sliceFromDisk(root, LEDGER, ask(from, to)));
				expect(disk.result).toEqual(one.answer);
				expect(disk.warned).toEqual(browser.warned);
				const { result: reach } = await warnings(() => reachFromDisk(root, LEDGER));
				expect(reach).toEqual(one.reach);
			} finally {
				rmSync(root, { recursive: true, force: true });
			}
		});
	}

	test('a reach and a slice that meet one fault on a page print it once between them', async () => {
		const page = freshPage(recorded({ [MONTHLY_INDEX]: { status: 404 } }).fetcher);
		const { warned } = await warnings(async () => {
			await readReach(page, LEDGER);
			return readSlice(page, LEDGER, ask('2026-08-30', '2026-09-01'));
		});
		expect(warned).toHaveLength(1);
		expect(warned[0]).toContain(`index-missing ${LEDGER} state/${MONTHLY_INDEX}`);
	});

	test('index-missing names yearly.json too, at both entry points, in one line', async () => {
		// monthly.json names 2026-08, so a span from July reaches back past it and asks for yearly.json.
		const span = ask('2026-07-30', '2026-08-02');
		const page = freshPage(recorded({ [YEARLY_INDEX]: { status: 404 } }).fetcher);
		const browser = await warnings(async () => ({
			drawn: await readSlice(page, LEDGER, span),
			reach: await readReach(page, LEDGER)
		}));
		expect(browser.result).toEqual({
			drawn: { state: 'unreachable', rows: [], at: '2026-07-30', fault: 'index-missing' },
			reach: { state: 'ok', first: '2026-08-01', through: '2026-09-05', fault: 'index-missing' }
		});
		expect(browser.warned).toEqual([
			`[ledger] index-missing ${LEDGER} state/${YEARLY_INDEX}: it is not there, though daily.json is. ` +
				'Run the upkeep again to write it; it lists nothing until a year is packed.'
		]);
		const root = fixtureTreeWithout(YEARLY_INDEX);
		try {
			const disk = await warnings(() => sliceFromDisk(root, LEDGER, span));
			expect(disk.result).toEqual(browser.result.drawn);
			expect(disk.warned).toEqual(browser.warned);
			const { result: reach } = await warnings(() => reachFromDisk(root, LEDGER));
			expect(reach).toEqual(browser.result.reach);
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});
});

test.describe('an empty monthly.json or yearly.json is a gap the design expects: nothing leads to a file that is not there', () => {
	const EMPTY_MONTHS = { version: COMPACT_INDEX_STAMP, ledger: LEDGER, period: 'monthly', entries: [] };

	test('a span that starts before the oldest daily day, and the reach, ask the site for no file it lacks', async () => {
		const { fetcher, asked } = recorded({ [MONTHLY_INDEX]: { status: 200, body: encoded(EMPTY_MONTHS) } });
		const page = freshPage(fetcher);
		const { result: drawn, warned } = await warnings(() => readSlice(page, LEDGER, ask('2026-08-30', '2026-09-02')));
		const { result: reach } = await warnings(() => readReach(page, LEDGER));
		expect(drawn).toEqual({ state: 'unreachable', rows: [], at: '2026-08-30', fault: null });
		expect(reach).toEqual({ state: 'ok', first: '2026-08-31', through: '2026-09-05', fault: null });
		expect(asked.map((one) => one.path).sort()).toEqual([DAILY_INDEX, MONTHLY_INDEX, YEARLY_INDEX].sort());
		expect(asked.filter((one) => one.answered !== 200)).toEqual([]);
		for (const fault of LEDGER_FAULTS) expect(warned.join('\n')).not.toContain(` ${fault} `);
	});

	test('at build time too, counted by a byte source that records every file it could not find', async () => {
		const root = fixtureTreeWithout(MONTHLY_INDEX);
		writeFileSync(path.join(root, ...MONTHLY_INDEX.split('/')), JSON.stringify(EMPTY_MONTHS));
		try {
			const disk = diskBytes(root);
			const notThere: string[] = [];
			const noted = (relative: string, bytes: Uint8Array | null): Uint8Array | null => {
				if (bytes === null) notThere.push(relative);
				return bytes;
			};
			const counting: ByteSource = {
				index: async (relative) => noted(relative, await disk.index(relative)),
				data: async (relative, version) => noted(relative, await disk.data(relative, version))
			};
			const page = pageKeeper(counting, counted().open);
			const { result: drawn } = await warnings(() => readSlice(page, LEDGER, ask('2026-08-30', '2026-09-02')));
			const { result: reach } = await warnings(() => readReach(page, LEDGER));
			expect([drawn.state, reach.state]).toEqual(['unreachable', 'ok']);
			expect(notThere).toEqual([]);
		} finally {
			rmSync(root, { recursive: true, force: true });
		}
	});
});


test.describe('THE ORACLE for ask(): a written question over chosen ledgers', () => {
	const opts = {
		ledgers: ['host-fingerprint', 'item-health'] as const,
		from: '2026-09-01',
		to: '2026-09-01',
		sql: 'SELECT h.date, h.job, i.job AS item_job FROM "host-fingerprint" h JOIN "item-health" i USING (date) ORDER BY h.shard, i.shard',
		maxChars: 1000,
		maxRows: 3,
		maxFetchBytes: 100_000_000
	};

	test('a join over two selected ledgers returns typed text rows and the expected cap', async () => {
		const { fetcher } = recorded();
		const answer = await readAsk(freshPage(fetcher), opts, {});
		expect(answer).toMatchObject({ state: 'ok', capped: true });
		if (answer.state !== 'ok') return;
		expect(answer.columns.map((column) => column.name)).toEqual(['date', 'job', 'item_job']);
		expect(answer.rows).toHaveLength(3);
		expect(answer.rows[0]).toEqual({ date: '2026-09-01', job: 'plan', item_job: 'work' });
	});

	test('the next call drops the unselected ledger view', async () => {
		const page = freshPage(recorded().fetcher);
		expect((await readAsk(page, opts, {})).state).toBe('ok');
		const answer = await readAsk(page, { ...opts, ledgers: ['host-fingerprint'], sql: 'SELECT * FROM "item-health"', maxRows: 10 }, {});
		expect(answer).toMatchObject({ state: 'refused', because: { kind: 'engine-error' } });
	});

	test('the writers tier is priced from its listing and read once when listed through', async () => {
		const page = freshPage(recorded().fetcher);
		const cost = await readAskCost(page, ['item-health'], '2026-09-06', '2026-09-06', { 'item-health': '2026-09-06' });
		expect(cost.files).toBe(2);
		expect(cost.unpackedDays).toEqual(['2026-09-06']);
		const answer = await readAsk(page, { ledgers: ['item-health'], from: '2026-09-06', to: '2026-09-06', sql: 'SELECT date, run_id, hostile FROM "item-health" ORDER BY run_id', maxChars: 200, maxRows: 10, maxFetchBytes: 100_000_000 }, { 'item-health': '2026-09-06' });
		expect(answer).toMatchObject({ state: 'ok', unpackedDays: ['2026-09-06'] });
		if (answer.state === 'ok') expect(answer.rows.map((row) => row.run_id)).toEqual(['raw-1', 'raw-2']);
	});

	test('a byte ceiling refuses before any data file is fetched', async () => {
		const { fetcher, asked } = recorded();
		const answer = await readAsk(freshPage(fetcher), { ...opts, maxFetchBytes: 1 }, {});
		expect(answer).toMatchObject({ state: 'refused', because: { kind: 'over-ceiling' } });
		expect(dataAsked(asked)).toEqual([]);
	});


	test('additional written-question oracle cases match committed answers', async () => {
		const page = freshPage(recorded().fetcher);
		const cases = [
			{ name: 'order-by-cap', sql: 'SELECT date, shard FROM "host-fingerprint" WHERE date=\'2026-09-01\' ORDER BY shard DESC', maxRows: 2 },
			{ name: 'trailing-comment', sql: 'SELECT 1 AS one -- done', maxRows: 10 },
			{ name: 'semicolon-comment', sql: 'SELECT 1 AS one; -- done', maxRows: 10 },
			{ name: 'typed-values', sql: "SELECT sum(cores) AS total, 1.5 AS decimal_value, DATE '2026-09-01' AS day_value, [1,2] AS list_value, {'a':1} AS struct_value FROM \"host-fingerprint\"", maxRows: 10 },
			{ name: 'summarize', sql: 'SUMMARIZE SELECT * FROM "host-fingerprint"', maxRows: 3 },
			{ name: 'explain', sql: 'EXPLAIN SELECT 1 AS one', maxRows: 10 },
			{ name: 'duplicate-id', sql: 'SELECT h.shard AS id, i.shard AS id FROM "host-fingerprint" h JOIN "item-health" i USING (date) ORDER BY h.shard, i.shard', maxRows: 3 }
		];
		for (const one of cases) {
			const answer = await readAsk(page, { ...opts, sql: one.sql, maxRows: one.maxRows }, {});
			expect(answer, one.name).toMatchObject({ state: 'ok' });
			if (answer.state === 'ok') expect(answer.rows, one.name).toEqual(expectedAnswer(one.name));
		}
	});

	test('a ledger with no file in the span can still answer through an empty view', async () => {
		const answer = await readAsk(freshPage(recorded().fetcher), {
			ledgers: ['host-fingerprint', 'item-health'],
			from: '2026-09-06',
			to: '2026-09-06',
			sql: 'SELECT count(*) AS rows FROM "host-fingerprint"',
			maxChars: 100,
			maxRows: 10,
			maxFetchBytes: 100_000_000
		}, { 'item-health': '2026-09-06' });
		expect(answer).toMatchObject({ state: 'ok' });
		if (answer.state === 'ok') expect(answer.rows).toEqual([{ rows: '0' }]);
	});

	test('listed writer files do not make a packed day read twice', async () => {
		const { fetcher, asked } = recorded();
		const answer = await readAsk(freshPage(fetcher), { ...opts, ledgers: ['host-fingerprint'], from: '2026-09-01', to: '2026-09-01', sql: 'SELECT count(*) AS rows FROM "host-fingerprint"', maxRows: 10 }, { 'host-fingerprint': '2026-09-01' });
		expect(answer).not.toEqual({ state: 'unreachable', ledger: 'host-fingerprint', at: '2026-09-01', fault: 'file-missing' });
		expect(dataAsked(asked).some((path) => path.startsWith('raw/'))).toBe(false);
	});

	test('days after the newest listing are clamped away, and a missing listing inside the range is unreachable', async () => {
		const quiet = await readAsk(freshPage(recorded().fetcher), { ...opts, ledgers: ['item-health'], from: '2026-09-07', to: '2026-09-07', sql: 'SELECT count(*) AS rows FROM "item-health"', maxRows: 10 }, { 'item-health': '2026-09-06' });
		expect(quiet).toMatchObject({ state: 'quiet' });
		const missing = await readAsk(freshPage(recorded().fetcher), { ...opts, ledgers: ['item-health'], from: '2026-09-07', to: '2026-09-07', sql: 'SELECT count(*) AS rows FROM "item-health"', maxRows: 10 }, { 'item-health': '2026-09-07' });
		expect(missing).toEqual({ state: 'unreachable', ledger: 'item-health', at: '2026-09-07', fault: 'file-missing' });
	});

	test('a date in no tier is unreachable, and concurrent calls both answer', async () => {
		const missing = await readAsk(freshPage(recorded().fetcher), { ...opts, from: '2026-07-30', to: '2026-07-30' }, {});
		expect(missing).toMatchObject({ state: 'unreachable', at: '2026-07-30' });
		const page = freshPage(recorded().fetcher);
		const [one, two] = await Promise.all([readAsk(page, opts, {}), readAsk(page, opts, {})]);
		expect(one.state).toBe('ok');
		expect(two.state).toBe('ok');
	});


	test('empty published ledger is missing, and broken coarser indexes are unreachable', async () => {
		const empty = { version: COMPACT_INDEX_STAMP, ledger: LEDGER, period: 'daily', entries: [] };
		const missing = await readAsk(freshPage(recorded({
			[DAILY_INDEX]: { status: 200, body: encoded(empty) },
			[MONTHLY_INDEX]: { status: 200, body: encoded({ ...empty, period: 'monthly' }) },
			[YEARLY_INDEX]: { status: 200, body: encoded({ ...empty, period: 'yearly' }) }
		}).fetcher), { ...opts, ledgers: ['host-fingerprint', 'item-health'] }, {});
		expect(missing).toEqual({ state: 'missing', ledger: 'host-fingerprint' });

		const absent = await readAsk(freshPage(recorded({ [MONTHLY_INDEX]: { status: 404 } }).fetcher), opts, {});
		expect(absent).toMatchObject({ state: 'unreachable', ledger: 'host-fingerprint', at: '2026-09-01', fault: 'index-missing' });
		const refused = await readAsk(freshPage(recorded({ [MONTHLY_INDEX]: reshaped({ version: '2099-01-01' }) }).fetcher), opts, {});
		expect(refused).toMatchObject({ state: 'unreachable', ledger: 'host-fingerprint', at: '2026-09-01', fault: 'index-missing' });
	});

	test('a raw listing naming a non-parquet file is unreachable at its day', async () => {
		const listing = decoded(readFileSync(path.join(STATE, 'raw', 'item-health', 'index', '2026-09-06.json')));
		const bad: Record<string, unknown> = { ...listing, files: ['00000000-0000-8000-8000-000000000001.json'] };
		bad.content_sha256 = '0'.repeat(64);
		const answer = await readAsk(freshPage(recorded({ [rawIndexPath('item-health', '2026-09-06')]: { status: 200, body: encoded(bad) } }).fetcher), {
			ledgers: ['item-health'],
			from: '2026-09-06',
			to: '2026-09-06',
			sql: 'SELECT count(*) AS rows FROM "item-health"',
			maxChars: 100,
			maxRows: 10,
			maxFetchBytes: 100_000_000
		}, { 'item-health': '2026-09-06' });
		expect(answer).toEqual({ state: 'unreachable', ledger: 'item-health', at: '2026-09-06', fault: 'index-missing' });
	});

	test('a bad statement is refused before the engine starts', async () => {
		const engine = counted();
		const answer = await readAsk(freshPage(recorded().fetcher, engine), { ...opts, sql: 'SELECT 1; DROP VIEW "host-fingerprint"' }, {});
		expect(answer).toEqual({ state: 'refused', because: { kind: 'statements', count: 2 } });
		expect(engine.opened()).toBe(0);
	});
});
