/** Actual native failure surfaces retain row divisors, calendar gaps and measured zero. */
import { expect, test } from './support/door-page';
import { nativeFailureMix } from '../src/lib/console/pipelines/failure-mix';
import { dateSeries, formatNumber } from './support/number-format';
import { frame } from '../src/lib/charts/frame';
import { dayBefore, items, openRetained } from './support/retained-telemetry';
import { setWindow } from './support/console-window/controls';
import { daysInWindow } from '../src/lib/charts/viewport';

test('native line geometry preserves unknown days, measured zero and isolated readings', () => {
	const window = { start: '2026-08-18', end: '2026-08-24' };
	const rows = [6, 5, 3, 2, 0].flatMap((ago) => items(dayBefore(window.end, ago), `day-${ago}`, 'publish', 'ok', 8));
	const mix = nativeFailureMix(rows.map((row) => ({ ...row })), daysInWindow(window));
	const geometry = dateSeries(mix.series,
		{ frame: frame(760, 220), density: 6, valueTicks: 5, padding: 0.2, rule: { changes: [], note: null } })!;
	expect(geometry.lines[0].points.map((point) => point.alone)).toEqual([false, false, false, false, true]);
	expect(geometry.lines[0].path.match(/M/g)).toHaveLength(3);
	expect(new Set(geometry.lines[0].points.map((point) => point.y)).size).toBe(1);
});

test('the actual native panel names its recorded-row divisor, not an inferred stage divisor', async ({ page }) => {
	await openRetained(page, (window) => [
		...items(window.end, 'listed', 'plan', 'failed', 1),
		...items(window.end, 'fetch', 'fetch', 'failed', 4),
		...items(window.end, 'extract', 'extract', 'failed', 2),
		...items(window.end, 'summarize', 'summarize', 'failed', 1),
		...items(window.end, 'done', 'publish', 'ok', 6),
		...items(dayBefore(window.end, 3), 'older', 'publish', 'ok', 5),
		...items(dayBefore(window.end, 3), 'older-fetch', 'fetch', 'failed', 1)
	]);
	await setWindow(page, 7);
	const surface = page.locator('[data-windowed="failure-mix"]');
	await expect(surface).toContainText(`${formatNumber(9 / 20 * 100, { si: false })}% of recorded rows failed.`);
	await expect(surface).toContainText('this counts rows, not distinct articles');
	await expect(surface.locator('[data-failed-rule-divisor]')).toContainText('5 recorded failures at fetch');
	await expect(surface.locator('[data-failed-rule-unknown]')).toContainText('5 of 5 failures at fetch have no recorded failed rule.');
	await expect(surface.locator('[data-source-losses], [data-failure-rows]')).toHaveCount(0);
	await setWindow(page, 1);
	await expect(surface).toHaveAttribute('data-window-days', '1');
	await expect(surface).toContainText(`${formatNumber(8 / 14 * 100, { si: false })}% of recorded rows failed.`);
});

test('actual native failure states keep waiting and unavailable distinct from no recorded rows', async ({ page }) => {
	for (const state of ['loading', 'unreachable'] as const) {
		await openRetained(page, () => [], state);
		await expect(page.locator('[data-reserved="failure-mix"]')).toHaveAttribute('data-panel-state', state);
		await expect(page.locator('[data-windowed="failure-mix"] [data-chart-type="dateSeries"]')).toHaveCount(0);
	}
	await openRetained(page, () => []);
	await expect(page.locator('[data-reserved="failure-mix"]')).toHaveAttribute('data-panel-state', 'quiet');
	await expect(page.locator('[data-windowed="failure-mix"]')).toContainText('No recorded row supplies a failure divisor.');
});

test('a measured clean day remains a true zero rather than an unrecorded quiet window', async ({ page }) => {
	await openRetained(page, ({ end }) => items(end, 'clean', 'publish', 'ok', 8));
	const surface = page.locator('[data-windowed="failure-mix"]');
	await expect(surface.locator('[data-nothing-fired]')).toHaveText('No recorded row failed at any step in these recorded days.');
	await expect(surface.locator('[data-chart-type="dateSeries"]')).toHaveCount(1);
	await expect(surface.locator('[data-readout="failure-mix"] [data-readout-row="Fetch"]')).toContainText('0');
});
