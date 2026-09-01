import { expect, test, type Page } from '@playwright/test';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { publishedSkyline } from '../src/lib/charts/glance';
import type { GlanceDay } from '../src/lib/charts/glance';

/**
 * Two skylines, each one bar a day over the window the control set.
 *
 * The card used to carry a smoothed line over a fixed fourteen days, under a
 * page whose control read thirty. Two spans on one page cannot be compared,
 * and a line between two days claims a value for the hours in between that
 * nobody counted. Bars, and the window everything else on the page follows.
 *
 * `Visuals published` gained `Articles published` beside it on 2026-09-01. The
 * visual count is a fraction of the article count and reads as one only when
 * the denominator is drawn beside it, so the two share `publishedSkyline` and
 * the oracle below asserts they report the same day count - which is the whole
 * of "they are on one window".
 *
 * The page intro used to end with two counts of rows on record. Both only ever
 * grow, so neither could ever indicate a state, and nothing on the page acted
 * on either. They are gone, and the assertions below are what stop them coming
 * back one sentence at a time.
 */

const FRONTEND = resolve(process.cwd());
const SRC = join(FRONTEND, 'src');
/** The canary day tree the browser suite is built from. */
const CANARY = resolve(FRONTEND, '..', 'backend', 'var', 'canary', 'digest');

const CONFIG = JSON.parse(
	readFileSync(resolve(FRONTEND, '..', 'config', 'appearance.json'), 'utf8')
) as { console?: { window_presets?: number[]; default_window_days?: number } };

const PRESETS = CONFIG.console?.window_presets ?? [7, 14, 30, 90];
const DEFAULT_DAYS = CONFIG.console?.default_window_days ?? 30;

/** The two cards, in the order the strip draws them. Articles first: the visual
 * count is a fraction of it, and a fraction reads as one only when the
 * denominator is beside it. */
const CARDS = ['Articles published', 'Visuals published'] as const;

/** Thousands separated, the way every count on this page is written. */
function grouped(value: number): string {
	return value.toLocaleString('en-GB');
}

/** How many items each committed day published, read from the payloads.
 *
 * The card's own arithmetic is not consulted. A count taken from the page would
 * only prove the page agrees with itself, and this is the one number the
 * articles card exists to print.
 */
function publishedItemsByDate(): Map<string, number> {
	const found = new Map<string, number>();
	const dirs = (at: string) =>
		readdirSync(at, { withFileTypes: true })
			.filter((entry) => entry.isDirectory())
			.map((entry) => entry.name)
			.sort();
	for (const year of dirs(CANARY)) {
		for (const month of dirs(join(CANARY, year))) {
			for (const day of dirs(join(CANARY, year, month))) {
				const raw = readFileSync(join(CANARY, year, month, day, 'digest.json'), 'utf8');
				found.set(`${year}-${month}-${day}`, (JSON.parse(raw) as { items: unknown[] }).items.length);
			}
		}
	}
	return found;
}

function day(date: string, published: number, items = published): GlanceDay {
	// The skyline reads one count off a day and never both, so the two measures
	// have to be settable apart or a test cannot tell which one it drew.
	return { date, published, items, minutesPerChart: null };
}

function sourceFiles(): string[] {
	const found: string[] = [];
	const walk = (at: string) => {
		for (const entry of readdirSync(at, { withFileTypes: true })) {
			const path = join(at, entry.name);
			if (entry.isDirectory()) walk(path);
			else if (/\.(ts|svelte|js)$/.test(path) && statSync(path).isFile()) found.push(path);
		}
	};
	walk(SRC);
	return found;
}

async function hydrated(page: Page) {
	await expect(page.locator(`[data-window-preset="${DEFAULT_DAYS}"] input`)).toBeEnabled();
}

async function setWindow(page: Page, days: number) {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

test('the window decides the columns, not the days that carry a run', () => {
	// Two days of data inside a seven-day window is seven bars, five of them
	// empty. A chart that shrank to its own data would draw two columns under a
	// control reading seven, which is the defect this rule exists to refuse.
	const sparse = publishedSkyline(
		[day('2026-08-27', 4), day('2026-08-28', 8)],
		{ start: '2026-08-22', end: '2026-08-28' }
	);
	expect(sparse.bars.map((bar) => bar.date)).toEqual([
		'2026-08-22',
		'2026-08-23',
		'2026-08-24',
		'2026-08-25',
		'2026-08-26',
		'2026-08-27',
		'2026-08-28'
	]);
	expect(sparse.bars.map((bar) => bar.published)).toEqual([0, 0, 0, 0, 0, 4, 8]);
	// The busiest day fills the box and everything else is drawn against it, so
	// the shape answers "which days were heavy" rather than "was anything done".
	expect(sparse.busiest).toBe(8);
	expect(sparse.bars.map((bar) => bar.height)).toEqual([0, 0, 0, 0, 0, 0.5, 1]);
	expect(sparse.total).toBe(12);
	expect(sparse.empty).toBe(false);
});

test('a day outside the window is outside the count as well as the picture', () => {
	// The count printed above the bars has to be the same window the bars are,
	// or a reader adding up the columns gets a different answer to the one the
	// card gave them.
	const window = { start: '2026-08-26', end: '2026-08-28' };
	const skyline = publishedSkyline(
		[day('2026-08-20', 100), day('2026-08-27', 3), day('2026-08-28', 5)],
		window
	);
	expect(skyline.bars.length).toBe(3);
	expect(skyline.total).toBe(8);
	expect(skyline.total).toBe(skyline.bars.reduce((sum, bar) => sum + bar.published, 0));
});

test('a window that published nothing says so rather than drawing thirty zeros', () => {
	const quiet = publishedSkyline([day('2026-08-27', 0)], {
		start: '2026-08-26',
		end: '2026-08-28'
	});
	expect(quiet.empty).toBe(true);
	expect(quiet.busiest).toBe(0);
	expect(quiet.bars.every((bar) => bar.height === 0)).toBe(true);
	// A window with no day in it at all is the same answer, not a crash.
	expect(publishedSkyline([], { start: '2026-08-26', end: '2026-08-28' }).empty).toBe(true);
});

test('the bars sit inside the box and never touch each other', () => {
	// A gap of a fifth of the column is what stops ninety days reading as one
	// filled block. It is a share of the pitch, so it holds at every span.
	for (const days of PRESETS) {
		const end = '2026-08-28';
		const start = new Date(Date.parse(`${end}T00:00:00Z`) - (days - 1) * 86_400_000)
			.toISOString()
			.slice(0, 10);
		const skyline = publishedSkyline([day(end, 1)], { start, end });
		expect(skyline.bars.length, `${days} days drew ${skyline.bars.length} bars`).toBe(days);
		for (const [index, bar] of skyline.bars.entries()) {
			expect(bar.x, `${days} days: bar ${index} starts left of the box`).toBeGreaterThanOrEqual(0);
			expect(bar.x + bar.width, `${days} days: bar ${index} runs past the box`).toBeLessThanOrEqual(
				1.000001
			);
			const next = skyline.bars[index + 1];
			if (next) expect(bar.x + bar.width).toBeLessThanOrEqual(next.x + 0.000001);
		}
	}
});

test('THE ORACLE: the bar count is the window day count, at every preset', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	for (const label of CARDS) {
		await expect(page.locator(`[data-kpi="${label}"]`)).toBeVisible();
	}

	for (const preset of PRESETS) {
		await setWindow(page, preset);
		// Read off the page, never typed here: a number written into a spec goes
		// stale the day the fixture grows a row, and it goes stale silently.
		const control = await page.locator('[data-window-control]').getAttribute('data-window-days');

		for (const label of CARDS) {
			const card = page.locator(`[data-kpi="${label}"]`);
			const plot = card.locator('svg[data-published-days]');
			await expect(plot, `${label} at ${preset} days: the strip stopped naming its span`).toHaveAttribute(
				'data-published-days',
				control ?? ''
			);
			await expect(
				plot.locator('rect[data-published-bar]'),
				`${label} at ${preset} days: a column is missing a bar`
			).toHaveCount(Number(control));

			// And the number above the bars is those bars added up. A total over a
			// different span would let a reader check the picture and be told they
			// were wrong.
			const drawn = await plot
				.locator('rect[data-published-bar]')
				.evaluateAll((nodes) =>
					nodes.reduce((sum, node) => sum + Number(node.getAttribute('data-published')), 0)
				);
			await expect(card.locator('.kpi-value')).toHaveText(grouped(drawn));
			await expect(card).toContainText(`in these ${preset} days`);
		}

		// Both strips report the same span. That is the whole of "they are on one
		// window", and it is what makes the smaller count readable as a share of
		// the larger one rather than as a number beside it.
		const spans = await page
			.locator('[data-glance] svg[data-published-days]')
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-published-days')));
		expect(spans, `${preset} days: the two skylines drew different spans`).toEqual(
			CARDS.map(() => control)
		);
	}
});

test('THE ORACLE: the articles card counts what the committed days published', async ({ page }) => {
	// Counted from the payloads themselves, never from the page. A count the page
	// also computed only proves the page agrees with itself.
	const byDate = publishedItemsByDate();
	expect(byDate.size, 'no committed day published an item, so the count is untested').toBeGreaterThan(
		0
	);

	await page.goto('/console/');
	await hydrated(page);

	const plot = page.locator('[data-kpi="Articles published"] svg[data-published-days]');
	const drawn = await plot
		.locator('rect[data-published-bar]')
		.evaluateAll((nodes) =>
			nodes.map((node) => [
				node.getAttribute('data-published-bar') ?? '',
				Number(node.getAttribute('data-published'))
			])
		);

	const window = drawn.map(([date]) => date);
	expect(window.length, 'the strip drew no columns').toBeGreaterThan(0);
	const expected = window.map((date) => byDate.get(date as string) ?? 0);
	expect(
		drawn.map(([, count]) => count),
		'the bars and the committed payloads disagree about what was published'
	).toEqual(expected);

	// The card's own total is the same window summed, so the number can be
	// checked against the picture.
	const total = expected.reduce((sum, count) => sum + count, 0);
	await expect(page.locator('[data-kpi="Articles published"] .kpi-value')).toHaveText(
		grouped(total)
	);

	// And the busiest day fills the box, or the shape is not drawn against its
	// own peak and a heavy day reads like a quiet one.
	const heights = await plot
		.locator('rect[data-published-bar]')
		.evaluateAll((nodes) => nodes.map((node) => Number(node.getAttribute('height'))));
	const busiest = Math.max(...expected);
	const tallest = heights[expected.indexOf(busiest)];
	expect(tallest, 'the busiest day is not drawn full height').toBeCloseTo(34, 1);
});

test('published days are bars, and every bar is one day wide', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	for (const label of CARDS) {
		const plot = page.locator(`[data-kpi="${label}"] svg[data-published-days]`);
		// A line would interpolate between two days, which is the claim this shape
		// exists not to make. There is no line in it to make it.
		await expect(plot.locator('polyline, path')).toHaveCount(0);
		const bars = plot.locator('rect[data-published-bar]');
		await expect(bars.first()).toHaveAttribute('fill', 'var(--chart-3)');

		// One bar has height. The whole strip having height would mean the busiest
		// day set every bar, and a strip with none would be an empty plot area.
		const heights = await bars.evaluateAll((nodes) =>
			nodes.map((node) => Number(node.getAttribute('height')))
		);
		expect(heights.some((height) => height > 0), `${label}: no day drew a bar at all`).toBe(true);
		expect(Math.max(...heights)).toBeCloseTo(34, 1);
	}
});

test('the strip is drawn before any script runs', async ({ page }) => {
	// Markup, not an engine: the prerendered document already carries the bars,
	// so both cards are complete with JavaScript off.
	const document = await (await page.request.get('/console/')).text();
	expect(document).toContain('data-published-bar');
	expect(document).toContain(`data-published-days="${DEFAULT_DAYS}"`);
	expect(document).toContain('var(--chart-3)');
	for (const measure of ['articles', 'visuals']) {
		expect(document, `${measure} is not in the prerendered document`).toContain(
			`data-published-measure="${measure}"`
		);
	}
});

test('one function draws both strips, so their geometry cannot drift', () => {
	// The pair only reads as a fraction while both are one bar a day at the same
	// pitch over the same window. Two copies would agree today and drift the
	// first time either was tuned.
	const span = { start: '2026-08-26', end: '2026-08-28' };
	const days = [day('2026-08-27', 1, 40), day('2026-08-28', 3, 60)];
	const visuals = publishedSkyline(days, span, 'published');
	const articles = publishedSkyline(days, span, 'items');

	expect(articles.bars.map((bar) => bar.published)).toEqual([0, 40, 60]);
	expect(visuals.bars.map((bar) => bar.published)).toEqual([0, 1, 3]);
	expect(articles.total).toBe(100);
	expect(visuals.total).toBe(4);
	// Same span, same pitch, same left edges. That is what makes the smaller
	// count readable against the larger one rather than beside it.
	expect(articles.bars.map((bar) => bar.date)).toEqual(visuals.bars.map((bar) => bar.date));
	expect(articles.bars.map((bar) => bar.x)).toEqual(visuals.bars.map((bar) => bar.x));
	expect(articles.bars.map((bar) => bar.width)).toEqual(visuals.bars.map((bar) => bar.width));
	// Each is drawn against its own busiest day, or the smaller series is a row
	// of hairlines and says nothing about which of its own days were heavy.
	expect(articles.busiest).toBe(60);
	expect(visuals.busiest).toBe(3);
});

test('the intro carries no count that only ever grows', async ({ page }) => {
	await page.goto('/console/');

	const intro = page.locator('[data-surface="operator"] > p').first();
	await expect(intro).toContainText('from the committed ledger');
	// Two sentences used to follow that one: a running count of scored items and
	// a running count of item-health rows. Neither can ever fall, so neither
	// could tell an operator anything about the state of the machine.
	await expect(intro).not.toContainText('on record');
	await expect(intro).not.toContainText(/\d/);
});

test('the two on-record counts have no reader left in the source', () => {
	// The row deletes the sentence and the computation behind it. A payload
	// field nobody reads is the state this asserts against, because it survives
	// every gate: it type-checks, it builds, and it costs the page bytes.
	const files = sourceFiles();
	expect(files.length, 'the source scan found nothing - it is broken').toBeGreaterThan(50);

	const totals = files.filter((path) => /\btotalRows\b/.test(readFileSync(path, 'utf8')));
	expect(totals.map((path) => path.slice(SRC.length + 1))).toEqual([]);

	// `itemHealthRows` stays as the ledger reader in `payload.ts`, which the
	// timings, the throughput and the source table all still need. What must not
	// come back is a payload key of that name, or anything reading one.
	const shipped = files.filter((path) =>
		/(\.itemHealthRows\b|\bitemHealthRows\s*:)/.test(readFileSync(path, 'utf8'))
	);
	expect(shipped.map((path) => path.slice(SRC.length + 1))).toEqual([]);
});
