/** One shipped Hardware journey and its independent native transport/publication boundaries. */
import { expect, test, type Page } from './support/browser';

const PANELS = [
	'two-clocks', 'processor-lost', 'disk-reads', 'machine-cards', 'slower-machines',
	'platform-mix', 'slowest-articles', 'tail-trend', 'closest-to-memory', 'memory-held',
	'context-headroom', 'article-cost', 'prompt-reuse', 'read-against-written', 'counterfactual-cost'
];
const NATIVE = /\/state\/(?:compact|raw)\/(?:item-health|host-fingerprint|run-shards)\//;

async function settled(page: Page): Promise<void> {
	await expect(page.locator('[data-console-panels="machine"]')).toHaveAttribute('data-route-state', 'ok');
}

test('Hardware reads native files, opens a dated answer and carries its window across a real tab', async ({ page }) => {
	const arrived: string[] = [];
	const privateRequests: string[] = [];
	const errors: string[] = [];
	page.on('response', (response) => {
		if (NATIVE.test(response.url()) && response.status() === 200) arrived.push(response.url());
	});
	page.on('request', (request) => {
		if (/\/(?:run|plan)\.json|\/state\/.*(?:run-plan|prompt)/.test(request.url())) privateRequests.push(request.url());
	});
	page.on('pageerror', (error) => errors.push(error.message));
	await page.goto('/console/machine/');
	await settled(page);
	expect(await page.locator('[data-console-panel-id]').evaluateAll((nodes) =>
		nodes.map((node) => node.getAttribute('data-console-panel-id')))).toEqual(PANELS);
	await expect(page.locator('[data-console-panel-id] > header > h3')).toHaveCount(15);
	for (const ledger of ['item-health', 'host-fingerprint', 'run-shards']) {
		expect(arrived.some((url) => url.includes(`/${ledger}/index/`)), `${ledger} index arrived`).toBe(true);
		expect(arrived.some((url) => url.includes(`/${ledger}/`) && new URL(url).pathname.endsWith('.parquet')),
			`${ledger} native rows arrived`).toBe(true);
	}
	expect(await page.locator('[data-clock-pair]').count(), 'the independent clocks arrived').toBeGreaterThan(0);
	const fleet = page.locator('[data-fleet-shape]');
	await expect(fleet).toHaveCount(1);
	expect(Number(await fleet.getAttribute('data-fleet-placements'))).toBeGreaterThan(0);
	const tokens = page.locator('[data-console-panel-id="read-against-written"]');
	const plot = tokens.locator('[data-chart-type="dateSeries"]');
	await expect(plot).toBeVisible();
	await plot.focus();
	await page.keyboard.press('ArrowLeft');
	await page.keyboard.press('Escape');
	await expect(tokens.locator('[data-readout]')).toContainText('Read tokens');
	await expect(tokens.locator('[data-readout]')).toContainText('Written tokens');
	await expect(tokens.locator('[data-readout]')).toContainText('20 Aug 2026');
	await expect(tokens.locator('[data-readout]')).not.toContainText('Not recorded');

	await page.locator('[data-window-preset="7"]').click();
	await settled(page);
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '7');
	await page.locator('[data-console-tab="pipelines"]').click();
	await expect(page.locator('[data-console-panels="pipelines"]')).toBeVisible();
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '7');
	await page.locator('[data-console-tab="machine"]').click();
	await settled(page);
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '7');
	await expect(page).toHaveTitle(/Hardware/);
	expect(privateRequests).toEqual([]);
	expect(errors).toEqual([]);
});

test('a failed host index alone is retried while successful article and count files stay held', async ({ page }) => {
	const successfulRequests: string[] = [];
	page.on('request', (request) => {
		if (/\/state\/(?:compact|raw)\/(?:item-health|run-shards)\//.test(request.url())) {
			successfulRequests.push(request.url());
		}
	});
	await page.route(/\/state\/compact\/host-fingerprint\/index\/[^/]+\.json/,
		(route) => route.abort('failed'));
	await page.goto('/console/machine/');
	await expect(page.locator('[data-console-panels="machine"]')).toHaveAttribute('data-route-state', 'unreachable');
	await expect(page.locator('[data-panel-query="memory-held"]')).toHaveAttribute('data-machine-panel-state', 'ok');
	await expect(page.locator('[data-console-retry]')).toBeVisible();
	const before = [...successfulRequests];
	expect(before.some((url) => url.includes('/run-shards/') && new URL(url).pathname.endsWith('.parquet'))).toBe(true);
	expect(before.some((url) => url.includes('/item-health/') && new URL(url).pathname.endsWith('.parquet'))).toBe(true);
	await page.unroute(/\/state\/compact\/host-fingerprint\/index\/[^/]+\.json/);
	await page.locator('[data-console-retry]').click();
	await settled(page);
	expect(await page.locator('[data-clock-pair]').count()).toBeGreaterThan(0);
	expect(successfulRequests).toEqual(before);
	await expect(page.locator('[data-console-retry]')).toHaveCount(0);
});

test('unpublished native indexes keep a named absence, not a lost record or invented drawing', async ({ page }) => {
	await page.route(/\/state\/compact\/(?:host-fingerprint|item-health|run-shards)\/index\/[^/]+\.json/,
		(route) => route.fulfill({ status: 404, body: '' }));
	await page.goto('/console/machine/');
	await expect(page.locator('[data-console-panels="machine"]')).toHaveAttribute('data-route-state', 'missing');
	await expect(page.locator('[data-panel-query][data-machine-panel-state="missing"]')).toHaveCount(15);
	await expect(page.locator('[data-panel-query="two-clocks"]')).toContainText('Not published yet.');
	await expect(page.locator('[data-clock-pair], [data-machine-refused], [data-recording="machine-destroyed"]')).toHaveCount(0);
	await expect(page.locator('[data-console-retry]')).toHaveCount(0);
});

test('actual prerendered Hardware contains words and reserved frames, never ledger values', async ({ browser }) => {
	const context = await browser.newContext({ javaScriptEnabled: false });
	try {
		const page = await context.newPage();
		const response = await page.goto('/console/machine/');
		expect(response?.status()).toBe(200);
		await expect(page.locator('[data-console-panel-id]')).toHaveCount(15);
		await expect(page.locator('[data-console-panel-id] > header > h3')).toHaveCount(15);
		await expect(page.locator('[data-panel-query][data-machine-panel-state="loading"]')).toHaveCount(15);
		await expect(page.locator('[data-panel-query] svg')).toHaveCount(15);
		await expect(page.locator('[data-panel-query] svg rect:not([data-reserved-ground]), [data-panel-query] svg path')).toHaveCount(0);
		await expect(page.locator('[data-console-standing]')).toHaveText('');
		await expect(page.locator('[data-machine-refused], [data-cost-figures], [data-clock-pair], [data-fleet-job]')).toHaveCount(0);
		const html = await response!.text();
		expect(html).not.toMatch(/machineCounters:|machineRuns:|runShards:|RunManifest|RunPlan/);
	} finally {
		await context.close();
	}
});
