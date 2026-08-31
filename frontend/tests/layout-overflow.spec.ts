/**
 * Row #3's oracle: no reader-facing page scrolls sideways, at any width, in
 * either theme.
 *
 * `document.documentElement.scrollWidth <= document.documentElement.clientWidth`
 * is the whole check, and it is the only thing that gives the owner's
 * 2026-08-31 ruling a memory. A horizontal scrollbar on a reading surface is a
 * control that hides its own contents: it says nothing about how much is behind
 * it, it is invisible until a pointer arrives, and on a phone it competes with
 * the gesture that moves between pages.
 *
 * Measured on this suite's own build before the fix: `/archive/` reported 368px
 * of document inside a 360px viewport, in both themes. Every other route was
 * already clean, which is why this file is a gate rather than a fix list - the
 * next 8px arrives in a component nobody is looking at.
 *
 * Two things this file is deliberately not:
 *
 * - **Not the console.** A sibling plan holds those routes and five live
 *   defects there are recorded in that plan. `console-frame.spec.ts` already
 *   asserts the same property per element there.
 * - **Not `/404`.** That document is the adapter's fallback shell rather than a
 *   rendered route, and `vite preview` serves it as a plain file - so
 *   SvelteKit's data fetch for it 404s and hydration throws, which is a preview
 *   artefact and not a layout fact. It is measured by hand in the section 12
 *   smoke instead.
 */

import { expect, test } from '@playwright/test';
import { readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { splitPills } from '../src/lib/day-shape';
import type { DigestVerticalRef } from '../src/lib/payload/types';

/** The tree the preview server serves, so a route here is a route that exists. */
const BUILD = join(dirname(fileURLToPath(import.meta.url)), '..', 'build');

function subdirectories(at: string): string[] {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

/** The newest published day in the built tree. Never a date written here: a
 * hardcoded one passes on an empty page the moment the fixture moves. */
const DAY = subdirectories(BUILD).filter((name) => /^\d{4}-\d{2}-\d{2}$/.test(name)).at(-1) as string;

/** A topic of that day, taken from the tree rather than named. The canary day
 * publishes one vertical, and which one is the fixture's business. */
const TOPIC = subdirectories(join(BUILD, DAY)).at(0) as string;

/** Every reader-facing route kind the build emits. */
const ROUTES = ['/', `/${DAY}/`, `/${DAY}/${TOPIC}/`, '/archive/', '/evals/'];

/** A phone, the gap between two breakpoints, and a wide desktop.
 * `frame.breakpoints_px` is [640, 1024, 1400]; 801 is where a layout that was
 * only ever tested at a breakpoint breaks. */
const WIDTHS = [360, 801, 1536];

/** Dark is the base and light is the stored override, so both are driven. */
const THEMES = ['dark', 'light'] as const;

function ref(id: string, count: number): DigestVerticalRef {
	return { id, display_name: id.toUpperCase(), count };
}

test.describe('the topic row folds instead of scrolling', () => {
	const nine = [
		ref('ai', 40),
		ref('business-economy', 13),
		ref('energy', 8),
		ref('health', 2),
		ref('india', 6),
		ref('science', 3),
		ref('sport', 1),
		ref('tech', 21),
		ref('world', 14)
	];

	test('a row that fits keeps every pill and opens no control', () => {
		const split = splitPills(nine, null, 9);
		expect(split.shown).toEqual(nine);
		expect(split.folded).toEqual([]);
	});

	test('the topics that fold are the smallest ones, and the order never moves', () => {
		const split = splitPills(nine, null, 4);

		// The four biggest stay: ai 40, tech 21, world 14, business-economy 13.
		expect(split.shown.map((v) => v.id)).toEqual(['ai', 'business-economy', 'tech', 'world']);
		// And both halves read in the payload's order, not in size order - a topic
		// that moved between two days for a reason a reader cannot see is worse
		// than a topic that is one click further away.
		expect(split.folded.map((v) => v.id)).toEqual([
			'energy',
			'health',
			'india',
			'science',
			'sport'
		]);
		expect(split.shown.length + split.folded.length).toBe(nine.length);
	});

	test('the topic the reader is on is never the one that folds away', () => {
		// `sport` has one story, so the count alone would hide it - together with
		// the only mark on the page saying where the reader is.
		const split = splitPills(nine, 'sport', 4);
		expect(split.shown.map((v) => v.id)).toContain('sport');
		expect(split.folded.map((v) => v.id)).not.toContain('sport');
	});

	test('a cap of zero still leaves a row rather than an empty control', () => {
		// The contract floors this at 1, so zero is unreachable through config.
		// It is asserted anyway: the alternative is a page whose entire topic set
		// is behind one closed disclosure.
		const split = splitPills(nine, null, 0);
		expect(split.shown.length).toBe(1);
		expect(split.folded.length).toBe(nine.length - 1);
	});
});

test.describe('no reader-facing page scrolls sideways', () => {
	for (const theme of THEMES) {
		test(`${theme}: every route, at every width`, async ({ page }) => {
			await page.addInitScript(`localStorage.setItem('idhazh:theme', '${theme}')`);

			for (const route of ROUTES) {
				for (const width of WIDTHS) {
					await page.setViewportSize({ width, height: 900 });
					await page.goto(route);
					// A locator assertion rather than a polled `page.evaluate`: the
					// second one races the client router's own first navigation and
					// fails with `Execution context was destroyed` on a page that is
					// perfectly fine.
					await expect(page.locator('html')).toHaveAttribute('data-theme', theme);

					const measured = await page.evaluate(() => {
						const root = document.documentElement;
						const limit = root.clientWidth;
						const over = Array.from(document.querySelectorAll('*'))
							.map((el) => ({ el, box: el.getBoundingClientRect() }))
							.filter(({ box }) => box.right + window.scrollX > limit + 0.5)
							.map(
								({ el, box }) =>
									`${el.tagName.toLowerCase()}.${String(el.getAttribute('class') ?? '')
										.split(' ')
										.slice(0, 2)
										.join('.')} ends at ${Math.round(box.right + window.scrollX)}`
							);
						return {
							scrollWidth: root.scrollWidth,
							clientWidth: limit,
							// A blank page passes the oracle for free, so the oracle is
							// only worth running on a page that rendered.
							rendered: document.querySelectorAll('.frame *').length,
							over: over.slice(0, 4)
						};
					});

					expect(
						measured.rendered,
						`${theme} ${route} at ${width}px rendered nothing, so the check below proves nothing`
					).toBeGreaterThan(10);
					expect(
						measured.scrollWidth,
						`${theme} ${route} at ${width}px scrolls sideways by ` +
							`${measured.scrollWidth - measured.clientWidth}px: ${measured.over.join('; ')}`
					).toBeLessThanOrEqual(measured.clientWidth);
				}
			}
		});
	}
});
