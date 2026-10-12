import { expect, test, type Page } from './support/door-page';
import { openRetained } from './support/retained-telemetry';
import { telemetryRow } from './support/telemetry-row';
import { presets, setWindow, windowed } from './support/console-window/controls';
import { spanSaid, ONE_DAYS } from './support/pipelines-span';
import { BY_ROUTE } from './support/console-expect/console-window';
import { clientCode, drawClient } from './support/console-window/client-render';
import { cutsByRun } from '../src/lib/server/cuts-by-run';
import { health, runOutcome, squareLabel, type RunFacts } from '../src/lib/console/run-square';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

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

test('the retained run square names only the run that actually cut an article', async ({ page }) => {
	const date = '2026-08-20';
	const cuts = cutsByRun([
		{ run_id: `${date}-1`, url_key: 'cut', source_words_before_cap: '2000', source_words: '1000' },
		{ run_id: `${date}-2`, url_key: 'whole', source_words_before_cap: '200', source_words: '200' }
	]);
	expect([...cuts]).toEqual([[`${date}-1`, 1]]);
	const runs: RunFacts[] = [1, 2].map((n) => ({
		n, status: 'completed', succeeded: 2, failed: 0, skipped: 0, sourceListStale: false
	}));
	const code = await clientCode([['RunHealthPanel', './src/routes/console/RunHealthPanel.svelte']]);
	const html = readFileSync(resolve('build', 'index.html'), 'utf8');
	await drawClient(page, code, 'RunHealthPanel', {
		yieldDays: [{ date, itemsPlanned: 4, itemsPublished: 4, itemsFailed: 0 }],
		grid: [{ date, squares: runs.map((run) => {
			const runId = `${date}-${run.n}`;
			const count = cuts.get(runId) ?? 0;
			return { runId, n: run.n, health: health(run, 70), label: squareLabel(date, run, 70, count),
				outcome: runOutcome(run, 70, count) };
		}) }],
		window: { start: '2026-08-19', end: date }, floorPct: 70,
		height: 220, width: 760, tickDensity: 6, readoutMaxShare: 1
	}, [...html.matchAll(/href="([^"]+\.css)"/g)].map((match) => match[1]));
	await expect(page.locator('[data-health]')).toHaveCount(2);
	await expect(page.locator('[data-health]').nth(0)).toHaveAttribute('aria-label', /1 read only in part/);
	await expect(page.locator('[data-health]').nth(1)).not.toHaveAttribute('aria-label', /read only in part/);
	await expect(page.locator('[data-readout-row="Run 1"]')).toContainText('1 read only in part');
});
