import { expect, test } from './support/browser';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { buildFeedLedgers, FEED_LEDGERS, stageFeedLedgers } from './support/feed-ledgers';
import {
	chooseExplorerQuestion,
	expectAnswer,
	openExplorer,
	runExplorer,
	tableRows
} from './support/explorer-answer';

const PINNED = '2026-10-23';

/** One real query and chart interaction cover the workbench, not every chart transition. */
test('a reader loads real ledgers, queries them, and draws the answer', async ({ page, context }) => {
	const source = test.info().outputPath('source');
	const staticRoot = test.info().outputPath('static');
	const site = join(staticRoot, 'state');
	await buildFeedLedgers(source);
	const copy = stageFeedLedgers(source, site);
	await context.addInitScript(() => Object.defineProperty(
		globalThis, '__RAW_LISTED_THROUGH__', { value: {}, configurable: true }
	));
	await context.route(/\/state\/(?:raw|compact)\//, (route) => {
		const url = new URL(route.request().url());
		const file = url.pathname.slice(url.pathname.indexOf('/state/') + '/state/'.length);
		if (!copy.files.includes(file)) return route.fulfill({ status: 404 });
		return route.fulfill({ status: 200, body: readFileSync(join(site, ...file.split('/'))) });
	});
	await page.setViewportSize({ width: 1280, height: 900 });
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(
		page,
		['dispatches', 'host-fingerprint'],
		'SELECT d.covers AS date, count(*) AS rows, max(h.cores) AS cores, ' +
			'max(d.content.article_text) AS text FROM dispatches d CROSS JOIN "host-fingerprint" h ' +
			'GROUP BY d.covers ORDER BY d.covers'
	);
	await runExplorer(page);
	await expectAnswer(page, 'table');
	expect(await tableRows(page)).toEqual([
		['2026-10-19', '1', '4', 'An article contains this recorded text.'],
		['2026-10-20', '1', '4', 'An article contains this recorded text.']
	]);
	for (const ledger of FEED_LEDGERS) {
		await expect(page.locator(`[data-ledger-name="${ledger}"]`)).toBeVisible();
	}

	await page.getByRole('tab', { name: 'Chart' }).click();
	await page.locator('[data-shape-choice="partsOfOne"]').click();
	await expect(page.locator('[data-shape-choice="partsOfOne"] input')).toBeChecked();
	const chart = page.locator('[data-chart-type="partsOfOne"][data-chart-name="data-explorer-shape"]');
	await expect(chart).toBeVisible();
	await expect(chart.getByLabel('rows: 1', { exact: true }).first()).toBeVisible();
	await chart.getByRole('list').focus();
	await page.keyboard.press('ArrowDown');
	await expect(page.locator('[data-readout="data-explorer-shape"]')).toContainText('2026-10-20');
	await page.setViewportSize({ width: 390, height: 844 });
	await expect(chart).toBeVisible();
	await expect.poll(() => page.evaluate(
		() => document.documentElement.scrollWidth <= document.documentElement.clientWidth
	)).toBe(true);
});
