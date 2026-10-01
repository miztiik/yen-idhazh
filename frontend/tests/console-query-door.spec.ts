/** The Hardware panel queries the real worker, keeps whole files and draws each read outcome. */
import { expect, test } from './support/browser';
import { machineRecordState, type MachineRecordState } from './support/machine-record-state';

const PANEL = '[data-windowed="machine-fleet"]';
const INDEX = '/state/compact/host-fingerprint/index/';

for (const state of ['loading', 'missing', 'quiet', 'unreachable'] as const satisfies readonly MachineRecordState[]) {
	test(`the machine panel draws ${state} from the real index boundary`, async ({ page }) => {
		await machineRecordState(page, state);
		await page.goto('/console/machine/');
		const panel = page.locator(PANEL);
		await expect(panel).toHaveAttribute('data-fleet-state', state);
		if (state === 'loading') {
			await expect(panel.locator('[data-panel-state="loading"]')).toBeVisible();
		} else {
			await expect(panel.locator(`[data-empty-state="${state}"]`)).toBeVisible();
			await expect(panel.locator('.empty-sentence')).not.toBeEmpty();
		}
	});
}

test('thirty days then seven query the real worker and fetch each whole file once', async ({ page, context, parquet }) => {
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
	test('sees the real query worker requests', async ({ page, context }) => {
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
		const observed = await serviceWorker.evaluate(() =>
			(globalThis as typeof globalThis & { observedWorkerRequests: string[] }).observedWorkerRequests
		);
		expect(observed.some((url) => url.includes(INDEX))).toBe(true);
		expect(observed.some((url) => /duckdb.*\.wasm(?:\?|$)/.test(url)),
			'the production service worker must see the dedicated query worker wasm request; do not substitute a proxy').toBe(true);
		console.log(JSON.stringify({ productionServiceWorker: serviceWorker.url(), engineRequests: observed.filter((url) => /duckdb/.test(url)) }));
	});
});