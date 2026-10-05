import { expect, test } from '@playwright/test';
import { createRequire } from 'node:module';
import { readAsk } from '../src/lib/data/ask-reader';
import { nodeEngine } from '../src/lib/data/engine';
import { fetchedBytes, type Fetcher } from '../src/lib/data/fetched-bytes';
import { pageKeeper, type PageKeeper } from '../src/lib/data/page-keeper';
import type { AskOptions } from '../src/lib/data/slice-shapes';
import { engineExtensionRepository } from '../src/lib/server/config';
import { buildLedger, everyDay, servedFrom } from './support/ledger-lifecycle';

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
const parquetAsked = (asked: readonly string[]): string[] => asked.filter((one) => one.endsWith('.parquet'));

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
