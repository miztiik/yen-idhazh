/** Real native request epochs, refused preferences and integrated canary smoke. */
import { expect, test } from './support/door-page';
import { hydrated, setWindow } from './support/console-window/controls';
import { FIRST, THROUGH, dayBefore, nativeRow, timedRow, packedPipelines, servePipelines, settled } from './support/pipelines-ledgers';
let root: string;
test.beforeAll(async () => {
	const days = Math.round((Date.parse(`${THROUGH}T00:00:00Z`) - Date.parse(`${FIRST}T00:00:00Z`)) / 86_400_000);
	const dates = Array.from({ length: days + 1 }, (_, index) => dayBefore(THROUGH, days - index));
	root = await packedPipelines('lifecycle', [
		...dates.map((date) => ({ covers: date, rows: date < dayBefore(THROUGH, 7) ? [] : [timedRow(date, {
			url_key: `url-${date}`, element_class: 'narrative', elements_found: 0, span_integrity: true
		}), nativeRow(date, { item_id: 'failed', url_key: `failed-${date}`, stage: 'fetch',
			outcome: 'failed', code: 'timeout', failed_rule: 'timeout' })] }))
	], dates.map((date) => ({ covers: date, rows: date < dayBefore(THROUGH, 7) ? [] : [{ date, url_key: `url-${date}`, extraction_suspect: false }] })));
});

test('denied window preferences and session storage do not prevent native loads', async ({ page }) => {
	await servePipelines(page, root);
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(String(error)));
	await page.addInitScript(() => {
		const get = Storage.prototype.getItem;
		const set = Storage.prototype.setItem;
		Storage.prototype.getItem = function (key) {
			if (key === 'idhazh:console-window') throw new DOMException('Preference denied', 'SecurityError');
			return get.call(this, key);
		};
		Storage.prototype.setItem = function (key, value) {
			if (key === 'idhazh:console-window') throw new DOMException('Preference denied', 'SecurityError');
			return set.call(this, key, value);
		};
		Object.defineProperty(window, 'sessionStorage', {
			configurable: true, get() { throw new DOMException('Session denied', 'SecurityError'); }
		});
	});
	await page.goto('/console/');
	await hydrated(page);
	await settled(page);
	await setWindow(page, 7);
	await settled(page);
	await expect(page.locator('[data-duration-cohort]')).toContainText('7 of 14 recorded item clocks');
	await expect(page.locator('[data-console-panel="What one more article costs"]')).toBeVisible();
	expect(errors).toEqual([]);
});

test('a late wide response cannot replace a short request or fabricate a short record', async ({ page }) => {
	await servePipelines(page, root);
	await page.addInitScript(() => localStorage.setItem('idhazh:console-window', '1'));
	let release!: () => void;
	const held = new Promise<void>((resolve) => release = resolve);
	let requested = false;
	const older = dayBefore(THROUGH, 6).replaceAll('-', '/');
	await page.route((url) => url.pathname.endsWith(`/state/compact/item-health/daily/${older}.parquet`), async (route) => {
		requested = true;
		await held;
		await route.fallback();
	});
	await page.goto('/console/');
	await hydrated(page);
	await settled(page);
	await setWindow(page, 7);
	await expect.poll(() => requested).toBe(true);
	await setWindow(page, 1);
	await settled(page);
	const arrived = page.waitForResponse((response) => response.url().includes(`${older}.parquet`));
	release();
	await arrived;
	await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
	await expect(page.locator('[data-duration-cohort]')).toContainText('1 of 2 recorded item clocks');
	await expect(page.locator('[data-window-status]')).toHaveText('Showing 1 day, to 15 Jun 2030.');
	await setWindow(page, 90);
	await settled(page);
	await expect(page.locator('[data-window-status]')).toHaveText('Showing 90 days, to 15 Jun 2030.');
});

test('an evaluator still in flight does not hide the loaded extractor or invent a quiet check', async ({ page }) => {
	await servePipelines(page, root);
	let release!: () => void;
	const held = new Promise<void>((resolve) => release = resolve);
	await page.route((url) => url.pathname.endsWith(`/state/compact/summary-quality-evals/daily/${THROUGH.replaceAll('-', '/')}.parquet`), async (route) => {
		await held;
		await route.fallback();
	});
	const panel = page.locator('[data-eval-panel="extraction"]');
	try {
		await page.goto('/console/');
		await expect(panel.locator('[data-extraction-source="native"]')).toHaveAttribute('data-panel-state', 'ready');
		await expect(panel.locator('[data-reserved="extraction-suspect"]')).toHaveAttribute('data-panel-state', 'loading');
		await expect(panel.locator('[data-nothing-fired]')).toHaveCount(0);
		await expect(panel).toContainText('narrative');
	} finally {
		release();
	}
	await settled(page);
	await expect(panel.locator('[data-extraction-source="flags"]')).toHaveAttribute('data-panel-state', 'ready');
	await expect(panel.locator('[data-nothing-fired]')).toHaveText(
		'No recorded extraction flag is true in these days. This does not establish that the extraction checker ran.');
	await expect(panel).toContainText('of 8 distinct recorded articles; 0 have no boolean flag');
});

for (const width of [390, 768, 1440]) {
	for (const theme of ['dark', 'light']) {
		test(`integrated actual canary smoke: ${width}px ${theme}, with cross-page navigation`, async ({ page }) => {
			const errors: string[] = [];
			const missing: string[] = [];
			page.on('pageerror', (error) => errors.push(String(error)));
			page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
			page.on('response', (response) => { if (response.status() === 404) missing.push(response.url()); });
			await page.setViewportSize({ width, height: 900 });
			await page.addInitScript((theme) => localStorage.setItem('idhazh:theme', theme), theme);
			await page.goto('/console/');
			await hydrated(page);
			await settled(page);
			await expect(page.locator('[data-console-panel]')).toHaveCount(12);
			await expect(page.locator('[data-console-panels="pipelines"]')).toHaveAttribute('data-route-state', 'ok');
			await expect(page.locator('[data-console-panels="pipelines"]')).not.toContainText('NaN');
			await expect(page.locator('[data-contract-blocked]')).toHaveCount(0);
			const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
			expect(overflow, 'the route overflows its real viewport').toBe(false);
			await page.locator('[data-console-carry="model"] a').click();
			await expect(page.locator('[data-console-route="model"]')).toBeVisible();
			await page.goBack();
			await settled(page);
			await expect(page.locator('[data-console-panels="pipelines"]')).toBeVisible();
			expect(errors).toEqual([]);
			expect(missing).toEqual([]);
		});
	}
}
