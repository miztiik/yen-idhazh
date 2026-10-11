import { expect, test } from './support/door-page';
import type { Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { shortDate } from '../src/lib/format';
import { daysBetween } from '../src/lib/charts/viewport';

/**
 * The throughput trend, held to the contract the timing trend above it holds.
 *
 * Two charts stacked on one page that hover differently cost the operator a
 * second guess, so this file asserts the same three things the timing trend
 * asserts of
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
) as {
	chart: { tick_density: number; readout_max_share: number };
	console: { window_presets: number[] };
};

const TICK_DENSITY = APPEARANCE.chart.tick_density;
const READOUT_MAX_SHARE = APPEARANCE.chart.readout_max_share;
/** The presets the one window control offers, read from the file that sets them
 * rather than written down here where an edit could drift them apart. */
const PRESETS = APPEARANCE.console.window_presets;

const PLOT = '[data-throughput="chart"] svg';

interface Candle {
	date: string;
	model: string | null;
}

/** The days the chart actually drew a candle for, oldest first. */
async function drawnDays(page: Page): Promise<Candle[]> {
	await expect(page.locator(PLOT)).toBeVisible();
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
	await expect(svg).toBeVisible();
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

/** Drive the one window control the page carries to a preset, and wait for the
 * page to agree it moved. The control is inert in the prerendered document, so
 * this also stands in for waiting on hydration. */
async function setWindow(page: Page, days: number) {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
	await expect(page.locator('[data-model-query="model-throughput"]')).toHaveAttribute('data-query-asked', String(days));
	await expect(page.locator('[data-model-query="model-throughput"]')).toHaveAttribute('data-query-state', 'ready');
}

test('the chart draws the selected window, not the whole published history', async ({ page }) => {
	await page.goto('/console/model/');
	// Inert until the page has hydrated, so waiting for it is waiting for the
	// control to be able to move the chart at all.
	await expect(page.locator(`[data-window-preset="${PRESETS[0]}"] input`)).toBeEnabled();

	const widest = Math.max(...PRESETS);
	const narrowest = Math.min(...PRESETS);
	expect(widest, 'a control with one preset cannot narrow anything').toBeGreaterThan(narrowest);

	await setWindow(page, widest);
	const wide = await axisDays(page);
	expect(
		wide.days,
		'the widest window drew one column or none, so there is nothing to narrow'
	).toBeGreaterThan(1);
	// The axis is a full calendar over its own range, so an empty day inside the
	// window is a column and not a bridge across the gap. Filtering the array to
	// the window left that behaviour with the component, which still expands its
	// own range - this is the second oracle for this row.
	expect(wide.days).toBe(daysBetween(wide.first, wide.last));

	await setWindow(page, narrowest);
	await expect(page.locator(PLOT)).toBeVisible();
	const narrow = await axisDays(page);

	// The row's whole point. Before this change the chart read `data.throughputDays`
	// straight and drew the same span at every preset; now it draws only the days
	// inside the chosen window, so the narrowest window draws strictly fewer.
	expect(narrow.days, 'the chart ignored the window and drew the whole history').toBeLessThan(
		wide.days
	);
	// It kept the newest day, the one the narrow window ends on, and dropped the
	// older day the window excludes.
	expect(narrow.last).toBe(wide.last);
	// Still a full calendar over its own, narrower, range.
	expect(narrow.days).toBe(daysBetween(narrow.first, narrow.last));
});

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

	// Days times series, the same count the timing trend asserts.
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
	await expect(page.locator('[data-model-query="model-throughput"]')).toHaveAttribute('data-query-state', 'ready');

	// The canary window has days, so this asserts the pair rather than the empty
	// branch: exactly one of the chart and the notice is on the page, never both
	// and never neither. A heading with nothing under it is the failure this
	// guards - the timing trend above says so in words when it has nothing, and
	// two adjacent charts that fail differently teach the operator nothing.
	const chart = await page.locator('[data-throughput="chart"]').count();
	const empty = await page.locator('[data-throughput="empty"]').count();
	expect(chart + empty).toBe(1);
	await expect(page.locator('h2', { hasText: 'Model tokens per second' })).toHaveCount(1);
});

test('the live throughput chart declares settings changes and the window median, not a model-step rule', async ({ page }) => {
	await page.goto('/console/model/');
	const drawn = await drawnDays(page);
	expect(drawn.length).toBeGreaterThan(0);
	await expect(page.locator('[data-throughput="chart"]')).toHaveAttribute('data-model-rule', /yes|no/);
	await expect(page.locator('[data-throughput-swap]')).toHaveCount(0);
	await expect(page.locator('[data-throughput-median]')).toHaveCount(1);
	await expect(page.locator('[data-throughput="verdict"]')).toContainText("window's median writing rate");
	const changes = await page.locator('[data-throughput="chart"] [data-model-rule-date]').evaluateAll((nodes) =>
		nodes.map((node) => node.getAttribute('data-model-rule-date')!));
	expect(changes.every((date) => drawn.some((day) => day.date === date))).toBe(true);
	if (changes.length === 0) await expect(page.locator('[data-model-rule-empty="model-throughput"]')).not.toHaveText('');
});
