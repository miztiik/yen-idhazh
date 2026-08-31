import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

/**
 * The footer lost three of its six blocks and no fact left the site.
 *
 * Two of those blocks were about today's run - the run number and time, and
 * how many stories did not finish. The footer is on every page that has one, so
 * both were printed under `/archive/`, `/console/` and `/evals/`, which render
 * no day at all, and printed a second time under `/`, where the day notice was
 * already saying them.
 *
 * These tests are the relocation proof. Every sentence the old footer carried
 * is counted exactly once in its new home, and the documents that render no day
 * are read for any trace of the day's run - the sentences and the inlined
 * payload both.
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

/** What the old footer stated, and what every page with a footer still states. */
const FOOTER_FACTS: Array<[string, RegExp]> = [
	['the verification sentence', /Every summary is checked against the article it came from\./],
	['the git build line', /Built from git/],
	['the retention promise', /Nothing is deleted\.|Charts older than \d+ months? are deleted\./],
	['the archive link', /href="[^"]*\/archive\/"/],
	['the console link', /href="[^"]*\/console\/"/],
	['the source-code link', />\s*Source code\s*</]
];

/** What the old footer stated about today's run, in its new wording. */
const DAY_FACTS: Array<[string, RegExp]> = [
	['the run stamp', /This page came from run \d+, at \d\d:\d\d UTC\./],
	['the did-not-finish count', /did not finish/],
	['the reason a story was skipped', /could not read enough of the page/]
];

test.describe('the three-line footer', () => {
	for (const route of FOOTER_ROUTES) {
		test(`${route} states every footer fact exactly once`, () => {
			const footer = footerOf(documentFor(route));

			for (const [name, pattern] of FOOTER_FACTS) {
				expect(occurrences(footer, pattern), `${name} on ${route}`).toBe(1);
			}
		});
	}

	test('the footer is three blocks, in the order Susan ruled', () => {
		const footer = footerOf(documentFor('/'));
		const nav = footer.indexOf('<nav');
		const git = footer.search(/Built from git/);
		const check = footer.search(/Every summary is checked/);

		expect(nav, 'the nav is missing').toBeGreaterThan(-1);
		expect(git, 'the git line does not follow the nav').toBeGreaterThan(nav);
		expect(check, 'the verification sentence is not last').toBeGreaterThan(git);
		// Three blocks and no fourth: one nav plus two paragraphs.
		expect(occurrences(footer, /<nav\b/)).toBe(1);
		expect(occurrences(footer, /<p\b/)).toBe(2);
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

test.describe('the sentences moved rather than died', () => {
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

	test('the footer takes one field from the day and no more', () => {
		const layout = readFileSync(
			resolve(process.cwd(), 'src', 'routes', '+layout.server.ts'),
			'utf8'
		);

		expect(layout).toContain(
			'footer: day ? { retention_window_months: day.retention_window_months }'
		);
		for (const field of ['items_failed', 'lastRun', 'day.date']) {
			expect(layout, `the layout still hands ${field} to every page`).not.toContain(field);
		}
	});
});
