import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';

/**
 * No page carries a day it does not render.
 *
 * The root layout used to return the whole latest day, and whatever a layout
 * load returns is inlined into every prerendered page beneath it. A reader
 * opening the console downloaded a day of article summaries to look at a chart:
 * 406.3 KB gzipped where 93.0 KB is the chart, and 315.6 KB against 2.4 KB on
 * `/evals/`, which draws no data at all. Measured 2026-08-26 over five
 * published days.
 *
 * Counted rather than compared against a second build. A marker count is the
 * same number whatever the published history holds, so the check does not move
 * when the pipeline publishes, and it costs one pass over bytes already on
 * disk.
 *
 * Runs in Node rather than in a page, like the arithmetic tests in
 * `frame.spec.ts`. It reads the build the preview server is about to serve.
 */

const BUILD = resolve(process.cwd(), 'build');

/** On every published item, and on nothing else this site serializes. */
const MARKER = 'key_points';

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

/** A page renders a day when it is the home page or a dated route. */
function rendersADay(route: string): boolean {
	return route === '/' || DATED.test(route);
}

test('no page inlines a day it does not render', () => {
	const carriers = pages()
		.filter((page) => !rendersADay(page.route) && page.route !== '/archive/')
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
 * `/archive/` is the one page excluded above, and it is excluded because it
 * inlines every committed day on purpose: the on-device search reads the
 * vectors out of those payloads without a request. Rebuilding that surface is
 * its own plan.
 *
 * Asserted rather than commented so the exclusion cannot outlive its reason. On
 * the day the archive stops inlining payloads this test fails, and the fix is
 * to delete the exclusion in the first test and this test with it.
 */
test('the archive exclusion still has a reason', () => {
	const archive = pages().find((page) => page.route === '/archive/');

	expect(archive, 'the build has no /archive/ page').toBeDefined();
	expect(
		archive?.markers ?? 0,
		'/archive/ no longer inlines day payloads - remove its exclusion above'
	).toBeGreaterThan(0);
});
