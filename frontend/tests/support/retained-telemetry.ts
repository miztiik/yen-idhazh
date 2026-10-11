/** Retained telemetry components keep their real-input tests after leaving Pipelines. */
import { expect, type Page } from './door-page';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { clientCode, drawClient } from './console-window/client-render';
import { windowOfDays, type TimeWindow } from '../../src/lib/charts/viewport';
import type { TelemetryRow } from '../../src/lib/charts/series';

let code: Promise<string> | undefined;
export async function openRetained(
	page: Page, build: (window: TimeWindow) => readonly TelemetryRow[]
): Promise<{ window: TimeWindow }> {
	const appearance = JSON.parse(readFileSync(resolve('..', 'config', 'appearance.json'), 'utf8'));
	const bands = JSON.parse(readFileSync(resolve('..', 'config', 'idhazh.json'), 'utf8')).summarize.bands;
	await page.goto('/');
	const stored = Number(await page.evaluate(() => localStorage.getItem('idhazh:console-window')));
	const initialDays = appearance.console.window_presets.includes(stored) ? stored : appearance.console.default_window_days;
	const pinned = '2026-08-24';
	const window = windowOfDays(pinned, initialDays, appearance.console.today_anchor);
	const rows = build(window);
	code ??= clientCode([['RetainedTelemetry', './tests/fixtures/panels/RetainedTelemetry.svelte']]);
	const html = readFileSync(resolve('build', 'index.html'), 'utf8');
	const styles = [...html.matchAll(/href="([^"]+\.css)"/g)].map((match) => match[1]);
	await drawClient(page, await code, 'RetainedTelemetry', {
		rows, bands, config: appearance.console, chart: appearance.chart, pinned, initialDays
	}, styles);
	await expect(page.locator('[data-telemetry-rows]')).toHaveAttribute('data-telemetry-rows', String(rows.length));
	return { window };
}
