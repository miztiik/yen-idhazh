import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

/**
 * The footer is its links, and the page carries nothing a later run can change.
 *
 * Two of its six August blocks were about today's run - the run number and
 * time, and how many stories did not finish. Those moved to the day notice and
 * these tests still count them there. Three more went in September and did not
 * move anywhere: the commit and build date, and the promise about what is
 * deleted, which was read off the newest day. The footer is on every page, so
 * each of the three rewrote the bytes of every page on the site whenever
 * anything published or anyone built.
 *
 * So this file now proves two things at once. The facts that moved are counted
 * exactly once in their new home. The facts that went are counted at zero, and
 * the root layout is held to handing every page nothing that comes from a day.
 */

const BUILD = resolve(process.cwd(), 'build');
const COMPONENTS = resolve(process.cwd(), 'src', 'lib', 'components');

/** The prerendered document, read as raw text.
 *
 * `/404` is `404.html` at the root, because that is the file GitHub Pages
 * serves. Every other route is a directory with an `index.html` in it.
 */
function documentFor(route: string): string {
	const path =
		route === '/404'
			? join(BUILD, '404.html')
			: join(BUILD, ...route.split('/').filter(Boolean), 'index.html');
	return readFileSync(path, 'utf8');
}

/** Just the footer element.
 *
 * A fact can appear elsewhere on a page for its own reasons - `/archive/`
 * states the retention promise in its own header - so a count over the whole
 * document would be counting two different sentences as one.
 */
function footerOf(html: string): string {
	const open = html.indexOf('<footer');
	const close = html.indexOf('</footer>', open);
	expect(open, 'no footer in the document').toBeGreaterThan(-1);
	expect(close, 'the footer never closes').toBeGreaterThan(open);
	return html.slice(open, close);
}

function occurrences(haystack: string, pattern: RegExp): number {
	const flags = pattern.flags.includes('g') ? pattern.flags : `${pattern.flags}g`;
	return haystack.match(new RegExp(pattern.source, flags))?.length ?? 0;
}

/** The routes named by the row, minus the one that has no footer to check. */
const FOOTER_ROUTES = ['/', '/archive/', '/evals/'];

/** The routes with a footer and no day on them. */
const NO_DAY = ['/archive/', '/evals/'];

/** What every page with a footer still states. */
const FOOTER_FACTS: Array<[string, RegExp]> = [
	['the archive link', /href="[^"]*\/archive\/"/],
	['the console link', /href="[^"]*\/console\/"/],
	['the source-code link', />\s*Source code\s*</]
];

/** What the footer stated until this row, and what no page states now.
 *
 * The retention promise is counted in the footer rather than in the document,
 * because `/archive/` states its own version in its own header - about the
 * archive a reader is looking at, and only on the page where deletion could
 * matter to them. Two different sentences would count as one over a whole page.
 */
const FOOTER_GONE: Array<[string, RegExp]> = [
	['the verification sentence', /Every summary is checked against the article it came from\./],
	['the git build line', /Built from git/],
	['the retention promise', /Nothing is deleted\.|Charts older than \d+ months? are deleted\./]
];

/** What the old footer stated about today's run, in its new wording. */
const DAY_FACTS: Array<[string, RegExp]> = [
	['the run stamp', /This page came from run \d+, at \d\d:\d\d UTC\./],
	['the did-not-finish count', /did not finish/],
	['the reason a story was skipped', /could not read enough of the page/]
];

test.describe('the one-line footer', () => {
	for (const route of FOOTER_ROUTES) {
		test(`${route} states every footer fact exactly once`, () => {
			const footer = footerOf(documentFor(route));

			for (const [name, pattern] of FOOTER_FACTS) {
				expect(occurrences(footer, pattern), `${name} on ${route}`).toBe(1);
			}
			for (const [name, pattern] of FOOTER_GONE) {
				expect(occurrences(footer, pattern), `${name} is back on ${route}`).toBe(0);
			}
		});
	}

	test('the footer is its links and nothing else', () => {
		const footer = footerOf(documentFor('/'));
		const nav = footer.indexOf('<nav');

		expect(nav, 'the nav is missing').toBeGreaterThan(-1);
		// One block and no second: one nav and no paragraph at all.
		expect(occurrences(footer, /<nav\b/)).toBe(1);
		expect(occurrences(footer, /<p\b/)).toBe(0);
	});

	test('no document carries the build stamp', () => {
		for (const route of [...FOOTER_ROUTES, '/404']) {
			const html = documentFor(route);

			expect(occurrences(html, /Built from git/), `the build line is on ${route}`).toBe(0);
			expect(occurrences(html, /deployed \d{4}-\d\d-\d\d/), `a build date is on ${route}`).toBe(0);
		}
	});
});

test.describe('a document that renders no day carries none of the day', () => {
	for (const route of NO_DAY) {
		test(`${route} states nothing about today's run`, () => {
			const html = documentFor(route);

			for (const [name, pattern] of DAY_FACTS) {
				expect(occurrences(html, pattern), `${name} is still on ${route}`).toBe(0);
			}
			// The rendered sentences are only half of it. What the root layout
			// returns is inlined into the document, so a field the footer no
			// longer reads costs these pages bytes until it stops travelling.
			expect(html, `${route} still inlines items_failed`).not.toContain('items_failed');
			expect(html, `${route} still inlines a run reference`).not.toContain('items_added');
		});
	}

	/**
	 * `/404` is the adapter's fallback shell and has never had a footer in it.
	 *
	 * Worth pinning rather than assuming: the row that removed these facts was
	 * written believing the day travelled here too, and it does not. Measured
	 * 2026-08-31 - the file is 4,351 bytes on both sides of the change.
	 */
	test('the 404 shell has no footer and never had the day', () => {
		const html = documentFor('/404');

		expect(html, 'the fallback grew a footer').not.toContain('<footer');
		expect(html).not.toContain('items_failed');
		for (const [name, pattern] of DAY_FACTS) {
			expect(occurrences(html, pattern), `${name} reached the 404 shell`).toBe(0);
		}
	});

	test('the day page keeps both moved facts, once each, in the notice', () => {
		const html = documentFor('/');
		const opens = html.indexOf('aria-label="About today"');
		const notice = html.slice(opens, html.indexOf('</section>', opens));

		expect(occurrences(notice, /This page came from run \d+, at \d\d:\d\d UTC\./)).toBe(1);
		expect(occurrences(footerOf(html), /run \d+/)).toBe(0);
	});
});

test.describe('what the layout hands every page', () => {
	test('the skipped-story reason is in the day notice and gone from the footer', () => {
		const notice = readFileSync(join(COMPONENTS, 'DayNotice.svelte'), 'utf8');
		const footer = readFileSync(join(COMPONENTS, 'SiteFooter.svelte'), 'utf8');

		// The canary day records no failure, so a canary build reaches this
		// sentence on no page. It is pinned at the source rather than not at all.
		expect(notice).toContain('could not read enough of the page to summarize');
		expect(notice).toContain('day.items_failed');
		expect(footer).not.toContain('could not read enough');
		expect(footer).not.toContain('items_failed');
	});

	/**
	 * The layout reads no day, and that is the whole row in one assertion.
	 *
	 * What a layout returns is inlined into every page beneath it, so one fact
	 * read off the newest day rewrites the bytes of every older page the next
	 * time a day publishes. The import is pinned rather than the field, because
	 * a field can be renamed and the cost comes from the read.
	 */
	test('the root layout reads no day and no build clock', () => {
		const layout = readFileSync(
			resolve(process.cwd(), 'src', 'routes', '+layout.server.ts'),
			'utf8'
		);

		expect(layout, 'the layout reads the published tree again').not.toContain('$lib/server/payload');
		expect(layout).not.toContain('new Date');
		for (const field of ['items_failed', 'lastRun', 'day.date', 'retention_window_months']) {
			expect(layout, `the layout still hands ${field} to every page`).not.toContain(field);
		}
	});

	test('nothing injects a commit or a build date any more', () => {
		const footer = readFileSync(join(COMPONENTS, 'SiteFooter.svelte'), 'utf8');
		const vite = readFileSync(resolve(process.cwd(), 'vite.config.ts'), 'utf8');
		const types = readFileSync(resolve(process.cwd(), 'src', 'app.d.ts'), 'utf8');

		for (const [name, source] of [
			['the footer', footer],
			['the vite config', vite],
			['the ambient types', types]
		] as Array<[string, string]>) {
			expect(source, `${name} still names __BUILD_COMMIT__`).not.toContain('__BUILD_COMMIT__');
			expect(source, `${name} still names __BUILD_DATE__`).not.toContain('__BUILD_DATE__');
		}
	});
});
