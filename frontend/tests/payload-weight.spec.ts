import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import { leadingStories, shellSeedItems } from '../src/lib/server/config';

/**
 * No page carries a day it does not render, and no reading page carries a day
 * it no longer renders.
 *
 * The root layout used to return the whole latest day, and whatever a layout
 * load returns is inlined into every prerendered page beneath it. A reader
 * opening the console downloaded a day of article summaries to look at a chart:
 * 406.3 KB gzipped where 93.0 KB is the chart, and 315.6 KB against 2.4 KB on
 * `/evals/`, which draws no data at all. Measured 2026-08-26 over five
 * published days.
 *
 * **The second rule is the one this file exists for now.** A reading document
 * carried every story its day published until 2026-09-01. It carries a seed,
 * and the browser fetches the rest. Left as it was, the sweep below would have
 * stayed true whatever a reading page inlined, so the guard that used to be
 * free from prerendering is written out here instead: a dated document is held
 * to the seed it is allowed, counted rather than weighed.
 *
 * Counted rather than compared against a second build. A marker count is the
 * same number whatever the published history holds, so the check does not move
 * when the pipeline publishes, and it costs one pass over bytes already on
 * disk. It is also the only bound a day page can have: `config/idhazh.json`
 * gives no page ceiling to a route whose weight is whatever the day published,
 * because the only way under such a ceiling is to publish fewer stories.
 *
 * What a count of markers cannot see, `scripts/bundle-gate.mjs` bounds: it holds
 * the routes named in `config/idhazh.json` under a gzip ceiling. `/archive/`
 * joined them on 2026-08-27, at a ceiling 237 times under the weight it used to
 * carry, and `/console/` on 2026-08-29, at a ceiling carrying three published
 * days rather than a year because it grows about 60 gzipped bytes a published
 * item. So this count and that ceiling now both answer for `/console/`, and they
 * answer different questions: the count says no day payload is on the page, the
 * ceiling says the page has not grown past what somebody priced.
 *
 * `/archive/` was excluded from the rule below until 2026-08-27, because it
 * inlined every committed day so on-device search could read the vectors
 * without a request. Search reads the month index now, so the exclusion and the
 * test that guarded it are both gone and the archive answers the same rule as
 * every other page.
 *
 * Runs in Node rather than in a page, like the arithmetic tests in
 * `frame.spec.ts`. It reads the build the preview server is about to serve.
 */

const BUILD = resolve(process.cwd(), 'build');

/** On every published item, and on nothing else this site serializes. */
const MARKER = 'key_points';

const DATED = /^\/\d{4}-\d{2}-\d{2}(\/|$)/;
/** A topic route: a date and one desk under it. */
const TOPIC = /^\/\d{4}-\d{2}-\d{2}\/[^/]+\/$/;

interface Page {
	route: string;
	markers: number;
}

function htmlUnder(directory: string): string[] {
	let found: string[] = [];
	for (const name of readdirSync(directory)) {
		const path = join(directory, name);
		if (statSync(path).isDirectory()) {
			if (name === '_app') continue;
			found = found.concat(htmlUnder(path));
		} else if (name === 'index.html' || name === '404.html') {
			found.push(path);
		}
	}
	return found;
}

function pages(): Page[] {
	return htmlUnder(BUILD).map((path) => {
		const parts = relative(BUILD, path).split(sep);
		const route = path.endsWith('404.html') ? '/404' : `/${parts.slice(0, -1).join('/')}/`;
		const html = readFileSync(path, 'utf8');
		return { route: route.replace('//', '/'), markers: html.split(MARKER).length - 1 };
	});
}

/** A page renders a day when it is the home page or a dated route. */
function rendersADay(route: string): boolean {
	return route === '/' || DATED.test(route);
}

test('no page inlines a day it does not render', () => {
	const carriers = pages()
		.filter((page) => !rendersADay(page.route))
		.filter((page) => page.markers > 0)
		.map((page) => `${page.route} carries ${page.markers} items`);

	expect(
		carriers,
		'a page below the root layout is inlining a day payload again:\n' + carriers.join('\n')
	).toEqual([]);
});

/**
 * The negative case. Without it the assertion above passes the day someone
 * renames the field, and passes loudest when the site is empty.
 *
 * One page is enough, and asking for more would be wrong: a day that published
 * nothing still renders a day and still carries no item. The canary corpus has
 * nineteen such days.
 */
test('the marker is found where a day is rendered', () => {
	const rendered = pages().filter((page) => rendersADay(page.route));

	expect(rendered.length, 'no home page and no dated route in the build').toBeGreaterThan(0);
	expect(
		rendered.filter((page) => page.markers > 0).length,
		`no page carries "${MARKER}" - the marker is stale, not the payload`
	).toBeGreaterThan(0);
});

/**
 * The archive is the page this rule was written for, so it gets its own
 * assertion rather than being covered only by the sweep above. It carried every
 * committed day - 1.7 MB gzipped - to feed on-device search, and the whole
 * point of the month index is that it no longer has to.
 */
test('the archive carries no day payload at all', () => {
	const archive = pages().find((page) => page.route === '/archive/');

	expect(archive, 'the build has no /archive/ page').toBeDefined();
	expect(
		archive?.markers ?? 0,
		'/archive/ is inlining day payloads again - search reads the month index'
	).toBe(0);
});

/**
 * Every reading document carries a seed, not a day.
 *
 * A topic document keeps the head of its own desk. A day document keeps the
 * head of the day UNION every story its leading block points at, because a lead
 * is chosen across the whole day and a link into a document that holds only a
 * prefix lands on nothing. So the two bounds differ by the size of the leading
 * block, and both come from config rather than from a number written here
 * (Rule #6).
 *
 * **This is the guard prerendering used to give free.** Until 2026-09-01 the
 * rule above was the whole file, and a dated route was exempt from it because
 * it genuinely rendered its whole day. Left exempt after the split it would
 * have gone on passing whatever a reading page inlined, which `layout.md`
 * records as a failure shape this repository has had twice.
 *
 * `/` is deliberately not here. It keeps the whole day inline for ever: it is
 * one document per build rather than one per published day, so it contributes
 * nothing to the cap problem, and it leaves one complete, script-free digest on
 * the site.
 */
test('a reading document carries no more stories than its own seed', () => {
	const seed = shellSeedItems();
	const bounds = { topic: seed, day: seed + leadingStories() };
	const reading = pages().filter((page) => DATED.test(page.route));

	expect(reading.length, 'the build has no dated route, so this proves nothing').toBeGreaterThan(
		0
	);
	const over = reading
		.filter((page) => page.markers > (TOPIC.test(page.route) ? bounds.topic : bounds.day))
		.map(
			(page) =>
				`${page.route} carries ${page.markers}, over the ` +
				`${TOPIC.test(page.route) ? bounds.topic : bounds.day} it is allowed`
		);
	expect(
		over,
		`a reading document is inlining more than its seed - ${bounds.topic} stories on a ` +
			`topic route, ${bounds.day} on a day route:\n` +
			over.join('\n')
	).toEqual([]);
	expect(
		reading.filter((page) => page.markers > 0).length,
		'no reading document carries a story at all - the seed is empty, not small'
	).toBeGreaterThan(0);
});
