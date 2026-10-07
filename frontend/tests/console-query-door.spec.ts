/** The Hardware panel queries the real worker, keeps whole files and draws each read outcome. */
import { expect, test } from './support/browser';
import { machineRecordState, type MachineRecordState } from './support/machine-record-state';

const PANEL = '[data-windowed="machine-fleet"]';

for (const state of ['loading', 'missing', 'quiet', 'unreachable'] as const satisfies readonly MachineRecordState[]) {
	test(`the machine panel draws ${state} from the real index boundary`, async ({ page }) => {
		await machineRecordState(page, state);
		await page.goto('/console/machine/');
		const panel = page.locator(PANEL);
		await expect(panel).toHaveAttribute('data-fleet-state', state);
		if (state === 'loading') {
			await expect(panel.locator('[data-panel-state="loading"]')).toBeVisible();
			await expect(panel.locator('[data-readout]')).toHaveCount(0);
		} else {
			await expect(panel.locator(`[data-empty-state="${state}"]`)).toBeVisible();
			await expect(panel.locator('.empty-sentence')).not.toBeEmpty();
		}
	});
}

test('the machine panel says a published record with no compact folder is not packed yet, never unpublished', async ({ page }) => {
	// The site copy stages nothing for such a record, so its index requests are answered 404.
	await machineRecordState(page, 'missing');
	await page.goto('/console/machine/');
	const panel = page.locator(PANEL);
	await expect(panel).toHaveAttribute('data-fleet-state', 'missing');
	await expect(panel.locator('[data-empty-state="missing"] .empty-sentence')).toHaveText('The machine record is not packed yet.');
	await expect(panel).not.toContainText(/published/i);
});

test('thirty days then seven query the real worker and fetch each whole file once', async ({ page, context, parquet }) => {
	const document = await page.request.get('/console/machine/').then((response) => response.text());
	expect(document).toContain('data-readout-fetched="host-fingerprint"');
	expect(document).not.toContain('data-readout="machine-fleet"');
	const fetched: string[] = [];
	const addons: string[] = [];
	context.on('request', (request) => {
		if (/\/state\/compact\/host-fingerprint\/(daily|monthly)\/.+\.parquet/.test(request.url())) fetched.push(request.url());
		if (request.url() === parquet.addon.url) addons.push(request.url());
	});
	await page.addInitScript(() => localStorage.setItem('idhazh:console-window', '30'));
	await page.goto('/console/machine/');
	const panel = page.locator(PANEL);
	await expect(panel).toHaveAttribute('data-fleet-state', 'ready');
	await expect(panel.locator('[data-readout="machine-fleet"]')).toHaveCount(1);
	await expect(panel.locator('[data-fleet-placements]')).toHaveAttribute('data-fleet-placements', /^[1-9]\d*$/);
	const firstCount = fetched.length;
	expect(firstCount).toBeGreaterThan(0);
	const firstThrough = await panel.getAttribute('data-fleet-through');
	await page.locator('[data-window-preset="7"]').click();
	await expect(panel).toHaveAttribute('data-window-days', '7');
	await expect(panel).toHaveAttribute('data-fleet-state', 'ready');
	expect(await panel.getAttribute('data-fleet-through')).toBe(firstThrough);
	expect(fetched).toHaveLength(firstCount);
	expect(new Set(fetched).size).toBe(fetched.length);
	expect(addons).toHaveLength(1);
	expect(page.workers().some((worker) => worker.url().startsWith('blob:'))).toBe(true);
});

test('the real query worker loads its cached add-on and obeys the page connection policy', async ({ page, context }) => {
	const forbidden: string[] = [];
	await context.route('https://blocked.invalid/**', async (route) => {
		forbidden.push(route.request().url());
		await route.abort();
	});
	await page.goto('/console/machine/');
	await expect(page.locator(PANEL)).toHaveAttribute('data-fleet-state', 'ready');
	const worker = page.workers().find((entry) => entry.url().startsWith('blob:'));
	expect(worker, 'the real query engine has a dedicated blob worker').toBeDefined();
	if (!worker) throw new Error('No query worker');
	const refused = await worker.evaluate(async () => {
		try {
			await fetch('https://blocked.invalid/query-worker-policy');
			return false;
		} catch {
			return true;
		}
	});
	expect(refused).toBe(true);
	expect(forbidden, 'CSP must refuse the request before it reaches the network route').toEqual([]);
});

test.describe('the production service worker', () => {
	test.use({ serviceWorkers: 'allow' });
	test('sees the real query worker requests', async ({ page, context, parquet }) => {
		await page.goto('/console/machine/');
		await expect(page.locator(PANEL)).toHaveAttribute('data-fleet-state', 'ready');
		await page.evaluate(async () => { await navigator.serviceWorker.ready; });
		await expect.poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null)).toBe(true);
		const serviceWorker = context.serviceWorkers()[0];
		expect(serviceWorker, 'the built site must install its real service worker').toBeDefined();
		await serviceWorker.evaluate(() => {
			const scope = globalThis as typeof globalThis & { observedWorkerRequests: string[] };
			scope.observedWorkerRequests = [];
			globalThis.addEventListener('fetch', (event) => {
				const request = (event as Event & { request: { url: string } }).request;
				scope.observedWorkerRequests.push(request.url);
			});
		});
		await page.reload();
		await expect(page.locator(PANEL)).toHaveAttribute('data-fleet-state', 'ready');
		const controlled = await page.evaluate(() => navigator.serviceWorker.controller?.scriptURL ?? null);
		const observed = await serviceWorker.evaluate(() =>
			(globalThis as typeof globalThis & { observedWorkerRequests: string[] }).observedWorkerRequests
		);
		expect(controlled).toBe(serviceWorker.url());
		expect(page.workers().some((worker) => worker.url().startsWith('blob:'))).toBe(true);
		expect(observed.filter((url) => url === parquet.addon.url),
			'the production service worker must see the real query worker add-on request; do not substitute a proxy').toHaveLength(1);
		console.log(JSON.stringify({ productionServiceWorker: serviceWorker.url(), engineRequests: observed.filter((url) => /duckdb/.test(url)) }));
	});
});