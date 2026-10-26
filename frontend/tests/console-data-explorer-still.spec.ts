import { expect, test } from './support/browser';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { buildFeedLedgers, FEED_LEDGERS } from './support/feed-ledgers';
import { buildLedger } from './support/ledger-lifecycle';
import { ledgerArchiveBaseUrl } from '../src/lib/server/config';
import { parseLedgerCatalog } from '../src/lib/data/ledger-catalog';
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
	const repository = test.info().outputPath('repository');
	const source = join(repository, 'state');
	await buildFeedLedgers(source);
	const registry = JSON.parse(readFileSync(resolve('..', 'config', 'ledgers.json'), 'utf8'));
	mkdirSync(join(repository, 'config'), { recursive: true });
	const registryPath = join(repository, 'config', 'ledgers.json');
	writeFileSync(registryPath, JSON.stringify(registry));
	const origin = ledgerArchiveBaseUrl();
	expect(origin).not.toBe('');
	const requests: string[] = [];
	page.on('request', (request) => requests.push(request.url()));
	await context.route(`${origin}/**`, (route) => {
		const relative = route.request().url().slice(origin.length + 1).split('?')[0];
		if (relative !== 'config/ledgers.json' && !relative.startsWith('state/compact/')) return route.abort('blockedbyclient');
		const file = join(repository, ...relative.split('/'));
		return existsSync(file) ? route.fulfill({ status: 200, body: readFileSync(file) }) : route.fulfill({ status: 404 });
	});
	await page.setViewportSize({ width: 1280, height: 900 });
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(
		page,
		['selected-articles', 'host-fingerprint'],
		'SELECT d.date, count(*) AS rows, max(h.cores) AS cores, ' +
			'max(d.title) AS title FROM "selected-articles" d CROSS JOIN "host-fingerprint" h ' +
			'GROUP BY d.date ORDER BY d.date'
	);
	await expect(page.locator('[data-ledger-name] input[type="checkbox"]')).toHaveCount(0);
	await expect(page.locator('[data-workbench-region="ledgers"]')).not.toContainText('availability not established');
	const statement = await page.locator('#explorer-sql').inputValue();
	await page.locator('[data-ledger-name="published"]').click();
	await expect(page.locator('#explorer-sql')).toHaveValue(statement);
	await expect(page.locator('[data-explorer-columns]')).toContainText('"published"');
	await runExplorer(page);
	await expectAnswer(page, 'table');
	expect(await tableRows(page)).toEqual([
		['2026-10-19', '1', '4', 'Caf\u00e9 \u6771\u4eac'],
		['2026-10-20', '1', '4', 'Caf\u00e9 \u6771\u4eac']
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

	// Only the generated repository changes. The preview server keeps the same compiled site.
	registry.families[0].ledgers.push({
		name: 'runtime-report', prefix: ['feed-ingest-plan', 'runtime-report'], grain: 'raw-and-compact',
		publish_to_data_explorer: true, stem: null, suffix: null
	});

	writeFileSync(registryPath, JSON.stringify(registry));
	await buildLedger(source, {
		ledger: 'runtime-report', catalog: parseLedgerCatalog(registry),
		pinned: '2026-10-22', days: [{ ago: 0, rows: 3 }], columns: { status: 'new packed rows' }
	});
	await page.setViewportSize({ width: 1280, height: 900 });
	await page.getByRole('button', { name: 'Refresh', exact: true }).click();
	await expect(page.locator('[data-ledger-name="runtime-report"]')).toBeVisible();
	await expect(page.locator('[data-explorer-answer]')).toHaveCount(0);
	await expect(page.locator('.history-menu li')).toHaveCount(1);
	await chooseExplorerQuestion(page, ['runtime-report'], 'SELECT status, count(*) AS rows FROM "runtime-report" GROUP BY status');
	await runExplorer(page);
	await expectAnswer(page, 'table');
	expect(await tableRows(page)).toEqual([['new packed rows', '3']]);
	await page.screenshot({ path: test.info().outputPath('compact-workbench.png') });
	expect(requests.filter((url) => /\/state\/raw\/|api\.github\.com|\/contents\//.test(url))).toEqual([]);
	expect(requests.filter((url) => url === `${origin}/config/ledgers.json`)).toHaveLength(2);
});

/** The File API is a distinct boundary: real bytes enter this tab, not a remote source. */
test('local Parquet stays on the page, works without a registry and is forgotten on Refresh', async ({ page, context }) => {
	const origin = ledgerArchiveBaseUrl();
	await context.route(`${origin}/**`, (route) => route.fulfill({ status: 503, body: 'Recorded unavailable registry' }));
	const requests: { url: string; method: string }[] = [];
	page.on('request', (request) => requests.push({ url: request.url(), method: request.method() }));
	await page.clock.setFixedTime(`${PINNED}T12:00:00Z`);
	await page.setViewportSize({ width: 1280, height: 900 });
	await page.goto('/console/data-explorer/');
	await expect(page.getByText('Local files and questions without repository tables still work.', { exact: false })).toBeVisible();
	const picker = page.getByLabel('Import Parquet');
	await picker.setInputFiles(resolve('..', 'tests', 'fixtures', 'parquet', 'local-sales.parquet'));
	await expect(page.locator('[data-explorer-columns]')).toContainText('"local_1"');
	await expect(page.locator('[data-explorer-columns]')).toContainText('units');
	await page.locator('#explorer-sql').fill('SELECT product, units, note FROM "local_1" ORDER BY units');
	await runExplorer(page);
	await expectAnswer(page, 'table');
	expect(await tableRows(page)).toEqual([['tea', '2', '<script>not executable</script>'], ['coffee', '3', 'null']]);
	await expect(page.locator('[data-explorer-answer] script')).toHaveCount(0);
	await page.screenshot({ path: test.info().outputPath('local-workbench.png') });
	await page.getByRole('button', { name: 'Save', exact: true }).click();
	await page.locator('.editor-actions input').fill('Local sales');
	await page.getByRole('button', { name: 'Keep', exact: true }).click();
	await page.getByRole('button', { name: 'Remove local_1' }).click();
	await runExplorer(page);
	await expectAnswer(page, 'refused');
	await expect(page.locator('[data-state="refused"]').first()).toContainText('import its local Parquet file again');
	await picker.setInputFiles(resolve('..', 'tests', 'fixtures', 'parquet', 'local-sales.parquet'));
	await expect(page.getByRole('button', { name: 'Remove local_2' })).toBeVisible();
	await page.getByRole('button', { name: 'Refresh', exact: true }).click();
	await expect(page.getByRole('button', { name: 'Remove local_2' })).toHaveCount(0);
	await expect(page.locator('[data-explorer-answer]')).toHaveCount(0);
	await page.locator('#explorer-sql').fill('SELECT 42 AS answer');
	await runExplorer(page);
	await expectAnswer(page, 'table');
	expect(await tableRows(page)).toEqual([['42']]);
	expect(requests.filter((request) => request.method !== 'GET')).toEqual([]);
	expect(requests.filter((request) => request.url.startsWith(origin) && !request.url.includes('config/ledgers.json'))).toEqual([]);
});
