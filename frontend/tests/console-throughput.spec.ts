import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { shortDate } from '../src/lib/format';

/**
 * The throughput trend, held to the contract the timing trend above it holds.
 *
 * Two charts stacked on one page that hover differently cost the operator a
 * second guess, so this file asserts the same three things row #4 asserts of
 * `Time per item, by stage`, against `Model tokens per second`: a date per
 * column, a mark on every plotted point, and a readout that cannot cover the
 * marks it explains.
 *
 * Measured 2026-08-30 by building the canary console twice from one tree, once
 * with the component as it stood before this row and once after: the throughput
 * axis went from 6 text nodes carrying 0 per-day labels to 7 carrying 2, over a
 * canary of 2 days. Five of those nodes are the y axis's own ticks either way,
 * so what changed is one span written as a single string becoming one date per
 * column.
 *
 * Every expectation below is derived from what the page itself published - the
 * day count and the two end dates on the `<svg>`, the plot width on the
 * `<svg>`, the cap on the `<svg>`. A test that hard-codes a date passes until
 * the fixture moves and then reports a defect that is not there.
 */

const APPEARANCE = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
) as { chart: { tick_density: number; readout_max_share: number } };

const TICK_DENSITY = APPEARANCE.chart.tick_density;
const READOUT_MAX_SHARE = APPEARANCE.chart.readout_max_share;

const PLOT = '[data-throughput="chart"] svg';

interface Candle {
	date: string;
	model: string | null;
}

/** The days the chart actually drew a candle for, oldest first. */
async function drawnDays(page: Page): Promise<Candle[]> {
	return page.locator('[data-candle="read"]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			date: node.getAttribute('data-date') ?? '',
			model: node.getAttribute('data-model')
		}))
	);
}

/** The columns the axis spans, which is the calendar and not the days that ran.
 * The chart publishes it, so the count cannot rot when the fixture moves. */
async function axisDays(page: Page): Promise<{ days: number; first: string; last: string }> {
	const svg = page.locator(PLOT);
	return {
		days: Number(await svg.getAttribute('data-throughput-days')),
		first: (await svg.getAttribute('data-throughput-first')) ?? '',
		last: (await svg.getAttribute('data-throughput-last')) ?? ''
	};
}

async function box(page: Page, selector: string) {
	const found = await page.locator(selector).boundingBox();
	expect(found, `${selector} has no box`).not.toBeNull();
	return found as { x: number; y: number; width: number; height: number };
}

test('the axis names a day per column, thinned to the density knob', async ({ page }) => {
	await page.goto('/console/model/');

	const { days, first, last } = await axisDays(page);
	expect(days, 'the chart drew no columns, so there is no axis to check').toBeGreaterThan(0);

	const labels = await page
		.locator('[data-throughput-label]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-throughput-label') ?? ''));

	// The rule: one label per column, capped by the knob. The chart drew a single
	// span string and no per-day label at all until 2026-08-30.
	expect(labels.length).toBe(Math.min(days, TICK_DENSITY));

	// Both ends always, because the ends are what a reader anchors the span on.
	expect(labels[0]).toBe(first);
	expect(labels[labels.length - 1]).toBe(last);

	// In order, and no column labelled twice.
	expect([...labels].sort()).toEqual(labels);
	expect(new Set(labels).size).toBe(labels.length);

	// The span left the axis and has to still be somewhere a screen reader lands.
	const described = await page.locator(PLOT).getAttribute('aria-label');
	expect(described).toContain(shortDate(first));
	expect(described).toContain(shortDate(last));
});

test('every plotted day carries a mark to aim at, in every series', async ({ page }) => {
	await page.goto('/console/model/');

	const drawn = await drawnDays(page);
	expect(drawn.length, 'no candles drew').toBeGreaterThan(0);

	const series = await page
		.locator('[data-candle]')
		.evaluateAll((nodes) =>
			[...new Set(nodes.map((node) => node.getAttribute('data-candle') ?? ''))].sort()
		);
	expect(series.length, 'no series drew').toBeGreaterThan(0);

	// Days times series, the same count row #4 asserts of the timing trend.
	await expect(page.locator('[data-candle]')).toHaveCount(drawn.length * series.length);

	// A candle carries a middle-half box, so a day cannot draw a bare whisker and
	// still count as a mark somebody can read a number off.
	await expect(page.locator('[data-candle="read"] rect')).toHaveCount(drawn.length);
});

test('the readout sits below the plot and stays inside its share of it', async ({ page }) => {
	await page.goto('/console/model/');

	const readout = page.locator('[data-readout="throughput"]');

	// It opens on the newest day rather than blank, so the strip never appears
	// under the pointer and pushes the marks it explains out from under it.
	await expect(readout).toHaveCount(1);
	await expect(readout.locator('[data-readout-day]')).toContainText('the newest day');
	await expect(page.locator('[data-throughput="guide"]')).toHaveCount(0);

	// The cap the component drew with, not a number copied into this file.
	const plot = await box(page, PLOT);
	const strip = await box(page, '[data-readout="throughput"]');

	// Below the plot, so occlusion is zero rather than small. Measured at 40 to
	// 55 percent of the plot on 2026-08-29, when the box floated over it.
	expect(strip.y).toBeGreaterThanOrEqual(plot.y + plot.height - 1);
	// Against the drawn width of the plot, which is how the timing chart above
	// measures the same cap. Two charts held to one knob have to measure it one
	// way, or the number in `config/appearance.json` means two things.
	expect(strip.width / plot.width).toBeLessThanOrEqual(READOUT_MAX_SHARE + 0.005);
});

test('the keyboard reaches every column, and Escape gives the newest day back', async ({
	page
}) => {
	await page.goto('/console/model/');

	const { days, last } = await axisDays(page);
	const svg = page.locator(PLOT);
	await expect(svg).toHaveAttribute('tabindex', '0');

	const readout = page.locator('[data-readout="throughput"]');
	const heading = readout.locator('[data-readout-day]');

	// Focus is driven from inside the page: the integrated browser runs a hidden
	// page, where the stability check behind a real click never resolves.
	await svg.evaluate((node: SVGSVGElement) => node.focus());
	await expect(page.locator('[data-throughput="guide"]')).toHaveCount(1);

	// Home, then one step right per remaining column. Every column must produce
	// its own heading - a step that lands on the column it came from is a day the
	// keyboard cannot reach.
	await page.keyboard.press('Home');
	const seen: string[] = [];
	for (let step = 0; step < days; step += 1) {
		seen.push((await heading.innerText()).trim());
		if (step < days - 1) await page.keyboard.press('ArrowRight');
	}
	expect(new Set(seen).size).toBe(days);

	// End lands on the newest, which is where an operator looks first.
	await page.keyboard.press('End');
	await expect(heading).toContainText(shortDate(last));

	// Escape gives the resting strip back rather than emptying it. A strip that
	// vanished would move the page under the pointer that was reading it.
	await page.keyboard.press('Escape');
	await expect(readout).toHaveCount(1);
	await expect(heading).toContainText('the newest day');
	await expect(page.locator('[data-throughput="guide"]')).toHaveCount(0);
});

test('the heading survives a window with nothing in it, and says so', async ({ page }) => {
	await page.goto('/console/model/');

	// The canary window has days, so this asserts the pair rather than the empty
	// branch: exactly one of the chart and the notice is on the page, never both
	// and never neither. A heading with nothing under it is the failure this
	// guards - the timing trend above says so in words when it has nothing, and
	// two adjacent charts that fail differently teach the operator nothing.
	const chart = await page.locator('[data-throughput="chart"]').count();
	const empty = await page.locator('[data-throughput="empty"]').count();
	expect(chart + empty).toBe(1);
	await expect(page.locator('h3', { hasText: 'Model tokens per second' })).toHaveCount(1);
});

test('a day whose model differs from the day before it draws a rule', async ({ page }) => {
	await page.goto('/console/model/');

	const drawn = await drawnDays(page);

	// Every candle carries the attribute the rule reads, or the rest of this test
	// would pass on a chart that had stopped looking at models at all. The canary
	// scores name none, so the value is the empty string - the binding running is
	// what this half proves, not the name.
	expect(drawn.length).toBeGreaterThan(0);
	expect(drawn.every((day) => day.model !== null)).toBe(true);

	// Both models named, or there is nothing to compare - the same rule the
	// verdict sentence uses. An unknown model ends the comparison.
	const expected = drawn
		.filter(
			(day, index) =>
				index > 0 &&
				day.model !== '' &&
				day.model !== null &&
				drawn[index - 1].model !== '' &&
				drawn[index - 1].model !== null &&
				day.model !== drawn[index - 1].model
		)
		.map((day) => day.date);

	const rules = await page
		.locator('[data-throughput-swap]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-throughput-swap') ?? ''));
	expect(rules).toEqual(expected);

	// A key only where a rule was drawn. A legend entry for a mark that is not on
	// the chart sends a reader looking for something that is not there.
	await expect(page.locator('[data-series="swap"]')).toHaveCount(expected.length > 0 ? 1 : 0);

	// The canary's throughput days are older than the first row in the scores
	// ledger, so no day here names a model, `expected` is empty, and the two
	// assertions above cannot watch a rule being drawn. On the published console
	// they can and do: the committed ledger names `qwen3-8b-q4-k-m` to
	// 2026-08-26 and `qwen3-5-9b-q4-k-m` from 2026-08-27, and the production
	// build drew exactly one rule, on 2026-08-27, measured 2026-08-30. This
	// early return is where the canary stops being able to check it - the
	// assertions below run unchanged the day the fixture carries two names.
	if (expected.length === 0) return;

	// The rule says which two models, so the step is attributable rather than
	// merely marked.
	const first = page.locator(`[data-throughput-swap="${rules[0]}"] title`);
	await expect(first).toHaveText(/Model changed from .+ to .+ on \d{4}-\d{2}-\d{2}\./);
});
