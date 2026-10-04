import { expect, test, type Browser, type Page } from '@playwright/test';
import { copyFileSync, cpSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, utimesSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'vite';
import { COMPACT_INDEX_STAMP, type CompactEntry, type Period } from '../src/lib/data/compact-index';
import { nodeEngine } from '../src/lib/data/engine';
import { dataPath, indexPath } from '../src/lib/data/slice-reader';
import type { SliceOptions, SliceResult } from '../src/lib/data/slice-shapes';
import { engineExtensionRepository } from '../src/lib/server/config';
import { sliceFromDisk } from '../src/lib/server/ledger-disk';
import type { MeasuredSlice, RangeChoice, TimedSlice } from './support/door-page/door';
import { addonCache, startRangeHost, type HostRequest, type RangeHost, type Throttle } from './support/range-host';

/**
 * A browser reads a packed year out of its year file by byte range, and this
 * spec drives it on a page of its own, `support/door-page/`, because no route on
 * the site calls `slice()` yet: the page is the query door as a console panel
 * reaches it, built by Vite into `test-results/`, and `support/range-host.ts`
 * serves it with the fixture's files the way GitHub Pages serves them.
 *
 * The door registers a year file with the engine by its address, and the engine
 * asks the host only for the footer and the row groups a query needs. Three
 * things would make it read the whole file without a word - the engine's own
 * default, an opening 1-byte GET not answered with 206, and any read answered
 * with 200 - so every GET for a year file has to name a range and be answered
 * 206. The rows must be the ones the whole file gives, in the
 * browser and on disk; a year file whose length is not its entry's is refused
 * before any of it is read; and a year file whose ETag changed while the browser
 * kept some of it is still read by range, because each read asks at an address no
 * earlier read used, so no request names the ETag the browser kept. Day files
 * stay fetched whole, and a day the index records `empty` or `lost` is never
 * asked of the host at all.
 *
 * The host serves the page, the fixture and the engine's parquet add-on from
 * 127.0.0.1, so the browser reaches no other host. The add-on is the one the
 * Node engine keeps under the home directory once it has downloaded it, and the
 * disk read that opens this spec is the read that downloads it on a fresh
 * machine - the one network fetch the door's tests make (owner ruling,
 * 2026-09-28).
 *
 * The last case is the measurement behind reading a year file by range: one
 * month out of a year file of real size, against that month's own file, and the
 * same month read twice on one page, on a slowed link. It needs the two files, so
 * it runs only where `IDHAZH_RANGE_BENCH_DIR` names a directory holding them.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE = path.resolve(here, '..', '..', 'tests', 'fixtures', 'ledger-door');
const STATE = path.join(FIXTURE, 'state');
const YEAR_STATE = path.join(FIXTURE, 'year-state');
const WORK = path.resolve(here, '..', 'test-results', 'ledger-ranges');
const PAGE_BUILD = path.join(WORK, 'page');
const LEDGER = 'host-fingerprint' as const;
const COLUMNS = ['date', 'run_id', 'job', 'shard', 'cores'];
const SPAN: SliceOptions = { columns: COLUMNS, from: '2026-08-30', to: '2026-09-02' };
const YEAR_FILE = dataPath(LEDGER, 'yearly', '2026');
const resolver = createRequire(import.meta.url);
const locate = (specifier: string): string => resolver.resolve(specifier);

/** The `max-age` Pages sends with every file. */
const PAGES_MAX_AGE = 600;

/** The door's page, built from `support/door-page/` the way Vite builds the site. */
async function buildDoorPage(): Promise<void> {
	await build({
		configFile: false,
		root: path.join(here, 'support', 'door-page'),
		base: '/',
		logLevel: 'warn',
		build: {
			outDir: PAGE_BUILD,
			emptyOutDir: true,
			target: 'es2022',
			assetsInlineLimit: 0,
			reportCompressedSize: false
		}
	});
}

/** A fresh copy of a fixture root under `test-results/`, so a case may change it. */
function copied(from: string, name: string): string {
	const to = path.join(WORK, name);
	rmSync(to, { recursive: true, force: true });
	cpSync(from, to, { recursive: true });
	return to;
}

/** A copy of the day fixture as the packing now writes it: the zero-row day recorded
 *  `empty` and the hole recorded `lost`, and neither with a file on the host. */
function copiedWithNoFile(name: string): string {
	const root = copied(STATE, name);
	const daily = path.join(root, ...indexPath(LEDGER, 'daily').split('/'));
	const index = JSON.parse(readFileSync(daily, 'utf8')) as { entries: CompactEntry[] };
	const entries = index.entries.flatMap((entry): CompactEntry[] =>
		entry.covers === '2026-09-03'
			? [
					{ covers: '2026-09-03', rows: 0, bytes: 0, state: 'empty' },
					{ covers: '2026-09-04', rows: 0, bytes: 0, state: 'lost' }
				]
			: [entry]
	);
	writeFileSync(daily, JSON.stringify({ ...index, version: COMPACT_INDEX_STAMP, entries }));
	rmSync(path.join(root, ...dataPath(LEDGER, 'daily', '2026-09-03').split('/')));
	return root;
}

async function openDoor(page: Page, host: RangeHost): Promise<void> {
	await page.goto(`${host.origin}/`);
	await page.waitForFunction(() => window.door !== undefined);
}

/** A response is logged as it closes, a moment after the page has its answer. */
const settle = (): Promise<void> => new Promise((resolve) => setTimeout(resolve, 200));

/** One slice on `page`, and every request the host logged for its root while it ran. */
async function sliceOn(
	page: Page,
	host: RangeHost,
	root: string,
	options: SliceOptions,
	choice: RangeChoice = 'door'
): Promise<{ timed: TimedSlice; asked: HostRequest[] }> {
	const from = host.log.length;
	const timed = await page.evaluate(
		([root, ledger, options, choice]) => window.door.slice(root, ledger, options, choice),
		[root, LEDGER, options, choice] as const
	);
	await settle();
	return { timed, asked: host.log.slice(from).filter((one) => one.root === root) };
}

const requestsFor = (asked: HostRequest[], file: string, method: string): HostRequest[] =>
	asked.filter((one) => one.path === file && one.method === method);

/** A deploy as Pages makes one: the year file under `root` gets a new modification
 *  time, so a new ETag, over the same bytes. */
function redeploy(root: string): void {
	const file = path.join(root, ...YEAR_FILE.split('/'));
	const moved = new Date(statSync(file).mtimeMs + 3_600_000);
	utimesSync(file, moved, moved);
}

/** The version the year file's entry names under `root`: its rows and its bytes. */
function versionOf(root: string): string {
	const index = JSON.parse(readFileSync(path.join(root, ...indexPath(LEDGER, 'yearly').split('/')), 'utf8')) as {
		entries: { rows: number; bytes: number }[];
	};
	return `${index.entries[0].rows}-${index.entries[0].bytes}`;
}

/** One read asked for the year file by range: every GET is answered 206, and no
 *  request names an ETag other than the one it was answered with. */
function expectReadByRange(asked: HostRequest[], read: string): void {
	const year = asked.filter((one) => one.path === YEAR_FILE);
	const gets = year.filter((one) => one.method === 'GET');
	expect(gets.length, `${read} asked for no part of the year file`).toBeGreaterThan(0);
	for (const one of gets) expect(one, `${read}: ${JSON.stringify(one)}`).toMatchObject({ status: 206 });
	for (const one of year) expect([null, one.etag], `${read} named another ETag: ${JSON.stringify(one)}`).toContain(one.ifRange);
}

/** Each read asked for the year file at one address of its own, under the version its entry names. */
function expectAddressesOfTheirOwn(reads: HostRequest[][], version: string): void {
	const used = new Set<string>();
	for (const [at, asked] of reads.entries()) {
		const addresses = new Set(asked.filter((one) => one.path === YEAR_FILE).map((one) => one.query));
		expect([...addresses], `read ${at + 1} asked for the year file at one address`).toHaveLength(1);
		const [address] = addresses;
		expect(new URLSearchParams(address).get('v'), `read ${at + 1} at ${address}`).toBe(version);
		expect(used.has(address), `read ${at + 1} asked at ${address}, where an earlier read asked`).toBe(false);
		used.add(address);
	}
}

test.describe('a year file read by byte range, in a browser', () => {
	test.describe.configure({ mode: 'serial' });

	let host: RangeHost;
	let disk: SliceResult;
	let servedYear: string;
	let servedFresh: string;
	let servedReopened: string;
	let servedWithNoFile: string;

	test.beforeAll(async ({}, testInfo) => {
		testInfo.setTimeout(180_000);
		mkdirSync(WORK, { recursive: true });
		// The disk read comes first: it is the oracle, and it leaves the add-on where the host serves it from.
		disk = await sliceFromDisk(YEAR_STATE, LEDGER, SPAN);
		await buildDoorPage();
		servedYear = copied(YEAR_STATE, 'year-state');
		servedFresh = copied(YEAR_STATE, 'fresh-state');
		servedReopened = copied(YEAR_STATE, 'reopened-state');
		servedWithNoFile = copiedWithNoFile('no-file-state');
		const longer = copied(YEAR_STATE, 'longer-entry');
		const yearly = path.join(longer, ...indexPath(LEDGER, 'yearly').split('/'));
		const index = JSON.parse(readFileSync(yearly, 'utf8')) as { entries: { bytes: number }[] };
		index.entries[0].bytes += 1;
		writeFileSync(yearly, JSON.stringify(index));
		host = await startRangeHost({
			site: PAGE_BUILD,
			plain: { ext: addonCache(engineExtensionRepository()) },
			data: {
				year: { dir: servedYear },
				fresh: { dir: servedFresh },
				reopened: { dir: servedReopened },
				days: { dir: STATE },
				longer: { dir: longer },
				lost: { dir: servedWithNoFile }
			},
			maxAge: PAGES_MAX_AGE
		});
	});

	test.afterAll(async () => {
		// Every request the host answered, for whoever reads a failure.
		if (host !== undefined) writeFileSync(path.join(WORK, 'requests.json'), JSON.stringify(host.log, null, 1));
		await host?.close();
	});

	test('a span in a packed year draws the same rows by byte range as from the whole file, and as the disk reads', async ({ browser, page }) => {
		expect(disk, 'the fixture has to read on disk first').toMatchObject({ state: 'ok', through: '2027-01-01' });
		await openDoor(page, host);
		const ranged = await sliceOn(page, host, 'year', SPAN);
		expect(ranged.timed.result, ranged.timed.warned.join('\n')).toEqual(disk);
		// Another context, so the browser keeps nothing of the year file the ranged read fetched.
		const context = await browser.newContext();
		try {
			const other = await context.newPage();
			await openDoor(other, host);
			const whole = await sliceOn(other, host, 'year', SPAN, 'no-file');
			expect(whole.timed.result, whole.timed.warned.join('\n')).toEqual(disk);
			expect(requestsFor(whole.asked, YEAR_FILE, 'GET')).toEqual([
				expect.objectContaining({ range: null, status: 200 })
			]);
		} finally {
			await context.close();
		}
	});

	test('every GET the engine makes for a year file names a byte range and is answered 206', async ({ page }) => {
		await openDoor(page, host);
		const { timed, asked } = await sliceOn(page, host, 'year', SPAN);
		expect(timed.result, timed.warned.join('\n')).toMatchObject({ state: 'ok' });
		const gets = requestsFor(asked, YEAR_FILE, 'GET');
		expect(gets.length, 'the engine asked for no part of the year file').toBeGreaterThan(1);
		for (const one of gets) {
			expect(one.range, JSON.stringify(one)).toMatch(/^bytes=\d+-\d+$/);
			expect(one, JSON.stringify(one)).toMatchObject({ status: 206 });
		}
		expect(gets[0].range, 'the engine opens a file with a 1-byte GET').toBe('bytes=0-0');
		// Pages answers a HEAD carrying a range with 200 and the full length, and the engine accepts it.
		const heads = requestsFor(asked, YEAR_FILE, 'HEAD');
		expect(heads.length).toBeGreaterThan(0);
		for (const one of heads) expect(one, JSON.stringify(one)).toMatchObject({ status: 200 });
	});

	test('a day file is still fetched whole, in one GET with no range', async ({ page }) => {
		await openDoor(page, host);
		const { timed, asked } = await sliceOn(page, host, 'days', { columns: COLUMNS, from: '2026-09-01', to: '2026-09-02' });
		expect(timed.result, timed.warned.join('\n')).toMatchObject({ state: 'ok' });
		const files = asked
			.filter((one) => one.path.endsWith('.parquet'))
			.map((one) => [one.path, one.method, one.range, one.status])
			.sort();
		expect(files).toEqual([
			[dataPath(LEDGER, 'daily', '2026-09-01'), 'GET', null, 200],
			[dataPath(LEDGER, 'daily', '2026-09-02'), 'GET', null, 200]
		]);
	});

	test('a span across an empty and a lost day reads the other days, names the lost one, and asks for neither file', async ({ page }) => {
		const span: SliceOptions = { columns: COLUMNS, from: '2026-09-01', to: '2026-09-05' };
		const fromDisk = await sliceFromDisk(servedWithNoFile, LEDGER, span);
		expect(fromDisk).toMatchObject({ state: 'ok', through: '2026-09-05', lostDays: ['2026-09-04'] });
		await openDoor(page, host);
		const { timed, asked } = await sliceOn(page, host, 'lost', span);
		expect(timed.result, timed.warned.join('\n')).toEqual(fromDisk);
		expect(timed.warned).toEqual([]);
		expect(asked.filter((one) => one.status === 404)).toEqual([]);
		expect(asked.filter((one) => one.path.endsWith('.parquet')).map((one) => one.path).sort()).toEqual([
			dataPath(LEDGER, 'daily', '2026-09-01'),
			dataPath(LEDGER, 'daily', '2026-09-02'),
			dataPath(LEDGER, 'daily', '2026-09-05')
		]);
	});

	test('a year file of another length than its entry is unreachable, and nothing past its opening is asked for', async ({ page }) => {
		await openDoor(page, host);
		const size = statSync(path.join(YEAR_STATE, ...YEAR_FILE.split('/'))).size;
		// Twice on one page: a refused file is not kept, so the second slice opens it again.
		for (let turn = 0; turn < 2; turn += 1) {
			const { timed, asked } = await sliceOn(page, host, 'longer', SPAN);
			expect(timed.result).toEqual({ state: 'unreachable', rows: [], at: SPAN.from, fault: null });
			if (turn === 0) {
				expect(timed.warned).toHaveLength(1);
				expect(timed.warned[0]).toContain(
					`${YEAR_FILE} opened at ${size} bytes to be read by range, and its entry says ${size + 1}`
				);
			} else {
				expect(timed.warned).toEqual([]);
			}
			// An opening is one 1-byte GET and one HEAD, at an address no earlier read used.
			expect(requestsFor(asked, YEAR_FILE, 'HEAD'), `turn ${turn}`).toHaveLength(1);
			for (const one of requestsFor(asked, YEAR_FILE, 'GET')) expect(one.range, `turn ${turn}`).toBe('bytes=0-0');
		}
	});

	test('a year file whose ETag changed after the browser kept part of it is still read by byte range', async ({ browser }) => {
		// Short-lived, so what the browser kept has gone stale before the second read.
		host.maxAge = 1;
		const context = await browser.newContext();
		try {
			const first = await context.newPage();
			await openDoor(first, host);
			const before = await sliceOn(first, host, 'year', SPAN);
			expect(before.timed.result, before.timed.warned.join('\n')).toEqual(disk);
			redeploy(servedYear);
			await first.waitForTimeout(2_000);
			const second = await context.newPage();
			await openDoor(second, host);
			const after = await sliceOn(second, host, 'year', SPAN);
			expect(after.timed.result, after.timed.warned.join('\n')).toEqual(disk);
			const gets = requestsFor(after.asked, YEAR_FILE, 'GET');
			for (const one of gets) expect(one, JSON.stringify(one)).toMatchObject({ status: 206 });
		} finally {
			host.maxAge = PAGES_MAX_AGE;
			await context.close();
		}
	});

	test('a year file whose ETag changed while the browser still holds part of it is still read by byte range', async ({ browser }) => {
		// A page reads the year file; a deploy then gives it a new ETag over the same bytes
		// while what the browser kept is still fresh; and the same page reads it again. At
		// the first read's address the browser would ask for a part it does not hold naming
		// the ETag it kept, and Pages answers that with the whole file (measured). Each read
		// asks at an address of its own, and the engine drops the file when the read ends.
		const context = await browser.newContext();
		try {
			const page = await context.newPage();
			await openDoor(page, host);
			const before = await sliceOn(page, host, 'fresh', SPAN);
			expect(before.timed.result, before.timed.warned.join('\n')).toEqual(disk);
			expect(await page.evaluate(() => window.door.held()), 'the engine still holds what the read opened').toEqual([]);
			redeploy(servedFresh);
			const after = await sliceOn(page, host, 'fresh', SPAN);
			expect(after.timed.result, after.timed.warned.join('\n')).toEqual(disk);
			expect(await page.evaluate(() => window.door.held()), 'the engine still holds what the read opened').toEqual([]);
			expectReadByRange(before.asked, 'the read before the deploy');
			expectReadByRange(after.asked, 'the read after the deploy');
			expectAddressesOfTheirOwn([before.asked, after.asked], versionOf(servedFresh));
		} finally {
			await context.close();
		}
	});

	test('a new page, opened while the browser still holds fresh parts of a year file and after its ETag changed, reads it by byte range', async ({ browser }) => {
		// Pages sends `max-age=600`, so what one page fetched is still fresh for a page
		// opened soon after it, and a deploy in between changes the ETag the browser kept.
		const context = await browser.newContext();
		try {
			const first = await context.newPage();
			await openDoor(first, host);
			const before = await sliceOn(first, host, 'reopened', SPAN);
			expect(before.timed.result, before.timed.warned.join('\n')).toEqual(disk);
			redeploy(servedReopened);
			const second = await context.newPage();
			await openDoor(second, host);
			const after = await sliceOn(second, host, 'reopened', SPAN);
			expect(after.timed.result, after.timed.warned.join('\n')).toEqual(disk);
			expectReadByRange(before.asked, 'the earlier page');
			expectReadByRange(after.asked, 'the new page');
			expectAddressesOfTheirOwn([before.asked, after.asked], versionOf(servedReopened));
		} finally {
			await context.close();
		}
	});
});

/** Lighthouse's slow 4G, as DevTools applies it: a 150 ms round trip times 3.75
 *  before each response, and 1.6 megabits a second times 0.9 for the body. */
const SLOW_4G: Throttle = { latencyMs: 562.5, bytesPerSecond: 188_743 };

/** The eval ledger's columns the console's model-change panel draws, the widest
 *  panel over that ledger, spelled as its files hold them. */
const PANEL_COLUMNS = [
	'date',
	'model_id',
	'summary_words',
	'source_words_before_cap',
	'source_words',
	'extractiveness',
	'verbatim_run',
	'band',
	'unsupported_numbers',
	'hedge_dropped'
];

const BENCH_DIR = process.env.IDHAZH_RANGE_BENCH_DIR ?? '';
const ROUNDS = 3;

interface BenchFile {
	path: string;
	covers: string;
	bytes: number;
	rows: number;
}

async function rowCount(file: string): Promise<number> {
	const engine = await nodeEngine(locate, engineExtensionRepository());
	const name = await engine.register(new Uint8Array(readFileSync(file)));
	try {
		const [counted] = await engine.rows(`SELECT count(*) AS n FROM read_parquet('${name}')`, []);
		return Number(counted.n);
	} finally {
		await engine.drop([name]);
	}
}

/** A year file and one month file of the same year, named `year-<YYYY>.parquet` and `month-<YYYY>-<MM>.parquet`. */
async function benchFiles(dir: string): Promise<{ year: BenchFile; month: BenchFile }> {
	const names = readdirSync(dir);
	const yearName = names.find((name) => /^year-\d{4}\.parquet$/.test(name));
	const monthName = names.find((name) => /^month-\d{4}-\d{2}\.parquet$/.test(name));
	if (yearName === undefined || monthName === undefined || !monthName.startsWith(`month-${yearName.slice(5, 9)}`)) {
		throw new Error(`${dir} has to hold year-<YYYY>.parquet and month-<YYYY>-<MM>.parquet of the same year`);
	}
	const described = async (name: string, covers: string): Promise<BenchFile> => {
		const file = path.join(dir, name);
		return { path: file, covers, bytes: statSync(file).size, rows: await rowCount(file) };
	};
	return {
		year: await described(yearName, yearName.slice(5, 9)),
		month: await described(monthName, monthName.slice(6, 13))
	};
}

/** A state root holding one packed file under its index, and a zero-row day
 *  after it, so a span inside the file is read from it. */
function benchRoot(name: string, period: Period, file: BenchFile, after: string): string {
	const root = path.join(WORK, 'bench', name);
	rmSync(root, { recursive: true, force: true });
	const write = (relative: string, value: unknown): void => {
		const target = path.join(root, ...relative.split('/'));
		mkdirSync(path.dirname(target), { recursive: true });
		writeFileSync(target, JSON.stringify(value));
	};
	const index = (at: Period, entries: object[]) => ({ entries, ledger: LEDGER, period: at, version: COMPACT_INDEX_STAMP });
	write(indexPath(LEDGER, 'daily'), index('daily', [{ covers: after, rows: 0, bytes: 0 }]));
	write(indexPath(LEDGER, period), index(period, [{ covers: file.covers, rows: file.rows, bytes: file.bytes }]));
	const target = path.join(root, ...dataPath(LEDGER, period, file.covers).split('/'));
	mkdirSync(path.dirname(target), { recursive: true });
	copyFileSync(file.path, target);
	return root;
}

const median = (values: number[]): number => {
	const sorted = [...values].sort((a, b) => a - b);
	return sorted[Math.floor(sorted.length / 2)];
};

test('measure: one month out of a year file by byte range, against its month file, on a slow 4G link', async ({ browser }, testInfo) => {
	test.skip(BENCH_DIR === '', 'IDHAZH_RANGE_BENCH_DIR names no directory holding a year file and a month file to measure');
	testInfo.setTimeout(40 * 60_000);
	mkdirSync(WORK, { recursive: true });
	await sliceFromDisk(YEAR_STATE, LEDGER, SPAN);
	await buildDoorPage();
	const { year, month } = await benchFiles(BENCH_DIR);
	const next = `${Number(year.covers) + 1}-01-01`;
	const host = await startRangeHost({
		site: PAGE_BUILD,
		plain: { ext: addonCache(engineExtensionRepository()) },
		data: {
			warm: { dir: STATE },
			month: { dir: benchRoot('month', 'monthly', month, next), throttle: SLOW_4G },
			year: { dir: benchRoot('year', 'yearly', year, next), throttle: SLOW_4G },
			deploy: { dir: benchRoot('deploy', 'yearly', year, next) }
		},
		maxAge: PAGES_MAX_AGE
	});
	const [y, m] = month.covers.split('-').map(Number);
	const span: SliceOptions = {
		columns: PANEL_COLUMNS,
		from: `${month.covers}-01`,
		to: new Date(Date.UTC(y, m, 0)).toISOString().slice(0, 10)
	};
	const monthFile = dataPath(LEDGER, 'monthly', month.covers);
	const yearFile = dataPath(LEDGER, 'yearly', year.covers);
	const cases: BenchCase[] = [
		{ name: 'month file, whole', root: 'month', choice: 'door', file: monthFile, reads: 1 },
		{ name: 'year file, by range', root: 'year', choice: 'door', file: yearFile, reads: 1 },
		{ name: 'month file, by range', root: 'month', choice: 'every-file', file: monthFile, reads: 1 },
		{ name: 'year file, by range, read again on one page', root: 'year', choice: 'door', file: yearFile, reads: 2 }
	];
	const runs: Record<string, number | string | boolean>[] = [];
	let deploy: Record<string, number | string | boolean>;
	try {
		for (let round = 0; round < ROUNDS; round += 1) {
			for (let at = 0; at < cases.length; at += 1) {
				const one = cases[(at + round) % cases.length];
				runs.push({ round, ...(await measureOnce(browser, host, one, span)) });
			}
		}
		deploy = await deployOnce(browser, host, yearFile, span);
	} finally {
		await host.close();
	}
	const summary = cases.map((one) => {
		const mine = runs.filter((run) => run.case === one.name);
		return {
			case: one.name,
			medianMs: Math.round(median(mine.map((run) => run.ms as number))),
			fileBytes: median(mine.map((run) => run.fileBytes as number)),
			fileGets: median(mine.map((run) => run.fileGets as number)),
			fileHeads: median(mine.map((run) => run.fileHeads as number)),
			indexRequests: median(mine.map((run) => run.indexRequests as number)),
			allTwoHundredSix: mine.every((run) => run.everyGetRanged206 === true)
		};
	});
	const report = { year: { ...year, path: path.basename(year.path) }, month: { ...month, path: path.basename(month.path) }, span, throttle: SLOW_4G, runs, summary, deploy };
	writeFileSync(path.join(WORK, 'measure.json'), JSON.stringify(report, null, 1));
	console.log(JSON.stringify({ summary, deploy }, null, 1));
	const [whole, byRange, , again] = summary;
	expect(new Set(runs.map((run) => `${run.state} ${run.rows} ${run.digest}`)).size, 'every run drew the same rows').toBe(1);
	for (const read of [byRange, again]) {
		expect(read.fileBytes, `${read.case} costs more than twice the month file`).toBeLessThanOrEqual(2 * month.bytes);
		expect(read.allTwoHundredSix, `${read.case}: a GET for the year file was not a range answered 206`).toBe(true);
		expect(read.medianMs, `${read.case} drew later than the month file whole`).toBeLessThanOrEqual(whole.medianMs);
	}
	expect(deploy.wholeAnswers, 'a read after a deploy was answered with the whole year file').toBe(0);
});

/** One measured case: the root it reads, which files by range, the file it counts,
 *  and how many reads of the span one page makes, the last of them measured. */
interface BenchCase {
	name: string;
	root: string;
	choice: RangeChoice;
	file: string;
	reads: number;
}

/** One timed case in a fresh browser context, after the engine and its add-on have
 *  loaded over an unslowed root: its reads one after another on one page, and what
 *  the host was asked for the last of them. */
async function measureOnce(
	browser: Browser,
	host: RangeHost,
	one: BenchCase,
	span: SliceOptions
): Promise<Record<string, number | string | boolean>> {
	const context = await browser.newContext();
	try {
		const page = await context.newPage();
		await openDoor(page, host);
		const warmed: MeasuredSlice = await page.evaluate(
			([ledger, columns]) => window.door.measure('warm', ledger, { columns, from: '2026-09-01', to: '2026-09-02' }, 'door'),
			[LEDGER, COLUMNS] as const
		);
		expect(warmed.state, warmed.warned.join('\n')).toBe('ok');
		const read = (): Promise<MeasuredSlice> =>
			page.evaluate(([root, ledger, span, choice]) => window.door.measure(root, ledger, span, choice), [one.root, LEDGER, span, one.choice] as const);
		const earlierMs: number[] = [];
		for (let turn = 1; turn < one.reads; turn += 1) {
			earlierMs.push(Math.round((await read()).ms));
			await settle();
		}
		const from = host.log.length;
		const timed = await read();
		await settle();
		const asked = host.log.slice(from).filter((request) => request.root === one.root);
		const gets = requestsFor(asked, one.file, 'GET');
		const indexes = asked.filter((request) => request.path.endsWith('.json'));
		return {
			case: one.name,
			ms: timed.ms,
			earlierMs: earlierMs.join(' '),
			state: timed.state,
			rows: timed.rows,
			digest: timed.digest,
			fileGets: gets.length,
			fileHeads: requestsFor(asked, one.file, 'HEAD').length,
			fileBytes: gets.reduce((sum, request) => sum + request.bodyBytes, 0),
			indexRequests: indexes.length,
			indexBytes: indexes.reduce((sum, request) => sum + request.bodyBytes, 0),
			everyGetRanged206: gets.every((request) => request.range !== null && request.status === 206),
			ranges: gets.map((request) => `${request.range ?? 'whole'}=${request.status}:${request.bodyBytes}`).join(' ')
		};
	} finally {
		await context.close();
	}
}

/** The month after the one `span` covers, whole. */
function nextMonth(span: SliceOptions): SliceOptions {
	const [y, m] = span.from.split('-').map(Number);
	const day = (at: number): string => new Date(at).toISOString().slice(0, 10);
	return { ...span, from: day(Date.UTC(y, m, 1)), to: day(Date.UTC(y, m + 1, 0)) };
}

/** One page reads a month out of the year file; a deploy then gives the file a new
 *  ETag over the same bytes, and the same page reads the next month. What the host
 *  answers for that second month, unslowed. */
async function deployOnce(
	browser: Browser,
	host: RangeHost,
	file: string,
	span: SliceOptions
): Promise<Record<string, number | string | boolean>> {
	const context = await browser.newContext();
	try {
		const page = await context.newPage();
		await openDoor(page, host);
		const first: MeasuredSlice = await page.evaluate(
			([ledger, span]) => window.door.measure('deploy', ledger, span, 'door'),
			[LEDGER, span] as const
		);
		expect(first.state, first.warned.join('\n')).toBe('ok');
		const onDisk = path.join(WORK, 'bench', 'deploy', ...file.split('/'));
		const moved = new Date(statSync(onDisk).mtimeMs + 3_600_000);
		utimesSync(onDisk, moved, moved);
		const from = host.log.length;
		const second: MeasuredSlice = await page.evaluate(
			([ledger, span]) => window.door.measure('deploy', ledger, span, 'door'),
			[LEDGER, nextMonth(span)] as const
		);
		await settle();
		const gets = requestsFor(host.log.slice(from).filter((request) => request.root === 'deploy'), file, 'GET');
		return {
			state: second.state,
			rows: second.rows,
			fileGets: gets.length,
			wholeAnswers: gets.filter((request) => request.status === 200).length,
			fileBytes: gets.reduce((sum, request) => sum + request.bodyBytes, 0),
			ranges: gets.map((request) => `${request.range ?? 'whole'}${request.ifRange ? ' if-range' : ''}=${request.status}:${request.bodyBytes}`).join(' ')
		};
	} finally {
		await context.close();
	}
}
