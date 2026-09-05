/**
 * Row #3's oracle: one whole committed day, looked at end to end.
 *
 * Every other check in this programme measures one drawing. That is the right
 * question for a component and the wrong one for a page: a per-visual oracle
 * cannot see forty-three drawings that turned out to be the same drawing, it
 * cannot see a day that never finishes arriving, and it cannot see a story
 * whose picture silently never came. This file asks those questions, on the
 * heaviest day the repository has committed, at a phone width and a desktop
 * width, in both themes (Susan, 2026-09-05).
 *
 * **It runs against the real build and it cannot be fooled into passing against
 * anything else.** The canary day the browser gate serves is eight stories on
 * one desk against a seed of fifteen, so it never fetches and never reaches day
 * scale - a check written here that ran there would assert almost nothing and
 * report a pass. `frontend/build` is one directory that both builds write, so
 * being handed the wrong tree is an ordinary Tuesday rather than a hypothetical.
 * Two things close it. This file is outside the default suite's file set
 * (`playwright.config.ts` ignores it, `playwright.whole-day.config.ts` is the
 * only config that selects it), and the module below refuses to load at all
 * unless the tree under test serves exactly the days this repository has
 * committed. A wrong tree is a loud red file, never a quiet green one.
 *
 * **The whole day is on the page, not the first twelve stories.** The stream
 * pages at twelve and a day of six hundred stories is fifty-two clicks, which
 * measured past the test timeout on a loaded machine. `/<date>/#<story id>` is
 * a published reader address and the pager honours it by drawing down to that
 * story in one render, so naming the LAST story of the day draws all of it -
 * which is also the deep link a reader follows out of a search result.
 *
 * **The scroll is stepped, and that is not a stylistic choice.** A story past
 * the seed asks for its drawing through an `IntersectionObserver` with a one
 * screen margin, so a jump to the bottom of the page fires the observers at the
 * bottom and none of the ones it flew past - and the arm then reports zero
 * fetches on a page whose fetching is fine. One viewport at a time is the step
 * that cannot skip a slot, and the count of drawings that arrived by fetch is
 * asserted rather than assumed, because a zero there is a null result and not a
 * pass.
 *
 * **The colour oracle is row 1's, applied to every drawing rather than to one.**
 * A probe element is given the same custom property the stylesheet routes each
 * mark to, and what the document computed for it is compared against what the
 * document painted. The two themes give those properties different values, so
 * no baked hex can satisfy both arms - which is what makes this an oracle
 * rather than a restatement of the stylesheet.
 *
 * **Which marks it looks for is read off the day's own drawings.** That is not
 * fussiness. Written against the canary's shape it demanded a grid line, and no
 * published drawing has ever carried one - measured 2026-09-05 across all 351
 * drawings the fifteen committed days hold. A check that decided instead from
 * what it found on the page would have gone quiet rather than red, which is the
 * same trap `docs/how-to/run-the-gates.md` records for skip conditions.
 */

import { expect, test, type Page } from '@playwright/test';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { orderByTime } from '../src/lib/day-shape';
import { shellSeedItems } from '../src/lib/server/config';
import { publishedDates } from '../src/lib/server/payload';
import type { DigestDay, DigestItem } from '../src/lib/payload/types';

/** This file's own directory, never `process.cwd()`: the answer has to be the
 * same whether the suite starts from `frontend/` or from the repository root. */
const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '..');
/** The tree the preview server serves. */
const BUILT = join(FRONTEND, 'build', 'digest');
/** The tree the pipeline commits, which is what a real build is made from. */
const COMMITTED = join(FRONTEND, 'public', 'digest');

/** Every day the built tree serves, newest first. Directory shape only, so this
 * costs a `readdir` rather than fifteen megabytes of JSON. */
function servedDates(): string[] {
	return publishedDates(BUILT);
}

/** Refuse a tree that is not the published site, before a single test runs.
 *
 * Decision 2 of this row made mechanical. The failure is a thrown module rather
 * than a skip: a skip in a suite nobody reads is indistinguishable from a check
 * that never existed, and this file's whole value is that it looks at day scale.
 */
function theTreeUnderTest(): string[] {
	const committed = publishedDates(COMMITTED);
	const served = servedDates();
	if (committed.length === 0) {
		throw new Error(
			`there is no committed digest under ${COMMITTED}, so there is no day to look at`
		);
	}
	const missing = committed.filter((date) => !served.includes(date));
	const extra = served.filter((date) => !committed.includes(date));
	if (missing.length > 0 || extra.length > 0) {
		throw new Error(
			`frontend/build was not made from the committed digest, so this check would prove ` +
				`nothing. It serves ${served.length} day(s) and the repository has committed ` +
				`${committed.length}. ` +
				(extra.length > 0 ? `Served but never committed: ${extra.join(', ')}. ` : '') +
				(missing.length > 0
					? `Committed but not served: ${missing.slice(0, 3).join(', ')}${
							missing.length > 3 ? ` and ${missing.length - 3} more` : ''
						}. `
					: '') +
				`Run 'npm run build' - not 'npm run build:canary' - and try again.`
		);
	}
	return served;
}

const SERVED_DATES = theTreeUnderTest();

/** How many drawings a served day stages, counted off the files themselves. */
function drawingFiles(date: string): number {
	const [year, month, day] = date.split('-');
	return readdirSync(join(BUILT, year, month, day)).filter((name) => name.endsWith('.svg')).length;
}

/** The served payload's size in bytes, which is what a browser downloads. */
function servedBytes(date: string): number {
	const [year, month, day] = date.split('-');
	return statSync(join(BUILT, year, month, day, 'digest.json')).size;
}

/** The heaviest committed day: the one that draws the most.
 *
 * Heaviest is measured in drawings rather than in stories, and the two are not
 * the same day. Measured 2026-09-05 over the fifteen committed days on this
 * tree: 2026-08-24 publishes the most stories, 731, and draws four of them -
 * 54.2 KB of markup. 2026-08-31 publishes 601 and draws 43 - 521.6 KB, nearly
 * ten times as much, on the axis this file exists to look at, while still
 * carrying 82 percent of the busiest day's stories. A drawing is also the only
 * thing on a story that costs a second request.
 *
 * Ties break on the served payload's own byte size, then on the newest date.
 * Both are read off the filesystem, so choosing the day costs no parsing.
 *
 * Never a date written here. A hardcoded one is a check that stops meaning
 * anything on the next publish, and quietly.
 */
const DAY = [...SERVED_DATES].sort(
	(a, b) => drawingFiles(b) - drawingFiles(a) || servedBytes(b) - servedBytes(a) || b.localeCompare(a)
)[0];

const [YEAR, MONTH, DATE] = DAY.split('-');
const SERVED = JSON.parse(
	readFileSync(join(BUILT, YEAR, MONTH, DATE, 'digest.json'), 'utf8')
) as DigestDay;

/** The day in the order the page draws it, which is newest first and not the
 * desk-blocked order the payload publishes. */
const ITEMS: DigestItem[] = orderByTime(SERVED.items);
/** Every story that published a drawing. What the page must end up holding. */
const DRAWN = ITEMS.filter((item) => item.visual?.state === 'rendered' && item.visual.path);
/** The last story of that order, whose own published address draws the day. */
const LAST = ITEMS[ITEMS.length - 1]?.item_id ?? '';
const SEED = shellSeedItems();

/** Every drawing the day publishes, as the bytes the page will hold. */
const MARKUP = DRAWN.map((item) =>
	readFileSync(join(FRONTEND, 'build', item.visual!.path as string), 'utf8')
);

/** One repaint rule in `ItemVisual.svelte`: what it aims at, and the token it
 * routes the paint to. */
interface Repaint {
	/** What a reader would call the thing. */
	part: string;
	/** The class the renderer puts on it, looked for in the drawing itself. */
	marker: string;
	/** What the stylesheet aims at, inside `main figure`. */
	selector: string;
	property: 'fill' | 'stroke';
	token: string;
}

const REPAINTS: Repaint[] = [
	{
		part: 'a bar',
		marker: 'mark-rect',
		selector: '.mark-rect > path',
		property: 'fill',
		token: '--chart-1'
	},
	{
		part: 'an axis label',
		marker: 'mark-text',
		selector: '.mark-text text',
		property: 'fill',
		token: '--color-text-secondary'
	},
	{
		part: 'an axis line',
		marker: 'mark-rule',
		selector: '.mark-rule:not(.role-axis-grid) line',
		property: 'stroke',
		token: '--chart-axis'
	},
	{
		part: 'a grid line',
		marker: 'role-axis-grid',
		selector: '.role-axis-grid line',
		property: 'stroke',
		token: '--chart-grid'
	}
];

/** How many of the day's drawings carry each part.
 *
 * Read off the committed drawings, never off a locator count. A check that
 * decides what to assert from what it finds on the page switches itself off the
 * day a class is renamed, reports green, and says nothing - the trap
 * `docs/how-to/run-the-gates.md` records for skip conditions, and the same trap
 * whether the guard is a skip or a branch.
 *
 * It is also the fact that stopped this file asserting the canary's shape
 * against a published day. Measured 2026-09-05 over all 351 drawings the 15
 * committed days publish: every one carries a bar, an axis label and an axis
 * line, and not one carries a grid line. The canary chart does carry one, so
 * `item-visual.spec.ts` exercises the `--chart-grid` rule and no published page
 * ever has.
 */
const DRAWINGS_WITH = new Map<string, number>(
	REPAINTS.map((rule) => [
		rule.marker,
		MARKUP.filter((drawing) => drawing.includes(rule.marker)).length
	])
);
const CENSUS = REPAINTS.map(
	(rule) => `${rule.part} in ${DRAWINGS_WITH.get(rule.marker)}`
).join(', ');

/** A phone and a desktop. The plan names these two widths; the three-width walk
 * over every route is `reading-page.spec.ts`, and repeating it here would cost
 * a third render of a six-hundred-story day to learn nothing new. */
const WIDTHS = [390, 1440];
/** Dark is the base and light is the override. Both are driven on one loaded
 * page: a theme change repaints, it does not navigate, so the day is fetched
 * and scrolled once and read twice. */
const THEMES = ['dark', 'light'] as const;

/** What the document computes for a token, read the way the page reads it.
 *
 * `background-color` rather than `fill` because every element has one, so the
 * probe needs no shape and no namespace - and both properties resolve the same
 * custom property through the same cascade.
 */
function tokenColour(page: Page, token: string): Promise<string> {
	return page.evaluate((name) => {
		const probe = document.createElement('div');
		probe.style.backgroundColor = `var(${name})`;
		document.body.append(probe);
		const painted = getComputedStyle(probe).backgroundColor;
		probe.remove();
		return painted;
	}, token);
}

/** Every value the page painted a drawn part with, for one CSS property. */
function painted(page: Page, selector: string, property: 'fill' | 'stroke'): Promise<string[]> {
	return page.evaluate(
		({ selector: query, property: name }) =>
			[...document.querySelectorAll(`main figure ${query}`)].map((node) =>
				getComputedStyle(node).getPropertyValue(name)
			),
		{ selector, property }
	);
}

async function wearing(page: Page, theme: string): Promise<void> {
	await page.evaluate(
		(chosen) => document.documentElement.setAttribute('data-theme', chosen),
		theme
	);
	// A locator assertion rather than a polled evaluate: an evaluate under a poll
	// loses its execution context to the client router's own first navigation.
	await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
}

/** Everything a visit did wrong, collected on the page rather than per step. */
interface Faults {
	/** Our own code throwing, or logging an error of its own. */
	errors: string[];
	/** The browser's own line for a request that came back an error. Kept apart
	 * because it is the network reporting itself rather than the page failing,
	 * and the two lists below already name every bad request. */
	network: string[];
	failed: string[];
	notOk: string[];
}

function watch(page: Page): Faults {
	const found: Faults = { errors: [], failed: [], notOk: [], network: [] };
	page.on('console', (message) => {
		if (message.type() !== 'error') return;
		const text = message.text();
		if (text.includes('Failed to load resource') || text.includes('net::ERR_')) {
			found.network.push(text);
			return;
		}
		found.errors.push(text);
	});
	page.on('pageerror', (error) => found.errors.push(String(error)));
	page.on('requestfailed', (request) => {
		const reason = request.failure()?.errorText ?? 'no reason given';
		// A document request the browser abandoned is one navigation superseded by
		// another, never a file the page could not get.
		if (request.resourceType() === 'document' && reason === 'net::ERR_ABORTED') return;
		found.failed.push(`${request.url()} (${reason})`);
	});
	page.on('response', (response) => {
		if (response.status() >= 400) found.notOk.push(`${response.status()} ${response.url()}`);
	});
	return found;
}

/** Walk the page down one screen at a time, so no lazy slot is flown past.
 *
 * The scroll height grows as drawings land, so the end of the walk is re-read on
 * every step rather than measured once at the top.
 */
async function stepDown(page: Page): Promise<number> {
	return page.evaluate(async () => {
		const settle = () =>
			new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
		const step = Math.max(window.innerHeight, 1);
		window.scrollTo(0, 0);
		await settle();
		let at = 0;
		let steps = 0;
		// A bound rather than `while (true)`: a page whose height grows faster than
		// the walk climbs would otherwise never end, and a hung arm says nothing.
		while (at < document.documentElement.scrollHeight && steps < 2000) {
			at += step;
			steps += 1;
			window.scrollTo(0, at);
			await settle();
		}
		window.scrollTo(0, 0);
		await settle();
		return steps;
	});
}

/** Open the heaviest day with its whole stream drawn, and wait for it to settle. */
async function openTheWholeDay(page: Page, width: number): Promise<void> {
	await page.setViewportSize({ width, height: 900 });
	await page.goto(`/${DAY}/#${LAST}`);
	await expect(
		page.locator('[data-payload-state]'),
		`${DAY} never finished arriving, so the page a reader is left with is a seed`
	).toHaveAttribute('data-payload-state', 'ready');
	await expect(
		page.locator('article.item'),
		`the page drew a different number of stories than the ${ITEMS.length} ${DAY} published`
	).toHaveCount(ITEMS.length);
}

test.describe('what the day has to be for any of this to mean anything', () => {
	test('the day is longer than the seed and draws more than one thing', () => {
		// Without these two facts every arm below is vacuous: a day inside the seed
		// never fetches, and a day with one drawing is a per-visual check wearing a
		// page-level name.
		expect(
			ITEMS.length,
			`${DAY} published ${ITEMS.length} stories against a seed of ${SEED}, so nothing is fetched`
		).toBeGreaterThan(SEED);
		expect(DRAWN.length, `${DAY} draws ${DRAWN.length} visuals`).toBeGreaterThan(1);
		expect(LAST, 'the day has no last story to address').not.toBe('');
		// The load-time guard restated where a reader of the test list can see it.
		// The canary tree served 20 days of fixtures when this was written, so a
		// count on its own says nothing - it is the day SET that has to match.
		expect(
			SERVED_DATES,
			'the tree under test does not serve the days this repository committed'
		).toEqual(publishedDates(COMMITTED));
	});

	test('every drawing the day publishes is its own drawing', () => {
		// The wall a per-visual oracle cannot see. Forty-three figures that are one
		// figure repeated is a page that reads as broken, and every one of them
		// passes a check that looks at one.
		const distinct = new Set(MARKUP).size;
		expect(
			distinct,
			`${DAY} draws ${DRAWN.length} visuals and only ${distinct} of them differ`
		).toBe(DRAWN.length);
	});

	test('the day draws something every repaint rule can be checked against', () => {
		// Without a bar there is no colour oracle at all, because the bar is the one
		// part a chart cannot be drawn without. The rest of the census is printed
		// rather than demanded: a rule with no published reader is a fact about the
		// renderer, not a failure of the page.
		expect(
			DRAWINGS_WITH.get('mark-rect'),
			`${DAY} draws ${DRAWN.length} visuals and none of them is a chart: ${CENSUS}`
		).toBeGreaterThan(0);
	});
});

for (const width of WIDTHS) {
	test.describe(`the whole day at ${width}px`, () => {
		test(`draws every story and every drawing, errors nothing, and scrolls sideways nowhere`, async ({
			page
		}) => {
			const faults = watch(page);
			const asked: string[] = [];
			page.on('request', (request) => {
				if (request.url().endsWith('.svg')) asked.push(request.url());
			});

			await openTheWholeDay(page, width);
			const steps = await stepDown(page);

			// Every drawing the day published, in the document. A story whose picture
			// never came is a shorter story and nothing on the page says so, which is
			// exactly the failure a per-story check cannot report.
			await expect(
				page.locator('main figure svg'),
				`${DAY} publishes ${DRAWN.length} drawings and the page drew fewer, after ` +
					`${steps} screens of scrolling`
			).toHaveCount(DRAWN.length);

			// And the lazy half of that count is not zero. Everything past the seed
			// arrives by fetch, so a run that asked for nothing has proved that a
			// prerendered document renders, which it would have done anyway.
			expect(
				asked.length,
				`no drawing was fetched over ${steps} screens, so the lazy path proved nothing`
			).toBeGreaterThan(0);

			const shape = await page.evaluate(() => ({
				figures: document.querySelectorAll('main figure').length,
				svgs: document.querySelectorAll('main figure svg').length,
				images: document.querySelectorAll('main img').length,
				stories: document.querySelectorAll('article.item').length,
				height: document.documentElement.scrollHeight
			}));
			expect(
				shape.figures,
				'a figure on the page holds no drawing or more than one'
			).toBe(shape.svgs);
			expect(
				shape.images,
				'a story on this day is still on the image carrier, which cannot read the page'
			).toBe(0);

			// The page has to hold still in both themes at this width. A theme change
			// repaints and does not navigate, so this costs a repaint rather than a
			// second six-hundred-story render.
			for (const theme of THEMES) {
				await wearing(page, theme);
				const measured = await page.evaluate(() => {
					const root = document.documentElement;
					const limit = root.clientWidth;
					const over = [...document.querySelectorAll('main *')]
						.map((el) => ({ el, box: el.getBoundingClientRect() }))
						.filter(({ box }) => box.right + window.scrollX > limit + 0.5)
						.map(
							({ el, box }) =>
								`${el.tagName.toLowerCase()}.${String(el.getAttribute('class') ?? '')
									.split(' ')
									.slice(0, 2)
									.join('.')} ends at ${Math.round(box.right + window.scrollX)}`
						);
					return { scrollWidth: root.scrollWidth, clientWidth: limit, over: over.slice(0, 4) };
				});
				expect(
					measured.scrollWidth,
					`${theme} at ${width}px scrolls sideways by ` +
						`${measured.scrollWidth - measured.clientWidth}px on a ${shape.stories}-story ` +
						`day: ${measured.over.join('; ')}`
				).toBeLessThanOrEqual(measured.clientWidth);
			}

			expect(
				faults.errors,
				`${width}px: the ${ITEMS.length}-story day of ${DAY} logged an error:\n` +
					faults.errors.join('\n')
			).toEqual([]);
			expect(
				faults.failed,
				`${width}px: something on ${DAY} was asked for and never arrived:\n` +
					faults.failed.join('\n')
			).toEqual([]);
			expect(
				faults.notOk,
				`${width}px: something on ${DAY} was answered with an error status:\n` +
					faults.notOk.join('\n')
			).toEqual([]);
			expect(
				faults.network,
				`${width}px: the browser reported a request that failed:\n` + faults.network.join('\n')
			).toEqual([]);
		});

		test('every drawing on the page takes its colours from a token, in both themes', async ({
			page
		}) => {
			await openTheWholeDay(page, width);
			await stepDown(page);
			await expect(page.locator('main figure svg')).toHaveCount(DRAWN.length);

			const seen: Record<string, string> = {};
			for (const theme of THEMES) {
				await wearing(page, theme);
				const values: string[] = [];

				for (const rule of REPAINTS) {
					const token = await tokenColour(page, rule.token);
					values.push(token);
					const drawn = await painted(page, rule.selector, rule.property);
					const carried = DRAWINGS_WITH.get(rule.marker) ?? 0;

					if (carried === 0) {
						// The day publishes none of these, so the page must draw none. The
						// day's own drawings decide that, never the page - a branch taken on
						// what the page happens to hold is a check that turns itself off.
						expect(
							drawn.length,
							`${theme} at ${width}px: no drawing of ${DAY} carries ${rule.part}, and the ` +
								`page drew ${drawn.length} anyway. The census is ${CENSUS}`
						).toBe(0);
						continue;
					}

					expect(
						drawn.length,
						`${theme} at ${width}px: ${carried} drawings of ${DAY} carry ${rule.part} and ` +
							`the page drew none`
					).toBeGreaterThan(0);
					const wrong = drawn.filter((value) => value !== token);
					expect(
						wrong.length,
						`${theme} at ${width}px: ${wrong.length} of ${drawn.length} - ${rule.part} - ` +
							`kept a baked colour, the first being ${wrong[0]} where the page paints ` +
							`${token} for ${rule.token}`
					).toBe(0);
				}

				// The drawing that is not a chart paints itself in `currentColor`, which
				// inside an image could only ever have resolved to black.
				const ink = await tokenColour(page, '--color-text');
				values.push(ink);
				const inks = await page.evaluate(() =>
					[...document.querySelectorAll('main figure svg')].map(
						(node) => getComputedStyle(node).color
					)
				);
				const wrongInks = inks.filter((value) => value !== ink);
				expect(
					wrongInks.length,
					`${theme} at ${width}px: ${wrongInks.length} of ${inks.length} drawings are not ` +
						`inheriting the page ink`
				).toBe(0);

				seen[theme] = values.join('|');
			}

			// The half no fixed hex can pass. If the five tokens read the same in both
			// themes, every equality above is satisfied by a baked colour and this
			// file has been measuring the stylesheet against itself.
			expect(
				seen.light,
				'the two themes paint the drawing the same, so a baked colour would pass every arm above'
			).not.toBe(seen.dark);
		});
	});
}
