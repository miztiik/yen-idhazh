import { expect, test, type Page } from '@playwright/test';

/**
 * The archive browses stories, not days.
 *
 * The Oracle this row is held to: the list renders every committed story in
 * published order newest first, and the page still renders when the index is
 * absent - falling back to the day row rather than white-screening.
 *
 * The suite runs against the canary build, which is one day of eight items over
 * nineteen quiet ones. That is enough to prove the order and the fallback, and
 * not enough to reach a second page: the page size is 25. The paging test below
 * therefore serves a larger index through `page.route`. That is the static host
 * answering differently, not our code replaced - the same boundary the missing
 * -index test uses, and the only one either test touches (Rule #7).
 */

const MONTH = /\/assist\/index\/\d{4}-\d{2}\.json$/;

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

test('the header states the retention window before anything is deleted', async ({ page }) => {
	await page.goto('/archive/');

	// The canary days carry `retention_window_months: -1`, which is what the
	// committed config ships. The promise has to be on the page either way.
	await expect(page.locator('[data-archive-scope]')).toContainText(
		/Nothing here is deleted\.|Charts older than \d+ months? are deleted\./
	);
});
