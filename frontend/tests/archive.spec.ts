import { expect, test, type Page } from '@playwright/test';

/**
 * The archive browses stories, not days.
 *
 * The Oracle this row is held to: the list renders every committed story in
 * published order newest first, the page still renders when the index is
 * absent - falling back to the day row rather than white-screening - and the
 * list still works with the whole on-device model directory gone.
 *
 * The suite runs against the canary build, which is one day of eight items over
 * nineteen quiet ones. That is enough to prove the order and the fallback, and
 * not enough to reach a second page: the page size is 25. The paging test below
 * therefore serves a larger index through `page.route`. That is the static host
 * answering differently, not our code replaced - the same boundary the missing
 * -index and model-absent tests use, and the only one any of them touches
 * (Rule #7).
 */

const MONTH = /\/index\/\d{4}-\d{2}\.json$/;

/** Every story on the page, in the order it is rendered. */
async function titles(page: Page): Promise<string[]> {
	return page.locator('[data-story-list="rows"] li a').allInnerTexts();
}

test('the day row is the index and the stories are the page', async ({ page }) => {
	await page.goto('/archive/');

	const days = page.locator('[data-day-row] a');
	await expect(days.first()).toBeVisible();
	expect(await days.count(), 'the canary corpus publishes twenty days').toBeGreaterThan(1);

	// The days are links to prerendered routes, so they work with no script.
	expect(await days.first().getAttribute('href')).toMatch(/\/\d{4}-\d{2}-\d{2}\/$/);

	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();
	expect((await titles(page)).length, 'no story reached the list').toBeGreaterThan(0);
});

test('a story links to its own anchor on the day that published it', async ({ page }) => {
	await page.goto('/archive/');

	const first = page.locator('[data-story-list="rows"] li a').first();
	await expect(first).toBeVisible();
	expect(await first.getAttribute('href')).toMatch(/\/\d{4}-\d{2}-\d{2}\/#[a-z0-9-]+$/);

	await first.click();
	await expect(page.locator('article').first()).toBeVisible();
});

test('the list runs newest first, and never reorders a day', async ({ page }) => {
	await page.goto('/archive/');
	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();

	const days = await page
		.locator('[data-story-list="rows"] li')
		.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-story-date') ?? ''));
	expect(days.length).toBeGreaterThan(0);

	// A day's stories sit together, so the same day never comes back later.
	const runs = days.filter((day, at) => at === 0 || day !== days[at - 1]);
	expect(new Set(runs).size, `a day is split across the list: ${runs.join(', ')}`).toBe(runs.length);
	// And the days themselves only ever go backwards in time.
	expect(runs).toEqual([...runs].sort().reverse());
});

test('the page pages with a control, and the control states its own size', async ({ page }) => {
	// Three real canary dates, twenty stories each. Sixty is more than two pages,
	// so the second click is the one that proves the count is not fixed.
	const dates = ['2026-08-18', '2026-08-19', '2026-08-20'];
	const entries = dates.flatMap((date, day) =>
		Array.from({ length: 20 }, (_, at) => ({
			date,
			item_id: `ai-${day * 20 + at + 1}`,
			title: `Story ${day * 20 + at + 1} on ${date}`,
			vertical: 'ai',
			vector: null
		}))
	);

	await page.route(MONTH, (route) =>
		route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				version: '2026-08-26',
				month: '2026-08',
				model_id: 'all-minilm-l6-v2-quantized',
				dimensions: 384,
				dtype: 'int8',
				scale: 1 / 127,
				entries
			})
		})
	);

	await page.goto('/archive/');
	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();
	expect(await page.locator('[data-story-list="rows"] li').count()).toBe(25);
	await expect(page.locator('[data-story-scope]')).toHaveText('Showing 25 of 60, newest first.');

	const more = page.locator('[data-story-more]');
	await expect(more).toHaveText(/Show 25 more/);
	await more.click();
	await expect(page.locator('[data-story-list="rows"] li')).toHaveCount(50);

	await expect(more).toHaveText(/Show 10 more/);
	await more.click();
	await expect(page.locator('[data-story-list="rows"] li')).toHaveCount(60);
	await expect(more).toHaveCount(0);

	// Newest first, and the newest date is the last one in the fixture.
	await expect(page.locator('[data-story-list="rows"] li a').first()).toHaveText(/on 2026-08-20/);
});

test('the page renders complete when the index is gone', async ({ page }) => {
	const errors: string[] = [];
	page.on('console', (message) => {
		if (message.type() === 'error') errors.push(message.text());
	});

	await page.route(MONTH, (route) => route.fulfill({ status: 404, body: 'not found' }));
	await page.goto('/archive/');

	await expect(page.locator('[data-story-list="unavailable"]')).toBeVisible();
	// The day row is the fallback, and it is prerendered, so it is untouched.
	expect(await page.locator('[data-day-row] a').count()).toBeGreaterThan(1);
	await expect(page.locator('h1')).toHaveText('Archive');
	await expect(page.locator('[data-story-more]')).toHaveCount(0);
	// The browser logs its own line for a 404, which is the request failing rather
	// than our code. Everything else on this list would be ours.
	const ours = errors.filter((text) => !text.includes('Failed to load resource'));
	expect(ours, 'a missing index must degrade, not error').toEqual([]);
});

test('the stories still list with the whole model directory gone', async ({ page }) => {
	// The runtime half of the CI model-absent gate. That gate parks `static/assist`
	// and asserts the bundle carries no `assist/`; this fails every request under
	// that path and asks for the stories anyway. Browsing is not an on-device model
	// feature, so nothing the list needs may be served from the encoder's directory
	// (`CLAUDE.md` section 0a). Staging the index there is what broke both, and this
	// is the test that would have caught it.
	await page.route('**/assist/**', (route) => route.fulfill({ status: 404, body: 'not found' }));

	await page.goto('/archive/');

	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();
	expect((await titles(page)).length, 'no story reached the list').toBeGreaterThan(0);
});

test('the header states the retention window before anything is deleted', async ({ page }) => {
	await page.goto('/archive/');

	// The canary days carry `retention_window_months: -1`, which is what the
	// committed config ships. The promise has to be on the page either way.
	await expect(page.locator('[data-archive-scope]')).toContainText(
		/Nothing here is deleted\.|Charts older than \d+ months? are deleted\./
	);
});

test('the browse window bounds the list, and states an empty window plainly', async ({ page }) => {
	// The Oracle for Finding 89. The anchor is the canary's newest published day,
	// 2026-08-20. These ten stories are dated the first of the month, so a
	// thirty-day window reaches them and a one-day window - the anchor day alone -
	// does not. The window bounds the fetch and the list; before this row the list
	// walked back through the archive until a page filled (Rule #12).
	const entries = Array.from({ length: 10 }, (_, at) => ({
		date: '2026-08-01',
		item_id: `ai-${at + 1}`,
		title: `Story ${at + 1} on 2026-08-01`,
		vertical: 'ai',
		vector: null
	}));

	// Every index file this page asks the host for. The window spans one month, so
	// there must be exactly one, whichever window the reader picks.
	const fetched: string[] = [];
	await page.route(MONTH, (route) => {
		fetched.push(new URL(route.request().url()).pathname);
		return route.fulfill({
			status: 200,
			contentType: 'application/json',
			body: JSON.stringify({
				version: '2026-08-26',
				month: '2026-08',
				model_id: 'all-minilm-l6-v2-quantized',
				dimensions: 384,
				dtype: 'int8',
				scale: 1 / 127,
				entries
			})
		});
	});

	await page.goto('/archive/');

	// The default window is thirty days, which reaches the first of the month, so
	// the ten stories are on the page - and only the one month they live in was
	// fetched, never a walk to an earlier one.
	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();
	expect(await page.locator('[data-story-list="rows"] li').count()).toBe(10);
	expect(
		new Set(fetched).size,
		`the window spans one month, so one index file is fetched, not ${fetched.length}`
	).toBe(1);

	// Narrow to a single day. That day is the anchor, no story sits on it, and the
	// list empties - stating which window emptied it and offering a wider one.
	await page.locator('[data-window-preset="1"]').click();
	await expect(page.locator('[data-archive-window]')).toHaveAttribute('data-window-days', '1');
	const empty = page.locator('[data-story-list="empty"]');
	await expect(empty).toBeVisible();
	await expect(empty).toContainText('No story in the last 1 day.');
	await expect(page.locator('[data-window-widen]')).toHaveText('Look back 90 days');
	expect(await page.locator('[data-story-list="rows"] li').count()).toBe(0);
	// Narrowing loaded no new month: the window only hides what was already here.
	expect(new Set(fetched).size, 'narrowing the window must not fetch another month').toBe(1);

	// The offer of a wider window brings the stories back, still from one file.
	await page.locator('[data-window-widen]').click();
	await expect(page.locator('[data-story-list="rows"] li').first()).toBeVisible();
	expect(await page.locator('[data-story-list="rows"] li').count()).toBe(10);
	expect(new Set(fetched).size, 'widening within the same month must not refetch it').toBe(1);
});
