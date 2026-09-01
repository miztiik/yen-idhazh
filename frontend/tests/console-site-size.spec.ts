import { expect, test, type Page } from '@playwright/test';
import { PAGES_CAP_BYTES, siteCost, siteRunway } from '../src/lib/charts/glance';
import type { RunSummary } from '../src/lib/server/payload';

/**
 * The site's size, as a rate rather than as a level.
 *
 * The chart this replaced drew megabytes added per day, and a day adds six
 * times as much when it publishes six times as many articles - so the shape was
 * the item ceiling with a size label on it. Bytes per article is the part a
 * change to a payload can move.
 *
 * The oracle is the flagged set. A chart that decides by eye which day is
 * unusual cannot be checked at all, so the rule is stated once - further from
 * the window's median than one standard deviation - and this file recomputes it
 * from numbers it owns, and then again from the numbers the page prints.
 *
 * What the runway is denominated in belongs to `console-band.spec.ts`.
 */

function manifest(date: string, siteBytes: number): RunSummary {
	return { date, runs: 1, planned: 0, failed: 0, siteBytes, siteFiles: 1, models: [], records: [] };
}

/** Seven days of payload tree, and the cost of each one written out by hand.
 *
 * Every day publishes 100 articles, so the arithmetic below is a division a
 * reader can do in their head and the expected values are literals rather than
 * a second copy of the code under test.
 */
const DAYS: { date: string; bytes: number; items: number; expected: number | null }[] = [
	{ date: '2026-08-01', bytes: 1_000_000, items: 100, expected: null },
	{ date: '2026-08-02', bytes: 1_300_000, items: 100, expected: 3000 },
	{ date: '2026-08-03', bytes: 1_600_000, items: 100, expected: 3000 },
	{ date: '2026-08-04', bytes: 1_900_000, items: 100, expected: 3000 },
	{ date: '2026-08-05', bytes: 2_400_000, items: 100, expected: 5000 },
	{ date: '2026-08-06', bytes: 2_500_000, items: 100, expected: 1000 },
	{ date: '2026-08-07', bytes: 2_800_000, items: 100, expected: 3000 },
	// Published nothing, so it has no rate at all. The day after it still
	// differences against it, because that is when the tree was last measured.
	{ date: '2026-08-08', bytes: 2_800_000, items: 0, expected: null },
	{ date: '2026-08-09', bytes: 3_100_000, items: 100, expected: 3000 }
];

const MANIFESTS = DAYS.map((day) => manifest(day.date, day.bytes));
const ITEMS = new Map(DAYS.map((day) => [day.date, day.items]));

/** The rule, restated from the numbers rather than read off the module. */
function band(values: number[]): { median: number; spread: number } {
	const sorted = [...values].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	const median = sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
	const spread = Math.sqrt(values.reduce((sum, v) => sum + (v - median) ** 2, 0) / values.length);
	return { median, spread };
}

function outside(dates: string[], values: number[]): string[] {
	const { median, spread } = band(values);
	return dates.filter((_, i) => Math.abs(values[i] - median) > spread);
}

test('a day costs its own bytes over its own articles, and a day with none has no cost', () => {
	const cost = siteCost(MANIFESTS, ITEMS);
	expect(cost.empty).toBe(false);
	expect(
		cost.days.map((day) => [day.date, Math.round(day.bytesPerItem)]),
		'a day the tree grew on but nothing was published cannot report a rate'
	).toEqual(
		DAYS.filter((day) => day.expected !== null).map((day) => [day.date, day.expected])
	);
});

test('THE ORACLE: the flagged days are the days outside one standard deviation of the median', () => {
	const cost = siteCost(MANIFESTS, ITEMS);
	const values = cost.days.map((day) => day.bytesPerItem);
	const expected = outside(
		cost.days.map((day) => day.date),
		values
	);

	// Written out as well as computed, so a change to the rule has to disagree
	// with a literal rather than with its own restatement.
	expect(expected, 'the fixture stopped producing an outlier in each direction').toEqual([
		'2026-08-05',
		'2026-08-06'
	]);
	expect(
		cost.days.filter((day) => day.flagged).map((day) => day.date),
		'the chart flags a different set of days than the rule does'
	).toEqual(expected);
	expect(Math.round(cost.median ?? 0)).toBe(3000);
	expect(Math.round(cost.spread ?? 0)).toBe(Math.round(band(values).spread));
});

test('the window bounds what is drawn and never what is differenced', () => {
	const cost = siteCost(MANIFESTS, ITEMS, { start: '2026-08-04', end: '2026-08-09' });
	expect(cost.days.map((day) => day.date)).toEqual([
		'2026-08-04',
		'2026-08-05',
		'2026-08-06',
		'2026-08-07',
		'2026-08-09'
	]);
	// The oldest day on screen still reads against the day before it. Against
	// zero it would be 19,000 bytes an article and the window would invent an
	// outlier every time it moved.
	expect(Math.round(cost.days[0].bytesPerItem)).toBe(3000);
	expect(cost.days.filter((day) => day.flagged).map((day) => day.date)).toEqual(
		outside(
			cost.days.map((day) => day.date),
			cost.days.map((day) => day.bytesPerItem)
		)
	);
});

test('one day is not a spread, and a window with no published day has no cost', () => {
	const single = siteCost(MANIFESTS, ITEMS, { start: '2026-08-02', end: '2026-08-02' });
	expect(single.days).toHaveLength(1);
	expect(single.spread, 'a spread taken over one number is not a spread').toBeNull();
	expect(single.days[0].flagged, 'one day cannot be unusual relative to itself').toBe(false);

	const none = siteCost(MANIFESTS, ITEMS, { start: '2026-08-08', end: '2026-08-08' });
	expect(none.empty).toBe(true);
	expect(none.median).toBeNull();
});

test('the runway is headroom over one article, and absent where there is no rate', () => {
	const used = 100_000_000;
	const alarm = 800 * 1024 * 1024;
	const runway = siteRunway(used, 3000, alarm, PAGES_CAP_BYTES);
	expect(runway).not.toBeNull();
	expect(Math.round(runway?.toCap ?? 0)).toBe(Math.round((PAGES_CAP_BYTES - used) / 3000));
	expect(Math.round(runway?.toAlarm ?? 0)).toBe(Math.round((alarm - used) / 3000));

	// Three ways there is no rate to divide by, and none of them may print an
	// answer. There is no fourth: a runway in articles takes no daily rate, so
	// there is no articles-a-day argument left to be zero.
	expect(siteRunway(used, null, alarm)).toBeNull();
	expect(siteRunway(used, 0, alarm)).toBeNull();
	expect(siteRunway(used, -2000, alarm)).toBeNull();
});

async function hydrated(page: Page) {
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', /\d+/);
}

/** What the page itself says each day cost, read back off the page. */
async function printed(page: Page) {
	return page.locator('[data-cost-day]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			date: node.getAttribute('data-cost-day') ?? '',
			bytes: Number(node.getAttribute('data-cost-bytes')),
			flagged: node.getAttribute('data-cost-flagged') === 'true'
		}))
	);
}

test('the page flags the same days its own numbers do', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	const section = page.locator('[data-windowed="site-cost-per-item"]');
	await expect(section, 'the per-article cost section is not on the page').toHaveCount(1);

	const rows = await printed(page);
	expect(rows.length, 'the section published no per-day cost to check').toBeGreaterThan(0);
	for (const row of rows) {
		expect(Number.isFinite(row.bytes), `${row.date} printed no cost`).toBe(true);
	}

	// Recomputed from what the page printed, not from what it computed.
	const expected =
		rows.length < 2
			? []
			: outside(
					rows.map((row) => row.date),
					rows.map((row) => row.bytes)
				);
	expect(
		rows.filter((row) => row.flagged).map((row) => row.date),
		'the marks on the chart and the rule the page states disagree'
	).toEqual(expected);
});

test('the cost section says what it counts, in bytes and per article', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	const section = page.locator('[data-windowed="site-cost-per-item"]');
	// A number with no unit and no basis is the defect this row was opened for.
	await expect(section.locator('[data-cost-summary]')).toContainText(/[\d,]+ B an article/);
	await expect(section).toContainText('over the articles that day published');
});

test('the standing band carries the level, the track and the runway', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	// The size moved off a card and into the band on 2026-08-30, because the band
	// stands on all three console routes and one page may not state one figure
	// twice. What it owes is unchanged: a level, the share of the one limit that
	// cannot move (Rule #2), and a runway.
	const band = page.locator('[data-console-band] [data-band-fact="size"]');
	await expect(band).toHaveCount(1);
	const sentence = page.locator('[data-band-size]');
	await expect(sentence).toContainText(/[\d.]+ MB of the 1 GB limit/);

	// The track draws the value it prints over that limit.
	const track = band.locator('[data-band-size-pct]');
	await expect(track).toHaveCount(1);
	const printedMb = Number(/([\d.]+) MB/.exec((await sentence.innerText()) ?? '')?.[1]);
	const drawnPct = Number(await track.getAttribute('data-band-size-pct'));
	const cap = Number(await track.getAttribute('data-band-size-cap'));
	expect(cap).toBe(PAGES_CAP_BYTES);
	expect(drawnPct).toBeCloseTo(((printedMb * 1024 * 1024) / PAGES_CAP_BYTES) * 100, 1);

	// The runway, in articles. One line: the rate it divides by, the days it was
	// measured over and the clause about which tree the cap measures all live on
	// `What one more article costs` below, which already owns the rate, its n and
	// its spread - and a band that repeated them spent sixty of its hundred words
	// on a caveat. What the unit has to be, and why it may not be published days,
	// is `console-band.spec.ts`.
	await expect(sentence).toContainText(/room for about [\d,]+ more articles/);
	const printedText = (await sentence.innerText()).trim();
	expect(printedText.split(/\s+/).length, 'the band is growing a paragraph again').toBeLessThan(20);
	expect(printedText, 'the basis came back to the band').not.toContain('an article over');
	expect(printedText, 'a build command is not a reader string').not.toContain('site-weight');
	expect(printedText, 'a subsystem term is not a reader term').not.toContain('payload tree');

	// And the panel below it still carries all three, so nothing was deleted.
	const panel = page.locator('[data-windowed="site-cost-per-item"]');
	await expect(panel).toContainText(/[\d,]+ B an article/);
	await expect(panel).toContainText('the most room we have');
});

test('the window delta is on the windowed panel, in megabytes', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	// It is a rate, so it lives with the other windowed size fact rather than in
	// the band, which is not windowed and stands on all three routes. A share is
	// what this used to print, and from the 13,595 bytes the oldest manifest
	// recorded it read +73,933 percent - and green, on a card watching growth.
	const panel = page.locator('[data-windowed="site-cost-per-item"]');
	await expect(panel).toContainText(/(Up|Down) [\d.,]+ MB over \d+ days|No second measurement/);
});

test('the runs-and-size table is gone, and its run facts are on the run squares', async ({
	page
}) => {
	await page.goto('/console/');
	await hydrated(page);

	// Two nouns joined by "and" was two sections. The size is a card now, and
	// the run counts were already four headings above on the strip.
	await expect(page.getByRole('heading', { name: 'Runs and site size' })).toHaveCount(0);

	const squares = page.locator('[data-run-history] [data-health]');
	expect(await squares.count(), 'the run strip drew no square to carry the counts').toBeGreaterThan(
		0
	);
	const labels = await squares.evaluateAll((nodes) =>
		nodes.map((node) => node.getAttribute('aria-label') ?? node.textContent ?? '')
	);
	expect(
		labels.some((label) => /\d+ of \d+ succeeded/.test(label)),
		'planned left the table without landing on a run square'
	).toBe(true);
});
