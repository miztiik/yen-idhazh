/** THE ORACLE for Row #12: a chart never draws a span nothing measured.
 *
 * Three console charts draw the window the control set rather than the days
 * their own data covers, which is right - narrowing the window would make a
 * seven-day record look like a thirty-day one. What was wrong is what they did
 * with the difference. Measured 2026-09-01 at 1440 on the built console:
 * `Time per item, by stage` drew a 1,292px plot with every mark between
 * x=1,030 and x=1,342 - 312px, 24 percent of the plot, all against the right
 * edge - because the window was 30 days and 8 carried a timing. `Failure rate
 * against volume` and `Summary length against the length asked for` drew
 * columns on the same 8 of 30. Nothing on any of the three said so, and a
 * pointer on one of the other 22 columns printed a row of blanks or a row of
 * zeros, which reads as a broken hover rather than as an empty day.
 *
 * The oracle is over the page, not over the rule: it counts the columns that
 * carry a mark itself, off the drawn geometry, and holds the chart's own
 * sentence to that count.
 *
 * It runs against the canary build. See `frontend/scripts/build-canary.mjs`.
 */

import { expect, test, type Locator, type Page } from '@playwright/test';
import { coverage, SPARSE_COVERAGE } from '../src/lib/charts/frame';

/** Every chart that declares a coverage sentence, and what it draws a mark
 * with. The selectors name a mark on the plot, never the sentence - the whole
 * point is that the count comes from the drawing. */
const CHARTS = [
	{
		name: 'timings',
		plot: '[data-timing="plot"]',
		readout: '[data-readout="timings"]',
		marks: 'circle[data-stage-mark], circle[data-stage-zero]',
		empty: 'Nothing was timed on this day'
	},
	{
		name: 'band-distance',
		plot: '[data-band-distance] svg',
		readout: '[data-readout="band-distance"]',
		marks: '[data-band-day] rect[data-band-part]',
		empty: 'Nothing was summarised on this day'
	},
	{
		name: 'failure-rate',
		plot: '[data-failure-chart]',
		readout: '[data-readout="failure-rate"]',
		marks: 'rect[data-band]',
		empty: 'No item was planned on this day'
	}
] as const;

/** Which columns of one chart carry a mark, by the x every mark sits on.
 *
 * Rounded to a tenth, because a stacked column's segments and a line's own dot
 * are drawn from the same column pixel through two different code paths and a
 * floating-point tail would count one column twice.
 */
async function columnsWithMarks(plot: Locator, marks: string): Promise<number> {
	return plot.evaluate((svg, selector) => {
		const xs = new Set<number>();
		for (const node of svg.querySelectorAll(selector)) {
			const at =
				node.tagName === 'circle'
					? Number(node.getAttribute('cx'))
					: Number(node.getAttribute('x')) + Number(node.getAttribute('width')) / 2;
			if (Number.isFinite(at)) xs.add(Math.round(at * 10) / 10);
		}
		return xs.size;
	}, marks);
}

/** The x of every column the chart tinted, so a mark can be checked against
 * them. Returned as spans in the chart's own pixels. */
async function tinted(plot: Locator): Promise<{ x: number; width: number }[]> {
	return plot.evaluate((svg) =>
		[...svg.querySelectorAll('rect[data-coverage-empty]')].map((node) => ({
			x: Number(node.getAttribute('x')),
			width: Number(node.getAttribute('width'))
		}))
	);
}

async function note(page: Page, name: string) {
	const strip = page.locator(`[data-coverage-note="${name}"]`);
	return {
		strip,
		days: Number(await strip.getAttribute('data-coverage-days')),
		measured: Number(await strip.getAttribute('data-coverage-measured')),
		text: ((await strip.textContent()) ?? '').replace(/\s+/g, ' ').trim()
	};
}

test('THE ORACLE: a chart that measured part of its window says which part', async ({ page }) => {
	await page.goto('/console/');

	let sparse = 0;
	for (const chart of CHARTS) {
		const plot = page.locator(chart.plot);
		await expect(plot, `${chart.name} is not on the page`).toHaveCount(1);

		const drawn = await columnsWithMarks(plot, chart.marks);
		const strip = page.locator(`[data-coverage-note="${chart.name}"]`);
		const declared = await strip.count();

		if (declared === 0) {
			// No sentence is a claim too: this chart measured enough of its window
			// that a break in a line is legible on its own.
			expect(await tinted(plot), `${chart.name} tints a span it never named`).toEqual([]);
			continue;
		}

		sparse += 1;
		const said = await note(page, chart.name);
		expect(
			said.measured,
			`${chart.name} says it measured ${said.measured} days and drew marks on ${drawn}`
		).toBe(drawn);
		expect(said.days, `${chart.name} draws no columns`).toBeGreaterThan(0);
		// The sentence names both numbers rather than a share, so a reader can
		// count the columns and check it (CLAUDE.md Rule #10).
		expect(said.text, 'the days measured is not in the sentence').toContain(String(said.measured));
		expect(said.text, 'the days drawn is not in the sentence').toContain(String(said.days));
		// And the sentence is only printed where the threshold says it should be.
		expect(
			said.measured / said.days,
			`${chart.name} explains a window it mostly measured`
		).toBeLessThan(SPARSE_COVERAGE);

		// The empty span is drawn, and it is drawn where the marks are not.
		const spans = await tinted(plot);
		expect(spans.length, `${chart.name} names an empty span and draws none`).toBeGreaterThan(0);
		for (const span of spans) expect(span.width).toBeGreaterThan(0);
		const marked = await plot.evaluate((svg, selector) => {
			const xs: number[] = [];
			for (const node of svg.querySelectorAll(selector)) {
				const at =
					node.tagName === 'circle'
						? Number(node.getAttribute('cx'))
						: Number(node.getAttribute('x')) + Number(node.getAttribute('width')) / 2;
				if (Number.isFinite(at)) xs.push(at);
			}
			return xs;
		}, chart.marks);
		for (const at of marked) {
			for (const span of spans) {
				expect(
					at > span.x && at < span.x + span.width,
					`${chart.name} tints a column it drew a mark on`
				).toBe(false);
			}
		}
	}

	expect(
		sparse,
		'no chart in this build measured less than its window, so the oracle asserts nothing'
	).toBeGreaterThan(0);
});

test('a pointer on an unmeasured column is told the day was not measured', async ({ page }) => {
	await page.goto('/console/');

	let checked = 0;
	for (const chart of CHARTS) {
		if ((await page.locator(`[data-coverage-note="${chart.name}"]`).count()) === 0) continue;

		const plot = page.locator(chart.plot);
		const readout = page.locator(chart.readout);
		// Focus lands on the oldest column. On a chart whose record starts inside
		// the window that column is one nothing measured, which is exactly the
		// case this row exists for.
		await plot.focus();
		const rows = readout.locator('[data-readout-row]');
		await expect(rows.first()).toBeVisible();
		const labels = await rows.evaluateAll((nodes) =>
			nodes.map((node) => node.getAttribute('data-readout-row') ?? '')
		);
		if (!labels.includes(chart.empty)) {
			// The oldest column carries data in this build. Nothing is wrong; this
			// chart just has no unmeasured column to land on.
			continue;
		}
		checked += 1;

		// One sentence, and not a set of blanks or a set of zeros beside it. A
		// zero here would say the day was measured and came out empty.
		expect(labels, `${chart.name} prints its series beside "nothing measured"`).toEqual([
			chart.empty
		]);
		const values = await rows.evaluateAll((nodes) =>
			nodes.map((node) => (node.querySelectorAll('dd')[1]?.textContent ?? '').trim())
		);
		expect(values, 'the row carries a value where it has nothing to report').toEqual(['']);

		// And stepping onto a measured column brings the series back, so the state
		// is a property of the column and not of the chart.
		for (let step = 0; step < 40; step += 1) await page.keyboard.press('ArrowRight');
		const atEnd = await rows.evaluateAll((nodes) =>
			nodes.map((node) => node.getAttribute('data-readout-row') ?? '')
		);
		expect(atEnd, `${chart.name} never leaves the unmeasured state`).not.toEqual([chart.empty]);
	}

	expect(
		checked,
		'no chart opened on an unmeasured column, so the readout state is untested'
	).toBeGreaterThan(0);
});

test.describe('the coverage rule itself', () => {
	test('it counts the columns and finds every gap', () => {
		const all = coverage([true, true, true]);
		expect(all).toEqual({ days: 3, measured: 3, sparse: false, gaps: [] });

		const some = coverage([false, false, true, false, true, false]);
		expect(some.days).toBe(6);
		expect(some.measured).toBe(2);
		expect(some.gaps).toEqual([
			[0, 1],
			[3, 3],
			[5, 5]
		]);
	});

	test('an empty chart is not a sparse one', () => {
		// Nothing at all is the panel's own empty state, in words, and a tinted
		// span across a plot with no axis on it explains nothing.
		expect(coverage([]).sparse).toBe(false);
		expect(coverage([false, false, false]).sparse).toBe(false);
	});

	test('the threshold is the line, and it is declared', () => {
		expect(SPARSE_COVERAGE).toBeGreaterThan(0);
		expect(SPARSE_COVERAGE).toBeLessThan(1);
		const under = Array.from({ length: 10 }, (_, index) => index < 4);
		const over = Array.from({ length: 10 }, (_, index) => index < 6);
		expect(under.filter(Boolean).length / 10).toBeLessThan(SPARSE_COVERAGE);
		expect(coverage(under).sparse).toBe(true);
		expect(over.filter(Boolean).length / 10).toBeGreaterThanOrEqual(SPARSE_COVERAGE);
		expect(coverage(over).sparse).toBe(false);
	});
});
