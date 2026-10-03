
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, test } from './support/browser';

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
	expect(html).toContain('connect-src');
	expect(html).toContain('extensions.duckdb.org');
});
