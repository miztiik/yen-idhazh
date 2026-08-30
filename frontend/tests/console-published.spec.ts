import { expect, test, type Page } from '@playwright/test';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { publishedSkyline } from '../src/lib/charts/glance';
import type { GlanceDay } from '../src/lib/charts/glance';

/**
 * Charts published, as one bar a day over the window the control set.
 *
 * The card used to carry a smoothed line over a fixed fourteen days, under a
 * page whose control read thirty. Two spans on one page cannot be compared,
 * and a line between two days claims a value for the hours in between that
 * nobody counted. Bars, and the window everything else on the page follows.
 *
 * The page intro used to end with two counts of rows on record. Both only ever
 * grow, so neither could ever indicate a state, and nothing on the page acted
 * on either. They are gone, and the assertions below are what stop them coming
 * back one sentence at a time.
 */

const FRONTEND = resolve(process.cwd());
const SRC = join(FRONTEND, 'src');

const CONFIG = JSON.parse(
	readFileSync(resolve(FRONTEND, '..', 'config', 'appearance.json'), 'utf8')
) as { console?: { window_presets?: number[]; default_window_days?: number } };

const PRESETS = CONFIG.console?.window_presets ?? [7, 14, 30, 90];
const DEFAULT_DAYS = CONFIG.console?.default_window_days ?? 30;

function day(date: string, published: number): GlanceDay {
	return { date, published, minutesPerChart: null };
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

	const card = page.locator('[data-kpi="Charts published"]');
	await expect(card).toBeVisible();

	for (const preset of PRESETS) {
		await setWindow(page, preset);
		const plot = card.locator('svg[data-published-days]');
		// Read off the page, never typed here: a number written into a spec goes
		// stale the day the fixture grows a row, and it goes stale silently.
		const control = await page.locator('[data-window-control]').getAttribute('data-window-days');
		await expect(plot, `${preset} days: the strip stopped naming its span`).toHaveAttribute(
			'data-published-days',
			control ?? ''
		);
		await expect(
			plot.locator('rect[data-published-bar]'),
			`${preset} days: a column is missing a bar`
		).toHaveCount(Number(control));

		// And the number above the bars is those bars added up. A total over a
		// different span would let a reader check the picture and be told they
		// were wrong.
		const drawn = await plot
			.locator('rect[data-published-bar]')
			.evaluateAll((nodes) =>
				nodes.reduce((sum, node) => sum + Number(node.getAttribute('data-published')), 0)
			);
		await expect(card.locator('.kpi-value')).toHaveText(String(drawn));
		await expect(card).toContainText(`in these ${preset} days`);
	}
});

test('published days are bars, and every bar is one day wide', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	const plot = page.locator('[data-kpi="Charts published"] svg[data-published-days]');
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
	expect(heights.some((height) => height > 0), 'no day drew a bar at all').toBe(true);
	expect(Math.max(...heights)).toBeCloseTo(34, 1);
});

test('the strip is drawn before any script runs', async ({ page }) => {
	// Markup, not an engine: the prerendered document already carries the bars,
	// so the card is complete with JavaScript off.
	const document = await (await page.request.get('/console/')).text();
	expect(document).toContain('data-published-bar');
	expect(document).toContain(`data-published-days="${DEFAULT_DAYS}"`);
	expect(document).toContain('var(--chart-3)');
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
