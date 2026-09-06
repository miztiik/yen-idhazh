import { expect, test, type BrowserContext, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { orderByTime } from '../src/lib/day-shape';
import type { DigestItem } from '../src/lib/payload/types';

/**
 * Read marks belong to one digest date, they expire by the calendar, and a
 * click writes one day.
 *
 * The bug the dating guards is a quiet one. Marks used to be a single flat list
 * of item ids with no date on them, so an id that came round again greyed out
 * an article the reader had never opened, and nothing on the page could tell
 * them it had happened. The list also grew for ever.
 *
 * Two claims arrived on 2026-09-06 and both are here:
 *
 * 1. **The window is the calendar, not the store's own order.** Keeping the
 *    newest N dates the store happened to hold bounded it by how often a reader
 *    came back. A reader who opened one day a month kept marks from N different
 *    months.
 * 2. **A click writes the day in hand and nothing else.** Every mark used to
 *    re-serialise the whole reading history under one key, so the cost of one
 *    click grew with everything the reader had ever read.
 *
 * These assertions are about storage, not appearance, so they read `data-read`
 * on the article rather than a colour.
 */

/** One key a date. */
const PREFIX = 'idhazh:read:';

/** The one key every mark used to live under. */
const LEGACY_KEY = 'idhazh:read';

const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'digest');

/** How many days of marks the browser keeps, off the committed config.
 *
 * A literal here would stop asserting anything the day the knob moved: seed
 * eight older days against a fourteen-day window and nothing is over the bound,
 * so the pruning never runs and the test passes on a store that was never cut.
 */
function readMarkDays(): number {
	const parsed = JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
	) as { digest?: { read_mark_days?: number } };
	const days = parsed.digest?.read_mark_days;
	expect(days, 'config/appearance.json no longer sets digest.read_mark_days').toBeDefined();
	return days as number;
}

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

/** Pin the page's idea of today.
 *
 * The window is measured against the device clock and the canary publishes one
 * fixed date, so a test that let the wall clock in would pass on the day it was
 * written and drop every mark once that date aged past the window. Nothing here
 * may depend on when it runs.
 */
async function freezeAt(page: Page, date: string): Promise<void> {
	await page.clock.setFixedTime(new Date(`${date}T12:00:00Z`));
}

/** The store, one entry a date. */
async function stored(page: Page): Promise<Record<string, string[]>> {
	return page.evaluate((prefix) => {
		const marks: Record<string, string[]> = {};
		for (let index = 0; index < localStorage.length; index += 1) {
			const key = localStorage.key(index);
			if (key === null || !key.startsWith(prefix)) continue;
			marks[key.slice(prefix.length)] = JSON.parse(localStorage.getItem(key) ?? '[]');
		}
		return marks;
	}, PREFIX);
}

/** Fill the store before any script on the page runs. */
async function seed(page: Page, marks: Record<string, string[]>): Promise<void> {
	await page.addInitScript(
		(given: { prefix: string; marks: Record<string, string[]> }) => {
			for (const [date, ids] of Object.entries(given.marks)) {
				localStorage.setItem(`${given.prefix}${date}`, JSON.stringify(ids));
			}
		},
		{ prefix: PREFIX, marks }
	);
}

/** Fill the one key marks used to live under, in whichever old shape. */
async function seedLegacy(page: Page, value: unknown): Promise<void> {
	await page.addInitScript(
		(given: { key: string; value: unknown }) =>
			localStorage.setItem(given.key, JSON.stringify(given.value)),
		{ key: LEGACY_KEY, value }
	);
}

/** The source link opens a new tab at the article's own site. Nothing may leave
 * this machine during a test, so every off-origin request is refused and the
 * popup is left blank. The click still fires, which is what matters. The origin
 * comes from the config rather than a literal: the preview port is overridable,
 * and a hardcoded one aborts the page itself. */
async function refuseOffOrigin(context: BrowserContext, baseURL: string | undefined) {
	await context.route(
		(url) => !url.href.startsWith(String(baseURL)),
		(route) => route.abort()
	);
}

test('a mark is filed under the day it was made and survives a reload', async ({
	page,
	context,
	baseURL
}) => {
	await refuseOffOrigin(context, baseURL);
	await freezeAt(page, DAY);

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
	await freezeAt(page, DAY);
	await seed(page, { [daysBefore(DAY, 1)[0]]: [FIRST] });

	await page.goto(`/${DAY}/`);
	await expect(page.locator('article[data-read="true"]')).toHaveCount(0);
});

test('the old flat list of ids is dropped rather than guessed at', async ({ page }) => {
	await freezeAt(page, DAY);
	await seedLegacy(page, [FIRST]);

	await page.goto(`/${DAY}/`);
	await expect(page.locator('article[data-read="true"]')).toHaveCount(0);
	expect(await stored(page)).toEqual({});
	expect(await page.evaluate((key) => localStorage.getItem(key), LEGACY_KEY)).toBeNull();
});

test('a store written under the one old key keeps the days the window still reaches', async ({
	page
}) => {
	// The dated map is the shape marks were really made in, so it is carried
	// over rather than dropped. The window still applies to what it carried.
	const span = readMarkDays();
	const stale = daysBefore(DAY, span)[span - 1];
	await freezeAt(page, DAY);
	await seedLegacy(page, { [DAY]: [FIRST], [stale]: ['stale'] });

	await page.goto(`/${DAY}/`);
	await expect(page.locator('article').first()).toHaveAttribute('data-read', 'true');
	expect(await stored(page)).toEqual({ [DAY]: [FIRST] });
	expect(await page.evaluate((key) => localStorage.getItem(key), LEGACY_KEY)).toBeNull();
});

test('every date the window no longer reaches is dropped', async ({ page }) => {
	// The window counts today, so the oldest date it reaches is today minus one
	// less than the span. The date one day older than that is the boundary this
	// pins; the year-old one is what the rule this replaced could not drop,
	// because five stored dates never exceeded a fourteen-date bound.
	const span = readMarkDays();
	const [yesterday] = daysBefore(DAY, 1);
	const oldest = daysBefore(DAY, span - 1)[span - 2];
	const justOut = daysBefore(DAY, span)[span - 1];
	const [longGone] = daysBefore(DAY, 400).slice(-1);

	await freezeAt(page, DAY);
	await seed(page, {
		[DAY]: [FIRST],
		[yesterday]: ['a'],
		[oldest]: ['b'],
		[justOut]: ['c'],
		[longGone]: ['d']
	});

	await page.goto(`/${DAY}/`);
	await expect(page.locator('article').first()).toHaveAttribute('data-read', 'true');

	expect(Object.keys(await stored(page)).sort()).toEqual([DAY, yesterday, oldest].sort());
});

test('a clock behind the day being read drops nothing', async ({ page }) => {
	// A device set a month slow reads every published date as the future. Only a
	// date OLDER than the floor goes, so the reader loses no mark to a bad clock.
	const [behind] = daysBefore(DAY, 30).slice(-1);
	await freezeAt(page, behind);
	await seed(page, { [DAY]: [FIRST] });

	await page.goto(`/${DAY}/`);
	await expect(page.locator('article').first()).toHaveAttribute('data-read', 'true');
	expect(await stored(page)).toEqual({ [DAY]: [FIRST] });
});

test('a click writes the day in hand, whatever else the store holds', async ({
	page,
	context,
	baseURL
}) => {
	// The cost claim, measured as bytes rather than argued. Twelve other days
	// inside the window, each carrying forty marks, must not change what one
	// click writes. Under one key holding every date they changed all of it.
	await refuseOffOrigin(context, baseURL);
	await freezeAt(page, DAY);
	await page.addInitScript(() => {
		const touched: { key: string; bytes: number }[] = [];
		(window as unknown as { touchedKeys: typeof touched }).touchedKeys = touched;
		const setItem = Storage.prototype.setItem;
		const removeItem = Storage.prototype.removeItem;
		Storage.prototype.setItem = function (key: string, value: string) {
			touched.push({ key, bytes: value.length });
			return setItem.call(this, key, value);
		};
		Storage.prototype.removeItem = function (key: string) {
			touched.push({ key, bytes: 0 });
			return removeItem.call(this, key);
		};
	});

	const markFirstStory = async () => {
		await page.evaluate(
			() => ((window as unknown as { touchedKeys: unknown[] }).touchedKeys.length = 0)
		);
		const first = page.locator('article').first();
		await expect(first).toHaveAttribute('data-read', 'false');
		await first.getByRole('link', { name: 'Read the original' }).click();
		await expect(first).toHaveAttribute('data-read', 'true');
		return page.evaluate(
			() => (window as unknown as { touchedKeys: { key: string; bytes: number }[] }).touchedKeys
		);
	};

	await page.goto(`/${DAY}/`);
	const alone = await markFirstStory();

	// Now the same click against a reader who has been here every day.
	await page.evaluate(
		(given: { prefix: string; day: string; others: string[]; ids: string[] }) => {
			localStorage.removeItem(`${given.prefix}${given.day}`);
			for (const date of given.others) {
				localStorage.setItem(`${given.prefix}${date}`, JSON.stringify(given.ids));
			}
		},
		{
			prefix: PREFIX,
			day: DAY,
			others: daysBefore(DAY, 12),
			ids: Array.from({ length: 40 }, (_, n) => `ai-${String(1000000000 + n)}`)
		}
	);
	await page.reload();
	const crowded = await markFirstStory();

	expect(alone.map((touch) => touch.key)).toEqual([`${PREFIX}${DAY}`]);
	expect(crowded.map((touch) => touch.key)).toEqual([`${PREFIX}${DAY}`]);
	expect(crowded[0].bytes).toBe(alone[0].bytes);
});

test('forgetting a day forgets that day only', async ({ page }) => {
	const [yesterday] = daysBefore(DAY, 1);
	await freezeAt(page, DAY);
	await seed(page, { [DAY]: [FIRST], [yesterday]: ['kept'] });

	await page.goto(`/${DAY}/`);
	await expect(page.locator('article').first()).toHaveAttribute('data-read', 'true');

	await page.getByRole('button', { name: 'Forget what I have read' }).click();
	await expect(page.locator('article[data-read="true"]')).toHaveCount(0);
	expect(await stored(page)).toEqual({ [yesterday]: ['kept'] });
});

test('a store the browser refuses does not stop the page rendering', async ({ page }) => {
	await freezeAt(page, DAY);
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
