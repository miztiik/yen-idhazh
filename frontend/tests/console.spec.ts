import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

/**
 * The console says whether the runs worked and which feeds are broken.
 *
 * It runs against the canary build, whose fixtures carry one run of each colour
 * and one feed of each kind the page has to tell apart. The canary build writes
 * the item-health ledger because the console reads timing medians from it. The
 * fixture still has no score ledger, which proves the page keeps rendering when
 * one data source is missing.
 *
 * See `backend/utilities/build_canary_day.py` for the fixture.
 */

const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary');

/** The day the canary build publishes, discovered rather than hardcoded.
 *
 * A hardcoded date passes on an empty 404 page the moment the fixture moves.
 */
function publishedDay(): string {
	const dirs = (at: string) =>
		readdirSync(at, { withFileTypes: true })
			.filter((entry) => entry.isDirectory())
			.map((entry) => entry.name)
			.sort();
	const root = join(CANARY, 'digest');
	const year = dirs(root).at(-1) as string;
	const month = dirs(join(root, year)).at(-1) as string;
	const day = dirs(join(root, year, month)).at(-1) as string;
	return `${year}-${month}-${day}`;
}

const DAY = publishedDay();

function span(start: string | null, end: string | null): number {
	if (!start || !end) return 0;
	return (
		(new Date(`${end}T00:00:00Z`).getTime() - new Date(`${start}T00:00:00Z`).getTime()) /
			86_400_000 +
		1
	);
}

/** How many runs the fixture manifest records for that day. */
function runCount(): number {
	const [year, month, day] = DAY.split('-');
	const raw = readFileSync(join(CANARY, 'digest', year, month, day, 'run.json'), 'utf8');
	return (JSON.parse(raw) as { runs: unknown[] }).runs.length;
}

/** Every request the page made that came back missing. */
function watchFor404s(page: Page): string[] {
	const missing: string[] = [];
	page.on('response', (response) => {
		if (response.status() === 404) missing.push(response.url());
	});
	return missing;
}

test('the grid draws one square per run, coloured by what the run did', async ({ page }) => {
	await page.goto('/console/');

	const column = page.locator(`[data-day="${DAY}"]`);
	await expect(column).toHaveCount(1);
	await expect(column.locator('[data-health]')).toHaveCount(runCount());

	// The fixture is authored as one run of each colour: it published
	// everything, then found nothing new, then broke.
	await expect(column.locator('[data-health="green"]')).toHaveCount(1);
	await expect(column.locator('[data-health="amber"]')).toHaveCount(1);
	await expect(column.locator('[data-health="red"]')).toHaveCount(1);
});

test('a square says what happened without a mouse', async ({ page }) => {
	await page.goto('/console/');

	// The colour alone is not the answer. Anyone who cannot see the difference
	// between amber and red still has to be able to read the run.
	const first = page.locator(`[data-day="${DAY}"] [data-health]`).first();
	await expect(first).toHaveAttribute('aria-label', new RegExp(`^${DAY} run 1,`));
	await expect(first).toHaveAttribute('title', /succeeded/);
});

test('a feed that answered with nothing is named, and a polite refusal is not', async ({ page }) => {
	await page.goto('/console/');

	// Answered with zero items. It cost the digest the same articles a refusal would.
	await expect(page.locator('[data-feed="canary-empty"]')).toHaveCount(1);
	// Permanently gone.
	await expect(page.locator('[data-feed="canary-gone"]')).toHaveCount(1);

	// Said no in robots.txt, every single run. Honouring it is the pipeline
	// working, so it is not a failure and the operator is not asked to look.
	await expect(page.locator('[data-feed="canary-polite"]')).toHaveCount(0);
	// Answered every run. A healthy feed is never listed.
	await expect(page.locator('[data-feed="canary-steady"]')).toHaveCount(0);
	// Never asked, so it can neither pass nor fail.
	await expect(page.locator('[data-feed="canary-quiet"]')).toHaveCount(0);
});

test('a feed past the quarantine count is marked rested', async ({ page }) => {
	await page.goto('/console/');

	const flaky = page.locator('[data-feed="canary-flaky"]');
	await expect(flaky.locator('[data-rested]')).toHaveCount(1);
	await expect(page.locator('[data-feed="canary-gone"] [data-rested]')).toHaveCount(0);

	// Worst first. An operator reading top-down reads the biggest problem first.
	const named = await page
		.locator('[data-feed]')
		.evaluateAll((rows) => rows.map((row) => row.getAttribute('data-feed')));
	expect(named).toEqual(['canary-flaky', 'canary-empty', 'canary-gone']);
});

test('stage medians come from item health, not the score ledger', async ({ page }) => {
	await page.goto('/console/');

	await expect(page.getByText('Median seconds per item, by stage')).toBeVisible();
	await expect(page.getByText('200 ms')).toBeVisible();
	await expect(page.getByText('30 ms')).toBeVisible();
	await expect(page.getByText('700 ms')).toBeVisible();
});

test('the telemetry viewport renders the published projection', async ({ page }) => {
	await page.goto('/console/');

	await expect(page.locator('[data-viewport-control]')).toBeVisible();
	await expect(page.locator('[data-failure-panels]')).toBeVisible();
	await expect(page.locator('[data-compression]')).toBeVisible();
	await expect(page.locator('[data-viewport-control]')).toContainText('3 rows in view');
});

test('keyboard alone pans and zooms the telemetry viewport', async ({ page }) => {
	await page.goto('/console/');

	const viewport = page.locator('[data-viewport-control]');
	await viewport.focus();
	await expect(viewport).toBeFocused();
	const start = await viewport.getAttribute('data-window-start');
	const end = await viewport.getAttribute('data-window-end');

	await page.keyboard.press('ArrowLeft');
	await expect(viewport).not.toHaveAttribute('data-window-start', start ?? '');

	const pannedStart = await viewport.getAttribute('data-window-start');
	const pannedEnd = await viewport.getAttribute('data-window-end');
	await page.keyboard.press('-');
	const widenedStart = await viewport.getAttribute('data-window-start');
	const widenedEnd = await viewport.getAttribute('data-window-end');
	expect(span(widenedStart, widenedEnd)).toBeGreaterThan(span(pannedStart, pannedEnd));
	await page.keyboard.press('-');
	const widerStart = await viewport.getAttribute('data-window-start');
	const widerEnd = await viewport.getAttribute('data-window-end');
	await page.keyboard.press('+');
	const zoomedStart = await viewport.getAttribute('data-window-start');
	const zoomedEnd = await viewport.getAttribute('data-window-end');
	expect(span(zoomedStart, zoomedEnd)).toBeLessThan(span(widerStart, widerEnd));
	expect(span(start, end)).toBeGreaterThan(0);
});

test('panning to a month with no rows leaves a visible gap', async ({ page }) => {
	await page.goto('/console/');

	const viewport = page.locator('[data-viewport-control]');
	await viewport.focus();
	for (let index = 0; index < 8; index += 1) {
		await page.keyboard.press('ArrowLeft');
	}

	await expect(page.getByText('No rows in this window').first()).toBeVisible();
	await expect(viewport).toContainText('0 rows in view');
});

test('a missing ledger costs the page a section, never the page', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	const missing = watchFor404s(page);

	await page.goto('/console/');

	// The canary build has no score ledger. The page says so and carries on:
	// the timing chart, run grid and feed table still draw.
	await expect(page.getByText('Nothing has been scored yet.')).toBeVisible();
	await expect(page.getByText('Median seconds per item, by stage')).toBeVisible();
	await expect(page.locator('[data-grid="days"]')).toBeVisible();
	await expect(page.locator('[data-feeds="table"]')).toBeVisible();

	expect(errors).toEqual([]);
	expect(missing).toEqual([]);
});
