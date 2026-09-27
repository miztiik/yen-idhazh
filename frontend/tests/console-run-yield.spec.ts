import { expect, test } from '@playwright/test';

/**
 * THE ORACLE for the drawn half of the run-yield chart: the bars are grouped,
 * and the share axis does not follow the data.
 *
 * `run-yield.spec.ts` proves the arithmetic - one column a day, a null share
 * where nothing was planned, a share above one kept above one. It cannot prove
 * what the component does with those numbers, and both of the rules below are
 * rules about the drawing.
 *
 * **Grouped, never stacked.** `planned` and `failed` are summed over the day's
 * runs and `published` is the day's own published set, so the three overlap and
 * are not three parts of one total. A stack asserts a whole nobody measured. A
 * later edit could stack them and every arithmetic case above would stay green,
 * because the numbers would be unchanged - only the drawing would lie. The tell
 * is geometric and needs no fixture: a grouped bar starts at the baseline, so
 * every bar's bottom edge is the same y. Stack them and two of the three sit on
 * top of another bar instead.
 *
 * **A fixed share axis.** The count axis follows the window's peak and has to.
 * The share axis must not, or a month that published half its plan draws at the
 * same height as one that published all of it. Its labels are the assertion:
 * they are the same five whatever the day holds.
 *
 * Both cases read only properties the data cannot move, so no edit to the
 * committed tree can turn this file red (`CLAUDE.md` section 13).
 */

const PANEL = '[data-glance-chart="run-yield"]';
const PLOT = `${PANEL} svg[data-run-yield-chart]`;

/** A window wide enough that the three bars of a day are drawn at all. Below
 * 480px of panel width the chart keeps the planned bar and drops the other two
 * into the strip, which is a different rule with a different test. */
const DESKTOP = { width: 1440, height: 1000 };

test('the three bars of a day stand side by side on one baseline', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.goto('/console/');

	// A window nothing was planned in draws a sentence instead of a plot. That is
	// its own rule; there is nothing here to measure.
	if ((await page.locator(`${PANEL} [data-run-yield-empty]`).count()) > 0) {
		test.skip(true, 'this build planned no items in the window, so no bar is drawn');
	}

	const plot = page.locator(PLOT);
	await expect(plot, 'the run-yield chart is not on the page').toHaveCount(1);

	const bars = await plot.evaluate((svg) =>
		[...svg.querySelectorAll('rect[data-run-bar]')].map((node) => ({
			series: node.getAttribute('data-run-bar') ?? '',
			x: Number(node.getAttribute('x')),
			width: Number(node.getAttribute('width')),
			bottom: Number(node.getAttribute('y')) + Number(node.getAttribute('height'))
		}))
	);
	expect(bars.length, 'the chart drew no bar at all').toBeGreaterThan(0);

	// Every bar reaches the same floor. This is what a stack cannot do.
	const floors = new Set(bars.map((bar) => Math.round(bar.bottom * 10) / 10));
	expect([...floors], 'a bar starts somewhere other than the baseline').toHaveLength(1);

	// And where a day drew more than one series, they are beside each other
	// rather than over each other.
	for (const bar of bars) {
		for (const other of bars) {
			if (bar === other) continue;
			const overlaps = bar.x < other.x + other.width && other.x < bar.x + bar.width;
			expect(overlaps, `bars at x=${bar.x} and x=${other.x} share horizontal room`).toBe(false);
		}
	}
});

test('the share axis carries the same five labels whatever the window holds', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.goto('/console/');

	if ((await page.locator(`${PANEL} [data-run-yield-empty]`).count()) > 0) {
		test.skip(true, 'this build planned no items in the window, so no axis is drawn');
	}

	const ticks = page.locator(`${PLOT} [data-yield-tick]`);
	await expect(ticks).toHaveText(['0%', '25%', '50%', '75%', '100%']);

	// Move the window. A data-following axis would relabel; this one may not. A
	// preset the build planned nothing in draws no axis at all, which is the
	// empty rule rather than this one.
	const presets = page.locator('[data-window-preset]');
	const count = await presets.count();
	for (let at = 0; at < count; at += 1) {
		await presets.nth(at).click();
		if ((await page.locator(`${PANEL} [data-run-yield-empty]`).count()) > 0) continue;
		await expect(ticks).toHaveText(['0%', '25%', '50%', '75%', '100%']);
	}
});
