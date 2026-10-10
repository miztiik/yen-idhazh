/** One shared control, declared surface coverage, and actual cross-route navigation. */
import { expect, test, type Page } from './support/door-page';
import { type RouteId } from '../src/lib/console/band';
import { BY_ROUTE } from './support/console-expect/console-window';
import { ONE_DAYS, spanSaid } from './support/span-said';

import { monthsInWindow, monthsToFetch, stepPreset, windowOfDays } from '../src/lib/charts/viewport';

import { hydrated, setWindow, windowed, routeHref, minus, presets, defaultDays } from './support/console-window/controls';
import { said } from './support/console-window/readout';

import { machineSpan } from './support/console-window/machine-spans';

import { config, telemetry } from './support/console-window/controls';
function monthsKept(today: string, months: number): string[] {
	const [year, month] = today.split('-').map(Number);
	const newest = year * 12 + (month - 1);
	return Array.from({ length: months }, (_, index) => {
		const total = newest - (months - 1) + index;
		const stem = String(Math.floor(total / 12)).padStart(4, '0');
		return `${stem}-${String((total % 12) + 1).padStart(2, '0')}`;
	});
}

test('a window of N days is exactly N days, and ends on the day it is handed', () => {
	// It used to shrink to the rows it found. That was invisible while nothing
	// named the span and a lie the moment a control does: a page reading 90 while
	// the charts draw 2 cannot be trusted about anything else. It also used to end
	// on the newest date in the rows it was handed, so a record that stopped moved
	// its window into the past; every route now hands it the newest published day.
	expect(windowOfDays('2026-08-28', 30, 'right')).toEqual({
		start: '2026-07-30',
		end: '2026-08-28'
	});
	expect(windowOfDays('2026-08-28', 7, 'right')).toEqual({
		start: '2026-08-22',
		end: '2026-08-28'
	});
	expect(windowOfDays('2026-08-28', 1, 'right')).toEqual({
		start: '2026-08-28',
		end: '2026-08-28'
	});
	// Centred pushes the end past the day it is handed, which is the anchor's whole
	// purpose: room on the right for days that have not happened yet.
	expect(windowOfDays('2026-08-28', 7, 'centre')).toEqual({
		start: '2026-08-25',
		end: '2026-08-31'
	});
});

test('a step lands on a preset, and stops at the ends rather than wrapping', () => {
	// The ends are read off the list, never written down. Seven was the narrowest
	// preset until a one-day span was added on 2026-09-06, and a literal end
	// stops testing the end the moment the list moves under it.
	const narrowest = Math.min(...presets());
	const widest = Math.max(...presets());

	expect(stepPreset(30, presets(), 1)).toBe(90);
	expect(stepPreset(30, presets(), -1)).toBe(14);
	expect(stepPreset(widest, presets(), 1)).toBe(widest);
	expect(stepPreset(narrowest, presets(), -1)).toBe(narrowest);
	expect(stepPreset(7, presets(), -1)).toBe(1);
	// A span that is not a preset still steps to the neighbouring one, so a
	// window left by a pan cannot strand the keys.
	expect(stepPreset(21, presets(), 1)).toBe(30);
	expect(stepPreset(21, presets(), -1)).toBe(14);
});

test('the cost of widening is the months not already in hand, and never a 404', () => {
	const available = ['2026-06', '2026-07', '2026-08'];
	expect(
		monthsToFetch({ start: '2026-08-01', end: '2026-08-28' }, available, ['2026-08'])
	).toEqual([]);
	expect(
		monthsToFetch({ start: '2026-06-15', end: '2026-08-28' }, available, ['2026-08'])
	).toEqual(['2026-06', '2026-07']);
	// A month the pipeline never published is not a cost. Asking for it would
	// only produce a 404 and a gap the charts already draw.
	expect(
		monthsToFetch({ start: '2026-04-01', end: '2026-08-28' }, available, ['2026-08'])
	).toEqual(['2026-06', '2026-07']);
});

test('the widest window this control offers never names a shard the cleanup age took', () => {
	// The gardener's `telemetry-aggregate` task deletes the browser's copy of a
	// month past its `public-copy` series, and that series must equal the ledger's
	// own `full-grain` one. This is the reader's half of the same promise: over
	// every anchor a year can offer, the months the widest read selects are all
	// months the cleanup kept, so widening costs a fetch and never a 404.
	//
	// It reads both windows rather than 366 and 14, because the two configs are
	// where the pair is set and a test that repeated the numbers would agree with
	// itself after an edit moved them.
	const publicCopy = telemetry().series?.['public-copy'];
	expect(publicCopy?.unit, 'the public copy is kept in whole months').toBe('months');
	const keepMonths = publicCopy?.value ?? 0;
	const maxDays = config().console?.max_window_days ?? 366;
	expect(keepMonths).toBe(telemetry().series?.['full-grain']?.value);

	for (let offset = 0; offset < 366; offset += 1) {
		const today = minus('2026-12-31', offset);
		const kept = monthsKept(today, keepMonths);
		const widest = windowOfDays(today, maxDays, 'right');
		expect(
			monthsToFetch(widest, kept, []),
			`a ${maxDays}-day read on ${today} wants a month ${keepMonths} months of cleanup removed`
		).toEqual(monthsInWindow(widest));
	}
});

test('THE ORACLE: the span picked on one console route is the span the next one opens on', async ({
	page
}) => {
	// The three routes share `idhazh:console-window`, which is the whole reason
	// the key exists: an operator comparing a slow day across Pipelines and
	// Hardware cannot do it if the two are on different spans. Bite-proofed both
	// ways round, because a route that only writes the key and never reads it
	// passes a one-way check.
	await page.goto(routeHref('pipelines'));
	await hydrated(page);
	await setWindow(page, 7);
	expect(await page.evaluate(() => localStorage.getItem('idhazh:console-window'))).toBe('7');

	await page.goto(routeHref('machine'));
	await hydrated(page);
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '7');
	await expect(page.locator('[data-window-preset="7"]')).toHaveAttribute('data-selected', 'true');
	const carried = await machineSpan(page);

	// And it is the span the route draws, not only the span it prints.
	await setWindow(page, 90);
	const widened = await machineSpan(page);
	expect(widened.runs, 'the carried span drew everything the widest one did').toBeGreaterThan(
		carried.runs
	);

	// Back the other way: Hardware writes the key and Pipelines reads it.
	await setWindow(page, 14);
	await page.goto(routeHref('pipelines'));
	await hydrated(page);
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '14');
	for (const surface of await windowed(page)) {
		expect(surface.days, `${surface.name} ignored the span carried from Hardware`).toBe(14);
	}
});

/** The span the control holds, and every span the route's windowed surfaces draw. */
async function heldAndDrawn(page: Page) {
	return {
		held: Number(await page.locator('[data-window-control]').getAttribute('data-window-days')),
		drawn: [...new Set((await windowed(page)).map((surface) => surface.days))]
	};
}

/** Click a route's tab and wait for that route's panels. The router follows the
 * link with no page load, which a mark left on `window` proves: a load would
 * clear it, and a page load is the move the case above already takes. */
async function followTab(page: Page, route: string) {
	await page.evaluate(() => Object.assign(window, { stayedOnPage: true }));
	await page.locator(`[data-console-tab="${route}"]`).click();
	await expect(page.locator(`[data-console-panels="${route}"]`)).toBeVisible();
	expect(
		await page.evaluate(() => 'stayedOnPage' in window),
		'the tab loaded a page, so the move this case is about never happened'
	).toBe(true);
}

test('THE ORACLE: after a tab click, the control holds the span the next route draws', async ({
	page
}) => {
	// The case above moves with a page load. An operator moves with the tabs, and
	// the router then mounts the next route under the same layout and drops the
	// last one, with the stored span read again by the route that arrives. The
	// control used to stay on 14 days there while every Judgement panel drew 1.
	// So the control is compared with what the page draws, never with a number
	// the data holds, and every check retries until the route has settled.
	await page.goto(routeHref('pipelines'));
	await hydrated(page);
	await setWindow(page, 1);

	await followTab(page, 'judgement');
	await expect.poll(() => heldAndDrawn(page)).toEqual({ held: 1, drawn: [1] });
	await expect(page.locator('[data-window-preset="1"] input')).toBeChecked();
	await expect(page.locator('[data-window-preset="1"] input')).toBeEnabled();

	// Back the other way, on a span picked on the route the tab led to.
	await setWindow(page, 7);
	await followTab(page, 'pipelines');
	await expect.poll(() => heldAndDrawn(page)).toEqual({ held: 7, drawn: [7] });
	await expect(page.locator('[data-window-preset="7"] input')).toBeChecked();
	await expect(page.locator('[data-window-preset="7"] input')).toBeEnabled();
});

async function disclosures(page: Page) {
	return page.locator('[data-daily-figures]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			name: node.getAttribute('data-daily-figures') ?? '',
			summary: (node.querySelector(':scope > summary')?.textContent ?? '').replace(/\s+/g, ' ').trim(),
			dates: [...node.querySelectorAll('[data-chart-day], [data-model-day]')].map(
				(row) =>
					row.getAttribute('data-chart-day') ?? row.getAttribute('data-model-day') ?? ''
			)
		}))
	);
}

test('a daily table drawn under the control stays inside the control span', async ({
	page
}) => {
	// The two tables ignored the preset above them until 2026-08-31, so the cards
	// on Summaries said 7 days while the rows under them held every day the
	// ledger ever wrote. Two answers to one question on one page is exactly what
	// the shared control was built to remove.
	//
	// The reducer tests own which dates have rows. This browser check keeps only
	// the route contract: the open control names the span, the disclosure says
	// the same span, and every row the table does draw fits inside it.
	for (const id of Object.keys(BY_ROUTE) as RouteId[]) {
		const expected = BY_ROUTE[id];
		if (expected === null || !expected.dailyTable) continue;
		const route = routeHref(id);
		await page.goto(route);
		await hydrated(page);

		expect((await disclosures(page)).length, `${route} publishes no daily table`).toBe(1);

		for (const preset of presets()) {
			await setWindow(page, preset);
			const [table] = await disclosures(page);
			// The name is one string on both routes and it says the span out loud.
			// One day is not day by day, so at one day it names that day (Reader,
			// 2026-10-07).
			expect(table.summary, `${route} renamed its daily table`).toBe(
				preset === 1
					? 'Show these figures for this one day'
					: `Show these figures day by day, over these ${preset} days`
			);
			expect(
				table.summary,
				`${route} opens a table without saying how many days are in it`
			).toMatch(spanSaid(preset));
			expect(table.summary, `${route} says "1 days"`).not.toMatch(ONE_DAYS);

			const sorted = [...table.dates].sort();
			expect(new Set(sorted).size, `${route} repeated a daily row at ${preset} days`).toBe(
				sorted.length
			);
			expect(sorted.length, `${route} drew more rows than days in the control span`).toBeLessThanOrEqual(
				preset
			);
			if (sorted.length > 1) {
				const span =
					Math.round(
						(Date.parse(`${sorted[sorted.length - 1]}T00:00:00Z`) -
							Date.parse(`${sorted[0]}T00:00:00Z`)) /
							86_400_000
					) + 1;
				expect(span, `${route} drew rows outside the ${preset}-day span`).toBeLessThanOrEqual(
					preset
				);
			}
		}
	}
});

test('a shut daily table is a line of prose, not a card', async ({ page }) => {
	// Shut, it was a bordered, shadowed, rounded card wrapped around one line of
	// link text - the visual weight of a section with the content of a footnote,
	// which is what made it read as something hanging off the page. An eye cannot
	// check a box-shadow, so this reads the computed values against the prose
	// beside it rather than against a hard-coded string.
	for (const id of Object.keys(BY_ROUTE) as RouteId[]) {
		const expected = BY_ROUTE[id];
		if (expected === null || !expected.dailyTable) continue;
		const route = routeHref(id);
		await page.goto(route);
		const shut = await page.locator('[data-daily-figures]').evaluate((node) => {
			const details = node as HTMLDetailsElement;
			details.open = false;
			const style = getComputedStyle(details);
			return {
				open: details.open,
				border: style.borderTopWidth,
				shadow: style.boxShadow,
				background: style.backgroundColor,
				padding: style.paddingTop
			};
		});
		expect(shut.open, `${route} opens its daily table on arrival`).toBe(false);
		expect(shut.border, `${route} keeps a border on a shut disclosure`).toBe('0px');
		expect(shut.shadow, `${route} keeps a shadow on a shut disclosure`).toBe('none');
		expect(shut.padding, `${route} keeps a card's padding on a shut disclosure`).toBe('0px');
		expect(
			['rgba(0, 0, 0, 0)', 'transparent'],
			`${route} keeps a card background on a shut disclosure: ${shut.background}`
		).toContain(shut.background);

		// And open it is a panel again, because then it holds one.
		const opened = await page.locator('[data-daily-figures]').evaluate((node) => {
			(node as HTMLDetailsElement).open = true;
			const style = getComputedStyle(node);
			return { border: style.borderTopWidth, shadow: style.boxShadow };
		});
		expect(opened.border, `${route} draws no frame around an open table`).not.toBe('0px');
		expect(opened.shadow, `${route} draws no elevation on an open table`).not.toBe('none');
	}
});

test('the prerendered page opens on the configured window, whatever was stored', async ({
	page
}) => {
	await page.goto(routeHref('pipelines'));
	await hydrated(page);
	await setWindow(page, presets().at(-1) as number);

	// Read on mount and never during prerender: the document a browser is handed
	// is always the window the server drew, so first paint cannot flicker.
	const document = await (await page.request.get(routeHref('pipelines'))).text();
	expect(document).toContain('data-window-control');
	expect(document).toContain(`data-window-days="${defaultDays()}"`);

	await page.reload();
	await hydrated(page);
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(presets().at(-1))
	);
});

test('the control names the window it is holding, and is inert before a script runs', async ({
	page
}) => {
	await page.goto(routeHref('pipelines'));

	const status = page.locator('[data-window-status]');
	await hydrated(page);
	await expect(status).toContainText(`showing ${defaultDays()} days`);
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');

	// Every preset is on the page at once. A menu would hide the wide one, which
	// is the one with a cost worth reading before it is paid.
	for (const preset of presets()) {
		await expect(page.locator(`[data-window-preset="${preset}"]`)).toBeVisible();
	}

	// And the prerendered document says it needs a script rather than offering a
	// control that would do nothing when clicked. It says the same of the panels
	// it governs: they hold their reserved shape with no script and nothing else,
	// because the rows they draw arrive by fetch. The sentence names the control
	// it means, because since 2026-09-27 the control is on the strip above and
	// the sentence is under the band.
	const document = await (await page.request.get(routeHref('pipelines'))).text();
	expect(document).toContain('The days control above needs JavaScript');
	expect(document).toContain('they draw rows a browser fetches');
	expect(
		document,
		'the prerendered control still claims the sections below are showing data'
	).not.toContain('needs JavaScript. Every windowed section below is showing');
	expect(document).toMatch(/<input[^>]*name="console-window"[^>]*disabled/);
});

test('one day is one day, in the sentence and to a screen reader', async ({ page }) => {
	// The one-day preset read "1 days" on its tile and in the sentence under the
	// band. The tile shows `1D` now, and still says its unit to a screen reader,
	// in the singular - and the `D` is hidden from that reader, so it is never
	// heard as "1D day".
	await page.goto(routeHref('pipelines'));
	await hydrated(page);
	const narrowest = Math.min(...presets());
	expect(narrowest, 'the presets no longer offer a single day, so this proves nothing').toBe(1);
	await setWindow(page, narrowest);
	await expect(page.locator('[data-window-status]')).toContainText('showing 1 day.');
	await expect(page.locator('[data-window-preset="1"] [aria-hidden="true"]')).toHaveText('1D');
	await expect(page.getByRole('radio', { name: '1 day', exact: true })).toHaveCount(1);
	await expect(page.getByRole('radio', { name: '14 days', exact: true })).toHaveCount(1);
});

/** The control and the strip it stands on, in viewport coordinates. */
async function controlBox(page: Page) {
	return page.evaluate(() => {
		const strip = (document.querySelector('[data-console-strip]') as HTMLElement).getBoundingClientRect();
		const control = (document.querySelector('[data-window-control]') as HTMLElement).getBoundingClientRect();
		const tabs = (document.querySelector('[data-console-nav]') as HTMLElement).getBoundingClientRect();
		return {
			innerWidth: window.innerWidth,
			width: Math.round(control.width),
			height: Math.round(control.height),
			left: Math.round(control.left),
			right: Math.round(control.right),
			top: Math.round(control.top),
			stripLeft: Math.round(strip.left),
			stripRight: Math.round(strip.right),
			tabsBottom: Math.round(tabs.bottom),
			shown: [...document.querySelectorAll('[data-window-preset] [aria-hidden="true"]')].map(
				(node) => (node.textContent ?? '').trim()
			)
		};
	});
}

for (const width of [390, 768, 1440]) {
	test(`THE ORACLE: the days control is five short tiles, 236 by 44, at ${width}`, async ({
		page
	}) => {
		// Five tiles at the 2.75rem touch floor both ways, 4px apart, and nothing
		// beside them: no label and no room kept for a price. Below the wide
		// breakpoint the control starts its own row under the tabs; from it, the
		// control ends the one-row strip.
		await page.setViewportSize({ width, height: 900 });
		await page.goto(routeHref('pipelines'));
		await hydrated(page);
		const at = await controlBox(page);
		console.log(
			`[control] asked ${width} -> innerWidth ${at.innerWidth}, ${at.width}x${at.height} ` +
				`at ${at.left}-${at.right}, strip ${at.stripLeft}-${at.stripRight}, tabs end ${at.tabsBottom}, ` +
				`control top ${at.top}`
		);
		expect(at.shown).toEqual(presets().map((preset) => `${preset}D`));
		expect(Math.abs(at.width - 236), `the control is ${at.width}px wide`).toBeLessThanOrEqual(1);
		expect(Math.abs(at.height - 44), `the control is ${at.height}px tall`).toBeLessThanOrEqual(1);
		if (width < 1024) {
			expect(Math.abs(at.left - at.stripLeft), 'the control does not start its row').toBeLessThanOrEqual(1);
			expect(at.top, 'the control is not on a row of its own under the tabs').toBeGreaterThanOrEqual(
				at.tabsBottom
			);
		} else {
			expect(Math.abs(at.right - at.stripRight), 'the control left the end of the strip').toBeLessThanOrEqual(1);
		}
	});
}

/** The top of everything between the strip and the first panel, and of that
 * panel - in page coordinates, so a scroll cannot read as a move. */
async function belowTheStrip(page: Page): Promise<Record<string, number>> {
	return page.evaluate(() => {
		const tops: Record<string, number> = {};
		for (const selector of [
			'[data-console-completeness]',
			'[data-console-band]',
			'[data-window-status]',
			'[data-console-panel]'
		]) {
			const node = document.querySelector(selector);
			if (node !== null) tops[selector] = node.getBoundingClientRect().top + window.scrollY;
		}
		return tops;
	});
}

for (const width of [390, 768, 1440]) {
	test(`THE ORACLE: picking each preset moves nothing below the strip, at ${width}`, async ({
		page
	}) => {
		// The tiles once kept a second line for a price whether or not one was
		// due, because a price that landed or cleared moved seven panels. The
		// price is in the sentence under the band now, and that sentence keeps the
		// room of its longest form - so this is the property a smaller control
		// could silently lose. It starts on one day, where every wider preset that
		// reaches the canary's older month is priced.
		await page.addInitScript(() => localStorage.setItem('idhazh:console-window', '1'));
		await page.setViewportSize({ width, height: 900 });
		await page.goto(routeHref('pipelines'));
		await expect(page.locator('[data-window-preset="1"] input')).toBeEnabled();
		await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '1');
		await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');
		// The canary keeps two telemetry months, so the widest presets reach one
		// the one-day window never fetched. Without a price this proves nothing.
		await expect(page.locator('[data-window-status]')).toContainText('would fetch');
		const before = await belowTheStrip(page);
		expect(Object.keys(before), 'a block below the strip is missing').toHaveLength(4);

		for (const preset of presets().filter((days) => days > 1)) {
			await setWindow(page, preset);
			await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');
			const after = await belowTheStrip(page);
			const moved = Object.keys(before)
				.filter((name) => Math.abs(after[name] - before[name]) > 1)
				.map((name) => `${name}: ${Math.round(before[name])} -> ${Math.round(after[name])}`);
			expect(moved, `picking ${preset} days moved the page at ${width}:\n${moved.join('\n')}`).toEqual([]);
		}
	});
}
test('the standing band does not follow the window', async ({ page }) => {
	// The site size is a level, not a rate, and since 2026-08-30 it is in the
	// standing band - which is not windowed at all, because that band stands on
	// every console route and a figure that moved with a control on one of them
	// would read as five different sites. So the whole sentence holds at every
	// preset, not only the number in it.
	await page.goto(routeHref('pipelines'));
	await hydrated(page);

	const size = page.locator('[data-band-size]');
	const before = ((await size.textContent()) ?? '').trim();
	await setWindow(page, 7);
	await expect(size).toHaveText(before);
	await expect(size).toContainText(/of the 1 GB limit/);

});

for (const [id, declared] of Object.entries(BY_ROUTE) as [RouteId, (typeof BY_ROUTE)[RouteId]][]) {
  if (declared === null) continue; // The Data explorer has its own explicit window coverage.
  test(`THE ORACLE: ${id} obeys the common control over every declared surface`, async ({ page }) => {
    await page.goto(routeHref(id));
    await hydrated(page);
    expect(presets().length, 'a control with one option cannot disagree with anything').toBeGreaterThan(1);
    const found = await windowed(page);
    expect(found.map((surface) => surface.name).sort(), 'the declared surface inventory must be complete').toEqual(declared.windowed);
    for (const preset of presets()) {
      await setWindow(page, preset);
      const surfaces = await windowed(page);
      expect(surfaces.length, 'a declared surface disappeared').toBe(found.length);
      for (const surface of surfaces) {
        expect(surface.days, `${surface.name} is drawing a different window`).toBe(preset);
        expect(surface.says, `${surface.name} never says its span`).toMatch(spanSaid(preset));
        expect(surface.says, `${surface.name} says "1 days"`).not.toMatch(ONE_DAYS);
      }
    }
  });
}
