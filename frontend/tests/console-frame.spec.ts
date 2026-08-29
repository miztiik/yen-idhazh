import { expect, test } from '@playwright/test';
import { cellFor, CELL_PX, GAP_PX } from '../src/lib/charts/run-history';

/**
 * The console's frame, measured rather than looked at.
 *
 * Two things this row promised and neither is visible in a screenshot: nothing
 * scrolls sideways on a desktop, and no chart is drawn so small that reading a
 * value off it is guesswork. Both were true of the page before this row - seven
 * horizontal scrollbars, and three charts at 164px each inside a 624px column -
 * and both are the kind of regression that arrives quietly with the next table.
 */

const DESKTOP = { width: 1440, height: 900 };

test.describe('the run strip uses the room it has', () => {
	test('an unmeasured strip still draws at the fixed pair', () => {
		// The server has no width. Deriving a cell from null must not yield zero,
		// or the prerendered strip is invisible until JavaScript runs.
		const metrics = cellFor(null, 30);
		expect(metrics.cell).toBe(CELL_PX);
		expect(metrics.gap).toBe(GAP_PX);
	});

	test('a wide frame grows the day column, up to a limit', () => {
		const narrow = cellFor(400, 30);
		const wide = cellFor(1400, 30);
		expect(wide.cell).toBeGreaterThan(narrow.cell);
		// Past a point a sequence stops reading as a sequence and starts reading
		// as a row of tiles, so the growth is bounded.
		expect(cellFor(9000, 4).cell).toBeLessThanOrEqual(34);
	});

	test('a crowded strip holds the pair it has always used, and scrolls instead', () => {
		// It grows into room and never shrinks out of it. Shrinking would let a
		// wide window quietly change what a phone does: there the strip scrolls
		// and opens on the newest run, which is a behaviour rather than a side
		// effect of the cell happening to be 16.
		const metrics = cellFor(300, 90);
		expect(metrics.cell).toBe(CELL_PX);
		expect(metrics.gap).toBe(GAP_PX);
	});

	test('the gap keeps its share, so the rhythm survives the resize', () => {
		// Two days apart must measure twice one day apart at every size, which is
		// only true if the gap scales with the cell rather than staying put.
		for (const width of [400, 800, 1400]) {
			const m = cellFor(width, 30);
			expect(m.gap / m.cell).toBeCloseTo(GAP_PX / CELL_PX, 1);
		}
	});
});

test.describe('the console frame', () => {
	test('nothing scrolls sideways on a desktop', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/');
		await page.waitForTimeout(600);

		const overflowing = await page.evaluate(() => {
			const bad: string[] = [];
			for (const el of document.querySelectorAll<HTMLElement>('*')) {
				const style = getComputedStyle(el);
				if (!/auto|scroll/.test(style.overflowX)) continue;
				// A container that CAN scroll is fine. One that HAS to is the fault.
				if (el.scrollWidth > el.clientWidth + 1) {
					bad.push(
						`${el.tagName.toLowerCase()}${el.className ? '.' + String(el.className).split(' ')[0] : ''} ${el.scrollWidth}>${el.clientWidth}`
					);
				}
			}
			return bad;
		});

		expect(overflowing, 'these containers must scroll sideways at 1440px').toEqual([]);
	});

	test('every chart you read a value off is drawn wide enough to read it', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/');
		await page.waitForTimeout(800);

		const charts = await page.evaluate(() =>
			[...document.querySelectorAll('figure svg, [data-glance-chart] svg, [data-timing="plot"]')]
				// A sparkline is deliberately small and carries no axis, no gridline
				// and no label - it shows direction, and the number beside it says how
				// much. Holding it to a width meant for a plot with an axis is a
				// category error, not a standard.
				.filter((svg) => svg.closest('[data-kpi]') === null)
				.map((svg) => {
					const owner = svg.closest('[data-glance-chart], [data-console-panel], figure, section');
					return {
						where:
							owner?.getAttribute('data-glance-chart') ??
							owner?.getAttribute('data-console-panel') ??
							owner?.getAttribute('aria-label') ??
							svg.getAttribute('aria-label') ??
							'unnamed',
						width: Math.round(svg.getBoundingClientRect().width)
					};
				})
				.filter((c) => c.width > 0)
		);

		expect(charts.length, 'no chart found - the scan is broken').toBeGreaterThan(0);
		// 164px was the measured width of three charts squeezed side by side into
		// a 624px column, and it is the number this bound exists to forbid.
		const narrow = charts.filter((c) => c.width < 320);
		expect(narrow, 'these charts are too narrow to read a value off').toEqual([]);
	});

	test('the page is one column of panels, not a wall of headings', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/');
		// `data-console-panel`, not `data-panel`: FailurePanels already carried the
		// shorter name, so the obvious selector passed before a single panel
		// existed. A test that cannot fail is not a test.
		const panels = await page.locator('[data-console-panel]').count();
		expect(panels).toBeGreaterThan(0);
	});

	test('the run strip actually grows in a browser, not just in the arithmetic', async ({
		page
	}) => {
		// `cellFor` is tested as a pure function above. This is the other half:
		// that the measured width reaches it at all. A resize observer that never
		// fires leaves the strip at its floor and every arithmetic test still
		// passes.
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/');
		await page.waitForTimeout(800);

		const measured = await page.evaluate(() => {
			const square = document.querySelector('[data-health]');
			const strip = document.querySelector('[data-run-history]');
			return {
				square: square ? Math.round(square.getBoundingClientRect().width) : null,
				room: strip ? Math.round(strip.getBoundingClientRect().width) : null,
				days: document.querySelectorAll('[data-day]').length
			};
		});

		expect(measured.square, 'no run square on the page').not.toBeNull();
		expect(measured.room ?? 0).toBeGreaterThan(600);
		// The floor is 16. Anything above it proves the observer reported and the
		// derived value was applied.
		expect(measured.square).toBeGreaterThan(16);
	});
});
