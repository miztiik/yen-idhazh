import { expect, test } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
	causeKey,
	datesIn,
	failedRows,
	failureLedger,
	failureRowKey,
	parseTelemetryCsv,
	type TelemetryRow
} from '../src/lib/charts/series';
import { rank, type Rankable, type RankedDisplay } from '../src/lib/charts/rank';
import type { TimeWindow } from '../src/lib/charts/viewport';

/**
 * A ledger that draws a plausible but wrong ranking is the failure worth a
 * test. Every bar looks right, the biggest cause is still at the top, and the
 * only thing wrong is that the counts do not add up to the rows underneath -
 * which nobody checks by eye over eleven causes and a thousand rows.
 *
 * So the partition is proved rather than assumed: the causes' counts sum to the
 * window's failed rows, and selecting each cause in turn yields row sets with
 * no overlap and no remainder. It is proved over the committed projection
 * rather than over invented rows, because a made-up ledger has whatever shape
 * the test wanted and the real one has eleven causes with a 529-to-1 spread.
 *
 * The interaction is proved twice over, in two places, because the canary
 * fixture deliberately records no failure at all: `build-canary.mjs` writes
 * dropped items as `ok`, since throwing away a page that is not an article is
 * the job. So the browser half here asserts the shapes and the two empty
 * states, and the click-through against real failures is the section-12 smoke
 * against the production build.
 */

const frontend = process.cwd();
const PUBLIC_TELEMETRY = resolve(frontend, 'public', 'telemetry');
const CANARY_TELEMETRY = resolve(frontend, '..', 'backend', 'var', 'canary', 'state', 'telemetry');

function shardRows(root: string): TelemetryRow[] {
	if (!existsSync(root)) return [];
	return readdirSync(root)
		.filter((name) => /^\d{4}-\d{2}\.csv$/.test(name))
		.sort()
		.flatMap((name) => parseTelemetryCsv(readFileSync(join(root, name), 'utf8')));
}

function wholeSpan(rows: TelemetryRow[]): TimeWindow {
	const dates = datesIn(rows);
	return { start: dates[0], end: dates[dates.length - 1] };
}

test.describe('the failure ledger, over the committed projection', () => {
	const rows = shardRows(PUBLIC_TELEMETRY);

	test('the fixture holds enough failures to prove anything', () => {
		// Everything below passes trivially on a ledger with no failures in it.
		// This is the guard that says the corpus can still answer the question.
		expect(rows.length, 'no committed telemetry shard - the read is broken').toBeGreaterThan(0);
		const failed = failedRows(rows, wholeSpan(rows), null);
		expect(failed.length, 'the projection records no failure at all').toBeGreaterThan(0);
		const ledger = failureLedger(rows, wholeSpan(rows));
		expect(ledger.causes.length, 'one cause cannot show a ranking').toBeGreaterThan(1);
	});

	test('the counts sum to the failed rows in the window', () => {
		const window = wholeSpan(rows);
		const ledger = failureLedger(rows, window);
		const failed = failedRows(rows, window, null);

		const summed = ledger.causes.reduce((total, cause) => total + cause.count, 0);
		expect(summed, 'the ledger and the list disagree about how many items failed').toBe(
			failed.length
		);
		expect(ledger.failed).toBe(failed.length);
	});

	test('selecting each cause in turn partitions the list, with no overlap and no remainder', () => {
		const window = wholeSpan(rows);
		const ledger = failureLedger(rows, window);
		const failed = failedRows(rows, window, null);

		// Object identity, not a composed key: two runs write byte-identical rows
		// for one item, and a string key would call that pair an overlap.
		const covered = new Set<TelemetryRow>();
		for (const cause of ledger.causes) {
			const slice = failedRows(rows, window, null, cause.key);
			expect(slice.length, `the ledger's count for ${cause.key} is not its rows`).toBe(
				cause.count
			);
			for (const row of slice) {
				expect(covered.has(row), `a row falls under two causes at ${cause.key}`).toBe(false);
				covered.add(row);
				expect(causeKey(row)).toBe(cause.key);
			}
		}

		expect(covered.size, 'the causes cover fewer rows than the list holds').toBe(failed.length);
		const missed = failed.filter((row) => !covered.has(row));
		expect(missed, 'these failed rows belong to no cause').toEqual([]);
	});

	test('a cause spans no more days than the window, and its trend adds up to its count', () => {
		const window = wholeSpan(rows);
		const ledger = failureLedger(rows, window);
		for (const cause of ledger.causes) {
			const daily = cause.daily.reduce((total, n) => total + n, 0);
			expect(daily, `${cause.key} draws a trend that is not its own count`).toBe(cause.count);
			expect(cause.lastAgo).toBeGreaterThanOrEqual(0);
			expect(cause.last >= window.start && cause.last <= window.end).toBe(true);
		}
	});

	test('breadth is read against the sources the window saw, not against the failures', () => {
		const window = wholeSpan(rows);
		const ledger = failureLedger(rows, window);
		const sources = new Set(
			rows
				.filter((row) => row.date >= window.start && row.date <= window.end)
				.map((row) => row.source_id)
				.filter(Boolean)
		);
		expect(ledger.sourcesSeen).toBe(sources.size);
		// The distinction the column exists for: one source changing its markup
		// and the extractor being broken carry the same count and different
		// breadth, so no cause may claim more sources than the window holds.
		for (const cause of ledger.causes) {
			expect(cause.sources).toBeGreaterThan(0);
			expect(cause.sources).toBeLessThanOrEqual(ledger.sourcesSeen);
		}
	});

	test('the ledger is uncapped, and the cap is the list that draws it', () => {
		const window = wholeSpan(rows);
		const ledger = failureLedger(rows, window);
		const entries: Rankable<RankedDisplay>[] = ledger.causes.map((cause) => ({
			key: cause.key,
			value: cause.count,
			row: { label: cause.code, value: `${cause.count}` }
		}));

		const capped = rank(entries, 3);
		expect(capped.rows.length).toBe(3);
		expect(capped.hidden).toBe(ledger.causes.length - 3);
		// Uncapped at the source, so the sum above cannot quietly become the sum
		// of whatever the display kept.
		expect(capped.hidden + capped.rows.length).toBe(ledger.causes.length);
		expect(capped.rows.map((row) => row.value)).toEqual(
			[...capped.rows.map((row) => row.value)].sort((a, b) => b - a)
		);
	});

	test('every drawn row has a key of its own, under every cause and under none', () => {
		const window = wholeSpan(rows);
		const ledger = failureLedger(rows, window);
		const lists = [
			failedRows(rows, window, null),
			...ledger.causes.map((cause) => failedRows(rows, window, null, cause.key))
		];

		// A repeated key throws inside a keyed each, the update is abandoned
		// part-way, and the rows already on screen stay - so a filter looks like
		// it let foreign causes through. Measured 2026-08-30 against the
		// committed projection before the index was in the key: selecting
		// extract/paywalled left fetch/http_client_error rows in the table.
		for (const list of lists) {
			const keys = new Set(list.map((row, index) => failureRowKey(row, index)));
			expect(keys.size).toBe(list.length);
		}

		// And the reason the index is needed rather than assumed: run and item
		// together do repeat in this ledger.
		const pairs = failedRows(rows, window, null).map((row) => `${row.run_id}-${row.item_id}`);
		expect(new Set(pairs).size, 'run and item are unique here, so read this test again').toBeLessThan(
			pairs.length
		);
	});

	test('a window with no row at all is not a window with no failure', () => {
		const empty = failureLedger(rows, { start: '1999-01-01', end: '1999-01-31' });
		expect(empty.rows).toBe(0);
		expect(empty.causes).toEqual([]);
		expect(empty.failed).toBe(0);
	});
});

test.describe('the failure section on the page', () => {
	test('the ledger sits above the rows it explains', async ({ page }) => {
		await page.goto('/console/');

		const order = await page.evaluate(() => {
			const ledger = document.querySelector('[data-failure-ledger]');
			const rows = document.querySelector('[data-failure-list]');
			if (!ledger || !rows) return null;
			// 4 is DOCUMENT_POSITION_FOLLOWING: the rows come after the ledger.
			return ledger.compareDocumentPosition(rows) & 4 ? 'ledger-first' : 'rows-first';
		});
		expect(order, 'the failure section is missing one of its two halves').toBe('ledger-first');
	});

	test('the two empty states say different things', async ({ page }) => {
		await page.goto('/console/');

		const ledger = page.locator('[data-failure-ledger]');
		await expect(ledger, 'the ledger must be on the page in every state').toHaveCount(1);

		// The canary fixture records no failure, so this is the ledger answering
		// no. A renamed attribute fails here rather than switching the test off.
		const canary = shardRows(CANARY_TELEMETRY);
		const start = await page.locator('[data-viewport-control]').getAttribute('data-window-start');
		const end = await page.locator('[data-viewport-control]').getAttribute('data-window-end');
		expect(start, 'the viewport publishes no window').not.toBeNull();
		const window = { start: start as string, end: end as string };
		const failed = failedRows(canary, window, null).length;

		if (failed === 0) {
			await expect(ledger.locator('[data-ranked="none"]')).toHaveText(
				'No item failed in this window.'
			);
		} else {
			await expect(ledger.locator('[data-ranked="rows"]')).toHaveCount(1);
		}

		// Pan back past every row the fixture holds. Now the ledger cannot answer,
		// and that is a different sentence from answering no.
		const viewport = page.locator('[data-viewport-control]');
		await viewport.focus();
		for (let index = 0; index < 8; index += 1) {
			await page.keyboard.press('ArrowLeft');
		}
		await expect(viewport).toContainText('0 rows in view');
		await expect(ledger.locator('[data-ranked="unmeasured"]')).toHaveText(
			'Nothing was recorded in this window.'
		);
	});

	test('the rows carry the item id without spending a column on it', async ({ page }) => {
		await page.goto('/console/');

		const canary = shardRows(CANARY_TELEMETRY);
		const start = await page.locator('[data-viewport-control]').getAttribute('data-window-start');
		const end = await page.locator('[data-viewport-control]').getAttribute('data-window-end');
		const window = { start: start as string, end: end as string };
		const failed = failedRows(canary, window, null);

		// Both arms assert. Which one runs is decided by the fixture, never by a
		// locator that returns zero because an attribute was renamed.
		if (failed.length === 0) {
			await expect(page.locator('[data-failure-list="empty"]')).toHaveText(
				'No failed item is in this window.'
			);
			return;
		}

		const headers = await page
			.locator('[data-failure-list="rows"] thead th')
			.allTextContents();
		expect(headers.map((text) => text.trim())).toEqual(['Day', 'Source', 'Stage', 'Code']);

		const first = page.locator('[data-failure-list="rows"] tbody tr').first();
		await expect(first).toHaveAttribute('title', failed[0].item_id);
	});
});
