/** Real native request epochs, refused preferences and integrated canary smoke. */
import { expect, test } from './support/door-page';
import { hydrated, setWindow } from './support/console-window/controls';
import { FIRST, THROUGH, dayBefore, nativeRow, timedRow, packedPipelines, servePipelines, settled } from './support/pipelines-ledgers';
import { routeConsoles } from '../src/lib/server/config';
import { buildRows, serveToPage } from './support/ledger-lifecycle';
import { shortDate } from '../src/lib/format';
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
	await expect(page.locator('[data-window-status]')).toHaveText('Main packed window: 15 Jun 2030 UTC.');
	await setWindow(page, 90);
	await settled(page);
	await expect(page.locator('[data-window-status]')).toHaveText('Main packed window: 18 Mar 2030 - 15 Jun 2030 UTC.');
});

test('removed visual diagnostics neither mount nor ask for evaluator data', async ({ page }) => {
	await servePipelines(page, root);
	const evaluatorRequests: string[] = [];
	page.on('request', (request) => {
		if (request.url().includes('/state/compact/summary-quality-evals/')) evaluatorRequests.push(new URL(request.url()).pathname.split('/summary-quality-evals/')[1]);
	});
	await page.goto('/console/');
	await hydrated(page);
	await settled(page);
	for (const id of ['pipeline-funnel', 'downgrade-funnel', 'extraction', 'visual-written-types']) {
		await expect(page.locator(`[data-console-panel-id="${id}"]`)).toHaveCount(0);
		await expect(page.locator(`[id="${id}"], a[href$="#${id}"]`)).toHaveCount(0);
	}
	await expect(page.getByRole('heading', { name: 'Planned and successfully written visual types', exact: true })).toHaveCount(0);
	await expect(page.locator('[data-visual-attempt-view="written"]')).toHaveCount(0);
	for (const id of ['chart-drawing', 'visual-refusals']) {
		await expect(page.locator(`[data-console-panel-id="${id}"]`)).toHaveCount(1);
	}
	expect(evaluatorRequests.sort()).toEqual(['index/daily.json', 'index/monthly.json', 'index/yearly.json']);
});

test('the run-wide article ranking keeps lagging host/count evidence separate from the current timeline', async ({ page }) => {
	const older = dayBefore(THROUGH, 1);
	const state = await packedPipelines('ranking-endpoint', [
		{ covers: older, rows: [
			timedRow(older, { item_id: 'older-short', machine_shard: 0 }),
			timedRow(older, { item_id: 'older-long', machine_shard: 1, item_total_ms: 1600, stage_gap_ms: 850 })
		] },
		{ covers: THROUGH, rows: [timedRow(THROUGH, {
			item_id: 'latest-clock', machine_shard: 0,
			item_started_at: `${THROUGH}T00:00:00Z`, item_ended_at: `${THROUGH}T00:00:02Z`
		})] }
	]);
	await buildRows(state, 'host-fingerprint', [{ covers: older, rows: [{ date: older, run_id: `${older}-1`, job: 'work', shard: 0 }] }]);
	await buildRows(state, 'run-shards', [{ covers: older, rows: [{ date: older, run_id: `${older}-1`, shards: 2 }] }]);
	await servePipelines(page, state);
	await serveToPage(page.context(), state, 'host-fingerprint');
	await serveToPage(page.context(), state, 'run-shards');
	await page.goto('/console/');
	await hydrated(page);
	await settled(page);
	await expect(page.locator('[data-run-timeline]')).toHaveAttribute('data-run-timeline', `${THROUGH}-1`);
	const ranking = page.locator('[data-console-panel-id="slowest-articles"]');
	await expect(ranking).toHaveCount(1);
	await expect(ranking.locator('[data-slowest-run]')).toHaveAttribute('data-slowest-run', `${older}-1`);
	await expect(ranking.locator('[data-native-window]')).toContainText(`${older} through ${older} UTC`);
	await expect(page.locator('[data-console-panel-id="stage-timings"] [data-native-window]'))
		.toHaveText(`Native record: ${older} through ${THROUGH} UTC.`);
	await expect(ranking.locator('[data-ranked-row]').first()).toContainText('older-long');
	await expect(ranking).not.toContainText('latest-clock');
});

test('integrated actual canary smoke: narrow viewport, with cross-page navigation', async ({ page }) => {
	const errors: string[] = [];
	const missing: string[] = [];
	page.on('pageerror', (error) => errors.push(String(error)));
	page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
	page.on('response', (response) => { if (response.status() === 404) missing.push(response.url()); });
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/console/');
	await hydrated(page);
	await settled(page);
	const panelCount = routeConsoles().pipelines.panel_groups.reduce((total, group) => total + group.panels.length, 0);
	await expect(page.locator('[data-console-panel]')).toHaveCount(panelCount);
	await expect(page.locator('[data-console-panels="pipelines"]')).toHaveAttribute('data-route-state', 'ok');
	await expect(page.locator('[data-console-panels="pipelines"]')).not.toContainText('NaN');
	await expect(page.locator('[data-contract-blocked]')).toHaveCount(0);
	await expect(page.locator('[data-console-band], [data-console-route-issue], [data-console-carry]')).toHaveCount(0);
	await expect(page.locator('[data-console-data-dates]')).not.toHaveAttribute('open', '');
	const totals = await page.locator('[data-published-total]').evaluateAll((nodes) =>
		nodes.map((node) => Number(node.getAttribute('data-published-total'))));
	for (const width of [1440, 390]) {
		await page.setViewportSize({ width, height: 900 });
		await expect.poll(async () => page.locator('[data-published-measure="articles"]').evaluate((node) =>
			Math.abs(Number(node.getAttribute('width')) - node.getBoundingClientRect().width) < 1)).toBe(true);
		const axes = await page.locator('[data-chart="published-counts"]').evaluateAll((nodes) => nodes.map((node) => {
			const svg = node.getBoundingClientRect();
			const bars = [...node.querySelectorAll('rect')];
			const labels = [...node.querySelectorAll('[data-day-axis]')];
			return {
				dates: labels.map((label) => label.getAttribute('data-day-axis')),
				ends: [bars[0], bars.at(-1)!].map((bar) => bar.getAttribute('data-published-bar')),
				aligned: labels.every((label) => {
					const bar = bars.find((bar) => bar.getAttribute('data-published-bar') === label.getAttribute('data-day-axis'))!;
					return Math.abs(Number(label.getAttribute('x')) -
						(Number(bar.getAttribute('x')) + Number(bar.getAttribute('width')) / 2)) < 0.001;
				}),
				fitted: labels.every((label, index) => {
					const box = label.getBoundingClientRect();
					return box.left >= svg.left && box.right <= svg.right && box.bottom <= svg.bottom &&
						(index === 0 || box.left > labels[index - 1].getBoundingClientRect().right);
				}),
				sum: bars.reduce((sum, bar) => sum + Number(bar.getAttribute('data-published')), 0),
				total: Number(node.getAttribute('data-published-total'))
			};
		}));
		for (const axis of axes) {
			expect(axis.dates.length).toBeGreaterThan(1);
			expect([axis.dates[0], axis.dates.at(-1)]).toEqual(axis.ends);
			expect(axis.aligned).toBe(true);
			expect(axis.fitted).toBe(true);
			expect(axis.sum).toBe(axis.total);
		}
	}
	for (const [index, measure] of ['articles', 'visuals'].entries()) {
		const plot = page.locator(`[data-published-measure="${measure}"]`);
		const strip = page.locator(`[data-readout="published-${measure}"]`);
		await expect(page.locator(`[data-kpi="${measure === 'articles' ? 'Articles' : 'Visuals'} published"] [data-kpi-note]`)).toHaveCount(0);
		await plot.press('Home');
		await expect(strip.locator('[data-readout-day]')).toHaveText(shortDate((await plot.locator('rect').first().getAttribute('data-published-bar'))!));
		await expect(strip.locator('.readout-value')).toHaveText('0');
		await plot.press('End');
		await expect(strip.locator('.readout-value')).toHaveText(String(totals[index]));
		const newest = await plot.locator('rect').last().boundingBox();
		if (!newest) throw new Error('The measured published-day bar must be visible.');
		await page.mouse.move(newest.x + newest.width / 2, newest.y + newest.height / 2);
		await expect(page.locator(`[data-chart-tooltip="published-${measure}"] dd`)).toHaveText(String(totals[index]));
		await plot.dispatchEvent('pointerdown', { pointerType: 'touch', clientX: newest.x + newest.width / 2, clientY: newest.y });
		await plot.dispatchEvent('pointerleave', { pointerType: 'touch' });
		await expect(strip.locator('.readout-value')).toHaveText(String(totals[index]));
	}
	await setWindow(page, 1);
	await settled(page);
	for (const measure of ['articles', 'visuals']) {
		const plot = page.locator(`[data-published-measure="${measure}"]`);
		const date = await plot.locator('rect').getAttribute('data-published-bar');
		await expect(plot.locator('[data-day-axis]')).toHaveCount(1);
		await expect(plot.locator('[data-day-axis]')).toHaveAttribute('data-day-axis', date!);
		await expect(plot.locator('[data-day-axis]')).toHaveText(shortDate(date!));
	}
	const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
	expect(overflow, 'the route overflows its real viewport').toBe(false);
	await page.locator('[data-console-rail] > details > summary').click();
	await page.locator('[data-console-tab="model"]').click();
	await expect(page.locator('[data-console-route="model"]')).toBeVisible();
	await expect(page.locator('[data-console-band], [data-console-route-issue], [data-console-carry]')).toHaveCount(0);
	await page.goBack();
	await settled(page);
	await expect(page.locator('[data-console-panels="pipelines"]')).toBeVisible();
	expect(errors).toEqual([]);
	expect(missing).toEqual([]);
});
