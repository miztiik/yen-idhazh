import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
	bandFor,
	bandOutliers,
	bandPlacements,
	bandSpan,
	bandSplit,
	placeInBand,
	type CompressionPoint,
	type SummaryBand,
	type TelemetryRow
} from '../src/lib/charts/series';
import { dayBefore, openServed } from './support/served-telemetry';
import { telemetryRow } from './support/telemetry-row';

/**
 * How far each day's summaries landed from the length the prompt asked for.
 *
 * This section used to be a scatter of article length against summary length:
 * 2,740 marks in one colour, measured 2026-08-30, which rendered the dense
 * middle as a solid block and hid the outliers - the only marks on it anybody
 * could act on. It is a per-day three-way split now, with the worst misses
 * named underneath.
 *
 * THE ORACLE is the row's whole point: `inside + short + long` equals the day's
 * own count of summaries the page can place a band for. The page is served
 * telemetry the test builds for the window it opened on, with summary lengths
 * chosen against the committed ladder, so each day's split is written out here.
 * A split that does not add up is mis-binning articles, and the picture would
 * still look right.
 */

const REPO = resolve(process.cwd(), '..');

/** Open the console and wait until it holds the rows this section draws from.
 *
 * Every panel here is built from telemetry rows, and since 2026-09-09 the page
 * holds none of them at first paint - it fetches its months on mount (owner
 * decision D3, `docs/architecture/publishing/console-payloads.md`). Reading the
 * section the moment the document arrived read the empty state and called it the
 * answer, so every count came back zero and the assertions that guard against a
 * fixture reaching no state at all fired instead.
 *
 * The page says where it is: `data-telemetry-rows` is how many it holds and
 * `data-telemetry-fetching` is whether more are in the air. Waiting on the count
 * rather than on a timeout means this cannot pass by being slow enough.
 */
async function open(page: Page): Promise<void> {
	await page.goto('/console/');
	// The count, not the flag. `data-telemetry-fetching` reads `no` before the
	// first fetch starts as well as after the last one lands, so waiting on it
	// alone would go straight through on an empty page.
	await page.waitForFunction(
		() =>
			Number(
				document.querySelector('[data-telemetry-rows]')?.getAttribute('data-telemetry-rows') ?? 0
			) > 0,
		undefined,
		{ timeout: 20_000 }
	);
}

/** The ladder the prompt is built from - the same file the page reads. */
const BANDS = (
	JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8')) as {
		summarize: { bands: SummaryBand[] };
	}
).summarize.bands;

/** How many outliers the list prints before the tail sentence takes over. */
const OUTLIER_ROWS = (
	JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')) as {
		console?: { band_outlier_rows?: number };
	}
).console?.band_outlier_rows ?? 10;

/** The band a length asks for, read straight off the committed ladder. */
function askedFor(sourceWords: number): SummaryBand {
	let chosen = BANDS[0];
	for (const band of BANDS) if (sourceWords >= band.min_source_words) chosen = band;
	return chosen;
}

/** One published article of `sourceWords` words whose summary ran `summaryWords`. */
function published(date: string, itemId: string, sourceWords: number, summaryWords: number | null, run = 1): TelemetryRow {
	return telemetryRow({
		date,
		run_id: `${date}-${run}`,
		item_id: itemId,
		source_words: sourceWords,
		summary_words: summaryWords
	});
}

interface Split {
	inside: number;
	short: number;
	long: number;
	items: number;
}

/** What the page did draw, one entry per column that carries a mark. */
async function drawn(page: Page): Promise<Record<string, Split>> {
	return page.locator('[data-band-day]').evaluateAll((nodes) => {
		const found: Record<string, { inside: number; short: number; long: number; items: number }> =
			{};
		for (const node of nodes) {
			const number = (name: string) => Number(node.getAttribute(name));
			found[node.getAttribute('data-band-day') ?? ''] = {
				inside: number('data-band-inside'),
				short: number('data-band-short'),
				long: number('data-band-long'),
				items: number('data-band-items')
			};
		}
		return found;
	});
}

test('THE ORACLE: the three-way split adds up to the day, every day in the window', async ({
	page
}) => {
	// Summary lengths are chosen against the rung each article reaches, so the split
	// below holds whatever the ladder's numbers are. A bound is inside the band.
	const rung = askedFor(400);
	const longRung = askedFor(2500);
	const { window } = await openServed(page, ({ end }) => {
		const older = dayBefore(end, 2);
		return [
			published(end, 'inside-low', 400, rung.target_words_min),
			published(end, 'inside-high', 400, rung.target_words_max),
			published(end, 'short', 400, rung.target_words_min - 1),
			published(end, 'long', 2500, longRung.target_words_max + 1),
			// A second run's row for an article the first run published: one article is
			// one item, kept at its longer reading, so this draws nothing of its own.
			published(end, 'inside-low', 300, rung.target_words_max + 500, 2),
			// Neither a failed item nor a summary with no length can be placed.
			telemetryRow({ date: end, run_id: `${end}-1`, item_id: 'failed', stage: 'fetch', outcome: 'failed' }),
			published(end, 'no-length', 400, null),
			published(older, 'older-short', 400, rung.target_words_min - 1),
			published(older, 'older-inside', 400, rung.target_words_min)
		];
	});

	// Every day, in both directions. A column the page invented and a day it
	// dropped are the same defect read from opposite ends.
	expect(await drawn(page)).toEqual({
		[window.end]: { inside: 2, short: 1, long: 1, items: 4 },
		[dayBefore(window.end, 2)]: { inside: 1, short: 1, long: 0, items: 2 }
	});

	// One rectangle per part that holds a summary, and never one per article: the
	// newest day's three parts and the older day's two. The scatter this replaced
	// drew 2,740 marks.
	await expect(page.locator('[data-band-part]')).toHaveCount(5);
	for (const part of ['inside', 'short', 'long']) {
		await expect(page.locator(`[data-band-part="${part}"]`), `no ${part} part was drawn`).not.toHaveCount(0);
	}
});

test('the scatter is gone, and nothing draws a point an article', async ({ page }) => {
	await open(page);

	await expect(page.locator('[data-compression]')).toHaveCount(0);
	await expect(page.locator('[data-band-distance]')).toHaveCount(1);
	// The marks the scatter drew: a circle an article, a diamond a cut one, and
	// a shaded band zone behind them.
	await expect(page.locator('[data-band-distance] svg circle')).toHaveCount(0);
	await expect(page.locator('[data-band-zone]')).toHaveCount(0);
	// Scoped, not page-wide: the source-cut range plot draws cap lines of its own.
	await expect(page.locator('[data-band-distance] [data-cap-line]')).toHaveCount(0);
});

test('the bounds are printed as numbers, and they are the ones the prompt asks for', async ({
	page
}) => {
	await open(page);

	const table = page.locator('[data-band-bounds]');
	await expect(table.locator('tbody tr')).toHaveCount(BANDS.length);

	// A shaded band with no printed bound cannot be checked against the columns
	// beside it. Every rung, read off the committed ladder rather than typed.
	for (const band of BANDS) {
		await expect(table.locator(`[data-band-target="${band.min_source_words}"]`)).toHaveText(
			`${band.target_words_min} to ${band.target_words_max}`
		);
	}

	// The header takes the one form an axis title and a column header take:
	// sentence case, a comma, the unit in lower case, no full stop.
	await expect(table.locator('thead')).toContainText('Article length, words');
	await expect(table.locator('thead')).toContainText('Target summary length, words');
});

test('the outlier list ranks by distance, prints its divisor, and caps itself', async ({ page }) => {
	await open(page);

	const list = page.locator('[data-band-outliers]');
	const rows = list.locator('[data-ranked-row]');
	const count = await rows.count();
	expect(count, 'the fixture put nothing outside a band, so the list asserts nothing').toBeGreaterThan(
		0
	);
	expect(count, 'the list ran past its own cap').toBeLessThanOrEqual(OUTLIER_ROWS);

	// The magnitudes, in the order the page drew them.
	const values = await rows
		.locator('[data-ranked-cell="value"]')
		.evaluateAll((nodes) => nodes.map((node) => Number((node.textContent ?? '').replace(/\D/g, ''))));
	expect(values, 'the list is not ranked by magnitude').toEqual([...values].sort((a, b) => b - a));

	// The divisor is on the page, because a bar scaled to a hidden maximum can be
	// read for order and cannot be read for size.
	const scale = list.locator('[data-ranked-max]');
	const max = Number(await scale.getAttribute('data-ranked-max'));
	expect(max, 'the printed divisor is not the largest magnitude drawn').toBe(values[0]);
	const printed = await scale.innerText();
	expect(printed).toContain('words outside the band');
	expect(Number(printed.replace(/\D/g, '')), 'the printed divisor is not the one drawn to').toBe(max);

	// Every bar is `value / max` of the rendered set. A bar scaled to anything
	// else lies about absolute size. The number is compared and the string is
	// not: the browser re-serialises `100.0000%` as `100%`.
	const widths = await rows
		.locator('[data-ranked-cell="bar"]')
		.evaluateAll((nodes) => nodes.map((node) => parseFloat((node as HTMLElement).style.inlineSize)));
	expect(widths).toEqual(values.map((value) => Number(((value / max) * 100).toFixed(4))));

	// Each row says which way it missed, in a word beside the name. Colour is one
	// signal and never the only one, and no row here is tinted at all.
	for (const status of await rows.locator('.ranked-status').allTextContents()) {
		expect(['too long', 'too short']).toContain(status.trim());
	}
});

test('the tail says how many rows are hidden, and never sums the distances', async ({ page }) => {
	// As many summaries past their band on the newest day as the list prints, each a
	// word further out than the last, and three more nine days earlier. Over fourteen
	// days three rows are hidden; over seven, none.
	const rung = askedFor(400);
	const pastTheBand = (date: string, prefix: string, count: number) =>
		Array.from({ length: count }, (_, at) =>
			published(date, `${prefix}-${at + 1}`, 400, rung.target_words_max + 1 + at)
		);
	await openServed(page, ({ end }) => [
		...pastTheBand(end, 'newest', OUTLIER_ROWS),
		...pastTheBand(dayBefore(end, 9), 'older', 3)
	]);
	const tail = page.locator('[data-band-outliers] [data-ranked="tail"]');

	await page.locator('[data-window-preset="14"]').click();
	await expect(page.locator('[data-windowed="band-distance"]')).toHaveAttribute('data-window-days', '14');
	// Counts add and distances do not: two summaries 40 words out are not one
	// summary 80 words out, so the tail reports rows and no total.
	await expect(tail).toHaveText('3 more articles are not shown.');
	expect(await tail.innerText()).not.toMatch(/words/);

	// A sentence saying zero rows are hidden is a line the operator reads and
	// learns nothing from.
	await page.locator('[data-window-preset="7"]').click();
	await expect(page.locator('[data-windowed="band-distance"]')).toHaveAttribute('data-window-days', '7');
	await expect(tail).toHaveCount(0);
});

test('a window with nothing in it says so, rather than drawing an empty chart', async ({ page }) => {
	await open(page);

	const chart = page.locator('[data-band-distance]');
	await expect(chart.locator('[data-band-part]')).not.toHaveCount(0);

	// Reached the way an operator reaches it, by panning off the days that have
	// rows. The fixture always has rows, so this is where the state is proved.
	const viewport = page.locator('[data-viewport-control]');
	await viewport.focus();
	for (let index = 0; index < 8; index += 1) await page.keyboard.press('ArrowLeft');

	await expect(chart).toContainText('No summaries in this window');
	await expect(chart.locator('[data-band-part]')).toHaveCount(0);
	// The two empty states say different things. This one means the ledger
	// answered no, so the list says so rather than reporting it cannot answer.
	await expect(page.locator('[data-band-outliers] [data-ranked="unmeasured"]')).toHaveCount(1);
});

test('the section declares its own window and follows the control', async ({ page }) => {
	await open(page);
	await expect(page.locator('[data-window-preset] input').first()).toBeEnabled();

	for (const days of [7, 90]) {
		await page.locator(`[data-window-preset="${days}"]`).click();
		await expect(page.locator('[data-windowed="band-distance"]')).toHaveAttribute(
			'data-window-days',
			String(days)
		);
	}
});

test('the chart draws in CSS pixels at every width, and labels its own axis', async ({ page }) => {
	// Loaded once: the first width drives the mount-time measure, the other two
	// the resize path.
	await page.setViewportSize({ width: 380, height: 900 });
	await open(page);
	for (const width of [380, 768, 1400]) {
		await page.setViewportSize({ width, height: 900 });

		// A viewBox is a scale factor, not a unit. One that disagrees with the
		// rendered width puts `font-size="10"` on screen at some other size.
		await expect
			.poll(async () =>
				page.locator('[data-band-distance] svg').evaluate((node) => {
					const declared = Number((node.getAttribute('viewBox') ?? '').split(/\s+/)[2]);
					return Math.abs(node.getBoundingClientRect().width - declared);
				})
			)
			.toBeLessThan(1);
	}

	// The count axis is named, and it is rotated so it runs along the axis it
	// names rather than across the row below it.
	const title = page.locator('[data-band-distance] [data-axis="y"]');
	await expect(title).toHaveText('Summaries');
	const box = await title.evaluate((node) => {
		const rect = node.getBoundingClientRect();
		return { width: rect.width, height: rect.height };
	});
	expect(box.height).toBeGreaterThan(box.width);
});

test('nothing on the section names a ledger column or prints a score', async ({ page }) => {
	await open(page);

	const text = await page.locator('[data-windowed="band-distance"]').innerText();
	for (const name of [
		'source_words',
		'summary_words',
		'source words',
		'truncation_flagged',
		'source_words_before_cap',
		'min_source_words',
		'target_words'
	]) {
		expect(text.toLowerCase(), `${name} is printed on the section`).not.toContain(name);
	}
	// No value between zero and one reaches the screen: every figure here is a
	// count of articles or a number of words.
	expect(text).not.toMatch(/\b[01]\.\d/);
});

test('a day axis carries dates, capped by the tick density the config sets', async ({ page }) => {
	await open(page);

	const density = (
		JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')) as {
			chart?: { tick_density?: number };
		}
	).chart?.tick_density ?? 6;

	const labels = page.locator('[data-band-distance] [data-day-label]');
	const count = await labels.count();
	expect(count, 'the day axis carries no date at all').toBeGreaterThan(1);
	expect(count, 'the day axis ran past its tick density').toBeLessThanOrEqual(density);

	// The ends are always labelled, so no column is more than half a gap from a
	// date the reader can name.
	const control = page.locator('[data-viewport-control]');
	await expect(labels.first()).toHaveAttribute(
		'data-day-label',
		(await control.getAttribute('data-window-start')) ?? ''
	);
	await expect(labels.last()).toHaveAttribute(
		'data-day-label',
		(await control.getAttribute('data-window-end')) ?? ''
	);
});

test('the ladder is read the way the prompt reads it: the longest band an article reaches', () => {
	const ladder: SummaryBand[] = [
		{ min_source_words: 0, target_words_min: 30, target_words_max: 45 },
		{ min_source_words: 60, target_words_min: 50, target_words_max: 90 },
		{ min_source_words: 700, target_words_min: 70, target_words_max: 150 }
	];

	// `SummarizeConfig.band_for` picks the longest band the article reaches, and
	// the first rung starts at zero so every article lands in one. Two readings
	// of one ladder would put an article in one band on the page and another in
	// the prompt, with nothing on screen looking wrong.
	expect(bandFor(ladder, 0)).toEqual(ladder[0]);
	expect(bandFor(ladder, 59)).toEqual(ladder[0]);
	expect(bandFor(ladder, 60)).toEqual(ladder[1]);
	expect(bandFor(ladder, 699)).toEqual(ladder[1]);
	expect(bandFor(ladder, 700)).toEqual(ladder[2]);
	expect(bandFor(ladder, 90_000)).toEqual(ladder[2]);
	// A config with no rungs places nothing, rather than placing everything in a
	// band it invented.
	expect(bandFor([], 400)).toBeNull();

	// The span each rung covers is read off the ladder, not off the rung: a rung
	// records the length it starts at, the next rung's floor is where it stops,
	// and the last one has no ceiling at all.
	expect(bandSpan(ladder, 0)).toBe('under 60');
	expect(bandSpan(ladder, 1)).toBe('60 to 699');
	expect(bandSpan(ladder, 2)).toBe('700 and over');
	// Grouped by hand, because `toLocaleString` reads the machine's locale.
	expect(bandSpan([{ min_source_words: 2000, target_words_min: 1, target_words_max: 2 }], 0)).toBe(
		'2,000 and over'
	);
});

test('a distance is the gap to the nearer bound, and inside the band it is zero', () => {
	const ladder: SummaryBand[] = [
		{ min_source_words: 0, target_words_min: 30, target_words_max: 45 },
		{ min_source_words: 60, target_words_min: 50, target_words_max: 90 }
	];
	const point = (id: string, source: number, summary: number): CompressionPoint => ({
		date: '2026-08-28',
		item_id: id,
		source_words: source,
		summary_words: summary,
		truncation_flagged: false
	});

	expect(placeInBand(point('a', 400, 70), ladder)).toMatchObject({ place: 'inside', distance: 0 });
	// Both bounds are inclusive: a summary that hit the number it was asked for
	// is inside the band, not one word past it.
	expect(placeInBand(point('b', 400, 50), ladder)).toMatchObject({ place: 'inside', distance: 0 });
	expect(placeInBand(point('c', 400, 90), ladder)).toMatchObject({ place: 'inside', distance: 0 });
	expect(placeInBand(point('d', 400, 41), ladder)).toMatchObject({ place: 'short', distance: 9 });
	expect(placeInBand(point('e', 400, 260), ladder)).toMatchObject({ place: 'long', distance: 170 });
	// The article's own length picks the band, so the same summary is short in
	// one rung and inside in another.
	expect(placeInBand(point('f', 40, 45), ladder)).toMatchObject({ place: 'inside' });
	expect(placeInBand(point('g', 400, 45), ladder)).toMatchObject({ place: 'short', distance: 5 });
	expect(placeInBand(point('h', 400, 70), [])).toBeNull();
});

test('every day of the window gets a column, including the days that published nothing', () => {
	const ladder: SummaryBand[] = [
		{ min_source_words: 0, target_words_min: 50, target_words_max: 90 }
	];
	const window = { start: '2026-08-26', end: '2026-08-28' };
	const point = (date: string, id: string, summary: number): CompressionPoint => ({
		date,
		item_id: id,
		source_words: 400,
		summary_words: summary,
		truncation_flagged: false
	});

	const placed = bandPlacements(
		[
			point('2026-08-26', 'a', 70),
			point('2026-08-26', 'b', 20),
			point('2026-08-28', 'c', 300),
			// Outside the window. A section that drew it would disagree with the
			// control the operator is looking at.
			point('2026-08-20', 'd', 70)
		],
		ladder,
		window
	);
	expect(placed.map((one) => one.item_id)).toEqual(['a', 'b', 'c']);

	// The middle day published nothing and still gets a column. A chart drawn
	// only over the days that have rows closes the gap a missed day left, and a
	// missed day is a fact the operator came here to see.
	expect(bandSplit(placed, window)).toEqual([
		{ date: '2026-08-26', inside: 1, short: 1, long: 0, items: 2 },
		{ date: '2026-08-27', inside: 0, short: 0, long: 0, items: 0 },
		{ date: '2026-08-28', inside: 0, short: 0, long: 1, items: 1 }
	]);

	// Worst first, and the inside rows are not outliers at all.
	const worst = bandOutliers(placed);
	expect(worst.map((one) => one.item_id)).toEqual(['c', 'b']);
	expect(worst.map((one) => one.distance)).toEqual([210, 30]);
});

test('two equal misses rank in a fixed order, so the page cannot move between builds', () => {
	const ladder: SummaryBand[] = [
		{ min_source_words: 0, target_words_min: 50, target_words_max: 90 }
	];
	const window = { start: '2026-08-26', end: '2026-08-28' };
	const point = (date: string, id: string, source: number): CompressionPoint => ({
		date,
		item_id: id,
		source_words: source,
		summary_words: 120,
		truncation_flagged: false
	});

	// Three articles 30 words past the same band. The longer article breaks the
	// tie, then the date, then the id - never the order they arrived in.
	const placed = bandPlacements(
		[point('2026-08-28', 'zzz', 400), point('2026-08-26', 'aaa', 400), point('2026-08-27', 'mid', 900)],
		ladder,
		window
	);
	expect(bandOutliers(placed).map((one) => one.item_id)).toEqual(['mid', 'aaa', 'zzz']);
	expect(bandOutliers([...placed].reverse()).map((one) => one.item_id)).toEqual([
		'mid',
		'aaa',
		'zzz'
	]);
});
