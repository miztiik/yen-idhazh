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
	type Loader,
	type LoadedDay
} from './support/day-loader';
import { assistConfig } from '../src/lib/server/config';

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
/** The content revision a served day carries. Its own `generated_at`, which is
 * what a republish moves and nothing else does. */
const REVISION = '2026-08-30T06:00';

/** A day payload holding stories the page can actually render.
 *
 * Four names, because the loader keeps a story only when it carries everything
 * the page reads off it without a guard - a story short of one of them is
 * dropped and counted, which `malformed-day.spec.ts` is the arm for.
 */
function dayBody(revision: string, ids: string[]): string {
	return JSON.stringify({
		version: '2026-09-01T09:00',
		generated_at: revision,
		items: ids.map((id) => ({
			item_id: id,
			title: 'A story',
			summary: 'A summary long enough to be a summary.',
			key_points: ['One point.']
		}))
	});
}

const PAYLOAD = dayBody(REVISION, ['ai-1']);

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

/** One `loadDay` call - the archive's own, with no wait states and no retry
 * control. It returns the story count, or null for a day it could not read. */
async function load(page: Page, date: string = DATE): Promise<number | null> {
	return page.evaluate(async (asked: string) => {
		const loader = (window as unknown as { dayLoader: Loader }).dayLoader;
		const day = await loader.loadDay(asked);
		return day === null ? null : day.items.length;
	}, date);
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

		// A failure is not an answer, so the loader does not hold one: the next ask
		// really asks. That is what lets a day recover with no retry control at
		// all - the archive fetches the day behind every result and has none - and
		// it is still one request per ask rather than one per render, because
		// nothing on a render path asks. Until 2026-09-06 the null was held for
		// the life of the session and the day was finished.
		const again = await watch(page, 30_000);
		expect(again.states).toEqual(['loading', 'unreachable']);
		expect(blocked.count, 'a failure was held, so the day could never recover').toBe(2);

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

test.describe('what one session keeps in hand', () => {
	test('a day that failed once is asked for again, and it recovers', async ({ page }) => {
		// The oracle. A search answer names a day, that day's fetch fails, and the
		// next answer naming it has no retry control to press - so if the failure
		// is held, that day is finished for the life of the session.
		const asked = new Intercepted();
		let refuse = true;
		await page.route(PATTERN, async (route) => {
			asked.take(route.request().url());
			if (refuse) {
				await route.abort('connectionfailed');
				return;
			}
			await route.fulfill({ contentType: 'application/json', body: dayBody(REVISION, ['ai-1']) });
		});

		await armed(page);
		expect(await load(page), 'the first ask did not fail').toBeNull();

		// The network recovers, and nothing tells the loader.
		refuse = false;
		const recovered = await load(page);
		console.log(`[payload-state] recovery interceptions: ${asked.count}`);
		expect(recovered, 'a day that failed once stayed failed for the session').toBe(1);
		expect(asked.count, 'the second ask never reached the network').toBe(2);

		// The reader's own route reaches the same rule through `watchDay`.
		refuse = true;
		const readerFailed = await watch(page, 30_000, true);
		expect(readerFailed.states).toEqual(['loading', 'unreachable']);
		refuse = false;
		const readerRecovered = await watch(page, 30_000);
		expect(readerRecovered.states, 'the reading page could not recover either').toEqual([
			'loading',
			'ready'
		]);
	});

	test('two asks racing on one failing day still cost one request', async ({ page }) => {
		// Single-flight sharing is what this row keeps. A failure that is not held
		// must not become a request per caller.
		const asked = new Intercepted();
		await page.route(PATTERN, async (route) => {
			asked.take(route.request().url());
			await new Promise((done) => setTimeout(done, 200));
			await route.abort('connectionfailed');
		});

		await armed(page);
		const both = await page.evaluate(async (date: string) => {
			const loader = (window as unknown as { dayLoader: Loader }).dayLoader;
			const pair = await Promise.all([loader.loadDay(date), loader.loadDay(date)]);
			return pair.map((day) => (day === null ? null : day.items.length));
		}, DATE);

		console.log(`[payload-state] racing interceptions: ${asked.count}`);
		expect(both, 'a failing day handed something back').toEqual([null, null]);
		expect(asked.count, 'two callers waiting on one day made two requests').toBe(1);
	});

	test('a retry hands back the day the page holds, unless the day changed', async ({ page }) => {
		// The revision is the key. A retry on an unchanged day must not throw away
		// the payload every derived view is built on, and a republished day must
		// not be served from the one before it.
		const changed = '2026-08-30T18:00';
		let served = 0;
		await page.route(PATTERN, async (route) => {
			served += 1;
			const body = served <= 2 ? dayBody(REVISION, ['ai-1']) : dayBody(changed, ['ai-2', 'ai-3']);
			await route.fulfill({ contentType: 'application/json', body });
		});

		await armed(page);
		const identity = await page.evaluate(async (date: string) => {
			const loader = (window as unknown as { dayLoader: Loader }).dayLoader;
			const quiet = { slowMs: 30_000, onStatus: () => {} };
			const first = await loader.watchDay(date, quiet);
			const same = await loader.watchDay(date, { ...quiet, again: true });
			const fresh = await loader.watchDay(date, { ...quiet, again: true });
			return {
				unchangedIsTheSameDay: first === same,
				republishedIsANewDay: first !== fresh,
				firstIds: (first?.items ?? []).map((item) => item.item_id ?? ''),
				freshIds: (fresh?.items ?? []).map((item) => item.item_id ?? '')
			};
		}, DATE);

		console.log(`[payload-state] revision interceptions: ${served}`);
		expect(served, 'a retry did not reach the network').toBe(3);
		expect(
			identity.unchangedIsTheSameDay,
			'a retry on an unchanged day replaced the payload the page already held'
		).toBe(true);
		expect(identity.republishedIsANewDay, 'a republished day was served stale').toBe(true);
		expect(identity.firstIds).toEqual(['ai-1']);
		expect(identity.freshIds, 'the republished day did not reach the page').toEqual([
			'ai-2',
			'ai-3'
		]);
	});

	test('one lookup index is built per day, and a second day gets its own', async ({ page }) => {
		// Finding 87. A result list resolves an id against a day it already holds,
		// once per result and again on every arrival. The count below is the whole
		// oracle: reading `items` once per lookup is a walk of the day per lookup,
		// and reading it once is an index the day owns.
		await armed(page);
		const probed = await page.evaluate(() => {
			const loader = (window as unknown as { dayLoader: Loader }).dayLoader;
			const story = (id: string) => ({
				item_id: id,
				title: id,
				summary: id,
				key_points: [] as string[]
			});
			/** A day that counts how many times anything reads its story list. */
			const watched = (items: ReturnType<typeof story>[]) => {
				const reads = { count: 0 };
				const day = { generated_at: '2026-08-30T06:00', items };
				const probe = new Proxy(day, {
					get(target, key, receiver) {
						if (key === 'items') reads.count += 1;
						return Reflect.get(target, key, receiver);
					}
				}) as unknown as LoadedDay;
				return { probe, reads };
			};

			const first = watched([story('ai-1'), story('ai-2'), story('ai-3')]);
			const asks = 50;
			let found = 0;
			for (let n = 0; n < asks; n += 1) {
				if (loader.itemOf(first.probe, 'ai-2') !== null) found += 1;
			}
			const firstReads = first.reads.count;
			const missing = loader.itemOf(first.probe, 'energy-9');
			const noDay = loader.itemOf(null, 'ai-2');

			const second = watched([story('energy-9')]);
			const secondFound = loader.itemOf(second.probe, 'energy-9');
			const crossed = loader.itemOf(second.probe, 'ai-1');
			const secondReads = second.reads.count;

			return {
				asks,
				found,
				firstReads,
				missing,
				noDay,
				secondReads,
				secondFound: secondFound === null ? null : secondFound.item_id,
				crossed
			};
		});

		expect(probed.found, 'a lookup stopped finding the story it was given').toBe(probed.asks);
		expect(probed.firstReads, `the day was walked once per lookup, ${probed.asks} times`).toBe(1);
		expect(probed.missing, 'a story the day does not hold was invented').toBeNull();
		expect(probed.noDay, 'a missing day did not answer null').toBeNull();
		expect(probed.secondReads, 'a second day did not get an index of its own').toBe(1);
		expect(probed.secondFound, 'the second day lost its own story').toBe('energy-9');
		expect(probed.crossed, "one day answered with another day's story").toBeNull();
	});

	test('the held days are bounded, and a whole archive answer survives', async ({ page }) => {
		// The bound is stated by two facts rather than by repeating its number: a
		// session holds at least as many days as one screen of search results can
		// name, and it does not hold every day it has ever visited.
		const asked = new Intercepted();
		await page.route('**/digest/**/digest.json', async (route) => {
			const url = route.request().url();
			asked.take(url);
			const parts = /(\d{4})\/(\d{2})\/(\d{2})\/digest\.json$/.exec(url);
			const date = parts ? `${parts[1]}-${parts[2]}-${parts[3]}` : DATE;
			await route.fulfill({
				contentType: 'application/json',
				body: dayBody(`${date}T06:00`, [`ai-${date}`])
			});
		});

		const visited: string[] = [];
		for (const month of ['01', '02']) {
			for (let day = 1; day <= 28; day += 1) {
				visited.push(`2026-${month}-${String(day).padStart(2, '0')}`);
			}
		}

		await armed(page);
		await page.evaluate(async (dates: string[]) => {
			const loader = (window as unknown as { dayLoader: Loader }).dayLoader;
			for (const date of dates) await loader.loadDay(date);
		}, visited);
		const fetched = asked.count;
		console.log(`[payload-state] days visited: ${visited.length}, interceptions: ${fetched}`);
		expect(fetched, 'a visited day was never fetched').toBe(visited.length);

		// The day the session just read.
		await load(page, visited[visited.length - 1]!);
		expect(asked.count, 'the day the session just read was dropped').toBe(fetched);

		// A whole search answer back. `assist.result_limit` is what one answer can
		// name, and `fetchDays` in the archive asks for every one of them.
		const answer = assistConfig().result_limit;
		await load(page, visited[visited.length - answer]!);
		expect(asked.count, `a session did not hold one answer of ${answer} days`).toBe(fetched);

		// And the first day of the session, long since left behind.
		await load(page, visited[0]!);
		expect(asked.count, 'the session held every day it had ever visited').toBe(fetched + 1);
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

	test('the day that failed offers the days this device still holds', async ({ page }) => {
		// A reader with no network, on a day they never opened, has been named the
		// day and handed a button that cannot work. These are the days already on
		// their own device, so every one of them opens.
		const paint = await renderer('PayloadState');
		await show(
			page,
			paint({
				status: 'unreachable',
				day: '30 August 2026',
				onRetry: () => {},
				held: [
					{ label: '29 August 2026', href: '/yen-idhazh/2026-08-29/' },
					{ label: '28 August 2026', href: '/yen-idhazh/2026-08-28/' }
				]
			}),
			'dark'
		);

		const offered = page.locator('.failed-held a');
		await expect(offered).toHaveCount(2);
		await expect(offered.first()).toHaveText('29 August 2026');
		// The base path is the caller's to build, and a link that dropped it is a
		// 404 for every reader and correct on a developer machine.
		await expect(offered.first()).toHaveAttribute('href', '/yen-idhazh/2026-08-29/');
		await expect(page.locator('[data-payload-held]')).toHaveText(
			'Days you can read with no network:'
		);

		// And the same state with nothing held says nothing about it, rather than
		// an empty heading over an empty list.
		await show(
			page,
			paint({ status: 'unreachable', day: '30 August 2026', onRetry: () => {} }),
			'dark'
		);
		await expect(page.locator('.failed-held')).toHaveCount(0);
		await expect(page.locator('[data-payload-held]')).toHaveCount(0);
		await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();
	});

	test('a slow day is one sentence and no panel', async ({ page }) => {		const paint = await renderer('PayloadState');
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
