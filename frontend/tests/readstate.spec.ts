import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { orderByTime } from '../src/lib/day-shape';
import type { DigestItem } from '../src/lib/payload/types';

/**
 * Read marks belong to one digest date, and they expire.
 *
 * The bug this guards is a quiet one. Marks used to be a single flat list of
 * item ids with no date on them, so an id that came round again greyed out an
 * article the reader had never opened, and nothing on the page could tell them
 * it had happened. The list also grew for ever.
 *
 * These assertions are about storage, not appearance, so they read `data-read`
 * on the article rather than a colour.
 */

const KEY = 'idhazh:read';
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'digest');

/** The day this build publishes, and the story the page draws first.
 *
 * The browser suite runs against the canary build, which carries one day. A
 * hardcoded date would pass on an empty 404 page the moment that day moved.
 *
 * The first story is the first the PAGE draws, not the first the payload lists:
 * the stream runs newest first by the time on the item, so the two are only the
 * same by accident. It is computed through `orderByTime`, the function the page
 * itself calls, so a change to the order moves this with it.
 */
function publishedDay(): { date: string; firstItemId: string } {
	const dirs = (at: string) =>
		readdirSync(at, { withFileTypes: true })
			.filter((entry) => entry.isDirectory())
			.map((entry) => entry.name)
			.sort();
	const year = dirs(CANARY).at(-1) as string;
	const month = dirs(join(CANARY, year)).at(-1) as string;
	const day = dirs(join(CANARY, year, month)).at(-1) as string;
	const raw = readFileSync(join(CANARY, year, month, day, 'digest.json'), 'utf8');
	const payload = JSON.parse(raw) as { items: DigestItem[] };
	return {
		date: `${year}-${month}-${day}`,
		firstItemId: orderByTime(payload.items)[0].item_id
	};
}

const { date: DAY, firstItemId: FIRST } = publishedDay();

/** The `count` dates before `date`, newest first. */
function daysBefore(date: string, count: number): string[] {
	const at = new Date(`${date}T00:00:00Z`);
	const out: string[] = [];
	for (let i = 0; i < count; i += 1) {
		at.setUTCDate(at.getUTCDate() - 1);
		out.push(at.toISOString().slice(0, 10));
	}
	return out;
}

async function stored(page: Page): Promise<Record<string, string[]>> {
	return page.evaluate((key) => JSON.parse(localStorage.getItem(key) ?? '{}'), KEY);
}

/** Fill the store before any script on the page runs. */
async function seed(page: Page, marks: unknown): Promise<void> {
	await page.addInitScript(
		(given: { key: string; marks: unknown }) =>
			localStorage.setItem(given.key, JSON.stringify(given.marks)),
		{ key: KEY, marks }
	);
}

test('a mark is filed under the day it was made and survives a reload', async ({
	page,
	context,
	baseURL
}) => {
	// The source link opens a new tab at the article's own site. Nothing may
	// leave this machine during a test, so every off-origin request is refused
	// and the popup is left blank. The click still fires, which is what matters.
	// The origin comes from the config rather than a literal: the preview port is
	// overridable, and a hardcoded one aborts the page itself.
	await context.route(
		(url) => !url.href.startsWith(String(baseURL)),
		(route) => route.abort()
	);

	await page.goto(`/${DAY}/`);
	const first = page.locator('article').first();
	await expect(first).toHaveAttribute('data-read', 'false');

	await first.getByRole('link', { name: 'Read the original' }).click();
	await expect(first).toHaveAttribute('data-read', 'true');
	expect(await stored(page)).toEqual({ [DAY]: [FIRST] });

	await page.reload();
	await expect(page.locator('article').first()).toHaveAttribute('data-read', 'true');

	// The front page is the same day under a shorter address, so it shows the
	// same marks. A mark that only existed on one of the two would look lost.
	await page.goto('/');
	await expect(page.locator('article').first()).toHaveAttribute('data-read', 'true');
});

test('an id filed under another day cannot mark this day', async ({ page }) => {
	// The wrong-article bug in one assertion. A flat list carries no date, so
	// this id would grey out an article the reader never opened.
	await seed(page, { [daysBefore(DAY, 1)[0]]: [FIRST] });

	await page.goto(`/${DAY}/`);
	await expect(page.locator('article[data-read="true"]')).toHaveCount(0);
});

test('the old flat list of ids is dropped rather than guessed at', async ({ page }) => {
	await seed(page, [FIRST]);

	await page.goto(`/${DAY}/`);
	await expect(page.locator('article[data-read="true"]')).toHaveCount(0);
	expect(await stored(page)).toEqual({});
});

test('only the newest days survive a page load', async ({ page }) => {
	// Nine days of marks against the seven-day window config holds.
	const older = daysBefore(DAY, 8);
	await seed(page, {
		...Object.fromEntries(older.map((date) => [date, ['stale']])),
		[DAY]: [FIRST]
	});

	await page.goto(`/${DAY}/`);
	await expect(page.locator('article').first()).toHaveAttribute('data-read', 'true');

	const kept = Object.keys(await stored(page)).sort();
	expect(kept).toEqual([DAY, ...older.slice(0, 6)].sort());
});

test('a store the browser refuses does not stop the page rendering', async ({ page }) => {
	await page.addInitScript(() => {
		// Private mode and a full quota both surface as a throw from setItem.
		Storage.prototype.setItem = () => {
			throw new Error('quota exceeded');
		};
	});

	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));

	await page.goto(`/${DAY}/`);
	await expect(page.locator('article').first()).toBeVisible();
	expect(errors).toEqual([]);
});
