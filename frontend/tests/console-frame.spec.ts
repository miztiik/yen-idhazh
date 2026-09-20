import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
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

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

interface PanelGroup {
	id: string;
	title: string;
	panels: string[];
}

/** What `config/appearance.json` says the Hardware route draws, and in what
 * order. Read inside each test rather than at module scope, so a malformed
 * config fails the one test that wanted it instead of the whole file. */
function machineGroups(): PanelGroup[] {
	const parsed = JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')) as {
		console?: { panel_groups?: Record<string, PanelGroup[]> };
	};
	const groups = parsed.console?.panel_groups?.machine ?? [];
	expect(groups.length, 'config/appearance.json declares no Hardware groups').toBeGreaterThan(0);
	return groups;
}

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

	test('THE ORACLE: every chart still names itself for anyone who cannot see it', async ({
		page
	}) => {
		// Visible prose on this page is cut on purpose. An accessible description
		// is not: a chart whose only description was the paragraph above it goes
		// silent for a screen reader the moment that paragraph is trimmed, and
		// nothing in a screenshot or a byte gate would show it.
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/');
		await page.waitForTimeout(800);

		const charts = await page.evaluate(() => {
			const describe = (node: Element): string => {
				const own = node.getAttribute('aria-label')?.trim();
				if (own) return own;
				const ids = node.getAttribute('aria-describedby');
				if (ids) {
					const text = ids
						.split(/\s+/)
						.map((id) => document.getElementById(id)?.textContent?.trim() ?? '')
						.join(' ')
						.trim();
					if (text) return text;
				}
				// A wrapper carries it for the server-drawn charts, where the engine
				// owns the element inside and would overwrite an attribute on it.
				return node.closest('[aria-label]')?.getAttribute('aria-label')?.trim() ?? '';
			};

			return [...document.querySelectorAll('[data-surface="operator"] svg')]
				.filter((svg) => svg.closest('[aria-hidden="true"]') === null)
				.filter((svg) => svg.getBoundingClientRect().width > 0)
				.map((svg) => {
					const owner = svg.closest(
						'[data-glance-chart], [data-console-panel], [data-windowed], figure, section'
					);
					return {
						where:
							owner?.getAttribute('data-glance-chart') ??
							owner?.getAttribute('data-console-panel') ??
							owner?.getAttribute('data-windowed') ??
							'unnamed',
						description: describe(svg)
					};
				});
		});

		expect(charts.length, 'no chart found - the scan is broken').toBeGreaterThan(6);
		expect(
			charts.filter((c) => c.description === ''),
			'these charts carry no accessible description'
		).toEqual([]);
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

	test('THE ORACLE: every Hardware panel hangs off a heading of its own group', async ({
		page
	}) => {
		// Thirteen equal siblings down one column is the finding this grouping
		// closes, and neither a screenshot nor a title scan can see it: both pass
		// on a page where every heading weighs the same. So the assertion is the
		// document structure - a group element, its own heading, and the panels
		// underneath it stepped down a level - read off the DOM rather than off
		// what any paragraph says.
		//
		// It is read against `console.panel_groups` rather than against itself.
		// A page that agreed with its own markup would pass with every panel in
		// the wrong group, which is exactly what a regrouping row can get wrong.
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/machine/');

		const declared = machineGroups();
		const groups = await page.locator('[data-console-group]').evaluateAll((nodes) =>
			nodes.map((node) => ({
				id: node.getAttribute('data-console-group') ?? '',
				declared: Number(node.getAttribute('data-console-group-panels')),
				heading: node.querySelector(':scope > h2')?.textContent?.trim() ?? '',
				held: node.querySelectorAll('[data-console-panel]').length,
				panels: [...node.querySelectorAll('[data-console-panel-id]')].map(
					(panel) => panel.getAttribute('data-console-panel-id') ?? ''
				),
				stepped: node.querySelectorAll('[data-console-panel] > header > h3').length
			}))
		);

		expect(
			groups.map((group) => group.id),
			'the route draws groups the config did not declare, or in another order'
		).toEqual(declared.map((group) => group.id));

		for (const [index, group] of groups.entries()) {
			expect(group.heading, `${group.id} does not draw its configured heading`).toBe(
				declared[index].title
			);
			expect(group.declared, `${group.id} declares no panel count`).toBeGreaterThan(0);
			expect(group.held, `${group.id} holds a different count from the one it declares`).toBe(
				group.declared
			);
			// The row's own oracle: every panel resolves to exactly one group, and
			// every group carries at least one panel. Read off the panel id rather
			// than the title, because the title is prose this row rewrote.
			expect(group.panels, `${group.id} does not hold the panels the config put in it`).toEqual(
				declared[index].panels
			);
			// A panel title still at h2 would sit beside the group heading in the
			// outline rather than under it, which is the flat page this row closed.
			expect(group.stepped, `${group.id} holds a panel title that is not an h3`).toBe(
				group.declared
			);
		}

		// Nothing is left outside. A panel the config forgot renders nowhere, and
		// a panel drawn beside the groups is the flat sibling this row removed.
		const loose = await page.locator('[data-console-panel]').count();
		expect(loose, 'a Hardware panel sits outside every group').toBe(
			groups.reduce((sum, group) => sum + group.held, 0)
		);
	});

	test('THE ORACLE: every Hardware subtitle ends by naming its own grain', async ({ page }) => {
		// Group membership used to carry the grain - a panel under `The open
		// window` followed the span control and one under `The newest run` did
		// not - and the page spent a paragraph above the panels explaining it.
		// Groups now name a decision instead, so one group holds a snapshot of a
		// run beside a reading over the span, and the carrier has to move onto
		// the panel. A subtitle whose last clause names no grain leaves a reader
		// guessing which of the two a figure is.
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/machine/');

		const notes = await page
			.locator('[data-console-panel-id]')
			.evaluateAll((nodes) =>
				nodes.map((node) => ({
					id: node.getAttribute('data-console-panel-id') ?? '',
					note: (node.querySelector(':scope > header > p')?.textContent ?? '')
						.replace(/\s+/g, ' ')
						.trim()
				}))
			);

		expect(notes.length, 'the route drew no panels to read').toBe(machineGroups().flatMap((group) => group.panels).length);
		for (const panel of notes) {
			expect(panel.note.length, `${panel.id} carries no subtitle at all`).toBeGreaterThan(20);
			// One sentence. A subtitle that grew into a paragraph is the wall of
			// small grey type the grouping was opened to cut through.
			expect(panel.note, `${panel.id}'s subtitle is more than one sentence`).not.toMatch(/\.\s+\S/);
			const last = panel.note.split(' - ').at(-1) ?? '';
			expect(last, `${panel.id}'s last clause names no grain`).toMatch(
				/newest run|last \d+ days/
			);
		}
	});

	test('THE ORACLE: a group heading outweighs the panel titles under it', async ({ page }) => {
		// The grouping only buys anything if the eye can tell a heading from the
		// thirteen titles below it. Measured rather than looked at, because a
		// token rename that put them back at one size would pass every other
		// check on this page.
		await page.setViewportSize(DESKTOP);
		await page.goto('/console/machine/');

		const sizes = await page.evaluate(() => {
			const group = document.querySelector('[data-console-group]');
			const heading = group?.querySelector(':scope > h2');
			const title = group?.querySelector('[data-console-panel] > header > h3');
			const size = (node: Element | null | undefined) =>
				node ? parseFloat(getComputedStyle(node).fontSize) : 0;
			return { heading: size(heading), title: size(title) };
		});

		expect(sizes.title, 'no panel title found under the first group').toBeGreaterThan(0);
		expect(
			sizes.heading,
			'the group heading is drawn no larger than the titles it groups'
		).toBeGreaterThan(sizes.title);
	});

	test('THE ORACLE: each route opens on the panel that verdicts the rest', async ({ page }) => {
		// The thirteenth chart rule: a verdict panel sits above the panels it
		// verdicts, or an operator reads ten readings before he reaches the line
		// that says whether to trust them. Asserted on the attribute the panel
		// declares, never on its title, so a rename cannot quietly retire it.
		for (const route of ['/console/', '/console/machine/']) {
			await page.goto(route);
			const panels = page.locator('[data-console-panel]');
			expect(await panels.count(), `${route} draws no panels`).toBeGreaterThan(0);
			expect(
				await panels.first().getAttribute('data-panel-verdict'),
				`${route} does not open on its verdict panel`
			).toBe('route');
			expect(
				await panels.first().getAttribute('data-panel-question'),
				`${route}'s first panel does not say which question it answers`
			).toBe('is it working');
			expect(
				await page.locator('[data-panel-verdict="route"]').count(),
				`${route} names more than one verdict panel`
			).toBe(1);
		}
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
