import { expect, test, type Page } from './support/door-page';
import { openRetained } from './support/retained-telemetry';
import { telemetryRow } from './support/telemetry-row';
import { presets, setWindow, windowed } from './support/console-window/controls';
import { spanSaid, ONE_DAYS } from './support/pipelines-span';
import { BY_ROUTE } from './support/console-expect/console-window';
import { runHealthGrid } from '../src/lib/console/pipelines/run-health';

test('retained timing columns span the selected calendar, not the lone measured day', async ({ page }) => {
	await openRetained(page, (window) => [
		telemetryRow({ date: window.end, fetch_ms: 300, extract_ms: 40, summarize_ms: 1000 })
	]);
	const plot = page.locator('[data-timing="plot"]');
	await expect(page.locator('[data-window-control] input').first()).toBeEnabled();
	for (const preset of presets()) {
		await setWindow(page, preset);
		await expect(plot).toHaveAttribute('data-timing-days', String(preset));
		const first = await plot.getAttribute('data-timing-first');
		const last = await plot.getAttribute('data-timing-last');
		expect(Math.round((Date.parse(`${last}T00:00:00Z`) -
			Date.parse(`${first}T00:00:00Z`)) / 86400000) + 1).toBe(preset);
	}
});

async function belowTheStrip(page: Page) {
	return page.evaluate(() => {
		const selectors = ['[data-console-completeness]', '[data-console-band]',
			'[data-window-status]', '[data-console-panel]'];
		return selectors.flatMap((selector) => {
			const node = document.querySelector(selector);
			return node === null ? [] : [node.getBoundingClientRect().top + window.scrollY];
		});
	});
}

for (const width of [360, 390, 1280]) {
	test(`retained month prices and native window chrome remain honest at ${width}`, async ({ page }) => {
		await page.addInitScript(() => localStorage.setItem('idhazh:console-window', '1'));
		await page.setViewportSize({ width, height: 900 });
		await openRetained(page, () => [], 'ready', {
			months: ['2026-06', '2026-07', '2026-08'], held: ['2026-08']
		});
		await expect(page.locator('[data-window-status]')).toContainText('30D would fetch 1 more month');
		await expect(page.locator('[data-window-status]')).toContainText('90D 2 more');
		await page.goto('/console/');
		await expect(page.locator('[data-window-preset="1"] input')).toBeEnabled();
		await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');
		await expect(page.locator('[data-window-status]')).toContainText('Showing 1 day, to ');
		const before = await belowTheStrip(page);
		expect(before.length).toBeGreaterThan(3);
		for (const preset of presets().filter((days) => days > 1)) {
			await setWindow(page, preset);
			await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');
			const after = await belowTheStrip(page);
			expect(after.length).toBe(before.length);
			expect(after.map((top, index) => Math.abs(top - before[index]) > 1)).not.toContain(true);
		}
	});
}

test('every native Pipelines surface follows the common control and says one day correctly', async ({ page }) => {
	await page.goto('/console/');
	await expect(page.locator('[data-window-control] input').first()).toBeEnabled();
	const found = await windowed(page);
	expect(found.map((surface) => surface.name).sort()).toEqual([...BY_ROUTE.pipelines!.windowed].sort());
	for (const preset of presets()) {
		await setWindow(page, preset);
		const surfaces = await windowed(page);
		expect(surfaces.length).toBe(found.length);
		for (const surface of surfaces) {
			expect(surface.days).toBe(preset);
			expect(surface.says).toMatch(spanSaid(preset));
			expect(surface.says).not.toMatch(ONE_DAYS);
		}
	}
});

test('native run health uses the private run facts without inventing item-ledger cuts', () => {
	const date = '2026-08-20';
	const grid = runHealthGrid([{ date, records: [1, 2].map((n) => ({
		runId: `${date}-${n}`, n, status: 'completed', succeeded: 2, failed: 0, skipped: 0, sourceListStale: false
	})) }], 70);
	expect(grid[0].squares.map((square) => square.runId)).toEqual([`${date}-1`, `${date}-2`]);
	expect(grid[0].squares.map((square) => square.outcome)).toEqual(['2 of 2 succeeded', '2 of 2 succeeded']);
	expect(grid[0].squares.every((square) => !square.label.includes('read only in part'))).toBe(true);
});
