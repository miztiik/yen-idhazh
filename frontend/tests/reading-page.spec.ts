/**
 * Row #20's oracle: the page twenty-one rows built, read whole.
 *
 * Every other spec in this directory checks one row's own change. This one
 * checks what happens where they meet, because that is the failure this plan
 * could actually have shipped - twenty-one changes each correct on its own,
 * composing into a page nobody looked at end to end.
 *
 * **It reads the served tree rather than naming a fixture.** The day, the
 * topic, the leads and the seed are all read off `build/`, so the same file
 * measures the canary day the browser gate serves and a real published day of
 * several hundred stories. What it asserts is the shape, never a count written
 * here.
 *
 * Four questions, and each one needs two rows to have disagreed to fail:
 *
 * - **The time is on the rail and nowhere else.** Row 16 put the time in the
 *   item's eyebrow and row 17 took it out again and gave it a column. Both
 *   landing would print every story's time twice.
 * - **The aside, the sticky filter panel and the time rail keep out of each
 *   other's way.** Three rows put three things in the same 1400px screen: row
 *   18's 18rem aside, row 7's panel that sticks from 1024px, row 17's rail.
 *   None of them knows about the other two.
 * - **A day that half arrives is still a designed page.** Rows 25 and 26 made
 *   the dated routes seed and fetch; row 14 designed what a reader meets when
 *   the fetch fails. The three arms below break the fetch at the network and
 *   count what they broke - an arm that intercepted nothing has proved that a
 *   page loads, which it would have done anyway.
 * - **The offline reader changes nothing a reader can see.** Row 28 put a
 *   worker in front of the same requests rows 25 and 26 make. A day out of the
 *   device and a day off the network have to be the same page.
 *
 * Several arms cannot run on a day shorter than `ui.shell_seed_items`, because
 * a document that already carries its whole day never fetches - so there is
 * nothing to break and nothing to serve from a cache - and none can run on a
 * day with one desk, which cannot fill a leading block. They read both off the
 * fixture rather than off a locator, and the browser gate's eight-story canary
 * is the case that skips: seven of sixteen arms there, and none on a real
 * published day. `item-zones.spec.ts` set the same precedent for the aside.
 * What the canary cannot reach is measured on the committed digest instead,
 * with hardware and date, in `docs/reference/measurements.md`.
 *
 * **One arm at the end is expected to fail, and says so.** Composing the rows
 * broke a story's own address: it only lands while the pager is already showing
 * it, and it is written as an assertion rather than described in a comment.
 * Both defects are recorded in `docs/architecture/publishing/layout.md`. An arm
 * marked this way turns the suite red the day the defect is fixed, which is
 * when the annotation comes off - which is what happened to the count above it.
 */

import { expect, test, type Page } from '@playwright/test';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { deskShortfall, leadingStories, orderByTime } from '../src/lib/day-shape';
import { shellSeedItems, uiConfig } from '../src/lib/server/config';
import { loadDay, publishedDates } from '../src/lib/server/payload';

/** The tree the preview server serves, so a route here is a route that exists. */
const BUILD = resolve(process.cwd(), 'build');
/** The two trees a build can be made from. Which one built the tree above is
 * asked rather than assumed, so this file measures the canary the browser gate
 * serves and a real published day without being told which it is looking at. */
const COMMITTED = resolve(process.cwd(), 'public', 'digest');
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'digest');

function subdirectories(at: string): string[] {
	if (!existsSync(at)) return [];
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

/** Every day the built site serves, and how many stories each one carries. */
function servedDays(): { date: string; items: number }[] {
	const root = join(BUILD, 'digest');
	const found: { date: string; items: number }[] = [];
	for (const year of subdirectories(root)) {
		for (const month of subdirectories(join(root, year))) {
			for (const day of subdirectories(join(root, year, month))) {
				const file = join(root, year, month, day, 'digest.json');
				if (!existsSync(file)) continue;
				const served = JSON.parse(readFileSync(file, 'utf8')) as { items: unknown[] };
				found.push({ date: `${year}-${month}-${day}`, items: served.items.length });
			}
		}
	}
	return found;
}

/** The BUSIEST day the built site serves that also earned a leading block.
 *
 * Every other spec here takes the newest, which is right for them: they ask
 * whether a page renders, and the newest day is what a reader opens. This one
 * asks whether it holds up under a day's worth of stories - a rail and a card
 * that read well at twelve and become a wall at several hundred is the failure
 * this page has had once already - and what the pipeline happened to publish
 * this morning is not that. On 2026-09-02 the newest day carried 128 stories
 * and the busiest carried 731.
 *
 * The leading block is the tie-break rather than the axis, because it is what
 * puts an aside on the page and the aside is one of the three things this file
 * checks for a collision. Every day published before 2026-09-01 predates the
 * block, so today the corpus straddles it; once it does not, the two rules pick
 * the same day and this line stops doing anything.
 *
 * Never a date written here: a hardcoded one passes on an empty page the moment
 * the fixture moves.
 */
function chosen(): { date: string; items: number } {
	const busiest = servedDays().sort((a, b) => b.items - a.items || b.date.localeCompare(a.date));
	if (busiest.length === 0) throw new Error('the built site serves no day at all');
	const committed = new Set(publishedDates(COMMITTED));
	const withLeads = busiest.find(
		(day) =>
			(loadDay(day.date, committed.has(day.date) ? COMMITTED : CANARY)?.leads ?? []).length > 0
	);
	return withLeads ?? busiest[0];
}

const BUSIEST = chosen();
const DAY = BUSIEST.date;
/** How many stories the served file carries, which is what a browser gets. */
const SERVED_ITEMS = BUSIEST.items;

/** The day's own facts.
 *
 * **Not the served file.** That carries `version` and `items` and nothing else -
 * the day's verticals, leads and runs travel in the prerendered document, which
 * is the whole point of the projection. So the leads and the desk counts are
 * read from the tree the build read.
 */
const SOURCE = publishedDates(COMMITTED).includes(DAY) ? COMMITTED : CANARY;
const FACTS = loadDay(DAY, SOURCE);

/** A topic of that day, taken from the tree rather than named. */
const TOPIC = subdirectories(join(BUILD, DAY)).at(0) as string;

const SEED = shellSeedItems();
/** Whether the day is longer than the document that seeds it. False on the
 * canary, where nothing fetches and the two fetch arms have nothing to hold. */
const PAST_SEED = SERVED_ITEMS > SEED;
/** How many leads the day earned, computed the way the page computes it. It is
 * what decides whether there is an aside to collide with anything. */
const LEADS = FACTS ? leadingStories(FACTS.leads ?? [], orderByTime(FACTS.items)).length : 0;

/** Every reader-facing route the build emits.
 *
 * `/404` is not one of them, for the reason `layout-overflow.spec.ts` gives:
 * that document is the adapter's fallback shell rather than a rendered route,
 * and `vite preview` serves it as a plain file - so SvelteKit's data fetch for
 * it 404s and hydration throws. That is a preview artefact and not a fact about
 * the page, so it is driven by hand in the section 12 smoke instead.
 */
const ROUTES = ['/', `/${DAY}/`, `/${DAY}/${TOPIC}/`, '/archive/', '/evals/'];

/** A phone, the gap between two breakpoints, and a wide desktop.
 * `frame.breakpoints_px` is [640, 1024, 1400]; 801 is where a layout that was
 * only ever tested at a breakpoint breaks, and 1536 is past the widest. */
const WIDTHS = [360, 801, 1536];

/** Dark is the base and light is the stored override, so both are driven.
 * Decision 2: dark is what most readers now see. */
const THEMES = ['dark', 'light'] as const;

/** The address the day payload is served from, spelled out rather than rebuilt
 * from `dayUrl` - a helper that agreed with the code under test would prove
 * nothing. */
const DAY_PATH = `/digest/${DAY.split('-').join('/')}/digest.json`;

/** Everything a visit did wrong, collected on the page rather than asserted per
 * navigation, so one walk of five routes reports every fault it found. */
interface Faults {
	errors: string[];
	failed: string[];
	notOk: string[];
}

function watch(page: Page): Faults {
	const found: Faults = { errors: [], failed: [], notOk: [] };
	page.on('console', (message) => {
		if (message.type() !== 'error') return;
		// The browser's own line for a request that came back an error. It is the
		// network reporting itself rather than our code throwing, and the two
		// lists below already hold every failed request by name - so counting it
		// here would report one fault twice and make the deliberate 404 the absent
		// arm serves read as a page that threw.
		if (message.text().includes('Failed to load resource')) return;
		found.errors.push(message.text());
	});
	page.on('pageerror', (error) => found.errors.push(String(error)));
	page.on('requestfailed', (request) => {
		// A DOCUMENT request the browser abandoned is one navigation superseded by
		// another, never a file the page could not get. `/evals/` is a signpost
		// rather than a page - it carries a `meta refresh` to the console - so
		// walking away from it always leaves one abandoned navigation behind.
		// Everything else is on the list, and a page whose own navigation aborted
		// fails the theme assertion in `open` before this line is read.
		const reason = request.failure()?.errorText ?? 'no reason given';
		if (request.resourceType() === 'document' && reason === 'net::ERR_ABORTED') return;
		found.failed.push(`${request.url()} (${reason})`);
	});
	page.on('response', (response) => {
		if (response.status() >= 400) found.notOk.push(`${response.status()} ${response.url()}`);
	});
	return found;
}

/** Open a route with the theme already chosen, and wait for the page to settle.
 *
 * A dated route reports its own settling, so it is waited for rather than timed.
 * `data-theme` is read with a locator assertion rather than a polled
 * `page.evaluate`, which races the client router's first navigation and fails
 * with `Execution context was destroyed` on a page that is perfectly fine.
 */
async function open(page: Page, theme: string, route: string, width: number): Promise<void> {
	await page.addInitScript(`localStorage.setItem('idhazh:theme', '${theme}')`);
	await page.setViewportSize({ width, height: 900 });
	await page.goto(route);
	await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
	const settling = page.locator('[data-payload-state]');
	if ((await settling.count()) > 0) {
		await expect(settling, `${route} never settled on a state`).toHaveAttribute(
			'data-payload-state',
			'ready'
		);
	}
}

test.describe('every reader route, at every width, in both themes', () => {
	for (const theme of THEMES) {
		for (const width of WIDTHS) {
			test(`${theme} at ${width}px: nothing errors, nothing 404s, nothing scrolls sideways`, async ({
				page
			}) => {
				const faults = watch(page);

				for (const route of ROUTES) {
					await open(page, theme, route, width);

					const measured = await page.evaluate(() => {
						const root = document.documentElement;
						return {
							scrollWidth: root.scrollWidth,
							clientWidth: root.clientWidth,
							// A blank page passes every check below for free, so the
							// checks are only worth running on a page that rendered.
							rendered: document.querySelectorAll('.frame *').length,
							stories: document.querySelectorAll('article.item').length
						};
					});

					expect(
						measured.rendered,
						`${theme} ${route} at ${width}px rendered nothing`
					).toBeGreaterThan(10);
					expect(
						measured.scrollWidth,
						`${theme} ${route} at ${width}px scrolls sideways by ` +
							`${measured.scrollWidth - measured.clientWidth}px with ` +
							`${measured.stories} stories drawn out of the day's ${SERVED_ITEMS}`
					).toBeLessThanOrEqual(measured.clientWidth);
				}

				expect(
					faults.errors,
					`${theme} at ${width}px logged an error on the ${SERVED_ITEMS}-story day ` +
						`of ${DAY}:\n${faults.errors.join('\n')}`
				).toEqual([]);
				expect(
					faults.failed,
					`${theme} at ${width}px asked for something that is not there:\n` +
						faults.failed.join('\n')
				).toEqual([]);
				expect(
					faults.notOk,
					`${theme} at ${width}px was answered with an error status:\n` + faults.notOk.join('\n')
				).toEqual([]);
			});
		}
	}
});

test.describe('where two rows meet', () => {
	test('the time is on the day rail and nowhere on a story', async ({ page }) => {
		await open(page, 'dark', `/${DAY}/`, 1536);

		const stories = page.locator('article.item');
		const drawn = await stories.count();
		expect(drawn, 'the day drew no story, so this proves nothing').toBeGreaterThan(0);

		// The zone is named once, above the column it explains. Not a suffix on
		// every label and not a band of its own at the top of the page.
		await expect(
			page.locator('[data-rail-note]'),
			'the rail names its clock more than once, or not at all'
		).toHaveCount(1);

		// One marker per group of equal times, never one per story. A marker on
		// every story is the rail drawing the duplicate it exists to remove.
		const marks = await page.locator('[data-rail-mark]').count();
		expect(marks, 'the rail drew no marker at all').toBeGreaterThan(0);
		expect(
			marks,
			`the rail drew ${marks} markers for ${drawn} stories, which is a label per story`
		).toBeLessThanOrEqual(drawn);

		// And the eyebrow carries no clock. Row 16 put one there and row 17 took
		// it away; a page carrying both prints the same number twice per story.
		const clocked = await page.locator('[data-item-eyebrow]').evaluateAll((nodes) =>
			nodes
				.map((node) => node.textContent ?? '')
				.filter((text) => /\b\d{1,2}:\d{2}\b/.test(text))
				.slice(0, 4)
		);
		expect(clocked, 'a story prints its time above the title as well as on the rail').toEqual([]);
	});

	test('the aside, the sticky panel and the time rail keep out of each other', async ({ page }) => {
		test.skip(
			LEADS === 0,
			`${DAY} earned no leading block, so this day has no aside to collide with anything`
		);
		await open(page, 'dark', `/${DAY}/`, 1536);

		const read = async () =>
			page.evaluate(() => {
				const box = (selector: string) => {
					const el = document.querySelector(selector);
					return el ? el.getBoundingClientRect().toJSON() : null;
				};
				return {
					aside: box('.day-aside'),
					panel: box('[data-filter-bar]'),
					rail: box('[data-time-rail]'),
					stream: box('.day-stream')
				};
			});

		const at_rest = await read();
		expect(at_rest.aside, 'the aside is not on the page at 1536px').not.toBeNull();
		expect(at_rest.panel, 'the filter panel is not on the page').not.toBeNull();
		expect(at_rest.rail, 'the time rail is not on the page').not.toBeNull();

		// The aside stands beside the stream, so it starts where the stream ends.
		expect(
			at_rest.aside!.left,
			`the aside starts at ${Math.round(at_rest.aside!.left)} and the stream runs to ` +
				`${Math.round(at_rest.stream!.right)}, so they overlap`
		).toBeGreaterThanOrEqual(at_rest.stream!.right - 0.5);
		// The rail is inside the stream, which is what keeps it clear of the aside.
		expect(
			at_rest.rail!.right,
			'the time rail runs under the aside'
		).toBeLessThanOrEqual(at_rest.aside!.left + 0.5);

		// Both stick. A reader scrolled to the bottom of a 359-story day has the
		// panel and the aside pinned at once, and that is the only moment they can
		// reach each other.
		await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
		await page.waitForFunction(() => window.scrollY > 0);
		const pinned = await read();
		const overlapping =
			pinned.panel!.right > pinned.aside!.left + 0.5 &&
			pinned.panel!.bottom > pinned.aside!.top + 0.5 &&
			pinned.aside!.bottom > pinned.panel!.top + 0.5;
		expect(
			overlapping,
			`scrolled to the end, the pinned panel ends at ${Math.round(pinned.panel!.right)} and the ` +
				`pinned aside starts at ${Math.round(pinned.aside!.left)}`
		).toBe(false);
	});

	test('the leading block is drawn and every lead lands on a story', async ({ page }) => {
		test.skip(LEADS === 0, `${DAY} earned no leading block`);
		await open(page, 'dark', `/${DAY}/`, 1536);

		await expect(page.locator('[data-leading]'), 'the leading block was not drawn').toHaveCount(1);
		const leads = await page.locator('[data-lead]').evaluateAll((nodes) =>
			nodes.map((node) => node.getAttribute('data-lead') ?? '')
		);
		expect(leads.length, 'the block drew no lead').toBe(LEADS);
		const dead = await page.evaluate(
			(ids) => ids.filter((id) => document.getElementById(id) === null),
			leads
		);
		expect(dead, 'a lead link lands on a story the page does not hold').toEqual([]);
	});

	test('a thin desk says what its sources offered', async ({ page }) => {
		const desk = FACTS?.verticals.find((ref) => ref.id === TOPIC);
		const thin = deskShortfall(desk, uiConfig().desk_thin_max);
		test.skip(
			thin === null,
			`${TOPIC} on ${DAY} published ${desk?.count ?? 0} stories, which is not a thin desk`
		);
		await open(page, 'dark', `/${DAY}/${TOPIC}/`, 1536);

		const line = page.locator('[data-desk-shortfall]');
		await expect(line, 'a thin desk does not say why it is thin').toHaveCount(1);
		await expect(line).toContainText(String(thin!.offered));
		await expect(line).toContainText(String(thin!.tooOld));
	});

	test('the scores address sends a reader to the console', async ({ page }) => {
		// `/evals/` is the address the scores used to live at. It is a signpost
		// now, and a signpost that stopped pointing anywhere is a dead reader
		// address - which is also why every walk above leaves one abandoned
		// navigation behind it.
		//
		// The landing is asserted rather than the markup: the refresh fires before
		// a locator can read the document it fired from, so a spec that looked for
		// the tag would be racing the very thing it is checking. It races the
		// arrival too - the refresh aborts the navigation that delivered it, which
		// is what `commit` and the catch below are for. The fallback link under it
		// is read off the built file, which does not move.
		await page.goto('/evals/', { waitUntil: 'commit' }).catch(() => {
			// The document retired its own navigation. That is the redirect working.
		});
		await expect
			.poll(() => page.url(), {
				message: 'the scores address did not send the reader to the console',
				timeout: 15_000
			})
			.toMatch(/\/console\/$/);

		const document = readFileSync(join(BUILD, 'evals', 'index.html'), 'utf8');
		expect(
			document,
			'a reader whose browser ignores the refresh has nothing to click'
		).toContain('Open the console');
	});
});

/**
 * What the composed page said about how much it was holding, held so it stays
 * fixed, and the one thing it still gets wrong.
 *
 * The count arms were written failing on 2026-09-02 and are ordinary assertions
 * now. The address arm below is still expected to fail: a story's own address
 * only lands while the pager is already showing it. What each one measures is
 * in `docs/architecture/publishing/layout.md`.
 */
test.describe('the count and the address', () => {
	/** The story count a built document states, before a browser runs anything.
	 *
	 * Read off the file rather than off a rendered page, because the half that
	 * was wrong is the half a reader with no script gets and never sees change.
	 * The line is stripped of Svelte's own markers rather than matched through
	 * them, so a change in how the compiler emits an `{#if}` cannot quietly turn
	 * this into a test that matches nothing.
	 */
	function printedCount(...parts: string[]): number {
		const at = readFileSync(join(BUILD, ...parts, 'index.html'), 'utf8');
		const opens = at.indexOf('notice-count');
		expect(opens, `/${parts.join('/')}/ draws no story-count line at all`).toBeGreaterThan(-1);
		const line = at
			.slice(at.indexOf('>', opens) + 1, at.indexOf('</p>', opens))
			.replace(/<!--.*?-->/g, '')
			.replace(/<[^>]*>/g, '')
			.replace(/\s+/g, ' ')
			.trim();
		const printed = /^(\d+) stor/.exec(line);
		expect(printed, `/${parts.join('/')}/ opens with "${line}" and states no count`).not.toBeNull();
		return Number(printed![1]);
	}

	test('the dated document says how many stories the day published', async ({ page }) => {
		test.skip(!PAST_SEED, `${DAY} carries its whole day, so its seed IS its count`);

		// The day's own bounded count, which is the number the topic row prints a
		// few lines below this sentence on the same screen.
		const published = (FACTS?.verticals ?? []).reduce((sum, ref) => sum + ref.count, 0);
		const before = printedCount(DAY);

		await open(page, 'dark', `/${DAY}/`, 1536);
		const settled = (await page.locator('p.notice-count').first().textContent()) ?? '';
		const after = Number(/(\d+)\s+stor/.exec(settled.replace(/\s+/g, ' '))?.[1]);

		console.log(
			`[reading-page] /${DAY}/ counts ${before} before hydration, ${after} after, ` +
				`on a day that published ${published}`
		);
		expect(
			before,
			`the first line under the date claims ${before} stories on a day that published ` +
				`${published}. It counts the list in hand rather than the day's own total, so a ` +
				`prerendered document states the seed of ${SEED} plus its leads and a reader with ` +
				'no script never sees another number'
		).toBe(published);
		expect(
			after,
			`the count ticked from ${before} to ${after} while the reader was looking at it`
		).toBe(before);
	});

	test('a topic document says how many stories that desk published', () => {
		const desk = FACTS?.verticals.find((ref) => ref.id === TOPIC);
		expect(desk, `${DAY} serves /${TOPIC}/ and its payload names no such desk`).toBeDefined();

		const printed = printedCount(DAY, TOPIC);
		console.log(`[reading-page] /${DAY}/${TOPIC}/ counts ${printed} of the desk's ${desk!.count}`);
		expect(
			printed,
			`the topic page claims ${printed} stories on a desk that published ${desk!.count}. A ` +
				'topic page is about one desk, so the desk is the number it owes the reader'
		).toBe(desk!.count);
	});

	test('every story the day published has an address that lands', async ({ page }) => {
		test.skip(!PAST_SEED, `${DAY} carries its whole day, so no story is below the seed`);
		test.fail();

		const items = orderByTime(FACTS!.items);
		const target = items.at(-1)!.item_id;
		await open(page, 'dark', `/${DAY}/#${target}`, 1536);

		const drawn = await page.locator('article.item').count();
		await expect(
			page.locator(`article.item[id="${target}"]`),
			`the stream draws ${drawn} of the day's ${items.length} stories - the first twelve plus ` +
				`its ${LEADS} leads - so every other story's own address scrolls a reader to the top ` +
				'of the day instead'
		).toHaveCount(1, { timeout: 5_000 });
	});
});

test.describe('a day whose stories never arrive', () => {
	test.skip(
		!PAST_SEED,
		`${DAY} publishes ${SERVED_ITEMS} stories against a seed of ${SEED}, so its ` +
			'document already carries the whole day and nothing fetches'
	);

	/** Break the day payload and count what was broken.
	 *
	 * Decision 3: an arm that reports zero interceptions is a null result rather
	 * than a pass, so the count is printed and asserted above zero before the
	 * state it is evidence for is asserted at all.
	 */
	async function broken(
		page: Page,
		name: string,
		answer: (route: import('@playwright/test').Route) => Promise<void>
	): Promise<number> {
		const taken: string[] = [];
		await page.route(`**${DAY_PATH}`, async (route) => {
			taken.push(new URL(route.request().url()).pathname);
			await answer(route);
		});
		await page.addInitScript(`localStorage.setItem('idhazh:theme', 'dark')`);
		await page.setViewportSize({ width: 1536, height: 900 });
		await page.goto(`/${DAY}/`);
		await expect(
			page.locator('[data-payload-state]'),
			`the ${name} arm never reached a settled state`
		).toHaveAttribute('data-payload-state', 'unreachable');
		console.log(`[reading-page] ${name}: intercepted ${taken.length} - ${taken.join(', ')}`);
		expect(taken.length, `the ${name} arm intercepted nothing, so it measured nothing`).toBeGreaterThan(
			0
		);
		return taken.length;
	}

	/** What the reader is left with, whichever way the day failed: the designed
	 * panel, the retry, and every story the document already carried. */
	async function designed(page: Page, name: string): Promise<void> {
		await expect(
			page.locator('[data-payload-state] .failed-headline'),
			`the ${name} arm drew no headline`
		).toContainText(DAY.slice(0, 4));
		await expect(
			page.getByRole('button', { name: 'Try again' }),
			`the ${name} arm offers no way to try again`
		).toHaveCount(1);
		const held = await page.locator('article.item').count();
		expect(
			held,
			`the ${name} arm took the document's own stories away as well`
		).toBeGreaterThan(0);
		const measured = await page.evaluate(() => ({
			scrollWidth: document.documentElement.scrollWidth,
			clientWidth: document.documentElement.clientWidth
		}));
		expect(
			measured.scrollWidth,
			`the ${name} arm scrolls sideways`
		).toBeLessThanOrEqual(measured.clientWidth);
	}

	test('absent: the host does not have the file', async ({ page }) => {
		const faults = watch(page);
		await broken(page, 'absent', (route) => route.fulfill({ status: 404, body: '' }));
		await designed(page, 'absent');
		// The 404 is the arm. What must not be there is anything thrown.
		expect(
			faults.errors,
			`the absent arm threw:\n${faults.errors.join('\n')}`
		).toEqual([]);
	});

	test('empty: the file is there and holds nothing', async ({ page }) => {
		const faults = watch(page);
		await broken(page, 'empty', (route) =>
			route.fulfill({ status: 200, contentType: 'application/json', body: '' })
		);
		await designed(page, 'empty');
		expect(faults.errors, `the empty arm threw:\n${faults.errors.join('\n')}`).toEqual([]);
	});

	test('unparseable: the file is there and is not a day', async ({ page }) => {
		const faults = watch(page);
		await broken(page, 'unparseable', (route) =>
			route.fulfill({ status: 200, contentType: 'application/json', body: '}{ not a day' })
		);
		await designed(page, 'unparseable');
		expect(faults.errors, `the unparseable arm threw:\n${faults.errors.join('\n')}`).toEqual([]);
	});
});

/** The offline reader, in front of the same requests the reading page makes.
 *
 * Workers are blocked for the rest of the suite (`playwright.config.ts`) and
 * turned back on here. Every test takes its own browser context, and the
 * teardown unregisters - a worker outlives the page that registered it, and one
 * left running answers the next spec's requests out of a cache.
 */
test.describe('with the offline reader installed', () => {
	test.use({ serviceWorkers: 'allow' });

	test.afterEach(async ({ page }) => {
		await page
			.evaluate(async () => {
				for (const registration of await navigator.serviceWorker.getRegistrations()) {
					await registration.unregister();
				}
				for (const name of await caches.keys()) await caches.delete(name);
			})
			.catch(() => {
				// An arm that ended on a page that could not load has nothing to
				// clean up, and the context is discarded either way.
			});
	});

	/** What the page is showing, and how much more it says it holds.
	 *
	 * Not a walk of the pager. `Show N more` counts the whole day rather than the
	 * part on screen, so a cached day of a different length or a different order
	 * changes either the ids or that number - and pressing the control 52 times on
	 * a 627-story day measures the pager's re-render instead, which took 1.3
	 * minutes on a quiet machine and ran past the timeout on a busy one.
	 */
	async function showing(page: Page): Promise<{ ids: string[]; more: string }> {
		const more = page.getByRole('button', { name: /^Show \d+ more$/ });
		return {
			ids: await page.locator('article.item').evaluateAll((nodes) => nodes.map((node) => node.id)),
			more: (await more.count()) > 0 ? ((await more.textContent()) ?? '').trim() : 'no more'
		};
	}

	test('a day out of the device and a day off the network are the same page', async ({ page }) => {
		test.skip(!PAST_SEED, `${DAY} never fetches, so there is nothing for a cache to hold`);

		await open(page, 'dark', `/${DAY}/`, 1536);
		await page.waitForFunction(() => navigator.serviceWorker.controller !== null, null, {
			timeout: 60_000
		});
		const fetched = await showing(page);
		expect(fetched.ids.length, 'the first visit drew no story').toBeGreaterThan(0);
		expect(
			fetched.more,
			'the first visit says it holds no more, so the day never arrived'
		).not.toBe('no more');

		await page.reload();
		await expect(page.locator('[data-payload-state]')).toHaveAttribute(
			'data-payload-state',
			'ready'
		);
		// What the worker actually answered, named by the browser rather than by
		// the worker. A second visit that went to the network is a null result:
		// it proves a page loads twice, which it would have done anyway.
		const served = await page.evaluate(
			() =>
				performance
					.getEntriesByType('resource')
					.filter((entry) => (entry as PerformanceResourceTiming).workerStart > 0).length
		);
		console.log(`[reading-page] the offline reader answered ${served} requests on the second visit`);
		expect(served, 'the second visit reached nothing the worker holds').toBeGreaterThan(0);

		const cached = await showing(page);
		expect(cached, 'a cached day is a different page from a fetched one').toEqual(fetched);
	});

	test('a deep link inside the document still lands', async ({ page }) => {
		test.skip(!PAST_SEED, `${DAY} carries its whole day, so nothing about it is fetched`);

		// A lead, which is the deepest address the document is built to reach: the
		// leads of this day sit past the head of the published order, which is what
		// `dayShell`'s `keep` exists for. How far an address can reach past that is
		// the defect recorded above.
		const target = leadingStories(FACTS!.leads ?? [], orderByTime(FACTS!.items)).at(-1)?.item_id;
		test.skip(target === undefined, `${DAY} earned no leading block`);
		await page.addInitScript(`localStorage.setItem('idhazh:theme', 'dark')`);
		await page.setViewportSize({ width: 1536, height: 900 });
		await page.goto(`/${DAY}/#${target}`);
		await expect(page.locator('[data-payload-state]')).toHaveAttribute(
			'data-payload-state',
			'ready'
		);

		const story = page.locator(`article.item[id="${target}"]`);
		await expect(story, 'the lead the link named is not on the page').toHaveCount(1);
		await expect(story, 'the deep link scrolled to a story nobody can see').toBeInViewport();
		await expect(story, 'the story was scrolled to but not focused').toBeFocused();
	});
});
