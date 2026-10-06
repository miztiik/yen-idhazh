import { expect, test } from '@playwright/test';
import { createRequire } from 'node:module';
import { windowOfDays, type TimeWindow } from '../src/lib/charts/viewport';
import { recordNotes } from '../src/lib/console/recording';
import { readAsk } from '../src/lib/data/ask-reader';
import { nodeEngine } from '../src/lib/data/engine';
import { fetchedBytes, type Fetcher } from '../src/lib/data/fetched-bytes';
import { readReach } from '../src/lib/data/ledger-reach';
import { pageKeeper, type PageKeeper } from '../src/lib/data/page-keeper';
import { daysBetween } from '../src/lib/data/slice';
import { readSlice } from '../src/lib/data/slice-reader';
import type { AskOptions, SliceOptions } from '../src/lib/data/slice-shapes';
import { engineExtensionRepository } from '../src/lib/server/config';
import { sliceFromDisk } from '../src/lib/server/ledger-disk';
import { windowRows, type LedgerTable } from '../src/lib/server/ledger-rows';
import { buildLedger, everyDay, servedFrom, siteCopy, type BuiltLedger } from './support/ledger-lifecycle';

/**
 * Which days do a written question, a panel slice and a console window read from a ledger in each lifecycle state?
 *
 * Every ledger here is built by the test that asks, with its days counted back from a day the
 * test pins, so each expected value is written out from what that test built: the rows an
 * answer reads, the first day it reads, the day it names as the ledger's first, and every file
 * a host is asked for. No case reads a committed fixture or the canary.
 */

const PINNED = '2030-06-15';
const LEDGER = 'host-fingerprint' as const;
const SITE = 'https://pages.test/yen-idhazh';
const ARCHIVE = 'https://archive.test/yen-idhazh';
const resolver = createRequire(import.meta.url);
const locate = (specifier: string): string => resolver.resolve(specifier);

/** A page that has read nothing yet, reading from `prefix` through `fetcher`. */
function aPage(fetcher: Fetcher, prefix = SITE): PageKeeper {
	return pageKeeper(fetchedBytes(prefix, fetcher), () => nodeEngine(locate, engineExtensionRepository()));
}

function question(from: string, to: string, sql: string): AskOptions {
	return { ledgers: [LEDGER], from, to, sql, maxChars: 1000, maxRows: 100, maxFetchBytes: 100_000_000 };
}

const ROWS_PER_DAY = `SELECT covers, count(*) AS rows FROM "${LEDGER}" GROUP BY covers ORDER BY covers`;
const FIRST_DAY_AND_ROWS = `SELECT min(covers) AS first_day, count(*) AS rows FROM "${LEDGER}"`;
const parquetAsked = (asked: readonly string[]): string[] => asked.filter((one) => one.endsWith('.parquet'));
const INDEXES = ['daily', 'monthly', 'yearly'].map((period) => `compact/${LEDGER}/index/${period}.json`);
/** A panel's slice of the built ledger: the day each row was filed under, and its number in that day. */
const slicing = (from: string, to: string): SliceOptions => ({ columns: ['date', 'n'], from, to });
const dayFile = (day: string): string => `compact/${LEDGER}/daily/${day.replaceAll('-', '/')}.parquet`;

test.describe('a ledger the test builds', () => {
	test('answers the rows it was built with, reads its empty day as quiet, and names its lost day', async () => {
		const root = test.info().outputPath('state');
		await buildLedger(root, {
			ledger: LEDGER,
			pinned: PINNED,
			days: [...everyDay(9, 7, 2), { ago: 6, state: 'empty' }, ...everyDay(5, 4, 2), { ago: 3, state: 'lost' }, ...everyDay(2, 0, 2)]
		});
		const site = aPage(servedFrom(root, SITE).fetcher);
		try {
			const answer = await readAsk(site, null, question('2030-06-06', '2030-06-15', ROWS_PER_DAY), {});
			expect(answer).toMatchObject({ state: 'ok', siteFrom: null, gaps: [{ ledger: LEDGER, lostDays: ['2030-06-12'], setAside: {} }] });
			expect(answer.state === 'ok' ? answer.rows : []).toEqual([
				{ covers: '2030-06-06', rows: '2' },
				{ covers: '2030-06-07', rows: '2' },
				{ covers: '2030-06-08', rows: '2' },
				{ covers: '2030-06-10', rows: '2' },
				{ covers: '2030-06-11', rows: '2' },
				{ covers: '2030-06-13', rows: '2' },
				{ covers: '2030-06-14', rows: '2' },
				{ covers: '2030-06-15', rows: '2' }
			]);
		} finally {
			await site.release();
		}
	});

	test('reads the days of a closed month from that month\'s one file', async () => {
		const root = test.info().outputPath('state');
		await buildLedger(root, { ledger: LEDGER, pinned: PINNED, days: everyDay(40, 0), closedMonths: ['2030-05'] });
		const served = servedFrom(root, SITE);
		const site = aPage(served.fetcher);
		try {
			const answer = await readAsk(site, null, question('2030-05-30', '2030-06-02', ROWS_PER_DAY), {});
			expect(answer).toMatchObject({ state: 'ok', siteFrom: null });
			expect(answer.state === 'ok' ? answer.rows : []).toEqual([
				{ covers: '2030-05-30', rows: '1' },
				{ covers: '2030-05-31', rows: '1' },
				{ covers: '2030-06-01', rows: '1' },
				{ covers: '2030-06-02', rows: '1' }
			]);
			expect(parquetAsked(served.asked)).toEqual([
				`compact/${LEDGER}/monthly/2030/05.parquet`,
				`compact/${LEDGER}/daily/2030/06/01.parquet`,
				`compact/${LEDGER}/daily/2030/06/02.parquet`
			]);
		} finally {
			await site.release();
		}
	});
});

test.describe('days before a ledger began are cut from the selected window', () => {
	test('a ledger that began 5 days before the pinned day: a 14-day window reads from its first day, names it, and asks the archive nothing', async () => {
		const root = test.info().outputPath('state');
		await buildLedger(root, { ledger: LEDGER, pinned: PINNED, days: everyDay(5, 0) });
		const archive = servedFrom(root, ARCHIVE);
		const site = aPage(servedFrom(root, SITE).fetcher);
		try {
			const answer = await readAsk(site, { keeper: aPage(archive.fetcher, ARCHIVE), siteWindowDays: 90 }, question('2030-06-02', PINNED, FIRST_DAY_AND_ROWS), {});
			expect(answer).toMatchObject({ state: 'ok', siteFrom: '2030-06-10', rows: [{ first_day: '2030-06-10', rows: '6' }] });
			expect(archive.asked).toEqual([]);
		} finally {
			await site.release();
		}
	});

	test('a ledger that began 20 days before the pinned day, trimmed by the site copy to 10: a 30-day window reads the archive from the ledger\'s first day, and names it', async () => {
		// The site copy keeps 6 to 15 Jun 2030, so the archive holds 26 May, the first day, to 5 Jun.
		const root = test.info().outputPath('state');
		await buildLedger(root, { ledger: LEDGER, pinned: PINNED, days: everyDay(20, 0) });
		const siteRoot = test.info().outputPath('site');
		siteCopy(root, siteRoot, LEDGER, 10);
		const archive = servedFrom(root, ARCHIVE);
		const site = aPage(servedFrom(siteRoot, SITE).fetcher);
		const archived = aPage(archive.fetcher, ARCHIVE);
		try {
			const answer = await readAsk(site, { keeper: archived, siteWindowDays: 10 }, question('2030-05-17', PINNED, FIRST_DAY_AND_ROWS), {});
			expect(answer).toMatchObject({ state: 'ok', siteFrom: '2030-05-26', rows: [{ first_day: '2030-05-26', rows: '21' }] });
			expect(archive.asked.filter((one) => !one.endsWith('.parquet')).sort()).toEqual(INDEXES);
			expect(parquetAsked(archive.asked).sort()).toEqual(daysBetween('2030-05-26', '2030-06-05').map((day) => `compact/${LEDGER}/daily/${day.replaceAll('-', '/')}.parquet`));
		} finally {
			await site.release();
			await archived.release();
		}
	});

	test('a ledger that began 1,461 days before the pinned day moves no window: 14 days are read as selected, and 365 days ask the archive only for days inside them', async () => {
		// Four years of one row a day. Every month before May 2030 is closed, and the site copy
		// keeps 90 days: 18 Mar to 15 Jun 2030, with March whole, so the site's first day is 1 Mar.
		const root = test.info().outputPath('state');
		const closedMonths = [...new Set(daysBetween('2026-06-15', '2030-04-30').map((day) => day.slice(0, 7)))];
		await buildLedger(root, { ledger: LEDGER, pinned: PINNED, days: everyDay(1461, 0), closedMonths });
		const siteRoot = test.info().outputPath('site');
		siteCopy(root, siteRoot, LEDGER, 90);

		const shortArchive = servedFrom(root, ARCHIVE);
		const shortSite = servedFrom(siteRoot, SITE);
		const fortnight = aPage(shortSite.fetcher);
		try {
			const answer = await readAsk(fortnight, { keeper: aPage(shortArchive.fetcher, ARCHIVE), siteWindowDays: 90 }, question('2030-06-02', PINNED, FIRST_DAY_AND_ROWS), {});
			expect(answer).toMatchObject({ state: 'ok', siteFrom: null, rows: [{ first_day: '2030-06-02', rows: '14' }] });
			expect(shortArchive.asked).toEqual([]);
			expect(parquetAsked(shortSite.asked)).toEqual(daysBetween('2030-06-02', '2030-06-15').map((day) => `compact/${LEDGER}/daily/${day.replaceAll('-', '/')}.parquet`));
		} finally {
			await fortnight.release();
		}

		const yearArchive = servedFrom(root, ARCHIVE);
		const year = aPage(servedFrom(siteRoot, SITE).fetcher);
		const archived = aPage(yearArchive.fetcher, ARCHIVE);
		try {
			const answer = await readAsk(year, { keeper: archived, siteWindowDays: 90 }, question('2029-06-16', PINNED, FIRST_DAY_AND_ROWS), {});
			expect(answer).toMatchObject({ state: 'ok', siteFrom: null, rows: [{ first_day: '2029-06-16', rows: '365' }] });
			expect(yearArchive.asked.filter((one) => !one.endsWith('.parquet')).sort()).toEqual(INDEXES);
			expect(parquetAsked(yearArchive.asked).sort()).toEqual([
				`compact/${LEDGER}/monthly/2029/06.parquet`,
				`compact/${LEDGER}/monthly/2029/07.parquet`,
				`compact/${LEDGER}/monthly/2029/08.parquet`,
				`compact/${LEDGER}/monthly/2029/09.parquet`,
				`compact/${LEDGER}/monthly/2029/10.parquet`,
				`compact/${LEDGER}/monthly/2029/11.parquet`,
				`compact/${LEDGER}/monthly/2029/12.parquet`,
				`compact/${LEDGER}/monthly/2030/01.parquet`,
				`compact/${LEDGER}/monthly/2030/02.parquet`
			]);
		} finally {
			await year.release();
			await archived.release();
		}
	});

	test('a day no index names after the ledger began is still day-missing when the archive reads it', async () => {
		// Began 20 days before the pinned day, with no entry 15 days before it, 31 May. The site
		// copy keeps 10 days, 6 to 15 Jun, so 29 May to 5 Jun are the archive's.
		const root = test.info().outputPath('state');
		await buildLedger(root, { ledger: LEDGER, pinned: PINNED, days: [...everyDay(20, 16), ...everyDay(14, 0)] });
		const siteRoot = test.info().outputPath('site');
		siteCopy(root, siteRoot, LEDGER, 10);
		const site = aPage(servedFrom(siteRoot, SITE).fetcher);
		try {
			const answer = await readAsk(site, { keeper: aPage(servedFrom(root, ARCHIVE).fetcher, ARCHIVE), siteWindowDays: 10 }, question('2030-05-29', PINNED, FIRST_DAY_AND_ROWS), {});
			expect(answer).toEqual({ state: 'unreachable', ledger: LEDGER, at: '2030-05-31', fault: 'day-missing' });
		} finally {
			await site.release();
		}
	});

	test('a ledger that paused for three days and lost one: the days before it began are cut, its quiet days stay quiet, and its lost day is named', async () => {
		const root = test.info().outputPath('state');
		await buildLedger(root, {
			ledger: LEDGER,
			pinned: PINNED,
			days: [...everyDay(10, 7), { ago: 6, state: 'empty' }, { ago: 5, state: 'empty' }, { ago: 4, state: 'empty' }, { ago: 3, rows: 1 }, { ago: 2, state: 'lost' }, ...everyDay(1, 0)]
		});
		const archive = servedFrom(root, ARCHIVE);
		const site = aPage(servedFrom(root, SITE).fetcher);
		try {
			const answer = await readAsk(site, { keeper: aPage(archive.fetcher, ARCHIVE), siteWindowDays: 90 }, question('2030-06-02', PINNED, FIRST_DAY_AND_ROWS), {});
			expect(answer).toMatchObject({
				state: 'ok',
				siteFrom: '2030-06-05',
				rows: [{ first_day: '2030-06-05', rows: '7' }],
				gaps: [{ ledger: LEDGER, lostDays: ['2030-06-13'], setAside: {} }]
			});
			expect(archive.asked).toEqual([]);
		} finally {
			await site.release();
		}
	});

	test('a ledger that has never held a row: the days before it began are cut, the answer is quiet, and the archive gets no request', async () => {
		const root = test.info().outputPath('state');
		await buildLedger(root, { ledger: LEDGER, pinned: PINNED, days: [3, 2, 1, 0].map((ago) => ({ ago, state: 'empty' as const })) });
		const archive = servedFrom(root, ARCHIVE);
		const site = aPage(servedFrom(root, SITE).fetcher);
		try {
			const answer = await readAsk(site, { keeper: aPage(archive.fetcher, ARCHIVE), siteWindowDays: 90 }, question('2030-06-02', PINNED, FIRST_DAY_AND_ROWS), {});
			expect(answer).toMatchObject({ state: 'quiet', siteFrom: '2030-06-12' });
			expect(archive.asked).toEqual([]);
		} finally {
			await site.release();
		}
	});
});

/** A page that reads a ledger, built under a fresh root with `days` and `closedMonths`, from the
 *  site's host, and every path under `state/` that host was asked for. */
async function builtSite(days: BuiltLedger['days'], closedMonths: string[] = []): Promise<{ page: PageKeeper; asked: string[] }> {
	const root = test.info().outputPath('state');
	await buildLedger(root, { ledger: LEDGER, pinned: PINNED, days, closedMonths });
	const served = servedFrom(root, SITE);
	return { page: aPage(served.fetcher), asked: served.asked };
}

test.describe('a panel slice cuts only the days before a ledger began', () => {
	test('a ledger whose first day is the fifth-last day of a 14-day slice: the answer covers those 5 days, names the first, and ends where the slice ends', async () => {
		// Packed 9 to 15 Jun 2030, one row a day. The slice asks for 31 May to 13 Jun.
		const { page, asked } = await builtSite(everyDay(6, 0));
		try {
			expect(await readSlice(page, LEDGER, slicing('2030-05-31', '2030-06-13'))).toEqual({
				state: 'ok',
				rows: [
					{ date: '2030-06-09', n: 1 },
					{ date: '2030-06-10', n: 1 },
					{ date: '2030-06-11', n: 1 },
					{ date: '2030-06-12', n: 1 },
					{ date: '2030-06-13', n: 1 }
				],
				first: '2030-06-09',
				through: '2030-06-15',
				lostDays: [],
				setAside: {}
			});
			expect(parquetAsked(asked).sort()).toEqual(daysBetween('2030-06-09', '2030-06-13').map(dayFile));
		} finally {
			await page.release();
		}
	});

	test('a slice that ends before the ledger began is quiet, names the ledger\'s first day, and fetches no data file', async () => {
		// Packed 11 to 15 Jun 2030; the slice asks for 1 to 5 Jun.
		const { page, asked } = await builtSite(everyDay(4, 0));
		try {
			expect(await readSlice(page, LEDGER, slicing('2030-06-01', '2030-06-05'))).toEqual({
				state: 'quiet',
				rows: [],
				first: '2030-06-11',
				through: '2030-06-15',
				lostDays: [],
				setAside: {}
			});
			expect(parquetAsked(asked)).toEqual([]);
		} finally {
			await page.release();
		}
	});

	test('a day no index names after the ledger began is still day-missing, at that day, and nothing is fetched', async () => {
		// Packed 5 to 15 Jun 2030, with no entry for 10 Jun.
		const { page, asked } = await builtSite([...everyDay(10, 6), ...everyDay(4, 0)]);
		try {
			expect(await readSlice(page, LEDGER, slicing('2030-06-02', PINNED))).toEqual({
				state: 'unreachable',
				rows: [],
				at: '2030-06-10',
				fault: 'day-missing'
			});
			expect(parquetAsked(asked)).toEqual([]);
		} finally {
			await page.release();
		}
	});

	test('a ledger that paused for three days and lost one: the days before it began are cut, its quiet days stay quiet, and its lost day is named', async () => {
		// 5 to 8 Jun 2030 packed, 9 to 11 Jun empty, 12 Jun packed, 13 Jun lost, 14 and 15 Jun packed.
		const { page } = await builtSite([
			...everyDay(10, 7),
			{ ago: 6, state: 'empty' },
			{ ago: 5, state: 'empty' },
			{ ago: 4, state: 'empty' },
			{ ago: 3, rows: 1 },
			{ ago: 2, state: 'lost' },
			...everyDay(1, 0)
		]);
		try {
			expect(await readSlice(page, LEDGER, slicing('2030-06-02', PINNED))).toEqual({
				state: 'ok',
				rows: [
					{ date: '2030-06-05', n: 1 },
					{ date: '2030-06-06', n: 1 },
					{ date: '2030-06-07', n: 1 },
					{ date: '2030-06-08', n: 1 },
					{ date: '2030-06-12', n: 1 },
					{ date: '2030-06-14', n: 1 },
					{ date: '2030-06-15', n: 1 }
				],
				first: '2030-06-05',
				through: '2030-06-15',
				lostDays: ['2030-06-13'],
				setAside: {}
			});
		} finally {
			await page.release();
		}
	});

	test('a ledger that has never held a row: the slice is quiet from its first day, and fetches no data file', async () => {
		// 12 to 15 Jun 2030, every day packed empty.
		const { page, asked } = await builtSite([3, 2, 1, 0].map((ago) => ({ ago, state: 'empty' as const })));
		try {
			expect(await readSlice(page, LEDGER, slicing('2030-06-02', PINNED))).toEqual({
				state: 'quiet',
				rows: [],
				first: '2030-06-12',
				through: '2030-06-15',
				lostDays: [],
				setAside: {}
			});
			expect(parquetAsked(asked)).toEqual([]);
		} finally {
			await page.release();
		}
	});

	test('a ledger that began inside a month the packing has closed is cut at that month\'s 1st, where its month entry starts', async () => {
		// Began 20 May 2030, one row a day. May is closed, so its one entry counts from 1 May, and
		// 1 to 19 May are quiet days of that month. The slice asks for the 60 days to 15 Jun.
		const { page, asked } = await builtSite(everyDay(26, 0), ['2030-05']);
		try {
			expect(await readSlice(page, LEDGER, slicing('2030-04-17', PINNED))).toEqual({
				state: 'ok',
				rows: daysBetween('2030-05-20', '2030-06-15').map((date) => ({ date, n: 1 })),
				first: '2030-05-01',
				through: '2030-06-15',
				lostDays: [],
				setAside: {}
			});
			expect(parquetAsked(asked).sort()).toEqual([
				...daysBetween('2030-06-01', '2030-06-15').map(dayFile),
				`compact/${LEDGER}/monthly/2030/05.parquet`
			]);
		} finally {
			await page.release();
		}
	});
});

test.describe('how far a ledger is packed comes from all three indexes', () => {
	test('a ledger whose packed days have all moved into a closed month reaches through that month\'s last day, and a slice reads them', async () => {
		// Packed 1 to 31 May 2030, one row a day, and May closed: daily.json names no day, and
		// monthly.json names May.
		const { page, asked } = await builtSite(everyDay(45, 15), ['2030-05']);
		try {
			expect(await readReach(page, LEDGER)).toEqual({
				state: 'ok',
				first: '2030-05-01',
				through: '2030-05-31',
				lastRows: { period: 'monthly', covers: '2030-05' },
				fault: null
			});
			expect(await readSlice(page, LEDGER, slicing('2030-05-18', '2030-05-31'))).toEqual({
				state: 'ok',
				rows: daysBetween('2030-05-18', '2030-05-31').map((date) => ({ date, n: 1 })),
				first: '2030-05-18',
				through: '2030-05-31',
				lostDays: [],
				setAside: {}
			});
			expect(await readSlice(page, LEDGER, slicing('2030-06-01', PINNED))).toEqual({
				state: 'quiet',
				rows: [],
				first: '2030-06-01',
				through: '2030-05-31',
				lostDays: [],
				setAside: {}
			});
			expect(parquetAsked(asked)).toEqual([`compact/${LEDGER}/monthly/2030/05.parquet`]);
		} finally {
			await page.release();
		}
	});
});

/** The rows a console route reads from a ledger built under a fresh root, for `window`, and
 *  every span its reader asked the door for. */
async function consoleRead(days: BuiltLedger['days'], window: TimeWindow, closedMonths: string[] = []): Promise<{ table: LedgerTable; asked: [string, string][] }> {
	const root = test.info().outputPath('state');
	await buildLedger(root, { ledger: LEDGER, pinned: PINNED, days, closedMonths });
	const asked: [string, string][] = [];
	const table = await windowRows(root, LEDGER, window, ['date', 'n'], (from, to) => {
		asked.push([from, to]);
		return sliceFromDisk(root, LEDGER, { columns: ['date', 'n'], from, to });
	});
	return { table, asked };
}

/** Each window the control offers, ending on the pinned day, the site's newest published day. */
const OFFERED = [1, 7, 14, 30, 90].map((days) => ({ days, ...windowOfDays(PINNED, days, 'right') }));
const FORTNIGHT = OFFERED.find((window) => window.days === 14)!;

/** The empty days from `oldest` days before the pinned day to `newest` days before it. */
function emptyDays(oldest: number, newest: number): BuiltLedger['days'] {
	const days: BuiltLedger['days'][number][] = [];
	for (let ago = oldest; ago >= newest; ago -= 1) days.push({ ago, state: 'empty' });
	return days;
}

test.describe('a console window ends on the newest published day, and reads only its own days', () => {
	test('a writer that stopped through a month close: the window reads no row, and the note names that month', async () => {
		// One row a day from 10 to 20 May 2030, May closed, then June packed empty to 14
		// Jun. The 14-day window is 2 to 15 Jun, and the 90-day one starts on 18 Mar.
		const { table, asked } = await consoleRead([...everyDay(36, 26), ...emptyDays(25, 1)], FORTNIGHT, ['2030-05']);
		expect(asked).toEqual([['2030-06-02', '2030-06-15']]);
		expect(table.rows).toEqual([]);
		expect(table.read).toEqual({
			state: 'read',
			through: '2030-06-14',
			lastRows: { period: 'monthly', covers: '2030-05' },
			lostDays: [],
			setAside: {}
		});
		expect(recordNotes([{ record: 'machine', read: table.read }], PINNED, FORTNIGHT, OFFERED)).toEqual([
			{
				kind: 'rows-end',
				records: ['machine'],
				text: 'The newest packed rows in the machine record are from May 2030. The packed days since then hold no rows, so nothing below that uses this record has anything to show in these 14 days. This page cannot tell if that is a quiet stretch or a fault. The 90-day window reaches back to May 2030.',
				emptiesWindow: true
			}
		]);
	});

	test('packing that paused 5 days before the newest published day: the window reads to where packing stopped, and the note names the days after', async () => {
		// One row a day, packed as far as 10 Jun 2030.
		const { table, asked } = await consoleRead(everyDay(30, 5), FORTNIGHT);
		expect(asked).toEqual([['2030-06-02', '2030-06-15']]);
		expect(table.rows).toEqual(daysBetween('2030-06-02', '2030-06-10').map((date) => ({ date, n: '1' })));
		expect(table.read).toEqual({
			state: 'read',
			through: '2030-06-10',
			lastRows: { period: 'daily', covers: '2030-06-10' },
			lostDays: [],
			setAside: {}
		});
		expect(recordNotes([{ record: 'machine', read: table.read }], PINNED, FORTNIGHT, OFFERED)).toEqual([
			{
				kind: 'behind',
				records: ['machine'],
				text: 'The machine record is packed as far as 10 Jun 2030, so the 5 days after it are not shown yet.',
				emptiesWindow: false
			}
		]);
	});

	test('a ledger packed as far as the day before the newest published day: the window reads to that day, and the quietest line names the day after', async () => {
		const { table } = await consoleRead(everyDay(20, 1), FORTNIGHT);
		expect(table.rows).toEqual(daysBetween('2030-06-02', '2030-06-14').map((date) => ({ date, n: '1' })));
		expect(recordNotes([{ record: 'machine', read: table.read }], PINNED, FORTNIGHT, OFFERED)).toEqual([
			{
				kind: 'on-time',
				records: ['machine'],
				text: 'The machine record is packed as far as 14 Jun 2030, so nothing below that uses it shows 15 Jun 2030 yet. That is normal: a day is packed only after it ends.',
				emptiesWindow: false
			}
		]);
	});

	test('a ledger that began inside the window is read from its first day, and says nothing about rows stopping', async () => {
		// Began on 10 Jun 2030, packed as far as 15 Jun.
		const { table, asked } = await consoleRead(everyDay(5, 0), FORTNIGHT);
		expect(asked).toEqual([['2030-06-02', '2030-06-15']]);
		expect(table.rows).toEqual(daysBetween('2030-06-10', '2030-06-15').map((date) => ({ date, n: '1' })));
		expect(recordNotes([{ record: 'machine', read: table.read }], PINNED, FORTNIGHT, OFFERED)).toEqual([]);
	});

	test('a ledger that has never held a row: its quiet days stay quiet, and no note says its rows stopped', async () => {
		const { table } = await consoleRead(emptyDays(20, 0), FORTNIGHT);
		expect(table.rows).toEqual([]);
		expect(table.read).toEqual({ state: 'read', through: PINNED, lastRows: null, lostDays: [], setAside: {} });
		expect(recordNotes([{ record: 'machine', read: table.read }], PINNED, FORTNIGHT, OFFERED)).toEqual([]);
	});
});