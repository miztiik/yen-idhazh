import { expect, test, type Page, type Route } from '@playwright/test';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { compile, preprocess } from 'svelte/compiler';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { render } from 'svelte/server';
import {
	BASE,
	Intercepted,
	loaderSource,
	servedDayUrl,
	type Loader
} from './support/day-loader';

/**
 * The client loader, the retry, the anchor, and the state a reader meets when
 * the rest of a day never arrives.
 *
 * **This drives the module rather than a route, and it still should.** Both
 * reading routes call this loader now, but only for a day longer than
 * `ui.shell_seed_items` - and the canary day is eight stories against a seed of
 * fifteen, so a spec that navigated a route and aborted `digest.json` would
 * abort nothing, pass, and mean nothing. That is what a degraded arm reporting
 * zero interceptions always is. So this file drives the real module itself, and
 * prints what it intercepted.
 *
 * Each step is the real thing rather than a stand-in:
 *
 * - `day.ts` takes `base` from `$app/paths` as a VALUE, so plain Node cannot
 *   import it. Vite bundles it here with that one import aliased to a file
 *   holding the base a GitHub Pages project path would give it. The code under
 *   test is the shipped source, built by the tool that ships it.
 * - The bundle is injected into a page of the real built site before its own
 *   scripts run. That is a debugger injection rather than a script element, so
 *   the site's `script-src 'self'` is not relaxed to let it in, and the fetch
 *   it makes is same-origin, which `connect-src 'self'` already allows.
 * - Every request is intercepted at the network layer. An aborted request is a
 *   fetch that really failed, not a fetch that was replaced.
 *
 * **The base is what proves decision 5 on its own.** It is a project path, not
 * the empty string the preview server serves from, so a URL built without
 * `base` cannot match the pattern below and the count would be zero. Zero
 * fails.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, '..');
const scratch = path.join(frontend, 'test-results', 'payload-state');

const DATE = '2026-08-30';
/** What the loader must ask for, spelled out rather than rebuilt from `dayUrl`. */
const WANTED = servedDayUrl(DATE);
const PATTERN = `**${WANTED}`;

/** A day payload holding one story the page can actually render.
 *
 * Four names, because the loader keeps a story only when it carries everything
 * the page reads off it without a guard - a story short of one of them is
 * dropped and counted, which `malformed-day.spec.ts` is the arm for.
 */
const PAYLOAD = JSON.stringify({
	version: '2026-09-01T09:00',
	items: [
		{
			item_id: 'ai-1',
			title: 'A story',
			summary: 'A summary long enough to be a summary.',
			key_points: ['One point.']
		}
	]
});

const LOADER = loaderSource('payload-state');
const primed = new WeakSet<Page>();

/** The loader, live in a page of the real built site.
 *
 * Every navigation re-runs the injected script, so the module's held days start
 * empty on each `goto` - which is what lets one test drive a fresh fetch twice.
 */
async function armed(page: Page): Promise<void> {
	if (!primed.has(page)) {
		await page.addInitScript({ content: await LOADER });
		primed.add(page);
	}
	await page.goto('/');
}

interface Watched {
	states: string[];
	items: number | null;
}

/** One `watchDay` call, with every state it reported, in order. */
async function watch(page: Page, slowMs: number, again = false): Promise<Watched> {
	return page.evaluate(
		async ([date, ms, retry]: [string, number, boolean]) => {
			const loader = (window as unknown as { dayLoader: Loader }).dayLoader;
			const states: string[] = [];
			const day = await loader.watchDay(date, {
				slowMs: ms,
				again: retry,
				onStatus: (status: string) => states.push(status)
			});
			return { states, items: day === null ? null : day.items.length };
		},
		[DATE, slowMs, again] as [string, number, boolean]
	);
}

test.describe('the day a browser could not read', () => {
	test('a blocked payload leaves the page readable and offers another try', async ({ page }) => {
		const blocked = new Intercepted();
		await page.route(PATTERN, async (route) => {
			blocked.take(route.request().url());
			await route.abort('connectionfailed');
		});

		const said: string[] = [];
		const uncaught: string[] = [];
		page.on('console', (message) => {
			if (message.type() === 'warning' || message.type() === 'error') said.push(message.text());
		});
		page.on('pageerror', (error) => uncaught.push(String(error)));

		await armed(page);
		const first = await watch(page, 30_000);

		// The count is the proof the arm ran. Printed, because a degraded arm
		// that reports nothing is indistinguishable from one that did nothing.
		console.log(`[payload-state] blocked-request interceptions: ${blocked.count}`);
		expect(
			blocked.count,
			'nothing was intercepted, so this arm proves nothing about a blocked payload'
		).toBeGreaterThan(0);
		expect(blocked.urls, 'the loader asked for an address that skips `base`').toEqual([WANTED]);

		expect(first.states, 'a failed fetch did not end in its own state').toEqual([
			'loading',
			'unreachable'
		]);
		expect(first.items, 'a failed fetch handed back a day').toBeNull();
		expect(uncaught, 'a failed fetch threw where a reader could see it').toEqual([]);
		// The browser console is the whole logging surface (section 1b), and what
		// it logs is what a reader would have to hand back: which day, and that it
		// could not be read.
		expect(
			said.filter((line) => line.includes(DATE)),
			'nothing in the console named the day that failed'
		).not.toEqual([]);

		// Asking again with nothing changed costs no second request. One flaky
		// connection may not become a request per render.
		const held = await watch(page, 30_000);
		expect(held.states).toEqual(['loading', 'unreachable']);
		expect(blocked.count, 'a held failure went back to the network on its own').toBe(1);

		// The retry, which is the only thing that asks twice.
		await page.unroute(PATTERN);
		const served = new Intercepted();
		await page.route(PATTERN, async (route) => {
			served.take(route.request().url());
			await route.fulfill({ contentType: 'application/json', body: PAYLOAD });
		});
		const retried = await watch(page, 30_000, true);
		console.log(`[payload-state] retry interceptions: ${served.count}`);
		expect(served.count, 'the retry never reached the network').toBe(1);
		expect(retried.states, 'the retry did not recover').toEqual(['loading', 'ready']);
		expect(retried.items).toBe(1);
	});

	test('a slow payload says one sentence, and a healthy one says nothing', async ({ page }) => {
		const slow = new Intercepted();
		await page.route(PATTERN, async (route) => {
			slow.take(route.request().url());
			// Longer than the threshold below by enough that a busy machine cannot
			// turn this arm into a coin toss.
			await new Promise((done) => setTimeout(done, 900));
			await route.fulfill({ contentType: 'application/json', body: PAYLOAD });
		});

		await armed(page);
		const waited = await watch(page, 150);
		console.log(`[payload-state] slow-payload interceptions: ${slow.count}`);
		expect(slow.count, 'nothing was intercepted, so nothing was slowed').toBeGreaterThan(0);
		expect(waited.states, 'a wait past the threshold said nothing').toEqual([
			'loading',
			'slow',
			'ready'
		]);

		// The same fetch under a threshold it never reaches. This is the arm that
		// keeps the sentence from becoming a spinner: a healthy day never sees it.
		await armed(page);
		const healthy = await watch(page, 30_000);
		expect(healthy.states, 'a healthy fetch showed the waiting sentence').toEqual([
			'loading',
			'ready'
		]);
		expect(slow.count, 'the second arm never fetched').toBe(2);
	});

	test('a date the loader cannot read asks the network for nothing', async ({ page }) => {
		const asked = new Intercepted();
		// Exactly the shape the loader builds, and nothing wider. A page under
		// `**/digest/**` also serves an item's picture, so a wider pattern counts
		// the page's own assets and the arm fails on a fetch nobody made.
		await page.route('**/digest/**/digest.json', async (route) => {
			asked.take(route.request().url());
			await route.abort();
		});
		await armed(page);

		const built = await page.evaluate(() => {
			const loader = (window as unknown as { dayLoader: Loader }).dayLoader;
			// Three of these split into three truthy parts on a dash, which is why
			// the shape is checked rather than the split. A date arrives from a
			// route parameter or a search index entry, so it is text (Rule #11).
			return {
				whole: loader.dayUrl('2026-08-30'),
				elsewhere: loader.dayUrl('2026-08-30', '/somewhere'),
				words: loader.dayUrl('not-a-date'),
				traversal: loader.dayUrl('..-..-..'),
				short: loader.dayUrl('2026-8-3'),
				empty: loader.dayUrl('')
			};
		});

		expect(built.whole, 'the published address moved').toBe(WANTED);
		expect(built.elsewhere).toBe('/somewhere/digest/2026/08/30/digest.json');
		for (const [name, url] of Object.entries(built)) {
			if (name === 'whole' || name === 'elsewhere') continue;
			expect(url, `${name} still became an address`).toBeNull();
		}
		expect(asked.count, 'a date the loader cannot read reached the network').toBe(0);
	});
});

test.describe('the fragment', () => {
	test('a story that arrives late is scrolled to and focused', async ({ page }) => {
		await armed(page);

		const landed = await page.evaluate(() => {
			const loader = (window as unknown as { dayLoader: Loader }).dayLoader;
			// Nothing on the page carries this id yet, which is the state a reading
			// page is in while its stories are still on the way.
			const early = loader.restoreAnchor('#ai-4821903756');

			const story = document.createElement('article');
			story.id = 'ai-4821903756';
			story.textContent = 'A story that arrived after the document did.';
			story.style.marginBlockStart = '400vh';
			document.body.append(story);

			const found = loader.restoreAnchor('#ai-4821903756');
			return {
				early,
				found,
				focused: document.activeElement?.id ?? '',
				tabindex: story.getAttribute('tabindex'),
				top: story.getBoundingClientRect().top,
				viewport: window.innerHeight
			};
		});

		expect(landed.early, 'it claimed a story that was not on the page').toBe(false);
		expect(landed.found, 'the story that arrived was never found').toBe(true);
		expect(landed.focused, 'the reader was left where they were').toBe('ai-4821903756');
		// An article takes no focus of its own, so the loader lends it one.
		expect(landed.tabindex).toBe('-1');
		expect(landed.top, 'the story is still below the fold').toBeLessThan(landed.viewport);
		expect(landed.top).toBeGreaterThanOrEqual(0);
	});

	test('a fragment naming nothing leaves the reader alone', async ({ page }) => {
		await armed(page);
		const quiet = await page.evaluate(() => {
			const loader = (window as unknown as { dayLoader: Loader }).dayLoader;
			return {
				empty: loader.restoreAnchor(''),
				missing: loader.restoreAnchor('#no-story-here'),
				// A fragment is text a reader was handed. It reaches getElementById,
				// which takes a literal id, so it can never become a query (Rule #11).
				selector: loader.restoreAnchor('#article[id]'),
				scrolled: window.scrollY
			};
		});
		expect([quiet.empty, quiet.missing, quiet.selector]).toEqual([false, false, false]);
		expect(quiet.scrolled, 'a fragment that named nothing still moved the page').toBe(0);
	});

	test('the shell honours a deep link on a real page', async ({ page }) => {
		// The half that works today, on a route that still carries every story in
		// its document. It is what proves the layout wired the restore at all -
		// a browser scrolls to a fragment on its own, but it never focuses one.
		await page.goto('/archive/');
		const dates = await page
			.locator('[data-day-row] a')
			.evaluateAll((links) =>
				links
					.map((link) => /(\d{4}-\d{2}-\d{2})/.exec(link.getAttribute('href') ?? '')?.[1] ?? '')
					.filter((date) => date !== '')
			);
		expect(dates.length, 'the canary build published no day to deep-link into').toBeGreaterThan(0);
		const date = dates.sort()[dates.length - 1]!;

		await page.goto(`/${date}/`);
		const ids = await page
			.locator('article[id]')
			.evaluateAll((items) => items.map((item) => item.id));
		expect(ids.length, 'the day page carries no story to link to').toBeGreaterThan(0);
		const last = ids[ids.length - 1]!;

		// Arrive from somewhere else, the way a reader following an archive link
		// does. Going straight from `/<date>/` to `/<date>/#id` is a SAME-document
		// navigation: the shell never re-mounts, so nothing runs and the arm reads
		// as a broken restore when it only measured the wrong journey.
		await page.goto('/archive/');
		await page.goto(`/${date}/#${last}`);
		await expect(page.locator(`article[id="${last}"]`)).toHaveAttribute('tabindex', '-1');
		const focused = await page.evaluate(() => document.activeElement?.id ?? '');
		expect(focused, 'a deep link left the reader at the top of the day').toBe(last);
	});
});

/** The component, compiled and rendered the way a route would render it. */
type Rendered = { body: string; css: string };

async function renderer(name: string): Promise<(props: Record<string, unknown>) => Rendered> {
	const filename = path.join(frontend, 'src', 'lib', 'components', `${name}.svelte`);
	const source = readFileSync(filename, 'utf8');
	const pre = await preprocess(source, vitePreprocess(), { filename });
	const result = compile(pre.code, { generate: 'server', filename, name });
	mkdirSync(scratch, { recursive: true });
	const module = path.join(scratch, `${name}.server.mjs`);
	writeFileSync(module, result.js.code, 'utf8');
	const loaded = await import(pathToFileURL(module).href);
	const css = result.css?.code ?? '';
	return (props) => ({ body: render(loaded.default, { props }).body, css });
}

const tokens = readFileSync(path.join(frontend, 'src', 'styles', 'tokens.css'), 'utf8');

/** The theme aliases `app.css` declares over the token scale.
 *
 * Read by PROPERTY NAME rather than by slicing the file at a selector. A slice
 * means the wrong thing the day the selectors swap order, and it swaps in
 * silence - which is how a dark-by-default sweep once handed the light colour
 * to the dark surface with every theme test still green.
 */
function themeAliases(): string {
	const app = readFileSync(path.join(frontend, 'src', 'styles', 'app.css'), 'utf8');
	const blocks = app.match(/[^{}]+\{[^{}]*--item-edge:[^{};]+;[^{}]*\}/g) ?? [];
	expect(blocks.length, '--item-edge moved out of app.css, so this render is unedged').toBe(2);
	return blocks.join('\n');
}

const ALIASES = themeAliases();

async function show(page: Page, out: Rendered, theme: 'dark' | 'light'): Promise<void> {
	await page.setContent(
		`<!doctype html><html${theme === 'light' ? " data-theme='light'" : ''}><head>` +
			`<style>${tokens}</style><style>${ALIASES}</style><style>${out.css}</style>` +
			`<style>body{margin:0;background:var(--color-bg);color:var(--color-text)}` +
			`#host{inline-size:44rem;padding:1rem}</style>` +
			`</head><body><div id="host">${out.body}</div></body></html>`,
		{ waitUntil: 'domcontentloaded' }
	);
}

test.describe('what the reader sees', () => {
	for (const theme of ['dark', 'light'] as const) {
		test(`the unreachable state is a designed screen in the ${theme} theme`, async ({ page }) => {
			const paint = await renderer('PayloadState');
			await show(
				page,
				paint({ status: 'unreachable', day: '30 August 2026', onRetry: () => {} }),
				theme
			);

			const region = page.locator('[data-payload-state]');
			await expect(region).toHaveAttribute('data-payload-state', 'unreachable');
			await expect(region).toContainText('The rest of 30 August 2026 did not arrive.');
			await expect(region).toContainText('The stories above are all here.');
			// It says the fetch failed. It never says the day was not published -
			// that is a different state, and a claim a reader can check.
			await expect(region).not.toContainText('published');

			await expect(
				page.getByRole('button', { name: 'Try again' }),
				'a failure with no way out'
			).toBeVisible();

			const look = await page.locator('.failed').evaluate((panel) => {
				const style = getComputedStyle(panel);
				return {
					background: style.backgroundColor,
					border: style.borderTopColor,
					ground: getComputedStyle(document.body).backgroundColor,
					width: panel.getBoundingClientRect().width
				};
			});
			// Figure and ground: the panel is not the page it sits on, and its edge
			// is drawn rather than assumed.
			expect(look.background, 'the panel is the page ground').not.toBe(look.ground);
			expect(look.border, 'the panel has no edge').not.toBe('rgba(0, 0, 0, 0)');
			expect(look.width).toBeGreaterThan(0);
		});
	}

	test('a slow day is one sentence and no panel', async ({ page }) => {
		const paint = await renderer('PayloadState');
		await show(page, paint({ status: 'slow', day: '30 August 2026', onRetry: () => {} }), 'dark');

		const region = page.locator('[data-payload-state]');
		await expect(region).toHaveAttribute('data-payload-state', 'slow');
		await expect(region).toHaveText('The rest of 30 August 2026 is still loading.');
		// No spinner, no skeleton, no bar. The frame a reader already has is
		// readable, so there is nothing for one to fill.
		expect(await page.locator('.waiting').count()).toBe(1);
		expect(await page.locator('.failed').count()).toBe(0);
		const animation = await page
			.locator('.waiting')
			.evaluate((line) => getComputedStyle(line).animationName);
		expect(animation, 'the waiting sentence animates').toBe('none');
	});

	test('the states that need no words say none', async ({ page }) => {
		const paint = await renderer('PayloadState');
		for (const status of ['loading', 'ready'] as const) {
			await show(page, paint({ status, day: '30 August 2026', onRetry: () => {} }), 'dark');
			const region = page.locator('[data-payload-state]');
			// The region stays in the document on every state. A live region added
			// at the moment its text changes announces nothing.
			await expect(region).toHaveAttribute('data-payload-state', status);
			await expect(region).toHaveText('');
		}
	});
});
