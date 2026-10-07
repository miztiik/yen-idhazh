import { expect, test, type Locator, type Page, type Request } from './support/browser';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { KILL_FILE } from '../src/lib/offline';
import { openExplorer, runExplorer } from './support/explorer-answer';
import { consolePanels, CONSOLE_ROUTE_PATHS } from './support/console-panels';
import { CONSOLE_WIDTHS, CONSOLE_WINDOW_HEIGHT, type ConsoleWidth } from './support/console-widths';
import { fillShare, readPanel } from './support/panel-gates';
import { newestDate } from './support/published';
import { viewsOf } from './support/views';

/**
 * THE CAPTURE: every console panel, pictured the way a reviewer needs to see
 * it, and written where a run can hand it over.
 *
 * Every panel id in `console.panel_groups` is pictured at every console width
 * in light and at the narrowest in dark (`viewsOf`), and that dark picture is
 * taken once more with every data request its route made answered 503 - the
 * one way to see a
 * panel's broken-fetch picture without a second build. The list is the config,
 * never an array written here, so a panel added to the console without a
 * picture fails this file rather than shipping unseen. The one exception is a
 * route that draws no panel id at all, which is named in `DRAWS_NO_PANEL_ID`
 * and held to drawing none, so it cannot start drawing them unpictured.
 *
 * **Nothing here compares pixels.** A committed baseline goes red when the
 * runner's fonts differ from the machine that wrote it, and a gate people learn
 * to re-bless is worse than none; the arithmetic gates live in
 * `panel-sufficiency.spec.ts`. This file makes the pictures and proves each one
 * is whole. Files are `<panel-id>--<width>--<theme>--<state>.png` under
 * `frontend/test-results/panels/`, so one panel at one width in one theme from
 * two runs lands side by side in a listing. An explicit CI design-review run
 * uploads the folder; routine CI skips this spec.
 *
 * **What makes an image whole.** A chart draws only once it is near the
 * window, so every panel is walked into view and the page is left to finish
 * before anything is taken. Each image is the panel and a band of the page
 * around it, half the gap between panels, so the panel's edge against its
 * ground is in the picture. A strip stuck to the top of the window belongs to
 * no panel, so it is unstuck for the shot. A panel taller than the window is
 * pictured on the page, past the window's edges, at the window the page was
 * opened at: a window grown to fit it would also grow a panel sized from the
 * window's height. And Playwright cuts a clip to the page without saying so,
 * so the image's own size is checked against the box that was asked for.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(here, '..', 'test-results', 'panels');

const THEMES = ['light', 'dark'] as const;
type Theme = (typeof THEMES)[number];

/** The picture that decides: the narrowest width, in the theme nobody checks. */
const BROKEN_WIDTH: ConsoleWidth = CONSOLE_WIDTHS[CONSOLE_WIDTHS.length - 1];
const BROKEN_THEME: Theme = 'dark';

/** The routes `console.panel_groups` orders that draw no panel id yet.
 *
 * Stated here rather than discovered, so a route that starts drawing ids fails
 * this file until its panels are pictured, instead of staying unpictured with a
 * green run. The Pipelines route draws its sections in the configured order,
 * but it hands `Panel` no id: of its eleven sections, one draws three panels,
 * four draw no panel frame at all, and none carries its id - so no picture can
 * be filed by one. Giving each section one framed, addressed panel is a change
 * to the route, not to its pictures.
 */
const DRAWS_NO_PANEL_ID: ReadonlySet<string> = new Set(['pipelines']);

/** What a page asks for its rows with. A script, a font or a stylesheet is
 * the page itself, and refusing one would picture a broken page rather than a
 * broken fetch. Executable wasm is code even when requested through fetch.
 * The worker's kill switch is fetched too, and it is the site
 * deciding whether to keep its worker rather than a panel reading its rows. */
const DATA_REQUESTS = new Set(['fetch', 'xhr']);

/** How long a page is given to settle once every fetch it made was refused.
 * A panel still waiting after that is a finding, not a failure: a failed fetch
 * drawn as a wait is exactly what the broken picture exists to show. */
const REFUSED_SETTLE_MS = 5_000;

/** Every stuck strip outside the panels, unstuck for the shot only. Sticky
 * keeps its place in the flow, so turning it static moves nothing else. */
const UNSTUCK = `[data-capture-unstuck='sticky'] { position: static !important; }
[data-capture-unstuck='fixed'] { visibility: hidden !important; }`;

const selectorOf = (id: string): string => `[data-console-panel-id="${id}"]`;

const withoutQuery = (url: string): string => url.split(/[?#]/)[0];

const readsRows = (request: Request): boolean =>
	DATA_REQUESTS.has(request.resourceType()) && !withoutQuery(request.url()).endsWith(`/${KILL_FILE}`)
		&& !withoutQuery(request.url()).endsWith('.wasm');

async function opened(page: Page, address: string, width: number, theme: Theme): Promise<void> {
	await page.setViewportSize({ width, height: CONSOLE_WINDOW_HEIGHT });
	await page.addInitScript((chosen) => localStorage.setItem('idhazh:theme', chosen), theme);
	await page.goto(address);
	await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
}

/** Every address the page asks for rows at from now on, without its query. */
function recorded(page: Page): Set<string> {
	const asked = new Set<string>();
	page.on('request', (request) => {
		if (readsRows(request)) asked.add(withoutQuery(request.url()));
	});
	return asked;
}

/** Answer every recorded address, and the query door's, with a 503 from now on.
 * Returns the addresses actually refused, so a caller can tell a refused fetch
 * from one the page never made again. */
async function refusing(page: Page, asked: ReadonlySet<string>): Promise<Set<string>> {
	const refused = new Set<string>();
	await page.route(
		(url) => asked.has(withoutQuery(url.href)) || url.pathname.includes('/state/compact/'),
		async (intercepted) => {
			refused.add(withoutQuery(intercepted.request().url()));
			await intercepted.fulfill({ status: 503, body: '' });
		}
	);
	return refused;
}

/** Check refused prerequisites; a refused ledger index prevents its data-file requests. */
async function allRefused(asked: ReadonlySet<string>, refused: ReadonlySet<string>): Promise<void> {
	const prerequisites = [...asked].filter((address) => {
		const pathname = new URL(address).pathname;
		return !pathname.includes('/state/compact/') || pathname.includes('/index/');
	});
	await expect
		.poll(() => prerequisites.filter((url) => !refused.has(url)), {
			timeout: 20_000,
			message: 'the broken load never asked again for data the first load read'
		})
		.toEqual([]);
}

/** Bring every panel near the window once, so every chart is asked to draw. */
async function walked(page: Page, panels: readonly string[]): Promise<void> {
	for (const id of panels) {
		const panel = page.locator(selectorOf(id));
		await expect(panel, `console.panel_groups names ${id}, and the page draws no panel with that id`).toHaveCount(1);
		await panel.evaluate((node) => node.scrollIntoView({ block: 'center', behavior: 'instant' }));
	}
	await page.evaluate(() => {
		for (const node of document.querySelectorAll('body *')) {
			if (node.closest('[data-console-panel-id]') !== null) continue;
			const { position } = getComputedStyle(node);
			if (position === 'sticky' || position === 'fixed') node.setAttribute('data-capture-unstuck', position);
		}
	});
}

/** The panels still waiting: a chart not yet drawn, or rows not yet arrived. */
async function waiting(page: Page, panels: readonly string[]): Promise<string[]> {
	return page.evaluate(
		(ids) =>
			ids.filter(
				(id) =>
					document
						.querySelector(`[data-console-panel-id="${id}"]`)
						?.querySelector('[data-chart="waiting"], [data-panel-state="loading"], [data-empty-state="loading"]') !=
					null
			),
		panels
	);
}

/** Which nothing a panel is drawing, or `drawn` when it is drawing its rows. */
async function stateOf(panel: Locator): Promise<string> {
	return panel.evaluate((node) => {
		const states = new Set(
			[...node.querySelectorAll('[data-panel-state], [data-empty-state]')].map(
				(one) => one.getAttribute('data-panel-state') ?? one.getAttribute('data-empty-state') ?? ''
			)
		);
		for (const state of ['unreachable', 'loading', 'missing', 'quiet', 'too-few']) if (states.has(state)) return state;
		return 'drawn';
	});
}

interface Shot {
	id: string;
	file: string;
	state: string;
	share: number | null;
}

/** One panel, padded by half the gap to its neighbour, checked whole and written. */
async function shot(page: Page, id: string, file: string): Promise<Shot> {
	const panel = page.locator(selectorOf(id));
	const pad = await panel.evaluate((node) => Math.floor((parseFloat(getComputedStyle(node).marginTop) || 0) / 2));
	// Placed with its top one band below the window's top, not centred:
	// `scrollIntoView` centres inside the window less its `scroll-padding-top`,
	// which the console sets while its strip is stuck. Then measured on the
	// page, which is the picture's frame: a window grown to fit a tall panel
	// would also grow a panel sized from the window's height - the Data
	// explorer's answer is one window tall below 1024 px - and picture the page
	// at a window it was not opened at.
	const placed = await panel.evaluate((node, gap) => {
		window.scrollTo({ top: window.scrollY + node.getBoundingClientRect().top - gap, behavior: 'instant' });
		if (node.getClientRects().length === 0) return null;
		const at = node.getBoundingClientRect();
		const root = document.documentElement;
		return {
			box: { x: at.left + window.scrollX, y: at.top + window.scrollY, width: at.width, height: at.height },
			size: { width: root.scrollWidth, height: root.scrollHeight }
		};
	}, pad);
	if (placed === null) throw new Error(`${id} has no box to picture`);
	const { box, size } = placed;
	const left = Math.max(0, Math.floor(box.x - pad));
	const top = Math.max(0, Math.floor(box.y - pad));
	const clip = {
		x: left,
		y: top,
		width: Math.min(size.width, Math.ceil(box.x + box.width + pad)) - left,
		height: Math.min(size.height, Math.ceil(box.y + box.height + pad)) - top
	};
	expect(
		box.y >= clip.y && box.y + box.height <= clip.y + clip.height,
		`${id} does not fit inside its own picture`
	).toBe(true);

	// `fullPage` reads the clip on the page and draws past the window's edges.
	const image = await page.screenshot({ clip, fullPage: true, style: UNSTUCK, animations: 'disabled' });
	// A PNG names its own size in bytes 16 to 23. A clip past the page is cut
	// to it without an error, so this is the only place a short image shows.
	const drawn = { width: image.readUInt32BE(16), height: image.readUInt32BE(20) };
	expect(drawn, `the picture of ${id} was cut short of the box it was asked for`).toEqual({
		width: clip.width,
		height: clip.height
	});
	const blank = await panel.evaluate((node) =>
		[...node.querySelectorAll('[data-readout]')]
			.filter((strip) => (strip.textContent ?? '').trim() === '')
			.map((strip) => strip.getAttribute('data-readout') ?? 'a strip')
	);
	expect(blank, `${id} was pictured with a readout strip that says nothing`).toEqual([]);
	writeFileSync(path.join(OUT, file), image);
	return { id, file, state: await stateOf(panel), share: fillShare(await readPanel(panel)) };
}

const line = (one: Shot): string =>
	`${one.id.padEnd(28)} ${one.state.padEnd(12)} share=${one.share === null ? 'none ' : one.share.toFixed(3)} ${one.file}`;

test('every route console.panel_groups names is one a capture can open', () => {
	const named = consolePanels().routes.map((route) => route.key);
	expect(named.sort(), 'the capture opens a route the config no longer names').toEqual(
		Object.keys(CONSOLE_ROUTE_PATHS).sort()
	);
});

for (const route of DRAWS_NO_PANEL_ID) {
	test(`the ${route} route still draws no panel id, so none of its panels can be pictured`, async ({ page }) => {
		const listed = consolePanels().routes.find((one) => one.key === route);
		if (listed === undefined) throw new Error(`console.panel_groups no longer names the ${route} route`);
		await opened(page, listed.address, CONSOLE_WIDTHS[0], 'light');
		test.info().annotations.push({
			type: 'not pictured',
			description: `${listed.panels.length} ${route} panels: ${listed.panels.join(', ')}`
		});
		await expect(
			page.locator('[data-console-panel-id]'),
			`${route} now draws panel ids - take it out of DRAWS_NO_PANEL_ID so its panels are pictured`
		).toHaveCount(0);
	});
}

test('the broken load refuses every data request the loaded page made, and the page says so', async ({ page }) => {
	// The Pipelines route reads its rows after it arrives, which no pictured
	// route does yet - so it is the one place the refusal the broken pictures
	// depend on can be shown working before a pictured panel fetches. Its own
	// surface says which nothing it is holding, in `data-telemetry-state`.
	const address = CONSOLE_ROUTE_PATHS.pipelines;
	const surface = page.locator('[data-console-panels="pipelines"]');
	const asked = recorded(page);
	await opened(page, address, BROKEN_WIDTH, BROKEN_THEME);
	await expect(surface).not.toHaveAttribute('data-telemetry-state', 'loading', { timeout: 20_000 });
	expect(asked.size, 'the route asked for no rows, so this proves nothing').toBeGreaterThan(0);
	expect(
		[...asked].filter((url) => url.endsWith(`/${KILL_FILE}`)),
		"the worker's kill switch was counted as a panel's data"
	).toEqual([]);

	const first = new Set(asked);
	const refused = await refusing(page, first);
	await opened(page, address, BROKEN_WIDTH, BROKEN_THEME);
	await allRefused(first, refused);
	await expect(surface).toHaveAttribute('data-telemetry-state', 'unreachable', { timeout: 20_000 });
});

const PICTURED = Object.keys(CONSOLE_ROUTE_PATHS).filter((route) => !DRAWS_NO_PANEL_ID.has(route));

for (const route of PICTURED) {
	for (const { width, theme } of viewsOf(CONSOLE_WIDTHS, THEMES)) {
		const broken = width === BROKEN_WIDTH && theme === BROKEN_THEME;
		test(`every ${route} panel, pictured at ${width} in ${theme}`, async ({ page }) => {
			const started = Date.now();
			const listed = consolePanels().routes.find((one) => one.key === route);
			if (listed === undefined) throw new Error(`console.panel_groups no longer names the ${route} route`);
			mkdirSync(OUT, { recursive: true });
			const notes = [`route=${route} address=${listed.address} width=${width} theme=${theme}`];

			const asked = recorded(page);
			await opened(page, listed.address, width, theme);
			if (route === 'data-explorer') {
				// A picture of the canary, so the page takes the canary's own newest day as today.
				await openExplorer(page, newestDate());
				await runExplorer(page);
			}
			await walked(page, listed.panels);
			await expect
				.poll(() => waiting(page, listed.panels), { timeout: 20_000, message: 'these panels never finished drawing' })
				.toEqual([]);
			const loaded: Shot[] = [];
			for (const id of listed.panels) loaded.push(await shot(page, id, `${id}--${width}--${theme}--loaded.png`));
			notes.push(...loaded.map(line));

			// A route that reads no rows after it arrives has no fetch to fail, and
			// its broken picture would be the healthy page under another name. So
			// the broken pictures are taken only where the page asked for data,
			// and the notes say which case this was.
			if (broken && asked.size === 0) {
				notes.push('', `the ${route} route asked for no data once it arrived, so there is no broken fetch to picture`);
			}
			if (broken && asked.size > 0) {
				const first = new Set(asked);
				const refused = await refusing(page, first);
				await opened(page, listed.address, width, theme);
				await walked(page, listed.panels);
				// Every request the first load made has to be made and refused again,
				// or a picture filed as broken could be the healthy page.
				if (route !== 'data-explorer') await allRefused(first, refused);
				const deadline = Date.now() + REFUSED_SETTLE_MS;
				while ((await waiting(page, listed.panels)).length > 0 && Date.now() < deadline) {
					await page.waitForTimeout(250);
				}
				const broke: Shot[] = [];
				for (const id of listed.panels) broke.push(await shot(page, id, `${id}--${width}--${theme}--unreachable.png`));
				notes.push(
					'',
					`with every data request refused (${refused.size}: ${[...refused].map((url) => new URL(url).pathname).join(' ')}):`
				);
				notes.push(...broke.map(line));
				const before = new Map(loaded.map((one) => [one.id, one.state]));
				const unexplained = broke.filter((one) => ['loading', 'quiet', 'missing'].includes(one.state));
				notes.push(
					'',
					unexplained.length === 0
						? 'every panel drew the unreachable state or what it already held'
						: 'drew a nothing other than unreachable when every fetch it made failed:'
				);
				for (const one of unexplained) {
					notes.push(`  ${one.id}: ${before.get(one.id)} on the loaded page, ${one.state} with every fetch refused`);
				}
			}

			notes.push('', `elapsed=${((Date.now() - started) / 1000).toFixed(1)} s`);
			writeFileSync(path.join(OUT, `_notes--${route}--${width}--${theme}.txt`), `${notes.join('\n')}\n`, 'utf8');
		});
	}
}
