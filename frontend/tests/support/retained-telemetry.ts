/** Actual native Pipelines components receive independently authored numeric rows. */
import { expect, type Page } from './door-page';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { clientCode, drawClient } from './console-window/client-render';
import { windowOfDays, type TimeWindow } from '../../src/lib/charts/viewport';
import type { TelemetryRow } from '../../src/lib/charts/series';
import type { PanelState } from '../../src/lib/console/waiting';
import { telemetryRow } from './telemetry-row';
export { dayBefore } from './pipelines-ledgers';

export function items(date: string, prefix: string, stage: string, outcome: string,
	count: number, over: Partial<TelemetryRow> = {}): TelemetryRow[] {
	return Array.from({ length: count }, (_, at) => telemetryRow({
		date, run_id: `${date}-1`, item_id: `${prefix}-${String(at + 1).padStart(4, '0')}`,
		stage, outcome, code: outcome === 'failed' ? `${stage}_failed` : '', ...over
	}));
}

let code: Promise<string> | undefined;
export async function openRetained(
	page: Page, build: (window: TimeWindow) => readonly (TelemetryRow & { failed_rule?: string | null })[], panelState: PanelState = 'ready',
	monthInputs: { months?: string[]; held?: string[] } = {}
): Promise<{ window: TimeWindow }> {
	const appearance = JSON.parse(readFileSync(resolve('..', 'config', 'appearance.json'), 'utf8'));
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
		rows, config: appearance.console, chart: appearance.chart, pinned, initialDays, panelState, ...monthInputs
	}, styles);
	await expect(page.locator('[data-telemetry-rows]')).toHaveAttribute('data-telemetry-rows', String(rows.length));
	return { window };
}
