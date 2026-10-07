import { expect, test, type Page, type Route } from '@playwright/test';
import { telemetryCsv } from '../src/lib/charts/series';
import { telemetryRow } from './support/telemetry-row';

/**
 * Row #17's oracle, wired: a failed month load heals on a later widen.
 *
 * The test answers every telemetry month the page asks for with a shard it
 * builds. A month the default window asks for when the page opens gets an empty
 * shard. A month the 90-day window asks for first fails; asked again, it gets
 * `ROWS_A_MONTH` rows dated inside that window. The old page marked a month
 * loaded BEFORE its fetch, so a fetch that failed left the month "loaded" and
 * empty for the rest of the session - a gap that never healed.
 *
 * The observable is the viewport's own count of rows in view. On the fixed page
 * the retry asks for the failed months again and the count climbs from 0 to
 * exactly the rows served; on the old page the retry finds the months already
 * marked done, fetches nothing, and the count stays at 0 - which is the red this
 * proves.
 */

/** Rows the test serves for each month the widened window asks for. */
const ROWS_A_MONTH = 3;

/** The month a telemetry shard request names, `YYYY-MM`. */
function monthOf(url: string): string {
	const month = /\/telemetry\/(\d{4}-\d{2})\.csv$/.exec(new URL(url).pathname)?.[1];
	if (month === undefined) throw new Error(`${url} names no telemetry month`);
	return month;
}

/** A month's shard: `rows` rows dated `day`, each a different item. */
function shard(day: string, rows: number): string {
	return telemetryCsv(
		Array.from({ length: rows }, (_, at) =>
			telemetryRow({ date: day, run_id: `${day}-1`, item_id: `healed-${at + 1}` })
		)
	);
}

/** Rows the viewport says it is drawing, read off its own sentence. */
async function rowsInView(page: Page): Promise<number> {
	const text = await page.locator('[data-windowed="telemetry-viewport"]').innerText();
	const match = /(\d+)\s+rows?\s+in view/.exec(text.replace(/\s+/g, ' '));
	expect(match, `the viewport never said how many rows it is drawing: ${text}`).not.toBeNull();
	return Number(match?.[1] ?? -1);
}

/** Wait for the control to be usable, i.e. a browser has hydrated the page. */
async function hydrated(page: Page): Promise<void> {
	await expect(page.locator('[data-window-preset="30"] input')).toBeEnabled();
}

/** Pick a preset and wait for any month fetch it triggered to settle. */
async function setWindow(page: Page, days: number): Promise<void> {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
	// The busy note is true while a month file is in the air and false once the
	// last one settles, so waiting for it is waiting for the merge to be done.
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-busy',
		'false'
	);
}

test('a failed month load heals on a later widen', async ({ page }) => {
	// Neuter the service worker: it fields same-origin fetches, and a request it
	// fulfils is one `page.route` never sees. An empty worker has no fetch
	// handler, so every telemetry fetch reaches the network and the route below.
	await page.route('**/service-worker.js', (route) =>
		route.fulfill({ status: 200, contentType: 'text/javascript', body: '' })
	);

	const asked: string[] = [];
	const opened = new Set<string>();
	let opening = true;
	let refusing = true;
	/** The first day of the widened window, read off the page before the retry. */
	let windowStart = '';
	await page.route('**/telemetry/*.csv', (route: Route) => {
		const month = monthOf(route.request().url());
		asked.push(month);
		if (opening) opened.add(month);
		if (opened.has(month)) {
			return route.fulfill({ status: 200, contentType: 'text/csv', body: shard(`${month}-01`, 0) });
		}
		if (refusing) return route.abort();
		const day = `${month}-01` > windowStart ? `${month}-01` : windowStart;
		return route.fulfill({ status: 200, contentType: 'text/csv', body: shard(day, ROWS_A_MONTH) });
	});

	await page.goto('/console/');
	// Clear anything a prior context left controlling the page or cached.
	await page.evaluate(async () => {
		if ('serviceWorker' in navigator) {
			for (const reg of await navigator.serviceWorker.getRegistrations()) await reg.unregister();
		}
		if ('caches' in window) for (const key of await caches.keys()) await caches.delete(key);
	});
	await hydrated(page);
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');
	expect(opened.size, 'the page opened without asking for a month').toBeGreaterThan(0);
	opening = false;

	// Widen far enough to reach months the opening window did not. Their fetches
	// fail, so no row arrives.
	await setWindow(page, 90);
	const refused = asked.filter((month) => !opened.has(month));
	expect(refused.length, 'widening asked for no month past the opening window').toBeGreaterThan(0);
	expect(await rowsInView(page)).toBe(0);
	windowStart = (await page.locator('[data-viewport-control]').getAttribute('data-window-start')) ?? '';
	expect(windowStart, 'the viewport publishes no window start').toMatch(/^\d{4}-\d{2}-\d{2}$/);

	// Clear the failure and ask again. On the fixed page the months were never
	// marked loaded, so this widen fetches them; on the old page they were marked
	// loaded before the failed fetch, so nothing is asked and nothing fills.
	refusing = false;
	const before = asked.length;
	await setWindow(page, 1);
	await setWindow(page, 90);

	expect(
		asked.slice(before),
		'the retry did not re-ask exactly the months a failed load left behind'
	).toEqual(refused);
	expect(await rowsInView(page), 'a failed month load did not heal').toBe(ROWS_A_MONTH * refused.length);
});
