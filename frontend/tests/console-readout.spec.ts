import { expect, test, type Locator, type Page } from './support/browser';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { render } from 'svelte/server';
import type { Manifest } from 'vite';
import { readoutOf } from '../src/lib/charts/readout';
import { clocksChart } from '../src/lib/charts/machine';
import { stacked } from '../src/lib/charts/stacked';
import { serverCompiler } from './support/server-render';

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

const ROUTES = [
	'/console/',
	'/console/model/',
	'/console/machine/',
	'/console/judgement/'
] as const;
// Every console route. The pointer, keyboard and tap blocks below read an
// `svg` column chart and run on the four that draw one; the partition, the
// title rule and the moved-words rule seed on marks as well as on drawings, so
// they reach `/console/voices/`, whose two day matrices are `<div>` grids.
const ALL_ROUTES = [...ROUTES, '/console/voices/'] as const;
const DESKTOP = { width: 1440, height: 1000 };
const PHONE = { width: 390, height: 844 };

test('a wrapped readout keeps its swatch on the first line and its value after the last word', async ({ page }, testInfo) => {
	const compiled = serverCompiler(testInfo.outputPath('readout-component'));
	const module = await compiled('src/lib/components/ChartReadout.svelte', 'ChartReadout', []);
	const component = (await import(pathToFileURL(module).href)).default;
	const label = 'A recorded machine with a processor name that needs several words on a narrow phone';
	const readout = readoutOf({
		type: 'dateSeries',
		columns: ['20 Aug 2026'],
		series: [{ label, swatch: 'var(--chart-1)', values: [42], format: String }],
		notMeasured: 'Not recorded',
		resting: 'last'
	});
	const manifest = JSON.parse(readFileSync(resolve('.svelte-kit/output/client/.vite/manifest.json'), 'utf8')) as Manifest;
	const styles = [...new Set(Object.values(manifest).flatMap((entry) => entry.css ?? []))]
		.map((file) => readFileSync(join('.svelte-kit/output/client', file), 'utf8'));
	styles.push(...compiled.css.values());
	const markup = render(component, { props: { readout, name: 'wrap-witness', maxShare: 1, hint: '' } }).body;
	await page.setViewportSize(PHONE);
	await page.setContent(`<style>${styles.join('\n')}</style><main style="width: 240px; margin: 16px">${markup}</main>`);
	const boxes = await page.locator('[data-readout-row]').evaluate((row) => {
		const label = row.querySelector('dd');
		const value = row.querySelectorAll('dd')[1];
		const swatch = row.querySelector('span');
		if (!label || !value || !swatch) throw new Error('The real readout did not render its three parts');
		const walker = document.createTreeWalker(label, NodeFilter.SHOW_TEXT);
		const fragments: DOMRect[] = [];
		while (walker.nextNode()) {
			const text = walker.currentNode.textContent ?? '';
			for (const match of text.matchAll(/\S+/g)) {
				const range = document.createRange();
				range.setStart(walker.currentNode, match.index);
				range.setEnd(walker.currentNode, match.index + match[0].length);
				fragments.push(range.getBoundingClientRect());
			}
		}
		const first = fragments[0];
		const last = fragments.at(-1);
		if (!first || !last) throw new Error('The readout label has no words');
		const colour = swatch.getBoundingClientRect();
		const number = value.getBoundingClientRect();
		return {
			wrapped: last.top > first.top,
			swatchSharesFirstLine: colour.top < first.bottom && colour.bottom > first.top,
			valueSharesLastLine: number.top < last.bottom && number.bottom > last.top,
			valueFollowsLastWord: number.left >= last.right,
			overflow: row.scrollWidth > row.clientWidth
		};
	});
	expect(boxes).toEqual({
		wrapped: true,
		swatchSharesFirstLine: true,
		valueSharesLastLine: true,
		valueFollowsLastWord: true,
		overflow: false
	});
});

/** Where every console chart's declaration lives. */
const OWNER = '[data-readout-columns], [data-readout-records], [data-readout-none]';

interface DeclaredChart {
	/** `columns`, `records`, `none`, or `undeclared` - and `undeclared` is the failure. */
	partition: 'columns' | 'records' | 'none' | 'undeclared';
	/** Enough of the chart's own attributes to name it in a failure message. */
	where: string;
	count: number;
	reason: string;
	/** How many readout strips the declaring element holds. */
	strips: number;
	/** Swatches drawn outside the strip - a standing legend, in other words. */
	legend: string[];
}

/** Every chart on the route, with the declaration its own markup carries.
 *
 * A chart is found by what it draws: an `svg` that is not an icon, a mark that
 * names itself with `role="img"`, or a mark a strip reads. The HTML charts - a
 * board, a strip of tiles, a matrix of squares - draw no `svg`, and seeding on
 * one alone walked straight past them. An icon is not a chart: `Icon.svelte`
 * draws every glyph with `class="icon"`, which `icons.spec.ts` holds it to. The
 * band above every route is not a chart either: it prints three facts in words
 * and its run squares are badges beside the verdict it prints.
 */
async function chartsOn(page: Page): Promise<DeclaredChart[]> {
	return page.evaluate((OWNER) => {
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

		const seeds = [
			...document.querySelectorAll(
				'[data-surface="operator"] svg, [data-surface="operator"] [role="img"], [data-surface="operator"] [data-readout-at]'
			)
		]
			.filter((node) => node.closest('svg.icon') === null)
			.filter((node) => node.closest('[data-console-band]') === null)
			// A mark inside an `svg` is covered by the `svg` it is drawn in.
			.filter((node) => node.tagName.toLowerCase() === 'svg' || node.closest('svg') === null)
			.filter((node) => {
				const box = node.getBoundingClientRect();
				return box.width > 0 && box.height > 0;
			});

		const found = new Map<Element, DeclaredChart>();
		for (const seed of seeds) {
			const owner = seed.closest(OWNER);
			if (owner === null) {
				const panel = seed.closest('[data-console-panel], [data-windowed], section') ?? seed;
				if (!found.has(panel)) {
					found.set(panel, {
						partition: 'undeclared',
						where: named(seed),
						count: 0,
						reason: '',
						strips: 0,
						legend: []
					});
				}
				continue;
			}
			if (found.has(owner)) continue;
			const columns = owner.getAttribute('data-readout-columns');
			const records = owner.getAttribute('data-readout-records');
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
			const legend =
				columns === null
					? []
					: [...owner.querySelectorAll('span, i, em')]
							.filter((el) => el.closest('[data-readout]') === null)
							.filter((el) => (el.textContent ?? '').trim() === '')
							// A mark that names itself is data, not a key. The run squares
							// under the chart of articles published against planned are spans
							// in the colours the readout's run rows print, and each carries
							// its own accessible name; a key swatch carries none. A fill drawn
							// inside such a mark is part of it too - the disk-read tiles paint
							// each day's bar as an empty span inside the tile that names the
							// day. Only a mark with no named mark inside it counts, so a whole
							// drawing that names itself cannot hide a key.
							.filter((el) => {
								const mark = el.closest('[role="img"][aria-label], [data-readout-at]');
								return (
									mark === null ||
									mark === owner ||
									!owner.contains(mark) ||
									mark.querySelector('[role="img"][aria-label], [data-readout-at]') !== null
								);
							})
							.filter((el) => {
								const box = el.getBoundingClientRect();
								return box.width > 0 && box.width <= 28 && box.height > 0 && box.height <= 28;
							})
							.filter((el) => printed.has(getComputedStyle(el).backgroundColor))
							.map((el) => el.outerHTML.slice(0, 120));
			found.set(owner, {
				partition: columns !== null ? 'columns' : records !== null ? 'records' : 'none',
				where: named(owner),
				count: Number(columns ?? records ?? 0),
				reason: owner.getAttribute('data-readout-none') ?? '',
				strips: owner.querySelectorAll('[data-readout]').length,
				legend
			});
		}
		return [...found.values()];
	}, OWNER);
}

/** Every element that declares it has no hover, chart or not. */
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

/** The words of a mark's name a strip has to carry: every figure, and every
 * word of four letters or more. The short words - of, at, the, and - are how a
 * sentence and a strip of labelled entries say the same thing differently. */
function significant(name: string): string[] {
	return name
		.toLowerCase()
		.split(/\s+/)
		.map((token) => token.replace(/^[("']+|[)"'.,:;]+$/g, ''))
		.filter((token) => /\d/.test(token) || /^[a-z'-]{4,}$/.test(token));
}

async function open(page: Page, route: string, size = DESKTOP): Promise<void> {
	await page.setViewportSize(size);
	await page.goto(route);
	if (route === '/console/machine/') {
		await expect(page.locator('[data-windowed="machine-fleet"]')).toHaveAttribute('data-fleet-state', 'ready');
	}
	// The engine charts hydrate after mount and swap their prerendered SVG out.
	await page.waitForTimeout(900);
}

/** The strip's heading, which is the column it is printing. */
function dayOf(owner: Locator): Locator {
	return owner.locator('[data-readout] [data-readout-day]').first();
}

test.describe('the readout is the default', () => {
	for (const route of ALL_ROUTES) {
		// One load per route: the five checks below read the same settled page,
		// so opening it once for each was five loads where one answers them all.
		test(`THE ORACLE: every chart on ${route} declares its readout, and every strip reads right`, async ({
			page
		}) => {
			await open(page, route);
			await test.step('every chart declares its columns, its records or says why not', async () => {
				const charts = await chartsOn(page);

				expect(charts.length, 'no chart found - the scan is broken').toBeGreaterThan(0);

				expect(
					charts.filter((chart) => chart.partition === 'undeclared').map((chart) => chart.where),
					'these charts declare neither a column, a record nor a reason for having none'
				).toEqual([]);

				// A chart with a column or a record has the strip, and it has it in its
				// own markup rather than somewhere else on the page.
				expect(
					charts
						.filter((chart) => chart.partition === 'columns' && chart.strips !== 1)
						.map((chart) => `${chart.where} holds ${chart.strips} strips`),
					'a chart with a shared column resolves exactly one readout strip'
				).toEqual([]);
				expect(
					charts
						.filter((chart) => chart.partition === 'records' && chart.strips < 1)
						.map((chart) => chart.where),
					'a chart that reads records prints no strip'
				).toEqual([]);

				// The strip is the legend. Nothing else in a column chart may draw a
				// swatch. A record chart keeps its own key: one record shows only its
				// own colours, so the key is the one place every colour is named.
				expect(
					charts
						.filter((chart) => chart.partition === 'columns' && chart.legend.length > 0)
						.map((chart) => `${chart.where}: ${chart.legend.join(' ')}`),
					'these charts draw a key as well as a strip'
				).toEqual([]);
			});
			await test.step('every chart that has no readout says why, and who agreed', async () => {
				const declared = await declarationsOn(page);

				// A reason, not a token. "none" and "n/a" pass an attribute check and
				// tell a reader nothing about what was decided - and a chart somebody
				// decided needs no hover looks the same as one where it was forgotten,
				// so the exception names who agreed it.
				expect(
					declared
						.filter((one) => one.reason.trim().split(/\s+/).length < 5)
						.map((one) => `${one.where}: "${one.reason}"`),
					'these reasons are too short to be a reason'
				).toEqual([]);
				expect(
					declared
						.filter((one) => !one.reason.trim().endsWith('; agreed with Susan'))
						.map((one) => `${one.where}: "${one.reason}"`),
					'these exceptions do not say who agreed them'
				).toEqual([]);
			});
			await test.step('no mark inside a chart carries a native tooltip', async () => {
				// A `title` is the browser's own tooltip: no key reaches it, no thumb
				// reaches it and no theme styles it. Every one a chart carried moved
				// into that chart's strip. An SVG `<title>` element is the same tooltip
				// under another name, so it is counted too. A title outside a chart - a
				// link, a badge - is not a mark, and is not this rule's business.
				const titled = await page.evaluate(
					(OWNER) =>
						[...document.querySelectorAll(OWNER)].flatMap((owner) => [
							...[owner, ...owner.querySelectorAll('[title]')]
								.filter((node) => node.hasAttribute('title'))
								.map((node) => `${node.tagName.toLowerCase()}: ${node.getAttribute('title')}`),
							...[...owner.querySelectorAll('title')].map(
								(node) => `svg <title>: ${(node.textContent ?? '').trim()}`
							)
						]),
					OWNER
				);
				expect(titled, 'these chart marks still carry a native tooltip').toEqual([]);
			});
			await test.step('every strip heads a day the way a reader spells it', async () => {
				// A strip heads its column with the reader's spelling of a day, `27 Sep
				// 2026`, never the ledger's, `2026-09-27`. A run id opens with a date and
				// is not one, so `2026-09-27-1` passes.
				const headings = await page
					.locator('[data-surface="operator"] [data-readout] [data-readout-day]')
					.evaluateAll((nodes) => nodes.map((node) => (node.textContent ?? '').trim()));
				expect(
					headings.filter((heading) => /^\d{4}-\d{2}-\d{2}(?![-\d])/.test(heading)),
					'these strips head a day in the ledger spelling'
				).toEqual([]);
			});
			// Last, because pointing at a mark is the one step that changes the page.
			await test.step('every mark a strip reads has every word of its name in that strip', async () => {
				// The witness that nothing a tooltip said was lost. The sentence a mark's
				// tooltip carried stays on the mark as its accessible name, so a screen
				// reader keeps it; pointing at the mark must then put every figure and
				// every word of four letters or more of that sentence in the strip.
				const owners = page.locator(
					'[data-surface="operator"] [data-readout-columns], [data-surface="operator"] [data-readout-records]'
				);
				const lost: string[] = [];
				for (let at = 0; at < (await owners.count()); at += 1) {
					const owner = owners.nth(at);
					const marks = owner.locator('[role="img"][aria-label], [data-readout-at][aria-label]');
					const count = Math.min(await marks.count(), 40);
					for (let index = 0; index < count; index += 1) {
						const mark = marks.nth(index);
						// The chart's own frame, a whole drawing, a mark that holds other
						// marks, and a mark of a chart nested inside this one are not one of
						// this chart's marks: pointing at them reads whatever sits there.
						const leaf = await mark.evaluate(
							(node, OWNER) =>
								node.tagName.toLowerCase() !== 'svg' &&
								!node.hasAttribute('tabindex') &&
								node.querySelector('[aria-label], [role="img"]') === null &&
								node.parentElement?.closest(OWNER) === node.closest(OWNER) &&
								node.closest(OWNER)?.hasAttribute('data-readout-none') === false &&
								node.getBoundingClientRect().width > 0,
							OWNER
						);
						if (!leaf) continue;
						await mark.evaluate((node) => node.scrollIntoView({ behavior: 'instant', block: 'center' }));
						const box = await mark.boundingBox();
						if (box === null) continue;
						await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
						await page.waitForTimeout(60);
						const name = (await mark.getAttribute('aria-label')) ?? '';
						const strip = (await owner.locator('[data-readout]').first().innerText()).toLowerCase();
						const missing = significant(name).filter((word) => !strip.includes(word));
						if (missing.length > 0) lost.push(`${name} -> missing ${missing.join(', ')}`);
					}
				}
				expect(lost, 'these marks name facts their strip does not print').toEqual([]);
			});
		});
	}

	test('THE ORACLE: the console has charts on every side of the partition', async ({ page }) => {
		// A partition with one side empty is a partition that proves nothing. The
		// last side is the interesting one: it is the set of charts somebody
		// decided should have no hover.
		const withColumns: string[] = [];
		const withRecords: string[] = [];
		const withReasons = new Set<string>();
		for (const route of ALL_ROUTES) {
			await open(page, route);
			const charts = await chartsOn(page);
			withColumns.push(...charts.filter((c) => c.partition === 'columns').map((c) => c.where));
			withRecords.push(...charts.filter((c) => c.partition === 'records').map((c) => c.where));
			for (const one of await declarationsOn(page)) withReasons.add(one.reason);
		}
		expect(withColumns.length, 'no chart on the console carries a readout').toBeGreaterThan(3);
		expect(withRecords.length, 'no chart on the console reads a record').toBeGreaterThan(2);
		expect(withReasons.size, 'no chart on the console states why it has none').toBeGreaterThan(2);
	});

	for (const route of ['/console/', '/console/machine/', '/console/voices/'] as const) {
		test(`the keyboard steps and clears a record strip on ${route}`, async ({ page }) => {
			await open(page, route);
			const owners = page.locator('[data-surface="operator"] [data-readout-records]');
			let driven = 0;
			for (let index = 0; index < (await owners.count()); index += 1) {
				const owner = owners.nth(index);
				if (Number((await owner.getAttribute('data-readout-records')) ?? 0) < 2) continue;
				const focusable = owner
					.locator('[tabindex="0"]')
					.or(owner.and(page.locator('[tabindex="0"]')))
					.first();
				if ((await focusable.count()) === 0) continue;
				const heading = owner.locator('[data-readout] [data-readout-subject]').first();
				const name = (await owner.getAttribute('aria-label')) ?? `records ${index}`;
				const resting = await heading.innerText();

				await focusable.focus();
				await page.waitForTimeout(150);
				const opened = await heading.innerText();
				// A list steps on Down, a row on Right, and a grid on both.
				await page.keyboard.press('ArrowRight');
				await page.keyboard.press('ArrowDown');
				await page.waitForTimeout(150);
				expect(await heading.innerText(), `${name}: no arrow key moved the strip`).not.toBe(opened);

				await page.keyboard.press('Escape');
				await page.waitForTimeout(150);
				expect(await heading.innerText(), `${name}: Escape did not return to rest`).toBe(resting);
				driven += 1;
			}
			expect(driven, `${route}: no record chart could be driven from the keyboard`).toBeGreaterThan(0);
		});
	}

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
				const name = (await owner.getAttribute('aria-label')) ?? `chart ${index}`;
				// Go to the chart, and scroll the panel rather than the plot inside
				// it. `hydrate` observes intersection, so a chart more than a screen
				// down has no `svg` at all until somebody goes to it - and waiting on
				// that `svg` first waits for the one thing only this scroll produces.
				// The same move puts the box where a pointer can reach it: a page
				// coordinate past the viewport height is not a place a mouse can go.
				// Instant rather than smooth, because a box read mid-scroll is a box
				// the mouse misses.
				await owner.evaluate((node) =>
					node.scrollIntoView({ behavior: 'instant', block: 'center' })
				);
				// A strip of tiles draws no `svg` and has no plot to point across; the
				// mark under the pointer answers it, and the moved-words block above
				// points at every one of its marks. An engine chart says it draws, so
				// it is waited for rather than walked past.
				if (
					(await owner.locator('svg').count()) === 0 &&
					(await owner.getAttribute('data-chart-drawn')) === null
				) {
					continue;
				}
				const plot = owner.locator('svg').first();
				// Named when nothing arrives. Waiting on the locator alone reports a
				// selector and the whole test budget, which says neither which chart
				// stayed blank nor that a chart is what went wrong.
				await expect(plot, `${name}: nothing was drawn after scrolling to it`).toBeVisible({
					timeout: 15000
				});
				const box = await plot.boundingBox();
				if (box === null || box.width < 40) continue;

				const middle = box.y + box.height / 2;
				await page.mouse.move(box.x + 4, middle);
				await page.waitForTimeout(150);
				const first = await dayOf(owner).innerText();
				await page.mouse.move(box.x + box.width - 4, middle);
				await page.waitForTimeout(150);
				const last = await dayOf(owner).innerText();

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
				// Scroll to it first, which is what a thumb does and what the engine
				// waits for: `hydrate` observes intersection, so a chart nine screens
				// down has no plot until somebody goes to it. Instant rather than
				// smooth - `scrollIntoViewIfNeeded` times out on a chart that is
				// still animating in.
				await owner.evaluate((node) =>
					node.scrollIntoView({ behavior: 'instant', block: 'center' })
				);
				// A chart drawn from rows the page fetches may still be waiting for
				// them. That is a state this loop walks past, not a fault - the count
				// at the foot still requires that one chart was tappable. Only a
				// chart that SAYS it has not drawn is skipped: a hand-written one
				// carries no such attribute and its marks are always there, so
				// skipping on a missing attribute would skip every chart on
				// `/console/model/` and pass nothing.
				if ((await owner.getAttribute('data-chart-drawn')) === 'no') {
					// It may be drawing right now - the scroll above is what the
					// engine was waiting for. `data-chart-drawn` turns `yes` when the
					// first mark lands, so it is the thing to wait on before walking
					// past.
					await owner
						.and(page.locator('[data-chart-drawn="yes"]'))
						.waitFor({ timeout: 6000 })
						.catch(() => {});
					if ((await owner.getAttribute('data-chart-drawn')) === 'no') continue;
				}
				const plot = owner.locator('svg').first();
				if ((await plot.count()) === 0) continue;
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
		// what CLAUDE.md Guardrail #1 asks of every published page. The check is a raw
		// HTTP fetch of the same address, so nothing on the page has run.
		//
		// Since 2026-09-09 a chart may be drawn from rows the page fetches rather
		// than from rows the document carries, and one of those cannot have its
		// column in the prerendered markup - the numbers are not there to print.
		// So the promise splits in two and each half is checked here. A chart over
		// inlined data still owes its resting column to the raw document. A chart
		// that declares `data-readout-fetched` owes it the moment its payload
		// lands, and owes an absence before that; the case below proves the second
		// half by blocking the payload, so a chart that quietly kept a prerendered
		// column would fail this rather than pass it.
		for (const route of ROUTES) {
			await open(page, route);
			const named = await page.evaluate(() =>
				[...document.querySelectorAll('[data-readout]')].map((node) => ({
					name: node.getAttribute('data-readout') ?? '',
					fetched: node.closest('[data-readout-fetched]') !== null
				}))
			);
			expect(named.length, `${route} rendered no readout strip`).toBeGreaterThan(0);

			const html = await page.request.get(route).then((res) => res.text());
			const inlined = named.filter((entry) => !entry.fetched);
			expect(
				inlined.length,
				`${route}: every strip claims fetched rows, so nothing is left to prerender`
			).toBeGreaterThan(0);
			for (const entry of inlined) {
				expect(html, `${route}: ${entry.name} is not in the prerendered document`).toContain(
					`data-readout="${entry.name}"`
				);
			}
			expect(html, `${route}: no resting column is prerendered`).toContain('data-readout-day');
		}
	});

	test('THE ORACLE: a strip over fetched rows arrives with its payload and not before', async ({
		page
	}) => {
		// The other half of the promise above, and the one that stops this pair
		// being weakened into nothing. A chart drawn from fetched rows may print
		// no column before the fetch lands - and it MUST print one after, or the
		// move from the document to the network cost the reader the numbers.
		//
		// The service worker is unregistered and every cache dropped first. It
		// serves the month shard from `idhazh-days` otherwise, so the blocked case
		// reports a page that works and proves nothing (agent-notes.md).
		await page.goto('/console/');
		await page.evaluate(async () => {
			for (const reg of await navigator.serviceWorker.getRegistrations()) await reg.unregister();
			for (const name of await caches.keys()) await caches.delete(name);
		});

		let blocked = 0;
		await page.route('**/telemetry/*.csv', (route) => {
			blocked += 1;
			return route.abort();
		});
		await page.goto('/console/');
		await page.waitForTimeout(1200);
		expect(blocked, 'no month shard was requested, so the block proved nothing').toBeGreaterThan(0);

		const absent = page.locator('[data-readout-fetched] [data-readout-day]');
		expect(await absent.count(), 'a strip printed a column with no rows behind it').toBe(0);
		// And the panel does NOT say the ledger holds no failure, because a blocked
		// month is not an empty one. It holds its reserved shape and
		// the sentence above the panels names the month that did not arrive.
		await expect(page.locator('[data-mix-empty]')).toHaveCount(0);
		await expect(page.locator('[data-reserved="failure-mix"]')).toHaveCount(1);
		await expect(page.locator('[data-console-standing]')).toHaveAttribute(
			'data-console-standing',
			'unreachable'
		);

		await page.unroute('**/telemetry/*.csv');
		await page.goto('/console/');
		await page.waitForTimeout(1200);
		const strip = page.locator('[data-readout-fetched] [data-readout-day]').first();
		await expect(strip).toHaveCount(1);
		expect((await strip.innerText()).trim().length, 'the strip arrived empty').toBeGreaterThan(0);
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
	});

	test('a strip is built from the labels, so it cannot be a different length', () => {
		const strip = readoutOf({
			type: 'dateSeries',
			columns: ['Mon', 'Tue', 'Wed'],
			series: [
				{
					label: 'Read',
					swatch: 'var(--chart-1)',
					values: [0, 10, 20],
					format: (value) => `${value}`
				},
				{
					label: 'Written',
					swatch: 'var(--chart-4)',
					values: [0, 1, 2],
					format: (value) => `${value}`
				}
			],
			notMeasured: 'Nothing was read on this day',
			resting: 'last'
		});
		expect(strip.columns).toEqual(['Mon', 'Tue', 'Wed']);
		expect(strip.series.map((one) => [one.label, one.swatch, one.values[2]])).toEqual([
			['Read', 'var(--chart-1)', '20'],
			['Written', 'var(--chart-4)', '2']
		]);
		expect(strip.resting).toBe(2);
		// A series one reading short is one day's numbers under another day's
		// heading, so the builder refuses it rather than printing it.
		expect(() =>
			readoutOf({
				type: 'dateSeries',
				columns: ['Mon', 'Tue'],
				series: [{ label: 'Read', swatch: null, values: [1], format: String }],
				notMeasured: 'Nothing was read on this day',
				resting: 'last'
			})
		).toThrow(/1 readings for 2 columns/);
	});

	test('a missing reading prints the not-measured word, never a dash or a zero', () => {
		const strip = readoutOf({
			type: 'dateSeries',
			columns: ['Mon', 'Tue'],
			series: [
				{ label: 'Read', swatch: null, values: [null, 4], format: String },
				{ label: 'Never read', swatch: null, values: [null, null], format: String }
			],
			notMeasured: 'Nothing was read on this day',
			resting: 'newest'
		});
		expect(strip.series[0].values).toEqual([null, '4']);
		expect(strip.notMeasured).toBe('Nothing was read on this day');
		// A key for a series the window never measured is a claim the data does
		// not support, so it has no entry at all.
		expect(strip.series.map((one) => one.label)).toEqual(['Read']);
		expect(() =>
			readoutOf({
				type: 'dateSeries',
				columns: ['Mon'],
				series: [{ label: 'Read', swatch: null, values: ['-'], format: String }],
				notMeasured: 'Nothing was read on this day',
				resting: 'last'
			})
		).toThrow(/hand null/);
	});
});
