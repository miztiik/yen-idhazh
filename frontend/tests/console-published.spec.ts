import { expect, test, type Page } from '@playwright/test';
import { chartsReady } from './support/charts-ready';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { publishedSkyline, publishingHorizon, siteCost } from '../src/lib/charts/glance';
import type { GlanceDay } from '../src/lib/charts/glance';
import type { RunSummary } from '../src/lib/server/payload';

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
 * What the card counts is held two ways, and neither reads what the site was
 * built from: the reader that counts a day's articles, `publishedCharts`, is
 * run over day payloads a test writes in `console.spec.ts`, and on the page the
 * card's count for a day is the count the daily chart table prints for it.
 *
 * The page intro used to end with two counts of rows on record. Both only ever
 * grow, so neither could ever indicate a state, and nothing on the page acted
 * on either. The visible-copy check below keeps those old introductory counts
 * from returning to the page.
 */

const FRONTEND = resolve(process.cwd());

const CONFIG = JSON.parse(
	readFileSync(resolve(FRONTEND, '..', 'config', 'appearance.json'), 'utf8')
) as { console?: { window_presets?: number[]; default_window_days?: number } };

const PRESETS = CONFIG.console?.window_presets ?? [1, 7, 14, 30, 90];
const DEFAULT_DAYS = CONFIG.console?.default_window_days ?? 30;

/** The two cards, in the order the strip draws them. Articles first: the visual
 * count is a fraction of it, and a fraction reads as one only when the
 * denominator is beside it. */
const CARDS = ['Articles published', 'Visuals published'] as const;

/** Thousands separated, the way every count on this page is written. */
function grouped(value: number): string {
	return value.toLocaleString('en-GB');
}

function day(date: string, published: number, items = published): GlanceDay {
	// The skyline reads one count off a day and never both, so the two measures
	// have to be settable apart or a test cannot tell which one it drew.
	return { date, published, items, minutesPerChart: null };
}

/** A run manifest with only the fields the cost arithmetic reads. */
function summary(date: string, siteBytes: number): RunSummary {
	return { date, runs: 1, planned: 0, failed: 0, siteBytes, siteFiles: 1, models: [], records: [] };
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
			await expect(card).toContainText(preset === 1 ? 'in this one day' : `in these ${preset} days`);
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

test('THE ORACLE: the articles card counts what the chart table says each day published', async ({
	page
}) => {
	await page.goto('/console/');
	await hydrated(page);

	// The card and the daily chart table draw one list, which the route builds
	// from one read of each day payload, so for every day the table prints, the
	// card's bar is the table's article count. What that read takes off a day
	// payload is held to payloads a test writes in `console.spec.ts`.
	const plot = page.locator('[data-kpi="Articles published"] svg[data-published-days]');
	const bars = new Map(
		await plot
			.locator('rect[data-published-bar]')
			.evaluateAll((nodes) =>
				nodes.map((node) => [
					node.getAttribute('data-published-bar') ?? '',
					Number(node.getAttribute('data-published'))
				] as [string, number])
			)
	);
	expect(bars.size, 'the strip drew no columns').toBeGreaterThan(0);
	const table = await page
		.locator('[data-chart-day]')
		.evaluateAll((rows) =>
			rows.map((row) => [
				row.getAttribute('data-chart-day') ?? '',
				Number((row.querySelector('[data-charts-cell="items"]')?.textContent ?? '').trim())
			] as [string, number])
		);
	expect(table.length, 'the table prints no day of the window, so nothing is compared').toBeGreaterThan(0);
	for (const [date, items] of table) {
		expect(bars.has(date), `the card draws no bar for ${date}, which the table prints`).toBe(true);
		expect(bars.get(date), `${date}: the card and the table count different articles`).toBe(items);
	}

	// The card's own total is the same window summed, so the number can be checked
	// against the picture.
	const counts = [...bars.values()];
	const total = counts.reduce((sum, count) => sum + count, 0);
	await expect(page.locator('[data-kpi="Articles published"] .kpi-value')).toHaveText(
		grouped(total)
	);

	// And the busiest day fills the box, or the shape is not drawn against its
	// own peak and a heavy day reads like a quiet one.
	const heights = await plot
		.locator('rect[data-published-bar]')
		.evaluateAll((nodes) => nodes.map((node) => Number(node.getAttribute('height'))));
	const busiest = Math.max(...counts);
	expect(busiest, 'no day in the window published an article').toBeGreaterThan(0);
	const tallest = heights[counts.indexOf(busiest)];
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

test('THE ORACLE: the cost panel says what it is for, and its chart fills its frame', async ({
	page
}) => {
	// The panel is the marginal cost of one more article, and it is on the page
	// to answer how long the project can keep publishing under the 1 GB cap. The
	// note had never said either, so a reader met a chart of bytes per article
	// with nothing to hold it against.
	await page.goto('/console/');
	await page.setViewportSize({ width: 1440, height: 1000 });
	await chartsReady(page);

	const panel = page.locator('[data-windowed="site-cost-per-item"]');
	await expect(panel).toContainText('How long we can keep publishing');
	await expect(panel).toContainText('1 GB Pages cap');

	// The horizon names the cap, the rate and the date, in one sentence whose
	// numbers are the ones the chart beside it was drawn from.
	const horizon = panel.locator('[data-cost-horizon]');
	await expect(horizon).toHaveCount(1);
	const said = (await horizon.innerText()).replace(/\s+/g, ' ');

	const rate = Number(/At ([\d,]+) B an article/.exec(said)?.[1]?.replace(/,/g, ''));
	const summary = (await panel.locator('[data-cost-summary]').innerText()).replace(/\s+/g, ' ');
	const median = Number(/([\d,]+) B an article/.exec(summary)?.[1]?.replace(/,/g, ''));
	expect(Number.isFinite(rate), `no rate in the horizon: ${said}`).toBe(true);
	expect(rate, 'the horizon and the chart quote two different rates').toBe(median);

	// The daily rate is a median over the days the chart drew, so it is the middle
	// of the counts the articles card draws for those same days. Every one of those
	// days has to be on the card: a day with no count is a fault, never a zero.
	const perDay = Number(
		/median of ([\d,]+) articles a published day/.exec(said)?.[1]?.replace(/,/g, '')
	);
	expect(Number.isFinite(perDay), `no daily rate in the horizon: ${said}`).toBe(true);
	const drawn = await panel
		.locator('[data-cost-day]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-cost-day') ?? ''));
	expect(drawn.length, 'the cost chart drew no day').toBeGreaterThan(0);
	const card = new Map(
		await page
			.locator('[data-kpi="Articles published"] rect[data-published-bar]')
			.evaluateAll((nodes) =>
				nodes.map((node) => [
					node.getAttribute('data-published-bar') ?? '',
					Number(node.getAttribute('data-published'))
				] as [string, number])
			)
	);
	for (const date of drawn) {
		expect(card.has(date), `the articles card draws no count for ${date}`).toBe(true);
	}
	const counts = drawn.map((date) => card.get(date) as number).sort((a, b) => a - b);
	const middle = Math.floor(counts.length / 2);
	const expected =
		counts.length % 2 ? counts[middle] : (counts[middle - 1] + counts[middle]) / 2;
	expect(perDay, 'the daily rate is not the median of the days the chart drew').toBe(
		Math.round(expected)
	);

	// And the caveat, which is the one thing the figure cannot say about itself.
	expect(said, 'the horizon does not say which tree it measured').toContain('built site');

	// The chart tracks its container rather than the 760 it was once given. Read
	// at three widths, because a hardcoded number matches one of them by luck.
	//
	// Go to the panel first, at every width. The engine draws a chart once it is
	// within a screen of the viewport, so a panel further down has no plot until
	// a reader arrives - and this one is two screens down at 1440 and three at
	// 390. Reading it from the top of the page never tested the rule it looks
	// like it tests: measured 2026-09-27 at 1440x1000, the plot sat 19px inside
	// that reach here and outside it on a Linux runner, where the fonts are not
	// the same. Waiting for the plot rather than for a clock is also the stricter
	// read - a sleep passes a chart that was never drawn at all.
	for (const width of [1440, 768, 390]) {
		await page.setViewportSize({ width, height: 1000 });
		await panel.evaluate((node) => node.scrollIntoView({ behavior: 'instant', block: 'center' }));
		await expect(panel.locator('svg'), `${width}: the cost chart is not drawn`).toHaveCount(1);
		// The frame settles on the next paint: the chart reads its own width back
		// and redraws at it. This is that settle, not a wait for the engine.
		await page.waitForTimeout(500);
		const drawnAt = await panel.evaluate((node) => {
			const svg = node.querySelector('svg');
			const host = svg?.parentElement;
			if (!svg || !host) return null;
			return {
				svg: svg.getBoundingClientRect().width,
				host: host.getBoundingClientRect().width
			};
		});
		expect(drawnAt, `${width}: the cost chart is not drawn`).not.toBeNull();
		expect(
			Math.abs((drawnAt?.svg ?? 0) - (drawnAt?.host ?? 0)),
			`${width}: the chart drew ${drawnAt?.svg} in a ${drawnAt?.host} frame`
		).toBeLessThanOrEqual(2);
	}
});

test('the horizon needs both rates, and prints nothing without either', () => {
	// A tree that never grew over an article it published has no cost, and a
	// window whose days published nothing has no daily rate. Neither is a zero,
	// and printing a date from one is the defect the band already had once.
	const runs = [
		summary('2026-08-01', 1_000_000),
		summary('2026-08-02', 1_300_000),
		summary('2026-08-03', 1_600_000)
	];
	const items = new Map([
		['2026-08-01', 100],
		['2026-08-02', 100],
		['2026-08-03', 100]
	]);
	const cost = siteCost(runs, items);
	// 3,000 bytes an article by construction, and 100 articles a published day.
	expect(cost.median).toBe(3000);

	const horizon = publishingHorizon(1_600_000, cost, items, 10_000_000);
	expect(horizon).not.toBeNull();
	expect(horizon?.articles).toBe((10_000_000 - 1_600_000) / 3000);
	expect(horizon?.articlesPerDay).toBe(100);
	// A division a reader can check, at the two rates the sentence quotes.
	expect(horizon?.years).toBeCloseTo((10_000_000 - 1_600_000) / 3000 / 100 / 365.25, 6);

	expect(publishingHorizon(null, cost, items, 10_000_000)).toBeNull();
	expect(
		publishingHorizon(1_600_000, { ...cost, median: null }, items, 10_000_000)
	).toBeNull();
	expect(publishingHorizon(1_600_000, cost, new Map(), 10_000_000)).toBeNull();
});

test('nothing above the first heading carries a count that only ever grows', async ({ page }) => {
	await page.goto('/console/');

	// This used to read the page subtitle, which was cut from all three routes on
	// 2026-08-31: it repeated what the active tab's own description says 150px
	// lower and cost 25px of a first viewport the band was already filling. What
	// it once carried is the thing that must not come back anywhere - a running
	// count of scored items and a running count of item-health rows. Neither can
	// ever fall, so neither could tell an operator anything about the state of
	// the machine.
	const above = await page.evaluate(() => {
		const surface = document.querySelector('[data-surface="operator"]');
		const heading = surface?.querySelector('h2') ?? null;
		// Every paragraph on the surface, not only the ones the shell happens to
		// hold directly: the route's panels sit one element deeper since the shell
		// moved into `console/+layout.svelte`, and a direct-child filter would have
		// gone through by finding nothing at all.
		return [...(surface?.querySelectorAll('p') ?? [])]
			.filter(
				(node) => heading === null || node.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING
			)
			.map((node) => (node.textContent ?? '').replace(/\s+/g, ' ').trim());
	});
	for (const text of above) {
		expect(text, `a standing paragraph carries a running count: ${text}`).not.toContain('on record');
	}
	// And the subtitle itself is gone rather than reworded.
	expect(above.join(' '), 'the page subtitle came back').not.toContain('from the committed ledger');
});
