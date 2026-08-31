/** The stage-timing chart's axis, its marks and the strip that reads them.
 *
 * The chart used to print one string for the whole span and no mark at any
 * point. So a spike could not be attributed to a date without counting columns
 * with a finger, and there was nothing to aim a pointer at. It also drew its
 * own span, so the control above it could read 30 days over a plot drawing 6.
 *
 * Measured on the built canary console page 2026-08-30, at the default 30-day
 * preset over 4 stages: 6 date labels where there was 1 span string, 9 marks
 * across 3 lines where there were 0, and a readout 0.330 of the plot wide
 * against a cap of 0.33 - the box it replaced measured 0.40 to 0.55. Every
 * count here is read off a fact the chart publishes about itself rather than
 * written down, so growing the fixture or moving the window cannot turn an
 * assertion into a tautology or a false failure.
 */

import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { dayColumnX, dayTicks, frame, readoutCapStyle, readoutMarks } from '../src/lib/charts/frame';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

interface ChartKnobs {
	tick_density: number;
	readout_max_share: number;
}

function knobs(): ChartKnobs {
	const parsed = JSON.parse(
		readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')
	) as { chart: ChartKnobs };
	return parsed.chart;
}

function days(start: string, count: number): string[] {
	const first = new Date(`${start}T00:00:00Z`);
	return Array.from({ length: count }, (_, step) => {
		const day = new Date(first);
		day.setUTCDate(day.getUTCDate() + step);
		return day.toISOString().slice(0, 10);
	});
}

test.describe('the day axis', () => {
	test('a window shorter than the density gets a label on every day', () => {
		expect(dayTicks([], 6)).toEqual([]);
		expect(dayTicks(days('2026-08-18', 3), 6).map((tick) => tick.index)).toEqual([0, 1, 2]);
		expect(dayTicks(days('2026-08-18', 6), 6).map((tick) => tick.index)).toEqual([
			0, 1, 2, 3, 4, 5
		]);
	});

	test('a longer window is thinned to the density, endpoints included', () => {
		const month = dayTicks(days('2026-08-01', 30), 6);
		expect(month).toHaveLength(6);
		expect(month.map((tick) => tick.index)).toEqual([0, 6, 12, 17, 23, 29]);
		expect(month[0].date).toBe('2026-08-01');
		expect(month[month.length - 1].date).toBe('2026-08-30');

		// The knob is the cap, so a lower one thins further and keeps both ends.
		const sparse = dayTicks(days('2026-08-01', 30), 3);
		expect(sparse.map((tick) => tick.index)).toEqual([0, 15, 29]);
	});

	test('one day is labelled once, in the middle, with its year', () => {
		expect(dayTicks(['2026-08-20'], 6)).toEqual([
			{ index: 0, date: '2026-08-20', text: '20 Aug 2026', anchor: 'middle' }
		]);
	});

	test('the year is printed where it changes and nowhere else', () => {
		const across = dayTicks(days('2025-12-20', 30), 6);
		const years = across.filter((tick) => /\d{4}$/.test(tick.text));
		// The first label always carries one, and the crossing carries the next.
		expect(years.length).toBeGreaterThanOrEqual(2);
		expect(across[0].text).toContain('2025');
		expect(across[across.length - 1].text).not.toContain('2025');
	});

	test('the ends anchor inwards so neither label hangs off the plot', () => {
		const week = dayTicks(days('2026-08-01', 10), 6);
		expect(week[0].anchor).toBe('start');
		expect(week[week.length - 1].anchor).toBe('end');
		for (const tick of week.slice(1, -1)) expect(tick.anchor).toBe('middle');
	});
});

test.describe('a day column', () => {
	const box = frame(760, 220);

	test('the first and last column sit on the plot edges', () => {
		expect(dayColumnX(0, 6, box)).toBe(box.left);
		expect(dayColumnX(5, 6, box)).toBe(box.right);
	});

	test('a pad pulls both ends inside, by the same amount', () => {
		expect(dayColumnX(0, 6, box, 8)).toBe(box.left + 8);
		expect(dayColumnX(5, 6, box, 8)).toBe(box.right - 8);
	});

	test('one column is drawn in the middle, not at the left edge', () => {
		expect(dayColumnX(0, 1, box)).toBe((box.left + box.right) / 2);
	});
});

test.describe('the readout strip', () => {
	test('the announcement is built from the rows the strip draws', () => {
		const marks = readoutMarks([
			{
				x: 12,
				date: '20 Aug 2026',
				rows: [
					{ label: 'fetch', value: '200 ms', colour: 'var(--series-1)' },
					{ label: 'summarize', value: 'not timed', colour: 'var(--series-3)' }
				]
			}
		]);
		expect(marks).toEqual([
			{ x: 12, lines: ['20 Aug 2026', 'fetch 200 ms', 'summarize not timed'] }
		]);
	});

	test('the cap is a share of the plot, and it is clamped to one', () => {
		expect(readoutCapStyle(0.33)).toBe('max-width: 33.00%');
		expect(readoutCapStyle(1.5)).toBe('max-width: 100.00%');
		expect(readoutCapStyle(-1)).toBe('max-width: 0.00%');
	});
});

test.describe('the timing chart on the page', () => {
	test('every column the density allows carries a date, and both ends do', async ({ page }) => {
		await page.goto('/console/');

		const plot = page.locator('[data-timing="plot"]');
		await expect(plot).toBeVisible();

		const drawn = Number(await plot.getAttribute('data-timing-days'));
		const first = await plot.getAttribute('data-timing-first');
		const last = await plot.getAttribute('data-timing-last');
		expect(drawn, 'the chart must publish how many days it drew').toBeGreaterThan(0);

		const labels = plot.locator('[data-timing-label]');
		const expected = Math.min(drawn, knobs().tick_density);
		await expect(labels, 'one date per column, capped by chart.tick_density').toHaveCount(expected);

		const dates = await labels.evaluateAll((nodes) =>
			nodes.map((node) => node.getAttribute('data-timing-label') ?? '')
		);
		expect(dates[0], 'the oldest day is always labelled').toBe(first);
		expect(dates[dates.length - 1], 'the newest day is always labelled').toBe(last);

		// The whole defect: one string for the span, so no column had a date.
		// `18-20 Aug 2026` is what that string looked like, and a single date
		// never carries a hyphen.
		const texts = await labels.evaluateAll((nodes) =>
			nodes.map((node) => node.textContent?.trim() ?? '')
		);
		for (const text of texts) expect(text, 'a column label is one date, never a span').not.toContain('-');
	});

	test('every plotted point carries a mark a pointer can land on', async ({ page }) => {
		await page.goto('/console/');

		const plot = page.locator('[data-timing="plot"]');
		const drawn = Number(await plot.getAttribute('data-timing-days'));
		const series = Number(await plot.getAttribute('data-timing-series'));
		expect(series, 'the chart must publish how many stages it drew').toBeGreaterThan(0);

		// A filled dot is a measured time, an open dot on the baseline is a
		// measured zero. Both are marks; a day a stage was never timed on has
		// neither, and the note under the chart says so.
		const marks = await plot.evaluate(
			(svg) => svg.querySelectorAll('circle[data-stage-mark], circle[data-stage-zero]').length
		);
		const lines = await plot.evaluate(
			(svg) => svg.querySelectorAll('polyline[data-stage-mark]').length
		);
		expect(lines, 'the lines are still drawn, the marks are added to them').toBeGreaterThan(0);
		expect(marks, 'a mark for every day of every stage the window timed').toBe(
			drawn * series - (await missing(page))
		);
		expect(marks).toBeGreaterThan(0);
	});

	test('the strip opens on the newest day and never covers the plot', async ({ page }) => {
		await page.goto('/console/');

		const plot = page.locator('[data-timing="plot"]');
		const strip = page.locator('[data-readout="timings"]');
		await expect(strip, 'the strip is on the page before anything is pointed at').toHaveCount(1);
		await expect(strip.locator('[data-readout-day]')).toContainText('the newest day');

		// No pointer, no guide: a line across the plot with nothing selected
		// would mark a column nobody chose.
		await expect(plot.locator('[data-timing="guide"]')).toHaveCount(0);

		const share = await page.evaluate(() => {
			const svg = document.querySelector('[data-timing="plot"]');
			const readout = document.querySelector('[data-readout="timings"]');
			if (!svg || !readout) return null;
			return readout.getBoundingClientRect().width / svg.getBoundingClientRect().width;
		});
		expect(share, 'the strip must have a laid-out width to measure').not.toBeNull();
		// A strip below the plot cannot occlude a mark at any width. The cap is
		// what stops it becoming a paragraph beside a chart being glanced at.
		expect(share ?? 1).toBeLessThanOrEqual(knobs().readout_max_share + 0.005);
	});

	test('the keyboard reaches every column and the guide follows it', async ({ page }) => {
		await page.goto('/console/');

		const plot = page.locator('[data-timing="plot"]');
		const drawn = Number(await plot.getAttribute('data-timing-days'));
		// Scoped to this chart's own strip. The throughput trend below carries a
		// readout of the same shape, so a bare attribute selector matches two.
		const day = page.locator('[data-readout="timings"] [data-readout-day]');

		await plot.focus();
		// Focus lands on the oldest column, so a keyboard reader starts where the
		// chart starts rather than wherever a mouse was last.
		await expect(day).toHaveText(await labelOf(page, 0));
		await expect(plot.locator('[data-timing="guide"]')).toHaveCount(1);

		const seen = new Set<string>();
		for (let step = 0; step < drawn; step += 1) {
			seen.add(((await day.textContent()) ?? '').trim());
			await page.keyboard.press('ArrowRight');
		}
		expect(seen.size, 'Right steps through every column, skipping none').toBe(drawn);

		await page.keyboard.press('End');
		const atEnd = ((await day.textContent()) ?? '').trim();
		await page.keyboard.press('Home');
		const atHome = ((await day.textContent()) ?? '').trim();
		expect(atEnd).not.toBe(atHome);

		// Escape does not blank the strip, it hands it back to the newest day.
		await page.keyboard.press('Escape');
		await expect(day).toContainText('the newest day');
		await expect(plot.locator('[data-timing="guide"]')).toHaveCount(0);
	});

	test('the columns are the window the control set, not the days with rows', async ({ page }) => {
		await page.goto('/console/');

		const control = page.locator('[data-window-control]');
		const plot = page.locator('[data-timing="plot"]');
		// Disabled until the page has mounted, so this is also the wait for the
		// control to be able to do anything at all.
		await expect(control.locator('input').first()).toBeEnabled();

		const presets = JSON.parse(
			readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')
		).console.window_presets as number[];
		expect(presets.length, 'one preset cannot disagree with anything').toBeGreaterThan(1);

		for (const preset of presets) {
			await page.locator(`[data-window-preset="${preset}"]`).click();
			await expect(control).toHaveAttribute('data-window-days', String(preset));
			// The chart used to build its calendar from its own first and last
			// dated row, so a control reading 30 sat above a plot drawing 6.
			await expect(plot, `the chart is drawing a span the control did not set`).toHaveAttribute(
				'data-timing-days',
				String(preset)
			);
			// And it draws that span from the right dates, not merely the right
			// number of them.
			const first = await plot.getAttribute('data-timing-first');
			const last = await plot.getAttribute('data-timing-last');
			expect(
				Math.round(
					(Date.parse(`${last}T00:00:00Z`) - Date.parse(`${first}T00:00:00Z`)) / 86_400_000
				) + 1,
				'the first and last column are not the ends of that span'
			).toBe(preset);
		}
	});
});

/** Days a stage was never timed on, counted off the notes the chart prints.
 *
 * The chart already names every absence in type. Reading the expectation from
 * there rather than from a number written here means a fixture that gains or
 * loses a gap moves both sides of the assertion at once.
 *
 * The whitespace is collapsed first. The sentence is built from two expressions
 * on two source lines, so the rendered text carries the newline between them
 * and a pattern written with a single space matches nothing - which reads as
 * "no day is missing" and inflates the expectation by exactly the number of
 * days it failed to see. So a sentence this cannot parse is an error and not a
 * zero: on a fixture with no gaps at all the two answers are the same number,
 * and a silent zero would be a passing test measuring nothing.
 */
async function missing(page: import('@playwright/test').Page): Promise<number> {
	const { blank, unparsed } = await page.evaluate(() => {
		let blank = 0;
		const unparsed: string[] = [];
		for (const note of document.querySelectorAll('[data-timing-note]')) {
			const text = (note.textContent ?? '').replace(/\s+/g, ' ');
			if (!text.includes('We timed no ')) continue;
			const match = text.match(/We timed no \w+ work on (\d+) of the \d+ days?/);
			if (match) blank += Number(match[1]);
			else unparsed.push(text);
		}
		return { blank, unparsed };
	});
	expect(unparsed, 'the chart reworded a note this count is read from').toEqual([]);
	return blank;
}

/** What the strip prints for a column, taken from the axis label at that index
 * where there is one - the two are the same date written the same way. */
async function labelOf(page: import('@playwright/test').Page, index: number): Promise<string> {
	const texts = await page
		.locator('[data-timing="plot"] [data-timing-label]')
		.evaluateAll((nodes) => nodes.map((node) => node.textContent?.trim() ?? ''));
	return texts[index];
}
