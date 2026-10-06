import { expect, test } from '@playwright/test';
import { createRequire } from 'node:module';
import { readAsk } from '../src/lib/data/ask-reader';
import { nodeEngine } from '../src/lib/data/engine';
import { fetchedBytes, type Fetcher } from '../src/lib/data/fetched-bytes';
import { pageKeeper, type PageKeeper } from '../src/lib/data/page-keeper';
import { daysBetween } from '../src/lib/data/slice';
import type { AskOptions } from '../src/lib/data/slice-shapes';
import { engineExtensionRepository } from '../src/lib/server/config';
import { buildLedger, everyDay, servedFrom, siteCopy } from './support/ledger-lifecycle';

/**
 * Which days does a written question read from a ledger in each lifecycle state?
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