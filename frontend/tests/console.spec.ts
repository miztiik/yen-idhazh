import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

/**
 * The console says whether the runs worked and which feeds are broken.
 *
 * It runs against the canary build, whose fixtures are authored to carry one
 * run of each colour and one feed of each kind the page has to tell apart. The
 * fixture also has no score ledger at all, which is what proves the page still
 * renders when a data source it draws from is missing.
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

test('a missing ledger costs the page a section, never the page', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	const missing = watchFor404s(page);

	await page.goto('/console/');

	// The canary build has no score ledger. The page says so and carries on:
	// the run grid above it and the feed table below it both still draw.
	await expect(page.getByText('Nothing has been scored yet.')).toBeVisible();
	await expect(page.locator('[data-grid="days"]')).toBeVisible();
	await expect(page.locator('[data-feeds="table"]')).toBeVisible();

	expect(errors).toEqual([]);
	expect(missing).toEqual([]);
});
