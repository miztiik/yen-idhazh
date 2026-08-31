import { expect, test, type Locator, type Page } from '@playwright/test';
import { columnStrip } from '../src/lib/charts/frame';
import { clocksChart, percentileChart } from '../src/lib/charts/machine';
import { stacked } from '../src/lib/charts/stacked';

/**
 * Every console chart says whether it has a column to hover, and says it in
 * markup rather than by omission.
 *
 * The console had a readout on seven charts of twenty-four and a standing
 * legend under several of the rest, so a reader learned two ways of naming a
 * series on one page and the second one printed a fact the first already had.
 * This row makes the strip the default and the legend gone.
 *
 * The half that matters most is the second partition. "This chart has no
 * hover" is a decision - a ranked list has no column two rows share, and a
 * strip on one would print the row the cursor is already on - but a chart that
 * simply forgot the readout looks exactly the same. So a chart with no shared
 * column carries `data-readout-none` with the reason in words, and the oracle
 * below fails on a chart that declares neither.
 */

const ROUTES = ['/console/', '/console/model/', '/console/machine/'] as const;
const DESKTOP = { width: 1440, height: 1000 };
const PHONE = { width: 390, height: 844 };

interface DeclaredChart {
	/** `columns`, `none`, or `undeclared` - and `undeclared` is the failure. */
	partition: 'columns' | 'none' | 'undeclared';
	/** Enough of the chart's own attributes to name it in a failure message. */
	where: string;
	columns: number;
	reason: string;
	/** How many readout strips the declaring element holds. */
	strips: number;
	/** Swatches drawn outside the strip - a standing legend, in other words. */
	legend: string[];
}

/** Every chart on the route, with the declaration its own markup carries.
 *
 * An icon is not a chart: `Icon.svelte` is the one component that draws a glyph
 * and it carries `class="icon"`, which `icons.spec.ts` already holds it to.
 */
async function chartsOn(page: Page): Promise<DeclaredChart[]> {
	return page.evaluate(() => {
		/** Enough of a name to find the chart again from a failure message. */
		const named = (node: Element): string => {
			const owner = node.closest(
				'[data-console-panel], [data-windowed], [data-glance-chart], figure, section'
			);
			return (
				node.getAttribute('aria-label') ??
				owner?.getAttribute('data-console-panel') ??
				owner?.getAttribute('data-windowed') ??
				owner?.getAttribute('data-glance-chart') ??
				owner?.getAttribute('aria-label') ??
				node.getAttribute('class') ??
				'unnamed'
			);
		};

		return [...document.querySelectorAll('[data-surface="operator"] svg')]
			.filter((svg) => !svg.classList.contains('icon'))
			.filter((svg) => svg.getBoundingClientRect().width > 0)
			.map((svg) => {
				const owner = svg.closest('[data-readout-columns], [data-readout-none]');
				if (owner === null) {
					return {
						partition: 'undeclared' as const,
						where: named(svg),
						columns: 0,
						reason: '',
						strips: 0,
						legend: []
					};
				}
				const declared = owner.getAttribute('data-readout-columns');
				// The row's claim is that the strip already prints the swatch and the
				// label, so a second swatch in the same colour is one fact drawn twice.
				// A swatch in a colour the strip does NOT print is not a key to a
				// series - the run-length chart tints one square to name the shaded
				// band its sentence is about, and no strip row is drawn in that fill.
				const printed = new Set(
					[...owner.querySelectorAll('[data-readout] [data-readout-row] span')].map(
						(el) => getComputedStyle(el).backgroundColor
					)
				);
				const legend = [...owner.querySelectorAll('span, i, em')]
					.filter((el) => el.closest('[data-readout]') === null)
					.filter((el) => (el.textContent ?? '').trim() === '')
					.filter((el) => {
						const box = el.getBoundingClientRect();
						return box.width > 0 && box.width <= 28 && box.height > 0 && box.height <= 28;
					})
					.filter((el) => printed.has(getComputedStyle(el).backgroundColor))
					.map((el) => el.outerHTML.slice(0, 120));
				return {
					partition: declared === null ? ('none' as const) : ('columns' as const),
					where: named(owner),
					columns: Number(declared ?? 0),
					reason: owner.getAttribute('data-readout-none') ?? '',
					strips: owner.querySelectorAll('[data-readout]').length,
					legend
				};
			});
	});
}

/** Every element that declares itself, chart or not.
 *
 * A target bar and a shard board draw no `svg` at all, so the scan above cannot
 * see them - and they are exactly the surfaces Decision 2 of the row names.
 * This is what holds their reason to the same standard.
 */
async function declarationsOn(page: Page): Promise<{ where: string; reason: string }[]> {
	return page.evaluate(() =>
		[...document.querySelectorAll('[data-surface="operator"] [data-readout-none]')].map((node) => ({
			where:
				node.getAttribute('data-target-bar') ??
				node.getAttribute('data-shard-board') ??
				node.getAttribute('aria-label') ??
				node.getAttribute('class') ??
				'unnamed',
			reason: node.getAttribute('data-readout-none') ?? ''
		}))
	);
}

async function open(page: Page, route: string, size = DESKTOP): Promise<void> {
	await page.setViewportSize(size);
	await page.goto(route);
	// The engine charts hydrate after mount and swap their prerendered SVG out.
	await page.waitForTimeout(900);
}

/** The strip's heading, which is the column it is printing. */
function dayOf(owner: Locator): Locator {
	return owner.locator('[data-readout] [data-readout-day]').first();
}

test.describe('the readout is the default', () => {
	for (const route of ROUTES) {
		test(`THE ORACLE: every chart on ${route} declares its columns or says why not`, async ({
			page
		}) => {
			await open(page, route);
			const charts = await chartsOn(page);

			expect(charts.length, 'no chart found - the scan is broken').toBeGreaterThan(0);

			expect(
				charts.filter((chart) => chart.partition === 'undeclared').map((chart) => chart.where),
				'these charts declare neither a shared column nor a reason for having none'
			).toEqual([]);

			// A chart with a column has the strip, and it has it in its own markup
			// rather than somewhere else on the page.
			expect(
				charts
					.filter((chart) => chart.partition === 'columns' && chart.strips !== 1)
					.map((chart) => `${chart.where} holds ${chart.strips} strips`),
				'a chart with a shared column resolves exactly one readout strip'
			).toEqual([]);

			// The strip is the legend. Nothing else in the chart may draw a swatch.
			expect(
				charts
					.filter((chart) => chart.partition === 'columns' && chart.legend.length > 0)
					.map((chart) => `${chart.where}: ${chart.legend.join(' ')}`),
				'these charts draw a key as well as a strip'
			).toEqual([]);
		});

		test(`every chart on ${route} that has no readout gives a reason in words`, async ({
			page
		}) => {
			await open(page, route);
			const declared = await declarationsOn(page);

			expect(declared.length, `${route} declares no chart without a readout`).toBeGreaterThan(0);

			// A reason, not a token. "none" and "n/a" pass an attribute check and
			// tell a reader nothing about what was decided.
			expect(
				declared
					.filter((one) => one.reason.trim().split(/\s+/).length < 5)
					.map((one) => `${one.where}: "${one.reason}"`),
				'these reasons are too short to be a reason'
			).toEqual([]);
		});
	}

	test('THE ORACLE: the console has charts on both sides of the partition', async ({ page }) => {
		// A partition with one side empty is a partition that proves nothing. The
		// second side is the interesting one: it is the set of charts somebody
		// decided should have no hover.
		const withColumns: string[] = [];
		const withReasons = new Set<string>();
		for (const route of ROUTES) {
			await open(page, route);
			const charts = await chartsOn(page);
			withColumns.push(...charts.filter((c) => c.partition === 'columns').map((c) => c.where));
			for (const one of await declarationsOn(page)) withReasons.add(one.reason);
		}
		expect(withColumns.length, 'no chart on the console carries a readout').toBeGreaterThan(3);
		expect(withReasons.size, 'no chart on the console states why it has none').toBeGreaterThan(2);
	});

	for (const route of ROUTES) {
		test(`pointing at either end of a chart on ${route} reads two different columns`, async ({
			page
		}) => {
			await open(page, route);
			const owners = page.locator('[data-surface="operator"] [data-readout-columns]');
			const count = await owners.count();
			expect(count, `${route} draws no chart with a shared column`).toBeGreaterThan(0);

			let compared = 0;
			for (let index = 0; index < count; index += 1) {
				const owner = owners.nth(index);
				const columns = Number((await owner.getAttribute('data-readout-columns')) ?? 0);
				if (columns < 2) continue;
				const plot = owner.locator('svg').first();
				// A chart below the fold reports a box the mouse cannot reach: a page
				// coordinate past the viewport height is not a place a pointer can go.
				await plot.scrollIntoViewIfNeeded();
				const box = await plot.boundingBox();
				if (box === null || box.width < 40) continue;

				const middle = box.y + box.height / 2;
				await page.mouse.move(box.x + 4, middle);
				await page.waitForTimeout(150);
				const first = await dayOf(owner).innerText();
				await page.mouse.move(box.x + box.width - 4, middle);
				await page.waitForTimeout(150);
				const last = await dayOf(owner).innerText();

				const name = (await owner.getAttribute('aria-label')) ?? `chart ${index}`;
				expect(first, `${name}: the first column printed nothing`).not.toBe('');
				expect(last, `${name}: the two ends of the plot print one column`).not.toBe(first);
				compared += 1;
			}
			expect(compared, `${route}: no chart had two columns to compare`).toBeGreaterThan(0);
		});

		test(`the keyboard steps and clears a readout on ${route}`, async ({ page }) => {
			await open(page, route);
			const owners = page.locator('[data-surface="operator"] [data-readout-columns]');
			const count = await owners.count();

			let driven = 0;
			for (let index = 0; index < count; index += 1) {
				const owner = owners.nth(index);
				const columns = Number((await owner.getAttribute('data-readout-columns')) ?? 0);
				if (columns < 2) continue;
				// One tab stop for a chart, never one per column: the `svg` takes the
				// focus on a hand-written chart and the wrapper takes it on an
				// engine-drawn one, because the engine replaces the SVG on hydration.
				const focusable = owner.locator('[tabindex="0"]').first();
				if ((await focusable.count()) === 0) continue;

				const name = (await owner.getAttribute('aria-label')) ?? `chart ${index}`;
				const resting = await dayOf(owner).innerText();

				await focusable.focus();
				await page.waitForTimeout(150);
				const opened = await dayOf(owner).innerText();

				await page.keyboard.press('ArrowRight');
				await page.waitForTimeout(150);
				const stepped = await dayOf(owner).innerText();
				expect(stepped, `${name}: Right did not move the readout`).not.toBe(opened);

				await page.keyboard.press('ArrowLeft');
				await page.waitForTimeout(150);
				expect(await dayOf(owner).innerText(), `${name}: Left did not step back`).toBe(opened);

				await page.keyboard.press('Escape');
				await page.waitForTimeout(150);
				expect(await dayOf(owner).innerText(), `${name}: Escape did not return to rest`).toBe(
					resting
				);
				driven += 1;
			}
			expect(driven, `${route}: no chart could be driven from the keyboard`).toBeGreaterThan(0);
		});

		test(`a tap selects a column on ${route}`, async ({ page }) => {
			// `pointerReadout` binds pointer events rather than mouse ones, so a
			// thumb reaches the same columns a cursor does. Asserted rather than
			// assumed: an SVG `<title>` needs a hover, and on a phone a hover is not
			// a thing that happens.
			await open(page, route, PHONE);
			const owners = page.locator('[data-surface="operator"] [data-readout-columns]');
			const count = await owners.count();

			let tapped = 0;
			for (let index = 0; index < count; index += 1) {
				const owner = owners.nth(index);
				if (Number((await owner.getAttribute('data-readout-columns')) ?? 0) < 2) continue;
				const plot = owner.locator('svg').first();
				await plot.scrollIntoViewIfNeeded();
				const box = await plot.boundingBox();
				if (box === null || box.width < 40) continue;

				const resting = await dayOf(owner).innerText();
				await page.mouse.move(box.x + 4, box.y + box.height / 2);
				await page.mouse.down();
				await page.mouse.up();
				await page.waitForTimeout(150);
				const picked = await dayOf(owner).innerText();
				expect(picked, 'a tap at the oldest column selected nothing').not.toBe(resting);
				tapped += 1;
				break;
			}
			expect(tapped, `${route}: no chart could be tapped`).toBe(1);
		});
	}

	test('THE ORACLE: the resting column is in the document before any script runs', async ({
		page
	}) => {
		// The hover is an addition. A reader with a blocked script, a slow network
		// or an old browser still gets one column's numbers in words, which is
		// what CLAUDE.md Rule #1 asks of every published page. The check is a raw
		// HTTP fetch of the same address, so nothing on the page has run.
		for (const route of ROUTES) {
			await open(page, route);
			const names = await page.evaluate(() =>
				[...document.querySelectorAll('[data-readout]')].map(
					(node) => node.getAttribute('data-readout') ?? ''
				)
			);
			expect(names.length, `${route} rendered no readout strip`).toBeGreaterThan(0);

			const html = await page.request.get(route).then((res) => res.text());
			for (const name of names) {
				expect(html, `${route}: ${name} is not in the prerendered document`).toContain(
					`data-readout="${name}"`
				);
			}
			expect(html, `${route}: no resting column is prerendered`).toContain('data-readout-day');
		}
	});
});

test.describe('the strip is the key', () => {
	test('no chart option carries a legend', () => {
		// The engine drew a key above three of its charts. The strip below the
		// plot prints the same swatch and the same label at the column the reader
		// is on, so the key was the same pair a second time - and a second copy is
		// how two of them drift.
		const stack = stacked(
			['Mon', 'Tue'],
			[
				{ label: 'fetch', token: '--chart-1', values: [2, 1] },
				{ label: 'extract', token: '--chart-2', values: [1, 5] }
			]
		);
		expect(stack.option.legend, 'the stacked chart draws a legend').toBeUndefined();

		const clocks = clocksChart([
			{ label: 'shard 0', ledger: 12.5, server: 12.4, gapPct: 0.8, agrees: true },
			{ label: 'shard 1', ledger: 9.5, server: 9.9, gapPct: 4.0, agrees: true }
		]);
		expect(clocks.option.legend, 'the clock chart draws a legend').toBeUndefined();

		const percentiles = percentileChart([
			{
				runId: '2026-08-30-1',
				items: 120,
				points: [
					{ percentile: 50, ms: 1000 },
					{ percentile: 99, ms: 9000 }
				]
			}
		]);
		expect(percentiles.option.legend, 'the percentile chart draws a legend').toBeUndefined();
	});

	test('a strip is built from the labels, so it cannot be a different length', () => {
		const strip = columnStrip(['Mon', 'Tue', 'Wed'], [
			{ label: 'Read', colour: 'var(--chart-1)', value: (index) => `${index * 10}` },
			{ label: 'Written', colour: 'var(--chart-4)', value: (index) => `${index}` }
		]);
		expect(strip.map((column) => column.date)).toEqual(['Mon', 'Tue', 'Wed']);
		expect(strip[2].rows).toEqual([
			{ label: 'Read', value: '20', colour: 'var(--chart-1)' },
			{ label: 'Written', value: '2', colour: 'var(--chart-4)' }
		]);
		// Zero, not a pixel. The engine keeps its insets in pixels and the element
		// is fluid, so `Chart.svelte` recomputes every share from the measured
		// width - a pixel written here would be right at one width only.
		expect(strip.every((column) => column.x === 0)).toBe(true);
	});
});
