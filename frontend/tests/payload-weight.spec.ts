import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';

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

/** On every published item, and on nothing else this site serializes. The
 * trailing colon matters: it matches a day item's `key_points:` field but not
 * the config's `key_points_min` / `key_points_max`, which the console inlines
 * alongside the summary bands and which are not a day payload. */
const MARKER = 'key_points:';

const DATED = /^\/\d{4}-\d{2}-\d{2}(\/|$)/;

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

/** A page renders a day when it is the home page. A dated address is answered
 * by the fallback shell, which carries no day at all - the browser fetches
 * one. */
function rendersADay(route: string): boolean {
	return route === '/';
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
 * `/` is the one page that renders a day, and it renders the whole newest one -
 * so a build whose home page carries no marker has either lost the field name
 * or lost the day.
 */
test('the marker is found where a day is rendered', () => {
	const rendered = pages().filter((page) => rendersADay(page.route));

	expect(rendered.length, 'no home page in the build').toBeGreaterThan(0);
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
 * There is no reading document left to hold to a seed.
 *
 * **This was the guard prerendering used to give free.** Until 2026-09-01 the
 * rule above was the whole file, and a dated route was exempt from it because
 * it genuinely rendered its whole day; left exempt after the split it would have
 * gone on passing whatever a reading page inlined, which `layout.md` records as
 * a failure shape this repository has had twice. So a dated document was held to
 * its own seed instead. From 2026-09-09 there is no dated document: one shell
 * answers every dated address, so the sweep above covers everything a build
 * writes and the exemption it needed is gone with the pages it exempted.
 *
 * What is left to check is that it stays gone. A dated document reappearing is a
 * route that grew a `prerender = true` back, and it would look like nothing at
 * all - the pages would go on working and the build would go on costing six
 * documents a published day.
 *
 * `/` is deliberately still exempt from the sweep. It keeps the whole day inline
 * for ever: it is one document per build rather than one per published day, so
 * it contributes nothing to the cap problem, and it leaves one complete,
 * script-free digest on the site.
 */
test('no dated document is written at all', () => {
	const dated = pages().filter((page) => DATED.test(page.route));

	expect(
		dated.map((page) => page.route),
		'a build wrote a document for a dated address'
	).toEqual([]);
});
