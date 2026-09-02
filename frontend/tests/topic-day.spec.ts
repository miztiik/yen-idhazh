import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync, existsSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { orderByTime } from '../src/lib/day-shape';
import type { DigestItem } from '../src/lib/payload/types';

/**
 * Row #25's oracle: a topic page holds the stories it used to inline.
 *
 * The document now carries the head of its own desk and the rest arrive from
 * the served day. The question that decides whether that was safe is not how
 * many stories the page ends up with - it is **which** ones, so this is a set
 * comparison. A count that matches with a different set is a story nobody can
 * reach, wearing a passing test.
 *
 * The set the page must hold is taken from the committed canary payload, which
 * is what the build-time loader reads and what the previous build inlined:
 * `day.items` filtered to the route's vertical, in published order. Nothing
 * here re-derives that rule - it applies the same one line the removed
 * build-time filter applied.
 *
 * **Every story is walked to, not just the first screen.** A day page shows
 * twelve at a time behind a `Show N more` control, so reading the rendered list
 * once would measure the pager rather than the payload. The control is pressed
 * until it is gone, which is exactly the reachability question: can a reader
 * get to every story the day published under this topic.
 *
 * What this file cannot reach is the fetch itself. The canary publishes one day
 * with one desk of eight stories, under a seed of fifteen, so its topic
 * document is complete and correctly asks for nothing. The loader's own failure
 * path is held by `payload-state.spec.ts`, which drives the shipped module with
 * every request intercepted; the route's degraded arm is driven by hand against
 * the real corpus in the section 12 smoke, with its interception count printed.
 */

const FRONTEND = process.cwd();
const BUILD = resolve(FRONTEND, 'build');
const CANARY = resolve(FRONTEND, '..', 'backend', 'var', 'canary', 'digest');

const DATE = /^\d{4}-\d{2}-\d{2}$/;

interface TopicRoute {
	date: string;
	vertical: string;
	/** The stories the day published under this topic, in published order. */
	published: string[];
	/** The same ids in the order the page draws them: newest first by the time on
	 * the story. Computed through `orderByTime`, the function the page calls. */
	reading: string[];
	/** What the prerendered document carries. */
	seeded: number;
	html: string;
}

function dirsIn(at: string): string[] {
	if (!existsSync(at)) return [];
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory() && entry.name !== '_app')
		.map((entry) => entry.name)
		.sort();
}

/** The day the pipeline committed for that date, read the way the build reads it. */
function committedDay(date: string): { items: DigestItem[] } | null {
	const [year, month, day] = date.split('-');
	const path = join(CANARY, year, month, day, 'digest.json');
	if (!existsSync(path)) return null;
	return JSON.parse(readFileSync(path, 'utf8'));
}

/** Every topic route in the tree the preview server serves. */
function topicRoutes(): TopicRoute[] {
	const found: TopicRoute[] = [];
	for (const date of dirsIn(BUILD).filter((name) => DATE.test(name))) {
		const day = committedDay(date);
		if (day === null) continue;
		for (const vertical of dirsIn(join(BUILD, date))) {
			const html = join(BUILD, date, vertical, 'index.html');
			if (!existsSync(html)) continue;
			const own = day.items.filter((item) => item.vertical === vertical);
			found.push({
				date,
				vertical,
				published: own.map((item) => item.item_id),
				reading: orderByTime(own).map((item) => item.item_id),
				// The same marker `payload-weight.spec.ts` counts: on every published
				// item and on nothing else this site serialises.
				seeded: readFileSync(html, 'utf8').split('key_points').length - 1,
				html
			});
		}
	}
	return found;
}

const ROUTES = topicRoutes();

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

test('the canary build has a topic route, or nothing below proves anything', () => {
	expect(ROUTES.length, 'no topic route in the built tree').toBeGreaterThan(0);
	expect(
		ROUTES.filter((route) => route.published.length > 0).length,
		'every topic route in the tree is empty, so the set comparison is vacuous'
	).toBeGreaterThan(0);
});

for (const route of ROUTES) {
	test.describe(`/${route.date}/${route.vertical}/`, () => {
		test('the document carries the seed and says whether more is coming', () => {
			const html = readFileSync(route.html, 'utf8');
			const complete = route.seeded >= route.published.length;
			expect(
				html,
				complete
					? 'the document holds the whole desk and still says it is waiting'
					: 'the document is short of the desk and does not say so'
			).toContain(`data-payload-state="${complete ? 'ready' : 'loading'}"`);
		});

		test('every story the day published under this topic is reachable', async ({ page }) => {
			const failed: string[] = [];
			const errors: string[] = [];
			page.on('requestfailed', (request) => failed.push(request.url()));
			page.on('console', (message) => {
				if (message.type() === 'error') errors.push(message.text());
			});
			page.on('pageerror', (error) => errors.push(String(error)));

			await page.goto(`/${route.date}/${route.vertical}/`);
			await expect(
				page.locator('[data-payload-state]'),
				'the page never settled on a state'
			).toHaveAttribute('data-payload-state', 'ready');

			const held = await reachable(page);

			// The set, which is the claim. Sorted, because the order question is
			// asked separately below and a set that matches in a different order is
			// a different failure with a different fix.
			expect([...held].sort(), 'the page holds a different set of stories').toEqual(
				[...route.published].sort()
			);
			// And the order, which is the day's own: a topic page is the day
			// filtered, so the day decides the sequence and the day runs newest
			// first by the time on the story.
			expect(held, 'the stories are not in the order the rail says they are').toEqual(
				route.reading
			);

			expect(errors, 'the topic page logged an error').toEqual([]);
			expect(failed, 'the topic page asked for something that is not there').toEqual([]);
		});
	});
}
