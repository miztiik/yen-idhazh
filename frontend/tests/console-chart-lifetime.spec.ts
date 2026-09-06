import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * THE ORACLE for a chart's lifetime: when it draws, what it draws after
 * something changes, and what it releases when it goes.
 *
 * Three faults sat in the engine and every one of them was invisible from
 * outside it. A chart took its option once at hydration and never looked at it
 * again, so a control that changed the option changed the markup and the page's
 * own description of the chart while the drawn chart went on showing the old
 * one - the prompt-cache switch on this route is exactly that, and the comment
 * above the chart said so out loud and worked around it with a remount. Every
 * mounted chart drew, including charts nine screens down and charts CSS had
 * hidden. And an instance could outlive the component that made it, because the
 * engine chunk is a network fetch and a component can be gone before it lands.
 *
 * So the engine publishes what it did, and this file reads it: `data-chart` on
 * the host says `waiting` or `live`, `data-chart-options` counts the times a
 * whole option was handed over and `data-chart-colours` counts the times only
 * the colours were, and `data-charts-live` on the document element says how
 * many instances the engine holds right now. A parity test that only compared
 * pictures would pass while the engine quietly re-sent every data point on
 * every theme flip; these counters are what make the cheap path checkable.
 *
 * The route is the Machine console because the canary build draws five engine
 * charts on it and gives one of them a control - a shape switch that changes
 * the option and nothing else.
 *
 * The bite, run 2026-09-06 on the canary build. Make `update` record the new
 * option and never hand it to the chart, and stop `destroy` releasing the
 * instance: the switch case fails with "the switch moved and the chart was
 * never told", `data-chart-options` 1 where 2 was expected, and the release
 * case fails with "the engine still holds charts belonging to the page a reader
 * left", 5 held where 0 was expected. The other two cases stay green, so each
 * case names one fault rather than four. Restoring the file - SHA-256
 * `9FACFE59...61A6` before the break and after it - turns all four green again.
 * Put both files back to `fdf5fc7a` instead and all four fail, three of them
 * because the engine published nothing to read.
 */

const DESKTOP = { width: 1440, height: 900 };
const NARROWER = { width: 1100, height: 900 };
const ROUTE = '/console/machine/';
/** The engine is a lazy chunk over the network, so first paint is not instant. */
const DRAWN = 20_000;

interface HostState {
	state: string;
	/** Null where the engine never touched the host, which is a failure in every
	 * case below that reads it. */
	options: number | null;
	colours: number | null;
	/** Distance from the top of the document, so a case can ask what a reader
	 * could actually see when the page settled. */
	top: number;
}

async function hostStates(page: Page): Promise<HostState[]> {
	return page.evaluate(() =>
		[...document.querySelectorAll('[data-chart]')].map((node) => {
			const count = (name: string) => {
				const raw = node.getAttribute(name);
				return raw === null ? null : Number(raw);
			};
			return {
				state: node.getAttribute('data-chart') ?? '',
				options: count('data-chart-options'),
				colours: count('data-chart-colours'),
				top: node.getBoundingClientRect().top + window.scrollY
			};
		})
	);
}

/** Every mark the chart at `index` has drawn, named by what it is, what colour
 * it carries and where it sits inside its own host.
 *
 * Sorted, because this is a set: the library is free to reorder its own nodes
 * between a repaint and a fresh draw, and an order that changed while every
 * mark stayed is not a fault. Positions are relative to the host and rounded,
 * so the comparison survives a page that scrolled and a browser that rounds.
 */
async function readMarks(page: Page, index: number): Promise<string[]> {
	return page.evaluate((at) => {
		const host = document.querySelectorAll('[data-chart]')[at];
		if (host === undefined) return [];
		const frame = host.getBoundingClientRect();
		return [
			...host.querySelectorAll('svg path, svg rect, svg circle, svg line, svg polyline, svg text')
		]
			.map((node) => {
				const box = node.getBoundingClientRect();
				const style = getComputedStyle(node);
				return [
					node.tagName,
					style.fill,
					style.stroke,
					Math.round(box.left - frame.left),
					Math.round(box.top - frame.top),
					Math.round(box.width),
					Math.round(box.height),
					(node.textContent ?? '').trim()
				].join('|');
			})
			.sort();
	}, index);
}

/** The marks once they have stopped moving. The library animates a change, so
 * one read can catch a chart part-way through a transition and report a frame
 * as a fact. */
async function settledMarks(page: Page, index: number): Promise<string[]> {
	let last: string[] = [];
	for (let tries = 0; tries < 40; tries += 1) {
		const now = await readMarks(page, index);
		if (now.length > 0 && now.join('\n') === last.join('\n')) return now;
		last = now;
		await page.waitForTimeout(200);
	}
	return last;
}

/** Where the chart belonging to a named control sits in the list of hosts, or
 * -1 for a panel that draws no engine chart. */
async function hostFor(page: Page, control: string): Promise<number> {
	return page.evaluate((name) => {
		let up = document.querySelector(`[data-shape-switch="${name}"]`);
		let host: Element | null = null;
		while (up !== null && host === null) {
			host = up.querySelector('[data-chart]');
			up = up.parentElement;
		}
		if (host === null) return -1;
		return [...document.querySelectorAll('[data-chart]')].indexOf(host);
	}, control);
}

/** Come to a chart the way a reader does, and wait for it to draw. Returns the
 * index it sits at, which is what `readMarks` and `hostStates` are keyed on. */
async function comeTo(page: Page, index: number): Promise<number> {
	const host = page.locator('[data-chart]').nth(index);
	await host.scrollIntoViewIfNeeded();
	await expect(host, 'a chart a reader scrolled to never drew').toHaveAttribute(
		'data-chart',
		'live',
		{ timeout: DRAWN }
	);
	return index;
}

async function theme(page: Page): Promise<string | null> {
	return page.evaluate(() => document.documentElement.getAttribute('data-theme'));
}

/** The built chunk holding a given marker. A chunk's name is a content hash, so
 * the two the engine needs are found by what is inside them - an attribute only
 * this engine writes, and the key the chart library stamps on a host. The build
 * is located from this file rather than from the working directory, which is
 * `frontend/` or the repository root depending on where the suite started. */
function chunkHolding(marker: string): string {
	const root = fileURLToPath(new URL('../build/_app/immutable/', import.meta.url));
	const found: string[] = [];
	const walk = (at: string) => {
		for (const entry of readdirSync(at, { withFileTypes: true })) {
			const path = join(at, entry.name);
			if (entry.isDirectory()) walk(path);
			else if (entry.name.endsWith('.js') && readFileSync(path, 'utf8').includes(marker)) {
				found.push(entry.name);
			}
		}
	};
	walk(root);
	if (found.length !== 1) {
		throw new Error(`expected one built chunk to hold ${marker}, found ${found.length}`);
	}
	return `**/${found[0]}`;
}

test('THE ORACLE: a chart nine screens down waits, and draws when a reader comes to it', async ({
	page
}) => {
	await page.setViewportSize(DESKTOP);
	await page.goto(ROUTE);
	await page.locator('[data-chart]').first().waitFor({ timeout: DRAWN });
	// The page is complete before any of this: the server drew every chart, so
	// what is being deferred is the tooltip and the redraw, never the picture.
	await page.waitForTimeout(2000);

	const drawn = await hostStates(page);
	expect(drawn.length, `${ROUTE} draws no engine chart - the scan is broken`).toBeGreaterThan(1);

	// The fold plus the one screen of reach the engine gives a chart. Nothing
	// past that has any reader asking for it yet.
	const reach = DESKTOP.height * 2;
	const far = drawn.filter((one) => one.top > reach);
	expect(far.length, 'no chart on this route is far enough down to defer').toBeGreaterThan(0);
	expect(
		far.filter((one) => one.state !== 'waiting').map((one) => Math.round(one.top)),
		'these charts drew before any reader came near them'
	).toEqual([]);

	// The other half of the same rule, and the one that matters more: offscreen
	// means "not yet", never "never".
	await comeTo(page, 0);
	const last = drawn.length - 1;
	if (drawn[last].top - drawn[0].top > reach) {
		expect(
			(await hostStates(page))[last].state,
			'coming to one chart drew a chart screens below it'
		).toBe('waiting');
	}
	await comeTo(page, last);
});

test('THE ORACLE: after a theme change and a resize the marks match a chart drawn fresh', async ({
	page,
	context
}) => {
	await page.setViewportSize(DESKTOP);
	await page.goto(ROUTE);
	const index = await comeTo(page, 0);
	const before = await settledMarks(page, index);
	expect(before.length, 'the chart drew nothing to compare').toBeGreaterThan(4);

	const start = (await hostStates(page))[index];
	expect(start.options, 'the chart took its whole option more than once before anything changed').toBe(1);
	expect(start.colours, 'the chart repainted before the theme moved').toBe(0);

	const was = await theme(page);
	await page.locator('[data-theme-toggle]').first().click();
	await expect.poll(() => theme(page), { timeout: DRAWN }).not.toBe(was);
	await page.setViewportSize(NARROWER);
	const after = await settledMarks(page, index);

	const moved = (await hostStates(page))[index];
	expect(moved.colours, 'the theme changed and the chart was never repainted').toBe(1);
	expect(
		moved.options,
		'a colour change handed the whole option over again, and its data with it'
	).toBe(1);
	expect(after, 'the theme changed and no mark changed with it').not.toEqual(before);

	// The same page, at the same size, loaded already in the new theme. That is
	// the expected set: a repaint that drops a mark, keeps an old colour or
	// leaves the chart at the old size differs from it.
	const fresh = await context.newPage();
	await fresh.setViewportSize(NARROWER);
	await fresh.goto(ROUTE);
	await comeTo(fresh, index);
	expect(await theme(fresh), 'the second page did not open in the theme just chosen').toBe(
		await theme(page)
	);
	const expected = await settledMarks(fresh, index);
	expect(expected.length, 'the freshly drawn chart drew nothing to compare').toBeGreaterThan(4);
	expect(after, 'a repainted chart and a freshly drawn one do not agree').toEqual(expected);
	await fresh.close();
});

test('THE ORACLE: a control that changes a chart changes the drawn chart', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.goto(ROUTE);

	const control = page.locator('[data-shape-switch="cache"]');
	await control.scrollIntoViewIfNeeded();
	const index = await hostFor(page, 'cache');
	expect(index, 'the prompt-cache panel draws no engine chart').toBeGreaterThanOrEqual(0);
	await comeTo(page, index);

	await expect(control).toHaveAttribute('data-shape', 'bars');
	const bars = await settledMarks(page, index);
	expect(bars.length, 'the chart drew nothing to compare').toBeGreaterThan(4);

	await control.locator('[data-shape-option="lines"]').click();
	await expect(control, 'the switch did not move').toHaveAttribute('data-shape', 'lines');
	const lines = await settledMarks(page, index);

	expect(
		(await hostStates(page))[index].options,
		'the switch moved and the chart was never told'
	).toBe(2);
	expect(lines, 'the switch moved and the live chart went on drawing the old shape').not.toEqual(
		bars
	);
});

test('THE ORACLE: a chart that leaves the page releases its instance', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.goto(ROUTE);
	await page.locator('[data-chart]').first().waitFor({ timeout: DRAWN });

	// Read the whole route the way a reader does, so every chart on it draws and
	// there is something to release.
	const count = await page.locator('[data-chart]').count();
	for (let at = 0; at < count; at += 1) await comeTo(page, at);
	await expect
		.poll(() => page.evaluate(() => document.querySelectorAll('[data-chart="waiting"]').length), {
			timeout: DRAWN
		})
		.toBe(0);

	const held = await page.evaluate(() => ({
		counted: Number(document.documentElement.getAttribute('data-charts-live') ?? -1),
		drawn: document.querySelectorAll('[data-chart="live"]').length
	}));
	expect(held.drawn, 'the route drew no chart to release').toBeGreaterThan(1);
	expect(held.counted, 'the engine holds a different number of charts from the page').toBe(
		held.drawn
	);

	// Client-side, so the engine's own count survives the move. A full page load
	// resets it and proves nothing.
	await page.locator('a[href$="/console/model/"]').first().click();
	await page.waitForURL('**/console/model/**');
	expect(
		await page.evaluate(() => performance.getEntriesByType('navigation').length),
		'the link reloaded the page, so the count was reset rather than kept'
	).toBe(1);

	await expect
		.poll(
			() =>
				page.evaluate(() => {
					const counted = Number(document.documentElement.getAttribute('data-charts-live') ?? -1);
					return counted - document.querySelectorAll('[data-chart="live"]').length;
				}),
			{
				timeout: DRAWN,
				message: 'the engine still holds charts belonging to the page a reader left'
			}
		)
		.toBe(0);
});

test('THE ORACLE: the page is complete with the engine gone, and nothing is thrown', async ({
	page
}) => {
	// The engine is two network fetches - the module and the chart library - and a
	// reader on a bad connection is the ordinary case rather than the exotic one.
	// What the server drew has to stand on its own, and a chart that cannot
	// hydrate has to say so in the console instead of throwing once per chart at a
	// reader who can do nothing about it. Both fetches get an arm, because a catch
	// on one of them is not a catch on the other.
	const arms = [
		{ what: 'the engine module', chunk: chunkHolding('data-charts-live') },
		{ what: 'the chart library', chunk: chunkHolding('_echarts_instance_') }
	];

	await page.setViewportSize(DESKTOP);
	for (const arm of arms) {
		const thrown: string[] = [];
		const caught = (error: Error) => thrown.push(String(error));
		page.on('pageerror', caught);

		await page.goto(ROUTE);
		// A service worker serves these from its own cache, and `route` never sees a
		// request it fulfils - so the block would report a pass while the engine
		// loaded from disk.
		await page.evaluate(async () => {
			for (const one of await navigator.serviceWorker.getRegistrations()) await one.unregister();
			for (const name of await caches.keys()) await caches.delete(name);
		});

		let blocked = 0;
		await page.route(arm.chunk, (route) => {
			blocked += 1;
			return route.abort();
		});
		await page.reload({ waitUntil: 'load' });
		const count = await page.locator('.chart-host').count();
		for (let at = 0; at < count; at += 1) {
			await page.locator('.chart-host').nth(at).scrollIntoViewIfNeeded();
		}
		await page.waitForTimeout(2500);

		expect(blocked, `${arm.what} was never blocked, so this arm proves nothing`).toBeGreaterThan(0);
		const complete = await page.evaluate(() => ({
			hosts: document.querySelectorAll('.chart-host').length,
			drawn: document.querySelectorAll('.chart-host svg').length,
			marks: document.querySelectorAll('.chart-host svg *').length,
			words: (document.body.innerText ?? '').trim().length
		}));
		expect(complete.hosts, `${arm.what}: the route drew no chart`).toBeGreaterThan(1);
		expect(complete.drawn, `${arm.what}: a chart lost its picture`).toBe(complete.hosts);
		expect(complete.marks, `${arm.what}: the charts are empty frames`).toBeGreaterThan(20);
		expect(complete.words, `${arm.what}: the page is blank`).toBeGreaterThan(1000);
		expect(thrown, `${arm.what} failed to load and a chart threw at the reader`).toEqual([]);

		page.off('pageerror', caught);
		await page.unroute(arm.chunk);
	}
});
