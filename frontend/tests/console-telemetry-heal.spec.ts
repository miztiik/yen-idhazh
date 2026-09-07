import { expect, test, type Page, type Route } from '@playwright/test';

/**
 * Row #17's oracle, wired: a failed month load heals on a later widen.
 *
 * The canary telemetry has two months. 2026-08 is the seed the document opens
 * on; 2026-07 holds one older run the seed never reached, so widening the
 * window fetches its file. The old page marked that month loaded BEFORE the
 * fetch, so a fetch that failed left the month "loaded" and empty for the rest
 * of the session - a gap that never healed. This drives exactly that: fail the
 * 2026-07 fetch, then widen again with the failure cleared, and the month must
 * fill.
 *
 * The observable is the viewport's own count of rows in view. On the fixed page
 * the retry pulls 2026-07 in and the count climbs; on the old page the retry
 * finds the month already marked done, fetches nothing, and the count does not
 * move - which is the red this proves.
 */

/** The month whose fetch this test fails and then heals. Older than the 30-day
 * seed, so the seed never carries it and widening is what asks for it. */
const OLDER_MONTH = '2026-07';

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

	let blockOlder = true;
	let olderRequests = 0;
	await page.route(`**/telemetry/${OLDER_MONTH}.csv`, (route: Route) => {
		olderRequests += 1;
		return blockOlder ? route.abort() : route.continue();
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

	// Widen far enough to reach the older month. Its fetch fails, so its rows
	// never arrive.
	await setWindow(page, 90);
	expect(olderRequests, 'widening never asked for the older month at all').toBeGreaterThan(0);
	const afterFail = await rowsInView(page);

	// Clear the failure and ask again. On the fixed page the month was never
	// marked loaded, so this widen fetches it; on the old page it was marked
	// loaded before the failed fetch, so nothing is asked and nothing fills.
	blockOlder = false;
	const before = olderRequests;
	await setWindow(page, 1);
	await setWindow(page, 90);

	const afterRetry = await rowsInView(page);
	expect(
		olderRequests,
		'the retry never re-asked for the month a failed load left behind'
	).toBeGreaterThan(before);
	expect(
		afterRetry,
		`a failed month load did not heal: ${afterFail} rows before the retry, ${afterRetry} after`
	).toBeGreaterThan(afterFail);
});
