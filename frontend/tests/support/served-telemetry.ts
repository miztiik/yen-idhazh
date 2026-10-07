/** How does a console test serve the telemetry months `/console/` asks for, from rows the test builds?
 *
 * The page holds no telemetry row when it opens. It fetches the month files its window
 * reaches into, so a test that answers those fetches checks values it wrote, whatever
 * day the site under test was built on. The rows are built for the window the page
 * opened on: the viewport prints that window before any row arrives, and every fetch
 * waits until the test has built its rows, so a test names each row's day by how far
 * it lies before the window's last day.
 */

import { expect, type Page } from '@playwright/test';
import { telemetryCsv, type TelemetryRow } from '../../src/lib/charts/series';
import type { TimeWindow } from '../../src/lib/charts/viewport';
import { telemetryRow } from './telemetry-row';

const DAY_MS = 86_400_000;

/** The UTC day `ago` days before `day`. */
export function dayBefore(day: string, ago: number): string {
	return new Date(Date.parse(`${day}T00:00:00Z`) - ago * DAY_MS).toISOString().slice(0, 10);
}

/** `count` items one day ended at `stage` with `outcome`, each its own item, one run a day. */
export function items(
	date: string,
	prefix: string,
	stage: string,
	outcome: string,
	count: number,
	over: Partial<TelemetryRow> = {}
): TelemetryRow[] {
	return Array.from({ length: count }, (_, at) =>
		telemetryRow({
			date,
			run_id: `${date}-1`,
			item_id: `${prefix}-${String(at + 1).padStart(4, '0')}`,
			stage,
			outcome,
			code: outcome === 'failed' ? `${stage}_failed` : '',
			...over
		})
	);
}

/** The month a telemetry file request names, `YYYY-MM`. */
function monthOf(url: string): string {
	const month = /\/telemetry\/(\d{4}-\d{2})\.csv$/.exec(new URL(url).pathname)?.[1];
	if (month === undefined) throw new Error(`${url} names no telemetry month`);
	return month;
}

export interface Served {
	/** The window the page opened on, as its viewport prints it. */
	window: TimeWindow;
	/** Every month file the page asked for, in the order it asked. */
	asked: string[];
}

/** Open `/console/` and answer every telemetry month it asks for with the rows `build`
 *  returns for the window the page opened on, each month file holding the rows dated in
 *  it. Resolves once the page has asked for every month a built row falls in and holds
 *  every built row. */
export async function openServed(
	page: Page,
	build: (window: TimeWindow) => readonly TelemetryRow[]
): Promise<Served> {
	const asked: string[] = [];
	let hand!: (rows: readonly TelemetryRow[]) => void;
	const built = new Promise<readonly TelemetryRow[]>((resolve) => (hand = resolve));
	await page.route('**/telemetry/*.csv', async (route) => {
		const month = monthOf(route.request().url());
		asked.push(month);
		const rows = (await built).filter((row) => row.date.startsWith(`${month}-`));
		await route.fulfill({ status: 200, contentType: 'text/csv', body: telemetryCsv([...rows]) });
	});
	await page.goto('/console/');

	const control = page.locator('[data-viewport-control]');
	const window = {
		start: (await control.getAttribute('data-window-start')) ?? '',
		end: (await control.getAttribute('data-window-end')) ?? ''
	};
	expect(window.end, 'the viewport prints no window, so no row can be dated in it').toMatch(/^\d{4}-\d{2}-\d{2}$/);
	const rows = build(window);
	hand(rows);

	// A month the page never asks for is a month whose rows never arrive, and every count
	// below would be short by them without saying why.
	await expect.poll(() => asked.length, 'the page asked for no telemetry month').toBeGreaterThan(0);
	for (const month of new Set(rows.map((row) => row.date.slice(0, 7)))) {
		await expect.poll(() => asked.includes(month), `the page never asked for ${month}, where built rows are dated`).toBe(true);
	}
	const panels = page.locator('[data-console-panels="pipelines"]');
	await expect(panels).toHaveAttribute('data-telemetry-fetching', 'no');
	await expect(panels, 'the page does not hold every built row').toHaveAttribute('data-telemetry-rows', String(rows.length));
	return { window, asked };
}
