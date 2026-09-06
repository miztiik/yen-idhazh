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
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
	coverage,
	coverageSentence,
	dayColumns,
	dayColumnX,
	dayTicks,
	frame,
	readoutCapStyle
} from '../src/lib/charts/frame';
import { readCsv } from '../src/lib/server/payload';

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

/** A plot wide enough that the fit never bites, so a test about the ceiling is
 * about the ceiling. 4,000px is over twice the widest window this ships in. */
function roomy(count: number): number[] {
	return Array.from({ length: count }, (_, index) => index * (4000 / Math.max(1, count - 1)));
}

/** Every date a tick carries a label for, in order. */
function labelled(ticks: { text: string }[]): string[] {
	return ticks.filter((tick) => tick.text !== '').map((tick) => tick.text);
}

test.describe('the day axis', () => {
	test('a window shorter than the density gets a label on every day', () => {
		expect(dayTicks([], { density: 6, columns: [] })).toEqual([]);
		expect(
			dayTicks(days('2026-08-18', 3), { density: 6, columns: roomy(3) }).map((tick) => tick.index)
		).toEqual([0, 1, 2]);
		expect(
			dayTicks(days('2026-08-18', 6), { density: 6, columns: roomy(6) }).map((tick) => tick.index)
		).toEqual([0, 1, 2, 3, 4, 5]);
	});

	test('a longer window is thinned to the density, endpoints included', () => {
		const month = dayTicks(days('2026-08-01', 30), { density: 6, columns: roomy(30) });
		expect(month).toHaveLength(6);
		expect(month.map((tick) => tick.index)).toEqual([0, 6, 12, 17, 23, 29]);
		expect(month[0].date).toBe('2026-08-01');
		expect(month[month.length - 1].date).toBe('2026-08-30');

		// The knob is the ceiling, so a lower one thins further and keeps both ends.
		const sparse = dayTicks(days('2026-08-01', 30), { density: 3, columns: roomy(30) });
		expect(sparse.map((tick) => tick.index)).toEqual([0, 15, 29]);
	});

	test('the ceiling is a ceiling, and the room decides the rest', () => {
		const dates = days('2026-08-01', 30);
		// 320px is about the plot a 390px phone gives this chart. Six dates at
		// `20 Aug 2026` need over 330px of text alone, so they cannot all be drawn.
		const phone = dayTicks(dates, {
			density: 6,
			columns: Array.from({ length: 30 }, (_, index) => (index * 320) / 29)
		});
		expect(phone, 'every column the ceiling allows still carries a mark').toHaveLength(6);
		expect(labelled(phone).length, 'and fewer of them carry a date').toBeLessThan(6);

		// The two ends survive as long as anything does, so the span of the chart
		// can still be read off the chart.
		expect(phone[0].text).not.toBe('');
		expect(phone[phone.length - 1].text).not.toBe('');

		// A wider plot of the same days carries more. That is the whole rule: one
		// count cannot hold at 1440 and at 390.
		const desktop = dayTicks(dates, { density: 6, columns: roomy(30) });
		expect(labelled(desktop).length).toBeGreaterThan(labelled(phone).length);
	});

	test('a dropped label keeps its tick mark, and prints nothing', () => {
		// A date is about 64px and the rule wants 8px between two of them, so 40px
		// of plot cannot carry even the two ends.
		const crowded = dayTicks(days('2026-08-01', 30), {
			density: 6,
			columns: Array.from({ length: 30 }, (_, index) => (index * 40) / 29)
		});
		expect(crowded, 'the grid does not change shape as the window does').toHaveLength(6);
		// The newest day is the one an operator reads first, so it is the survivor.
		expect(labelled(crowded)).toEqual(['30 Aug 2026']);
		expect(crowded[crowded.length - 1].anchor).toBe('end');
	});

	test('one day is labelled once, in the middle, with its year', () => {
		expect(dayTicks(['2026-08-20'], { density: 6, columns: [0] })).toEqual([
			{ index: 0, date: '2026-08-20', text: '20 Aug 2026', anchor: 'middle' }
		]);
	});

	test('the year is printed where it changes and nowhere else', () => {
		const across = dayTicks(days('2025-12-20', 30), { density: 6, columns: roomy(30) });
		const years = across.filter((tick) => /\d{4}$/.test(tick.text));
		// The first label always carries one, and the crossing carries the next.
		expect(years.length).toBeGreaterThanOrEqual(2);
		expect(across[0].text).toContain('2025');
		expect(across[across.length - 1].text).not.toContain('2025');
	});

	test('the ends anchor inwards so neither label hangs off the plot', () => {
		const week = dayTicks(days('2026-08-01', 10), { density: 6, columns: roomy(10) });
		expect(week[0].anchor).toBe('start');
		expect(week[week.length - 1].anchor).toBe('end');
		for (const tick of week.slice(1, -1)) expect(tick.anchor).toBe('middle');
	});

	test('the columns come from the same function the marks do', () => {
		const box = frame(760, 220);
		const columns = dayColumns(6, box);
		expect(columns).toEqual([0, 1, 2, 3, 4, 5].map((index) => dayColumnX(index, 6, box)));
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
	// The strip used to carry a second test here, asserting that `readoutMarks`
	// preformatted one sentence per series onto every mark. Nothing printed those
	// sentences - `ChartReadout.svelte` is the live region and it prints the rows
	// - so the field went on 2026-09-06 and this test went with it. Which column
	// a mark stands for is now held in `frame.spec.ts`, against the walk it
	// replaced.

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
		const ceiling = Math.min(drawn, knobs().tick_density);
		const shown = await labels.count();
		expect(shown, 'chart.tick_density is the ceiling on dates, never the target').toBeLessThanOrEqual(
			ceiling
		);
		expect(shown, 'both ends always carry a date').toBeGreaterThanOrEqual(2);

		// Every column the ceiling allows keeps its mark, whether or not its date
		// survived the fit. A reader counting columns needs the grid.
		await expect(plot.locator('[data-day-tick]')).toHaveCount(ceiling);

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
		const series = Number(await plot.getAttribute('data-timing-series'));
		expect(series, 'the chart must publish how many stages it drew').toBeGreaterThan(0);

		// A filled dot is a measured time, an open dot on the baseline is a
		// measured zero. Both are marks; a day a stage was never timed on has
		// neither.
		const marks = await plot.evaluate(
			(svg) => svg.querySelectorAll('circle[data-stage-mark], circle[data-stage-zero]').length
		);
		const lines = await plot.evaluate(
			(svg) => svg.querySelectorAll('polyline[data-stage-mark]').length
		);
		expect(lines, 'the lines are still drawn, the marks are added to them').toBeGreaterThan(0);
		expect(marks).toBeGreaterThan(0);

		// The columns those marks sit on, against the days the chart says it
		// timed. Geometry, not a note: a mark drawn on a day nothing was timed on
		// is the defect, and it would still carry the right count.
		const columns = await plot.evaluate(
			(svg) =>
				new Set(
					[...svg.querySelectorAll('circle[data-stage-mark], circle[data-stage-zero]')].map(
						(node) => Math.round(Number(node.getAttribute('cx')) * 10) / 10
					)
				).size
		);
		expect(columns, 'a mark is drawn on a column the chart says it never timed').toBe(
			await timedDays(page)
		);
		// And no mark falls inside a span the chart tinted as unmeasured.
		const stray = await plot.evaluate((svg) => {
			const spans = [...svg.querySelectorAll('rect[data-coverage-empty]')].map((node) => ({
				from: Number(node.getAttribute('x')),
				to: Number(node.getAttribute('x')) + Number(node.getAttribute('width'))
			}));
			return [...svg.querySelectorAll('circle[data-stage-mark], circle[data-stage-zero]')].filter(
				(node) => {
					const at = Number(node.getAttribute('cx'));
					return spans.some((span) => at > span.from && at < span.to);
				}
			).length;
		});
		expect(stray, 'a mark is drawn inside a span the chart tinted as unmeasured').toBe(0);
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

test.describe('the coverage sentence', () => {
	test('THE ORACLE: one sentence, whatever the series count, with both its numbers', async ({
		page
	}) => {
		await page.goto('/console/');

		// It was one note per stage under the plot, and the three said one
		// window-level fact three times in near-identical words - so a fourth stage
		// would have made it four. The count is the defect, not the length.
		const one = page.locator('[data-timing-coverage]');
		await expect(one, 'the chart prints more than one coverage sentence').toHaveCount(1);
		await expect(page.locator('[data-timing-note]'), 'a per-series note survived').toHaveCount(0);

		const plot = page.locator('[data-timing="plot"]');
		const from = (await plot.getAttribute('data-timing-first')) ?? '';
		const to = (await plot.getAttribute('data-timing-last')) ?? '';
		const want = timedInWindow(from, to);
		expect(want.days, 'the fixture window times every day, so the sentence is untested').toBeGreaterThan(
			0
		);

		// Read from the ledger, not from the chart. Both numbers are printed
		// because a share cannot be checked against columns a reader can count
		// (CLAUDE.md Rule #10).
		expect(Number(await one.getAttribute('data-coverage-measured'))).toBe(want.days);
		expect(Number(await one.getAttribute('data-coverage-items'))).toBe(want.items);
		expect(Number(await one.getAttribute('data-coverage-timed-low'))).toBe(want.low);
		expect(Number(await one.getAttribute('data-coverage-timed-high'))).toBe(want.high);

		const said = ((await one.textContent()) ?? '').replace(/\s+/g, ' ').trim();
		expect(said).toContain(`${want.days} of these ${await plot.getAttribute('data-timing-days')} days`);
		expect(said).toContain(`of the ${group(want.items)} items on them`);
		// The denominator is the day's own item count, never the sum of the three
		// stages' totals: one item waits on all three, so summing counts it three
		// times over.
		expect(want.items, 'the denominator triple-counts the items').toBeLessThan(
			want.low + want.high + want.low
		);
	});

	test('the sentence says nothing where the window was timed in full', () => {
		const full = coverage([true, true, true, true]);
		expect(coverageSentence(full, 'We timed', { low: 9, high: 9, total: 9 })).toBeNull();
	});

	test('where two stages disagree the numerator is a range', () => {
		const sparse = coverage([true, false, false, false]);
		expect(coverageSentence(sparse, 'We timed', { low: 3900, high: 3955, total: 5113 })).toBe(
			'We timed 1 of these 4 days, and 3,900 to 3,955 of the 5,113 items on them. The tinted span is days nothing recorded, not quiet days.'
		);
		// And where they agree it is one number, not a range with two equal ends.
		expect(coverageSentence(sparse, 'We timed', { low: 3955, high: 3955, total: 5113 })).toBe(
			'We timed 1 of these 4 days, and 3,955 of the 5,113 items on them. The tinted span is days nothing recorded, not quiet days.'
		);
	});

	test('the open-dot legend is printed once, and only where an open dot is drawn', async ({
		page
	}) => {
		await page.goto('/console/');
		const zeros = await page
			.locator('[data-timing="plot"]')
			.evaluate((svg) => svg.querySelectorAll('circle[data-stage-zero]').length);
		await expect(page.locator('[data-timing-zero-key]')).toHaveCount(zeros > 0 ? 1 : 0);
	});
});

/** Every item-health row the canary wrote. */
function ledger(): Record<string, string>[] {
	const dir = join(REPO, 'backend', 'var', 'canary', 'state', 'item-health');
	return readdirSync(dir)
		.filter((name) => name.endsWith('.csv'))
		.flatMap((name) => readCsv(join(dir, name)).rows);
}

const STAGES = ['fetch_ms', 'extract_ms', 'summarize_ms'] as const;

/** What the chart's sentence has to say, recomputed from the CSV.
 *
 * A day counts as timed where any of the three stages has a millisecond on it,
 * which is the same rule the page keeps - and the same rule stated twice from
 * two readings of one file is what makes this an oracle rather than a copy.
 * The stage count appears nowhere: it is the thing that must have stopped
 * mattering.
 */
function timedInWindow(
	from: string,
	to: string
): { days: number; items: number; low: number; high: number } {
	const byDay = new Map<string, Record<string, string>[]>();
	for (const row of ledger()) {
		if (row.date < from || row.date > to) continue;
		byDay.set(row.date, [...(byDay.get(row.date) ?? []), row]);
	}
	const counted = (rows: Record<string, string>[], column: string) =>
		rows.filter((row) => (row[column] ?? '') !== '').length;

	const timed = [...byDay.values()].filter((rows) =>
		STAGES.some((column) => counted(rows, column) > 0)
	);
	const perStage = STAGES.map((column) =>
		timed.reduce((total, rows) => total + counted(rows, column), 0)
	).filter((total) => total > 0);
	return {
		days: timed.length,
		items: timed.reduce((total, rows) => total + rows.length, 0),
		low: perStage.length === 0 ? 0 : Math.min(...perStage),
		high: perStage.length === 0 ? 0 : Math.max(...perStage)
	};
}

function group(value: number): string {
	return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/** How many of the window's days the chart says it timed.
 *
 * Read off the one coverage sentence rather than counted here, so a fixture
 * that gains or loses a day moves both sides of an assertion at once. Absent
 * where the chart timed every day of its window, and then the answer is the
 * window itself.
 */
async function timedDays(page: import('@playwright/test').Page): Promise<number> {
	const strip = page.locator('[data-coverage-note="timings"]');
	if ((await strip.count()) === 0) {
		return Number(await page.locator('[data-timing="plot"]').getAttribute('data-timing-days'));
	}
	return Number(await strip.getAttribute('data-coverage-measured'));
}

/** What the strip prints for a column, taken from the axis label at that index
 * where there is one - the two are the same date written the same way. */
async function labelOf(page: import('@playwright/test').Page, index: number): Promise<string> {
	const texts = await page
		.locator('[data-timing="plot"] [data-timing-label]')
		.evaluateAll((nodes) => nodes.map((node) => node.textContent?.trim() ?? ''));
	return texts[index];
}
