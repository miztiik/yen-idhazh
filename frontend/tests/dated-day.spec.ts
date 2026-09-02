import { expect, test, type Page } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { orderByTime } from '../src/lib/day-shape';
import type { DigestItem } from '../src/lib/payload/types';
import { shellSeedItems } from '../src/lib/server/config';
import { dayShell, loadDay, publishedDates } from '../src/lib/server/payload';

/**
 * Row #26's oracle: a dated day page holds the stories it used to inline, and a
 * deep link into it still lands.
 *
 * `/<date>/` now carries the head of the day plus every story its leading block
 * points at, and the rest arrive from the served day. Two things have to remain
 * true, and they are different questions.
 *
 * **Which stories, not how many.** A count that matches with a different set is
 * a story nobody can reach wearing a passing test, so the comparison below is
 * over ids. The expected set is read from `build/digest/`, which is the file the
 * browser itself fetches - not from a corpus this file names - so the check says
 * the same thing whichever tree the preview server is serving.
 *
 * **Every story is walked to.** The stream pages at twelve, so reading the
 * rendered list once would measure the pager rather than the payload. The
 * control is pressed until it is gone.
 *
 * **A deep link is a canonical reader address.** The leading block is a set of
 * anchors into the stream and its leads are chosen across the whole day, so a
 * document holding a plain prefix would ship links that land on nothing. That is
 * what `dayShell`'s `keep` is for, and the first group below holds it against
 * the committed corpus, where a day carries leads at positions the head cannot
 * reach. The browser group then proves the landing itself: scrolled into view
 * and focused, which is the half a browser does not do on its own.
 */

const FRONTEND = process.cwd();
const BUILD = resolve(FRONTEND, 'build');
/** The committed days, whichever tree the preview server happens to serve. */
const COMMITTED = resolve(FRONTEND, 'public', 'digest');

const DATE = /^\d{4}-\d{2}-\d{2}$/;

test.describe('the day a document seeds', () => {
	const seed = shellSeedItems();

	/** Where each of a day's leads sits in the published order. */
	function leadPositions(date: string): number[] {
		const day = loadDay(date, COMMITTED);
		if (!day) return [];
		const at = new Map(day.items.map((item, index) => [item.item_id, index]));
		return (day.leads ?? []).map((lead) => at.get(lead.item_id) ?? -1);
	}

	test('a committed day names a lead the head cannot reach, or the rest proves nothing', () => {
		const dates = publishedDates(COMMITTED);
		expect(dates.length, 'no day is committed').toBeGreaterThan(0);
		const deep = dates.flatMap(leadPositions).filter((at) => at >= seed);
		expect(
			deep.length,
			`no committed day leads with a story past position ${seed}, so keeping one is untested`
		).toBeGreaterThan(0);
	});

	test('every lead is in the seed, whatever its position', () => {
		for (const date of publishedDates(COMMITTED)) {
			const day = loadDay(date, COMMITTED);
			const leads = (day?.leads ?? []).map((lead) => lead.item_id);
			const shell = dayShell(date, seed, { keep: leads, root: COMMITTED });
			const seeded = new Set((shell?.seed ?? []).map((item) => item.item_id));
			const lost = leads.filter((id) => !seeded.has(id));
			expect(lost, `${date} leads with a story its document does not carry`).toEqual([]);
		}
	});

	test('the seed is the head plus the leads and nothing else, and the day is not doubled', () => {
		for (const date of publishedDates(COMMITTED)) {
			const day = loadDay(date, COMMITTED);
			if (!day) continue;
			const leads = (day.leads ?? []).map((lead) => lead.item_id);
			const shell = dayShell(date, seed, { keep: leads, root: COMMITTED })!;
			expect(
				shell.seed.length,
				`${date} seeds more than the head and its leads`
			).toBeLessThanOrEqual(seed + leads.length);
			expect(
				[...shell.seed, ...shell.rest].map((item) => item.item_id).sort(),
				`${date} lost or doubled a story across the split`
			).toEqual(day.items.map((item) => item.item_id).sort());
		}
	});
});

interface DayRoute {
	date: string;
	/** Every story id the day serves, in published order. */
	served: string[];
	/** The same ids in the order the page draws them: newest first by the time on
	 * the story. Computed through `orderByTime`, the function the page calls, so
	 * this file cannot disagree with the page about what the order is. */
	reading: string[];
	/** Every story id the prerendered document renders, in document order. */
	rendered: string[];
	/** Every story id the document's leading block points at. */
	leads: string[];
	html: string;
}

function dirsIn(at: string): string[] {
	if (!existsSync(at)) return [];
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory() && entry.name !== '_app')
		.map((entry) => entry.name)
		.sort();
}

/** All of a pattern's first capture, in the order they appear. */
function captured(html: string, pattern: RegExp): string[] {
	return [...html.matchAll(pattern)].map((match) => match[1]);
}

/** Every story the document renders, in document order.
 *
 * Read off the open tag's attributes rather than off one written order, because
 * the order attributes are serialised in is the compiler's business and not a
 * promise to this file.
 */
function renderedItems(html: string): string[] {
	return captured(html, /<article\b([^>]*)>/g)
		.filter((attributes) => /\bclass="[^"]*\bitem\b/.test(attributes))
		.map((attributes) => /\bid="([^"]+)"/.exec(attributes)?.[1] ?? '')
		.filter((id) => id !== '');
}

/** The day the built tree serves at that date - the file the browser fetches. */
function servedDay(date: string): { items: DigestItem[] } | null {
	const [year, month, day] = date.split('-');
	const path = join(BUILD, 'digest', year, month, day, 'digest.json');
	if (!existsSync(path)) return null;
	return JSON.parse(readFileSync(path, 'utf8'));
}

/** Every dated route in the tree the preview server serves. */
function dayRoutes(): DayRoute[] {
	const found: DayRoute[] = [];
	for (const date of dirsIn(BUILD).filter((name) => DATE.test(name))) {
		const html = join(BUILD, date, 'index.html');
		const served = servedDay(date);
		if (!existsSync(html) || served === null) continue;
		const document = readFileSync(html, 'utf8');
		found.push({
			date,
			served: served.items.map((item) => item.item_id),
			reading: orderByTime(served.items).map((item) => item.item_id),
			rendered: renderedItems(document),
			leads: captured(document, /data-lead="([^"]+)"/g),
			html
		});
	}
	return found;
}

const ROUTES = dayRoutes();
/** The route whose deepest anchor sits furthest down the day. */
const DEEPEST = ROUTES.filter((route) => route.rendered.length > 0).sort(
	(a, b) => a.rendered.length - b.rendered.length
).at(-1);

/** Every story the page can be walked to, in the order it draws them. */
async function reachable(page: Page): Promise<string[]> {
	const more = page.getByRole('button', { name: /^Show \d+ more$/ });
	// Bounded rather than `while (true)`: a pager that stops shrinking would
	// otherwise hang the suite instead of failing it.
	for (let round = 0; round < 200; round += 1) {
		if ((await more.count()) === 0) break;
		await more.click();
	}
	expect(await more.count(), 'the pager never ran out of stories').toBe(0);
	return page.locator('article.item[id]').evaluateAll((nodes) => nodes.map((node) => node.id));
}

test('the built tree has a dated route with stories, or nothing below proves anything', () => {
	expect(ROUTES.length, 'no dated route in the built tree').toBeGreaterThan(0);
	expect(
		ROUTES.filter((route) => route.served.length > 0).length,
		'every dated route in the tree is empty, so the set comparison is vacuous'
	).toBeGreaterThan(0);
});

for (const route of ROUTES) {
	test.describe(`/${route.date}/`, () => {
		test('the document carries a seed and says whether more is coming', () => {
			const html = readFileSync(route.html, 'utf8');
			const complete = route.rendered.length >= route.served.length;
			expect(
				html,
				complete
					? 'the document holds the whole day and still says it is waiting'
					: 'the document is short of the day and does not say so'
			).toContain(`data-payload-state="${complete ? 'ready' : 'loading'}"`);
		});

		test('every lead the document draws is an anchor it can reach', () => {
			const held = new Set(route.rendered);
			const dead = route.leads.filter((id) => !held.has(id));
			expect(dead, 'a lead link in the prerendered document lands on nothing').toEqual([]);
		});

		// A day that published nothing renders the designed empty screen and has
		// no list to walk. `day-states.spec.ts` owns that page; walking it here
		// would only cost the suite a page load per quiet day - nineteen of them
		// in the canary corpus - to assert an empty set against an empty set.
		if (route.served.length === 0) return;

		test('every story the day published is reachable', async ({ page }) => {
			const failed: string[] = [];
			const errors: string[] = [];
			page.on('requestfailed', (request) => failed.push(request.url()));
			page.on('console', (message) => {
				if (message.type() === 'error') errors.push(message.text());
			});
			page.on('pageerror', (error) => errors.push(String(error)));

			await page.goto(`/${route.date}/`);
			await expect(
				page.locator('[data-payload-state]'),
				'the page never settled on a state'
			).toHaveAttribute('data-payload-state', 'ready');

			const held = await reachable(page);

			// The set, which is the claim. Sorted, because the order question is
			// asked separately below and a set that matches in a different order is
			// a different failure with a different fix.
			expect([...held].sort(), 'the page holds a different set of stories').toEqual(
				[...route.served].sort()
			);
			// And the order, which is the day's own: newest first by the time on the
			// story, with the rail drawing a marker where it changes.
			expect(held, 'the stories are not in the order the rail says they are').toEqual(
				route.reading
			);

			expect(errors, 'the day page logged an error').toEqual([]);
			expect(failed, 'the day page asked for something that is not there').toEqual([]);
		});
	});
}

/**
 * The deep link, on the route whose document reaches furthest down the day.
 *
 * The target is the last story the document draws, because document order is
 * published order - so on a day with leads it is a lead the head could never
 * have held, and on a small day it is that day's last story. Either way it is
 * the deepest address the page publishes.
 *
 * Scrolled AND focused, because a browser does the first by itself and never the
 * second: a reader arriving by keyboard on a page that only scrolled lands at
 * the top of the document and has to tab back down to what the link sent them
 * to read.
 */
test('a deep link into a day scrolls to its story and focuses it', async ({ page }) => {
	expect(DEEPEST, 'no dated route in the tree renders a story').toBeDefined();
	const route = DEEPEST!;
	const target = route.rendered.at(-1)!;

	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(String(error)));

	await page.goto(`/${route.date}/#${target}`);
	await expect(
		page.locator('[data-payload-state]'),
		'the page never settled on a state'
	).toHaveAttribute('data-payload-state', 'ready');

	const story = page.locator(`article.item[id="${target}"]`);
	await expect(story, 'the story the link named is not on the page').toHaveCount(1);
	await expect(story, 'the link scrolled to a story nobody can see').toBeInViewport();
	await expect(story, 'the story was scrolled to but not focused').toBeFocused();
	expect(errors, 'following the deep link threw').toEqual([]);
});
