import { expect, test } from './support/browser';
import {
	chooseExplorerQuestion,
	expectAnswer,
	openExplorer,
	runExplorer,
	serveBuilt,
	tableRows
} from './support/explorer-answer';

const PINNED = '2030-06-15';

/** One real query and chart interaction cover the workbench, not every chart transition. */
test('a reader loads real ledgers, queries them, and draws the answer', async ({ page, context }) => {
	await serveBuilt(
		context,
		test.info().outputPath('state'),
		{ ledger: 'published', pinned: PINNED, days: [{ ago: 1, rows: 1 }, { ago: 0, rows: 2 }] },
		{ ledger: 'item-health', pinned: PINNED, days: [{ ago: 0, rows: 2 }] }
	);
	await page.setViewportSize({ width: 1280, height: 900 });
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(
		page,
		['published', 'item-health'],
		'SELECT p.date, count(*) AS rows, count(DISTINCT p.date) AS days ' +
			'FROM "published" p, "item-health" h GROUP BY p.date ORDER BY p.date'
	);
	await runExplorer(page);
	await expectAnswer(page, 'table');
	expect(await tableRows(page)).toEqual([
		['2030-06-14', '2', '1'],
		['2030-06-15', '4', '1']
	]);

	await page.getByRole('tab', { name: 'Chart' }).click();
	await page.locator('[data-shape-choice="partsOfOne"]').click();
	await expect(page.locator('[data-shape-choice="partsOfOne"] input')).toBeChecked();
	const chart = page.locator('[data-chart-type="partsOfOne"][data-chart-name="data-explorer-shape"]');
	await expect(chart).toBeVisible();
	await expect(chart.getByLabel('rows: 4', { exact: true })).toBeVisible();
	await chart.getByRole('list').focus();
	await page.keyboard.press('ArrowDown');
	await expect(page.locator('[data-readout="data-explorer-shape"]')).toContainText('2030-06-15');
	await page.setViewportSize({ width: 390, height: 844 });
	await expect(chart).toBeVisible();
	await expect.poll(() => page.evaluate(
		() => document.documentElement.scrollWidth <= document.documentElement.clientWidth
	)).toBe(true);
});
