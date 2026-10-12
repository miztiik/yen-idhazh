import { expect, test, type Page } from './support/browser';
import { telemetryCsv } from '../src/lib/charts/series';
import { telemetryRow } from './support/telemetry-row';

/** A failed console month must remain retryable, independently of the day loader. */
test('a failed telemetry month heals when the reader widens the window again', async ({ page }) => {
	const opened = new Set<string>();
	const asked: string[] = [];
	let opening = true;
	let refusing = true;
	let windowStart = '';
	await page.route('**/telemetry/*.csv', (route) => {
		const match = /\/telemetry\/(\d{4}-\d{2})\.csv$/.exec(new URL(route.request().url()).pathname);
		if (match === null) throw new Error(`Not a telemetry month: ${route.request().url()}`);
		const month = match[1];
		asked.push(month);
		if (opening) opened.add(month);
		if (!opened.has(month) && refusing) return route.abort();
		const day = `${month}-01` > windowStart ? `${month}-01` : windowStart;
		const rows = opened.has(month) ? [] : [
			telemetryRow({ date: day, run_id: `${day}-1`, item_id: `healed-${month}` })
		];
		return route.fulfill({ status: 200, contentType: 'text/csv', body: telemetryCsv(rows) });
	});

	await page.goto('/console/');
	await expect(page.locator('[data-window-preset="30"] input')).toBeEnabled();
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');
	expect(opened.size, 'the page must ask for a telemetry month on opening').toBeGreaterThan(0);
	opening = false;

	await setWindow(page, 90);
	const refused = asked.filter((month) => !opened.has(month));
	expect(refused.length, 'widening must reach a month beyond the opening window').toBeGreaterThan(0);
	await expect(page.locator('[data-windowed="telemetry-viewport"]')).toContainText('0 rows in view');
	const start = await page.locator('[data-viewport-control]').getAttribute('data-window-start');
	expect(start).toMatch(/^\d{4}-\d{2}-\d{2}$/);
	if (start === null) throw new Error('The viewport must expose its window start');
	windowStart = start;

	refusing = false;
	const before = asked.length;
	await setWindow(page, 1);
	await setWindow(page, 90);
	expect(asked.slice(before), 'only failed months should be fetched again').toEqual(refused);
	await expect(page.locator('[data-windowed="telemetry-viewport"]')).toContainText(
		`${refused.length} ${refused.length === 1 ? 'row' : 'rows'} in view`
	);
});

async function setWindow(page: Page, days: number): Promise<void> {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', String(days));
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');
}
