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
 * Four questions, and each one needs two changes to have disagreed to fail:
 *
 * - **Every story carries its own time, and the page names the zone once.** The
 *   time was in the item's eyebrow, then taken out and given a
 *   shared rail, then the rail was deleted and the time given back to
 *   the story. What survived all three is the caption: `Times shown in UTC.`,
 *   once per page, which is what makes a bare clock readable.
 * - **The aside and the sticky filter panel keep out of each other's way.** Two
 *   changes put two things in the same 1400px screen: an 18rem aside and a
 *   panel that sticks from 1024px. Neither knows about the other.
 * - **A day that half arrives is still a designed page.** The dated routes seed
 *   and fetch; a separate design says what a reader meets when
 *   the fetch fails. The three cases below break the fetch at the network and
 *   count what they broke - a case that intercepted nothing has proved that a
 *   page loads, which it would have done anyway.
 * - **The offline reader changes nothing a reader can see.** A worker sits in
 *   front of the same requests the seed and fetch make. A day out of the
 *   device and a day off the network have to be the same page.
 *
 * Several cases cannot run on a day shorter than `ui.shell_seed_items`, because
 * a document that already carries its whole day never fetches - so there is
 * nothing to break and nothing to serve from a cache - and none can run on a
 * day with one desk, which cannot fill a leading block. They read both off the
 * fixture rather than off a locator, and the browser gate's eight-story canary
 * is the case that skips: seven of sixteen tests there, and none on a real
 * published day. `item-zones.spec.ts` set the same precedent for the aside.
 * What the canary cannot reach is measured on the committed digest instead,
 * with hardware and date, in `docs/reference/measurements.md`.
 *
 * **Two cases at the end were written failing and now pass.** Composing the rows
 * broke two things: the dated document counted the stories in its own hand
 * instead of the day's, and a story's own address only landed while the pager
 * was already showing it. Both were fixed on 2026-09-02 and both cases are now
 * ordinary assertions, which is what keeps them fixed. What they measure is in
 * `docs/architecture/publishing/layout.md`.
 */

import { expect, test, type Page } from '@playwright/test';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { deskCount, deskShortfall, leadingStories, orderByTime } from '../src/lib/day-shape';
import { projectDay } from '../src/lib/payload/project';
import { shellSeedItems, uiConfig } from '../src/lib/server/config';
import { loadDay, publishedDates } from '../src/lib/server/payload';
import { dayReady } from './support/day-ready';

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
 * **The served file carries them since 2026-09-09.** It used to carry `version`
 * and `items` and nothing else, with the day's verticals, leads and runs riding
 * in the prerendered document - and deleting that document is what forced them
 * onto the wire. They are still read from the tree the build read, because that
 * is where the check's expectation should come from rather than from the file
 * under test.
 */
const SOURCE = publishedDates(COMMITTED).includes(DAY) ? COMMITTED : CANARY;
const FACTS = loadDay(DAY, SOURCE);

/** A topic of that day, taken from the day's own desk list rather than from a
 * directory `build/` no longer writes. */
const TOPIC = String((FACTS?.verticals ?? [])[0]?.id ?? '');

const SEED = shellSeedItems();
/** Whether the day is longer than the document that seeds it. False on the
 * canary, where nothing fetches and the two fetch cases have nothing to hold. */
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
		// case serves read as a page that threw.
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
		await dayReady(page, `${route} never settled on a state`);
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
	test('every story carries its own time, and the zone is named once', async ({ page }) => {
		await open(page, 'dark', `/${DAY}/`, 1536);

		const stories = page.locator('article.item');
		const drawn = await stories.count();
		expect(drawn, 'the day drew no story, so this proves nothing').toBeGreaterThan(0);

		// The zone is named once, above the stream it explains. Not a suffix on
		// every stamp and not a band of its own at the top of the page. This
		// assertion outlived the time rail that used to carry the sentence: the
		// rail was the duplicate, the caption is what makes a bare clock readable.
		await expect(
			page.locator('[data-time-note]'),
			'the day names its clock more than once, or not at all'
		).toHaveCount(1);
		await expect(page.locator('[data-time-note]')).toHaveText('Times shown in UTC.');

		// And the time is beside the heading, on every story that has one. The
		// rail printed one marker an hour and left 86.3 percent of stories with no
		// time at all (1,218 markers over 8,922 committed stories, re-measured
		// 2026-09-12); what replaced it is the story's own stamp.
		const clocked = await page.locator('[data-item-time]').count();
		expect(
			clocked,
			`${clocked} of ${drawn} stories print a time, and only a story whose ` +
				`time_source is unknown may print none`
		).toBeGreaterThanOrEqual(drawn - 1);
	});

	test('the aside and the sticky panel keep out of each other', async ({ page }) => {
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
					stream: box('.day-stream')
				};
			});

		const at_rest = await read();
		expect(at_rest.aside, 'the aside is not on the page at 1536px').not.toBeNull();
		expect(at_rest.panel, 'the filter panel is not on the page').not.toBeNull();

		// The aside stands beside the stream, so it starts where the stream ends.
		expect(
			at_rest.aside!.left,
			`the aside starts at ${Math.round(at_rest.aside!.left)} and the stream runs to ` +
				`${Math.round(at_rest.stream!.right)}, so they overlap`
		).toBeGreaterThanOrEqual(at_rest.stream!.right - 0.5);

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
 * The two things composing the rows got wrong, held so they stay fixed.
 *
 * Both were written here failing on 2026-09-02 and both are ordinary assertions
 * now. What each one measures is in `docs/architecture/publishing/layout.md`.
 */
test.describe('the count and the address', () => {
	/** The story count the page states, once the day it names is in hand.
	 *
	 * **It used to be read off the built document**, because the half that was
	 * wrong was the half a reader with no script got and never saw change. There
	 * is no dated document since 2026-09-09 - one shell answers every dated
	 * address - so the number is read where a reader reads it. What the check is
	 * about has not moved: the notice states the day's own published total, never
	 * the length of the list in hand, so it cannot tick up while a reader is
	 * looking at it.
	 */
	async function printedCount(page: Page, route: string): Promise<number> {
		await open(page, 'dark', route, 1536);
		await dayReady(page);
		const line = ((await page.locator('p.notice-count').first().textContent()) ?? '')
			.replace(/\s+/g, ' ')
			.trim();
		const printed = /^(\d+) stor/.exec(line);
		expect(printed, `${route} opens with "${line}" and states no count`).not.toBeNull();
		return Number(printed![1]);
	}

	test('the dated page says how many stories the day published', async ({ page }) => {
		// The day's own bounded count, which is the number the topic row prints a
		// few lines below this sentence on the same screen. Through `deskCount`,
		// because the page counts stories where a reader finds them: `count` is the
		// carrying feed's word, and the two part on a relabelled story.
		const published = (FACTS?.verticals ?? []).reduce((sum, ref) => sum + deskCount(ref), 0);
		const drawn = await printedCount(page, `/${DAY}/`);
		const stories = await page.locator('article.item[id]').count();

		console.log(
			`[reading-page] /${DAY}/ counts ${drawn} on a day that published ${published}, ` +
				`with ${stories} stories on the first screen`
		);
		expect(
			drawn,
			`the first line under the date claims ${drawn} stories on a day that published ` +
				`${published}. It counts the list in hand rather than the day's own total, so a ` +
				'reader pressing the pager would watch it tick'
		).toBe(published);
		// And the case that says the number is not simply the list: the stream pages
		// at twelve, so a count taken off what is drawn would be smaller on any day
		// past that.
		expect(stories, 'the page drew no story, so the count above proves nothing').toBeGreaterThan(0);
	});

	test('a topic page says how many stories that desk published', async ({ page }) => {
		const desk = FACTS?.verticals.find((ref) => ref.id === TOPIC);
		expect(desk, `${DAY} serves /${TOPIC}/ and its payload names no such desk`).toBeDefined();

		// `deskCount` and not `count`: the page is about where stories are READ,
		// and a story its feed filed under this name but the day published under
		// another is not on this page to be counted.
		const owed = deskCount(desk!);
		const printed = await printedCount(page, `/${DAY}/${TOPIC}/`);
		console.log(`[reading-page] /${DAY}/${TOPIC}/ counts ${printed} of the desk's ${owed}`);
		expect(
			printed,
			`the topic page claims ${printed} stories on a desk that published ${owed}. A ` +
				'topic page is about one desk, so the desk is the number it owes the reader'
		).toBe(owed);
	});

	test('every story the day published has an address that lands', async ({ page }) => {
		test.skip(!PAST_SEED, `${DAY} carries its whole day, so no story is below the seed`);

		const items = orderByTime(FACTS!.items);
		// A lead is already in the document, so a lead would prove nothing about a
		// pager. The nearest story that is not one stands in for it.
		const leads = new Set(
			leadingStories(FACTS!.leads ?? [], items).map((story) => story.item_id)
		);
		const notALead = (from: number): number => {
			for (let at = from; at < items.length; at += 1) if (!leads.has(items[at].item_id)) return at;
			for (let at = from - 1; at >= 0; at -= 1) if (!leads.has(items[at].item_id)) return at;
			return from;
		};
		// One past the pager's first page, one deep in the middle, and the last
		// story of the day - which is the address furthest from anything the
		// document carries.
		const walk = [...new Set([12, 300, items.length - 1].filter((at) => at < items.length))]
			.map(notALead)
			.sort((a, b) => a - b);
		expect(walk.length, `${DAY} is too short to walk past its own pager`).toBeGreaterThan(0);

		for (const position of walk) {
			const target = items[position].item_id;
			await open(page, 'dark', `/${DAY}/#${target}`, 1536);

			const story = page.locator(`article.item[id="${target}"]`);
			const drawn = await page.locator('article.item').count();
			await expect(
				story,
				`position ${position} of ${items.length}: the stream drew ${drawn} stories and none ` +
					'of them was the one the address named'
			).toHaveCount(1, { timeout: 15_000 });
			await expect(
				story,
				`position ${position} of ${items.length} was drawn but not scrolled to`
			).toBeInViewport();
			await expect(
				story,
				`position ${position} of ${items.length} was scrolled to but not focused`
			).toBeFocused();
			console.log(
				`[reading-page] position ${position} of ${items.length}: resolved, in view, focused`
			);
		}
	});

	test('an address for a story this day never held says so', async ({ page }) => {
		await open(page, 'dark', `/${DAY}/#no-such-story-on-this-day`, 1536);

		const region = page.locator('[data-anchor-missing]');
		await expect(region, 'the page carries no region to say it in').toHaveCount(1);
		await expect(
			region,
			'a link to a story this day never held drops the reader at the top with nothing said'
		).toHaveAttribute('data-anchor-missing', 'yes');
		await expect(region).toContainText('not on this page');
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
	 * Decision 3: a case that reports zero interceptions is a null result rather
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
			`the ${name} case never reached a settled state`
		).toHaveAttribute('data-payload-state', 'unreachable');
		console.log(`[reading-page] ${name}: intercepted ${taken.length} - ${taken.join(', ')}`);
		expect(taken.length, `the ${name} case intercepted nothing, so it measured nothing`).toBeGreaterThan(
			0
		);
		return taken.length;
	}

	/** What the reader is left with, whichever way the day failed: the designed
	 * panel, the retry, and every story the document already carried. */
	async function designed(page: Page, name: string): Promise<void> {
		await expect(
			page.locator('[data-payload-state] .failed-headline'),
			`the ${name} case drew no headline`
		).toContainText(DAY.slice(0, 4));
		await expect(
			page.getByRole('button', { name: 'Try again' }),
			`the ${name} case offers no way to try again`
		).toHaveCount(1);
		const held = await page.locator('article.item').count();
		expect(
			held,
			`the ${name} case took the document's own stories away as well`
		).toBeGreaterThan(0);
		const measured = await page.evaluate(() => ({
			scrollWidth: document.documentElement.scrollWidth,
			clientWidth: document.documentElement.clientWidth
		}));
		expect(
			measured.scrollWidth,
			`the ${name} case scrolls sideways`
		).toBeLessThanOrEqual(measured.clientWidth);
	}

	test('absent: the host does not have the file', async ({ page }) => {
		const faults = watch(page);
		await broken(page, 'absent', (route) => route.fulfill({ status: 404, body: '' }));
		await designed(page, 'absent');
		// The 404 is the case. What must not be there is anything thrown.
		expect(
			faults.errors,
			`the absent case threw:\n${faults.errors.join('\n')}`
		).toEqual([]);
	});

	test('empty: the file is there and holds nothing', async ({ page }) => {
		const faults = watch(page);
		await broken(page, 'empty', (route) =>
			route.fulfill({ status: 200, contentType: 'application/json', body: '' })
		);
		await designed(page, 'empty');
		expect(faults.errors, `the empty case threw:\n${faults.errors.join('\n')}`).toEqual([]);
	});

	test('unparseable: the file is there and is not a day', async ({ page }) => {
		const faults = watch(page);
		await broken(page, 'unparseable', (route) =>
			route.fulfill({ status: 200, contentType: 'application/json', body: '}{ not a day' })
		);
		await designed(page, 'unparseable');
		expect(faults.errors, `the unparseable case threw:\n${faults.errors.join('\n')}`).toEqual([]);
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
				// A case that ended on a page that could not load has nothing to
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
		await dayReady(page);
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
			await dayReady(page);
		const story = page.locator(`article.item[id="${target}"]`);
		await expect(story, 'the lead the link named is not on the page').toHaveCount(1);
		await expect(story, 'the deep link scrolled to a story nobody can see').toBeInViewport();
		await expect(story, 'the story was scrolled to but not focused').toBeFocused();
	});
});

/**
 * The publisher card's oracle: one card per story, and every publisher on it is a
 * way in.
 *
 * The day's grouping has been computed, persisted and deliberately withheld from
 * the page since it was written, because the first attempt at drawing it took a
 * grouped story off the list while its address still existed - so the story was
 * unreachable through every reading route and the page said it was not here.
 * This is the answer to that, and it is what the cases below are about:
 *
 * - The anchor draws one card, and the stories it folds do not draw cards.
 * - The card names the other newsrooms, and every name is a link.
 * - **Every folded address still lands**: drawn, scrolled to, and focused.
 * - Nothing is removed. The payload the page was handed still carries every
 *   story, so the archive and the month index - both built from that payload and
 *   never from this page - cannot have lost one.
 *
 * **The day is routed rather than read off `build/`.** A dated URL is answered by
 * one shell that fetches its day, so a spec can hand the real page any day it
 * likes. It has to: the committed archive's groups are whatever the sources ran
 * that morning, and none of them is three outlets on one story with a fourth
 * story beside it, which is the shape every case here needs (`CLAUDE.md`
 * section 13). The payload is built by `projectDay` - the projector that writes
 * every served day - so the publisher names are derived here exactly as they are
 * in a build.
 *
 * **The knob-off arm is in `day-list.spec.ts` and not here.** `ui.draw_same_story`
 * is read at build time and inlined into the one shell, so a browser arm would
 * need a second build of the whole site; what it would prove past the logic arm
 * is that one `$derived` reads the knob. The logic arm drives `foldedMembers`
 * with the knob off and gets an empty set, which is one card per story.
 */
test.describe('one card, and every publisher on it is a way in', () => {
	const FOLD_DAY = '2026-01-03';
	const FOLD_PATH = `/digest/${FOLD_DAY.split('-').join('/')}/digest.json`;
	/** The anchor, then the two stories folded behind it, then a story on its own.
	 * `rank_score` decides the order the names are printed in. */
	const ANCHOR = 'ai-01';
	const MEMBERS = ['ai-02', 'ai-03'];
	const ALONE = 'world-01';
	/** A story no outlet matched TODAY, which one outlet ran the evening before. */
	const PICKED_UP = 'world-02';

	/** One committed story, carrying what the card and the projector read. */
	function story(
		item_id: string,
		source_name: string,
		rank_score: number,
		same_story_as: string | null
	): Record<string, unknown> {
		return {
			item_id,
			vertical: item_id.split('-')[0],
			title: `Story ${item_id} from ${source_name}`,
			summary: `What ${source_name} reported about ${item_id}.`,
			key_points: [`${item_id} happened.`],
			reader_note: null,
			band: 'high',
			band_reason: null,
			truncated: false,
			visual: null,
			source_name,
			source_id: source_name.toLowerCase(),
			source_kind: 'reporting',
			source_url: `https://${source_name.toLowerCase()}.test/${item_id}`,
			published_at: '2026-01-03T09:00:00Z',
			time_source: 'feed',
			carried_by: 1,
			watchlist_hit: false,
			on_front_page: false,
			rank_score,
			// Three outlets ran it, so two of them are other outlets whichever member
			// you stand on. The count and the names have to agree.
			also_covered_by: 2,
			same_story_as,
			introduced_by_run: 1,
			lenses: []
		};
	}

	const COMMITTED = {
		version: '2026-01-03T09:00',
		date: FOLD_DAY,
		generated_at: '2026-01-03T10:00:00Z',
		partial: false,
		items_planned: 5,
		items_failed: 0,
		runs: [{ n: 1, at: '2026-01-03T10:00:00Z', items_added: 4 }],
		verticals: [
			{ id: 'ai', display_name: 'AI', count: 3, desk_count: 3 },
			{ id: 'world', display_name: 'World', count: 2, desk_count: 2 }
		],
		// One lead on the anchor and one on a story the anchor folds. The second is
		// what says which of the two wins, and the fold does: a folded story is not
		// drawn as its own card, so it is not an anchor the block can point at.
		leads: [
			{ item_id: ANCHOR, reason: 'Three newsrooms ran it.' },
			{ item_id: MEMBERS[0], reason: 'A second telling of the same story.' }
		],
		items: [
			story(ANCHOR, 'Alpha', 0.9, null),
			story(MEMBERS[0], 'Beta', 0.7, ANCHOR),
			story(MEMBERS[1], 'Gamma', 0.8, ANCHOR),
			{ ...story(ALONE, 'Delta', 0.4, null), also_covered_by: 0 },
			{
				...story(PICKED_UP, 'Zeta', 0.3, null),
				also_covered_by: 0,
				also_ran_earlier: [
					{
						date: '2026-01-02',
						item_id: 'world-9999999999',
						source_name: 'Epsilon'
					}
				]
			}
		]
	};

	/** The served day, written by the projector that writes every served day. */
	const SERVED = projectDay(JSON.stringify(COMMITTED));

	/** Open the routed day, and count what was intercepted.
	 *
	 * A case that intercepted nothing has proved that a page loads, which it would
	 * have done anyway - the same rule the broken-day cases above follow.
	 */
	async function openFolded(page: Page, hash = ''): Promise<void> {
		const taken: string[] = [];
		await page.route(`**${FOLD_PATH}`, async (route) => {
			taken.push(new URL(route.request().url()).pathname);
			await route.fulfill({ status: 200, contentType: 'application/json', body: SERVED });
		});
		await page.addInitScript(`localStorage.setItem('idhazh:theme', 'dark')`);
		await page.setViewportSize({ width: 1536, height: 900 });
		await page.goto(`/${FOLD_DAY}/${hash}`);
		await dayReady(page, `/${FOLD_DAY}/${hash} never settled on a state`);
		expect(taken.length, 'the case intercepted nothing, so it measured nothing').toBeGreaterThan(0);
	}

	const drawn = (page: Page): Promise<string[]> =>
		page.locator('article.item[id]').evaluateAll((nodes) => nodes.map((node) => node.id));

	test('the projector kept every story, so nothing built from the payload lost one', () => {
		// The archive list and the month search index are both built from this
		// payload and never from the page, so this is what says a folded story keeps
		// its archive entry and its search entry. The fold is a drawing decision.
		const served = JSON.parse(SERVED) as { items: { item_id: string; same_story_as?: string }[] };
		expect(served.items.map((item) => item.item_id)).toEqual([
			ANCHOR,
			...MEMBERS,
			ALONE,
			PICKED_UP
		]);
		for (const member of MEMBERS) {
			const item = served.items.find((one) => one.item_id === member);
			expect(item?.same_story_as, `${member} lost the story it names`).toBe(ANCHOR);
		}
	});

	test('the anchor draws one card and the stories it folds draw none', async ({ page }) => {
		await openFolded(page);

		const ids = await drawn(page);
		expect(ids, 'the page did not fold the group into one card').toEqual([
			ANCHOR,
			ALONE,
			PICKED_UP
		]);
		expect(
			ids.filter((id) => id === ANCHOR).length,
			'the anchor was drawn more than once'
		).toBe(1);
	});

	test('the card names the other newsrooms, and every name is a link to one', async ({ page }) => {
		await openFolded(page);

		const stack = page.locator(`article.item[id="${ANCHOR}"] [data-item-stack]`);
		await expect(stack, 'the folding card names nobody').toHaveCount(1);
		await expect(stack, 'the stack lost its sentence').toContainText('Also covered by');

		// Strongest first, which is `rank_score` order: Gamma at 0.8 before Beta at
		// 0.7. A stack in payload order would pass a count and fail this.
		const pills = page.locator(`article.item[id="${ANCHOR}"] [data-coverage-pill]`);
		await expect(pills).toHaveText(['Gamma', 'Beta']);
		expect(
			await pills.evaluateAll((nodes) =>
				nodes.map((node) => node.getAttribute('data-coverage-pill'))
			),
			'a publisher name points at a story other than the one it folds'
		).toEqual([MEMBERS[1], MEMBERS[0]]);
		expect(
			await pills.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('href'))),
			'a publisher name is not a link to that story on this page'
		).toEqual([`#${MEMBERS[1]}`, `#${MEMBERS[0]}`]);

		// A story no group holds keeps the sentence and gets no stack, because the
		// count and the names answer different questions.
		await expect(
			page.locator(`article.item[id="${ALONE}"] [data-item-stack]`),
			'a story on its own was given a publisher stack'
		).toHaveCount(0);
	});

	test('a newsroom that ran it yesterday is a name in the same stack, dated', async ({ page }) => {
		// The window past midnight, as a reader meets it. The story keeps its own
		// card - a cross-day match folds nothing, because a fold onto a card this
		// page does not hold is a fold onto nothing - and what it gains is one more
		// name, saying which day and pointing at that day's page.
		await openFolded(page);

		const earlier = page.locator(`article.item[id="${PICKED_UP}"] [data-earlier-pill]`);
		await expect(earlier, 'the earlier telling is not named').toHaveCount(1);
		await expect(earlier, 'the name does not say which day it ran').toContainText('Epsilon');
		await expect(earlier).toContainText('yesterday');
		expect(
			await earlier.getAttribute('href'),
			'an earlier name does not link to the day that holds it'
		).toBe('/2026/01/02/#world-9999999999');

		// And the story it is on is still drawn, which is the whole difference
		// between a name and a fold.
		await expect(
			page.locator(`article.item[id="${PICKED_UP}"]`),
			'a cross-day match folded the story away'
		).toHaveCount(1);
	});

	// One test per folded story rather than one loop over both, because a second
	// `goto` to the same address with a different fragment is a hash change: the
	// client router never re-fetches, so the second pass would measure a page the
	// first pass had already loaded. A cold load of the address is the case.
	for (const member of MEMBERS) {
		test(`${member} is folded, and its own address still lands on it`, async ({ page }) => {
			// This is the whole of what pulled the collapse the first time. A folded
			// story is not removed - it keeps its address - so its address has to work.
			await openFolded(page, `#${member}`);

			const card = page.locator(`article.item[id="${member}"]`);
			const ids = await drawn(page);
			await expect(
				card,
				`the page drew ${ids.join(', ')} and none of them was the story the address named`
			).toHaveCount(1, { timeout: 15_000 });
			await expect(card, `${member} was drawn but not scrolled to`).toBeInViewport();
			await expect(card, `${member} was scrolled to but not focused`).toBeFocused();

			// And the page does not say the story is missing, which is the sentence the
			// first attempt at this made every grouped story print.
			await expect(
				page.locator('[data-anchor-missing]'),
				`${member} is on the page and the page says it is not`
			).toHaveAttribute('data-anchor-missing', 'no');
			console.log(`[reading-page] ${member}: folded, addressed, drawn, in view, focused`);
		});
	}

	test('pressing a publisher name opens that newsroom on the same page', async ({ page }) => {
		await openFolded(page);

		await page.locator(`[data-coverage-pill="${MEMBERS[0]}"]`).click();
		const card = page.locator(`article.item[id="${MEMBERS[0]}"]`);
		await expect(card, 'the name did not open the story it folds').toHaveCount(1, {
			timeout: 15_000
		});
		await expect(card, 'the story opened but the page did not go to it').toBeInViewport();
		// Our summary of THEIR piece, with their own way out under it. That is why
		// the name links here rather than straight out to the publisher.
		await expect(card.locator('[data-item-summary]')).toContainText('Beta');
		await expect(card.locator('a[href^="https://beta.test/"]')).toHaveCount(1);
	});

	test('the pager does not offer stories the fold took off the page', async ({ page }) => {
		// The day published four stories and the page draws two. `Show N more`
		// counts against the day's own total unless the list is narrowed on purpose,
		// so a fold that left the floor alone would offer two stories for ever.
		await openFolded(page);
		await expect(
			page.getByRole('button', { name: /^Show \d+ more$/ }),
			'the pager offers stories the fold removed, so it can never empty'
		).toHaveCount(0);
	});

	test('the leading block drops a lead the fold took off the page', async ({ page }) => {
		// A lead is an anchor into the stream, so a lead on a story that is not drawn
		// is a link to nothing. The block resolves against the list the page holds,
		// which is the list after the fold, so the lead simply is not in it - the
		// block is one entry shorter rather than one entry broken.
		await openFolded(page);

		const leads = await page
			.locator('[data-lead]')
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-lead')));
		expect(leads, 'the block kept a lead on a story the page does not draw').toEqual([ANCHOR]);
	});
});
