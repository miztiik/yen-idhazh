
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { connectSources, assetBaseUrl, encoderOrigins, engineOrigins, archiveOrigins } from '../asset-base.js';
import { expect, test } from './support/browser';
import { chooseExplorerQuestion, expectedAsk, EXPLORER_CANARY_DAY, openExplorer, runExplorer, tableRows } from './support/explorer-answer';
import type { LedgerName } from '../src/lib/data/ledger';

const JOIN_LEDGERS = ['published', 'item-health'] as const satisfies readonly LedgerName[];
const JOIN_SQL = 'SELECT \'published x item-health\' AS pair, CAST(count(*) AS VARCHAR) AS rows FROM "published" p, "item-health" h';
const JOIN_FROM = '2026-08-07';

test('THE ORACLE: Records opens as the sixth tab and renders its two panels before a run', async ({ page }) => {
	const response = await page.goto('/console/data-explorer/', { waitUntil: 'domcontentloaded' });
	expect([200, 404]).toContain(response?.status());
	await expect(page.locator('[data-console-route="data-explorer"]')).toHaveCount(1);
	await expect(page.locator('[data-console-tab="data-explorer"]')).toContainText('Records');
	await expect(page.locator('[data-console-panel-id="data-explorer-ask"]')).toHaveCount(1);
	await expect(page.locator('[data-console-panel-id="data-explorer-rows"]')).toHaveCount(1);
	await expect(page.locator('[data-explorer-idle]')).toContainText('Press Run');
	await expect(page.locator('[data-explorer-action-line]')).toContainText('This page holds');
});

test('THE ORACLE: the Records fallback document carries the shipped content policy', () => {
	const html = readFileSync(resolve(process.cwd(), 'build', '404.html'), 'utf8');
	expect(html).toContain('content-security-policy');
	const expected = `connect-src ${connectSources(assetBaseUrl(), [...encoderOrigins(), ...engineOrigins(), ...archiveOrigins()]).map((source) => source === 'self' ? "'self'" : source).join(' ')}`;
	expect(html).toContain(expected);
	expect(html).toContain('extensions.duckdb.org');
});


test('THE ORACLE: a typed join matches the query door and the run cost matches the network', async ({ page }) => {
	await openExplorer(page);
	const columnFetches: string[] = [];
	page.on('response', (response) => {
		const url = response.url();
		const pathname = new URL(url).pathname;
		if (pathname.includes('/state/') && pathname.endsWith('.parquet')) columnFetches.push(pathname);
	});
	await chooseExplorerQuestion(page, JOIN_LEDGERS, JOIN_SQL);
	expect(new Set(columnFetches.map((path) => path.match(/\/state\/(?:compact|raw)\/([^/]+)\//)?.[1]).filter(Boolean))).toEqual(
		new Set(JOIN_LEDGERS)
	);

	const runResponses: Promise<number>[] = [];
	page.on('response', (response) => {
		const url = response.url();
		const pathname = new URL(url).pathname;
		if (!pathname.includes('/state/') || !pathname.endsWith('.parquet')) return;
		runResponses.push(response.body().then((body) => body.byteLength).catch(() => 0));
	});
	await runExplorer(page);
	const expected = await expectedAsk(page, {
		ledgers: JOIN_LEDGERS,
		from: JOIN_FROM,
		to: EXPLORER_CANARY_DAY,
		sql: JOIN_SQL,
		maxChars: 4000,
		maxRows: 1000,
		maxFetchBytes: 64 * 1024 * 1024
	});
	expect(expected).toMatchObject({ state: 'ok' });
	if (expected.state !== 'ok') return;
	expect(await tableRows(page)).toEqual(expected.rows.map((row) => expected.columns.map((column) => String(row[column.name] ?? 'null'))));
	const line = page.locator('[data-explorer-action-line]');
	expect(Number(await line.getAttribute('data-files'))).toBeGreaterThan(0);
	expect(Number(await line.getAttribute('data-bytes'))).toBe((await Promise.all(runResponses)).reduce((sum, bytes) => sum + bytes, 0));
});

test('THE ORACLE: Records does not scroll sideways at phone width', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 900 });
	await openExplorer(page);
	const width = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
	expect(width.scroll).toBeLessThanOrEqual(width.client);
});

test('THE ORACLE: the browser refuses an origin outside connect-src', async ({ page }) => {
	await openExplorer(page);
	const violated = page.evaluate(() => new Promise<string>((resolve) => {
		document.addEventListener('securitypolicyviolation', (event) => resolve(event.violatedDirective), { once: true });
		void fetch('https://example.invalid/x').catch(() => undefined);
	}));
	await expect(violated).resolves.toContain('connect-src');
});


test('THE ORACLE: hostile cell text stays plain in the real table', async ({ page }) => {
	await openExplorer(page);
	await chooseExplorerQuestion(page, ['published'], 'SELECT \'<script>alert(1)</script> https://example.invalid/x\' AS hostile FROM "published" LIMIT 1');
	await runExplorer(page);
	const table = page.locator('[data-explorer-answer]');
	await expect(table).toContainText('<script>alert(1)</script> https://example.invalid/x');
	await expect(table.locator('a, script, img')).toHaveCount(0);
});
