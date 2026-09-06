/**
 * Row #16's oracle: the item's facts are in two places, and which place a fact
 * is in says what it is about.
 *
 * Above the title go the four a reader uses to decide whether to read at all.
 * Below the summary go the claims about the summary and the two things you can
 * do next. Two promises follow, and both fail silently.
 *
 * 1. **The eyebrow holds at most four child elements, at every width.** A line
 *    that holds four on a desktop and five on a phone because a chip wrapped in
 *    from somewhere else is the failure this exists to catch, so every width the
 *    project commits to is driven rather than the default one. The count is of
 *    ELEMENTS: an item that earned three lens chips still spends one slot,
 *    because they arrive inside one wrapper.
 * 2. **The confidence sentence, `Listen` and `Read the original` follow the
 *    summary in document order, on every item.** Printing "our summary leaves
 *    out figures from the opening" above a headline the reader has not read is a
 *    disclaimer on nothing. Document order rather than paint order, because the
 *    footer moves into a side column at the side-rail breakpoint and the promise
 *    is about the reading order rather than about the geometry.
 *
 * Every item, and the count is asserted rather than assumed. The day list pages
 * at twelve, so the run below opens the rest first and then checks that what is
 * on screen is the whole day the canary published.
 *
 * The third test is Node-only and holds decision 4: which kinds of source get
 * named on the item. It reads the rule rather than the corpus - the share of
 * labelled stories in the committed tree is a fact about the news, and it moved
 * without anybody changing a line.
 */

import { expect, test, type Page } from '@playwright/test';
import { readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { KIND_WORTH_SAYING, SOURCE_KINDS } from '../src/lib/bands';
import { loadDay } from '../src/lib/server/payload';

const HERE = dirname(fileURLToPath(import.meta.url));
/** The tree the preview server serves, so a route here is a route that exists. */
const BUILD = join(HERE, '..', 'build');
/** The tree that built it. `loadDay` reads the day the page rendered. */
const CANARY = resolve(HERE, '..', '..', 'backend', 'var', 'canary', 'digest');

/** Never a date written here: a hardcoded one passes on an empty page the
 * moment the fixture moves. */
const DAY = readdirSync(BUILD, { withFileTypes: true })
	.filter((entry) => entry.isDirectory() && /^\d{4}-\d{2}-\d{2}$/.test(entry.name))
	.map((entry) => entry.name)
	.sort()
	.at(-1) as string;

/** A phone, the gap between two breakpoints, and a wide desktop. The same three
 * `layout-overflow.spec.ts` drives; `frame.breakpoints_px` is [640, 1024, 1400],
 * and 801 is where a layout only ever tested at a breakpoint breaks. */
const WIDTHS = [360, 801, 1536];

/** The whole day is on the page, however many `Show N more` it took.
 *
 * The home page inlines the day and a dated route seeds it and fetches the rest,
 * so the poll is what makes this honest on both: an assertion taken before the
 * fetch lands checks the seed and reports a pass over stories it never saw.
 */
async function everyItem(page: Page, expected: number): Promise<void> {
	for (let guard = 0; guard <= expected; guard += 1) {
		const more = page.getByRole('button', { name: /^Show \d+ more$/ });
		if ((await more.count()) === 0) break;
		await more.first().click();
	}
	await expect
		.poll(() => page.locator('article.item').count(), {
			message: 'the page never showed the whole day'
		})
		.toBe(expected);
}

/** What every item on the page put where. One pass over the document, because a
 * per-item round trip on a day of several hundred items is minutes. */
async function placements(page: Page) {
	return page.evaluate(() => {
		return [...document.querySelectorAll('article.item')].map((item) => {
			const eyebrow = item.querySelector('[data-item-eyebrow]');
			const summary = item.querySelector('[data-item-summary]');
			const follows = (node: Element | null) =>
				node === null
					? null
					: Boolean(
							summary &&
								summary.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING
						);
			return {
				id: item.id,
				hasEyebrow: eyebrow !== null,
				hasSummary: summary !== null,
				eyebrowChildren: eyebrow ? eyebrow.children.length : -1,
				eyebrowText: eyebrow ? (eyebrow.textContent ?? '').replace(/\s+/g, ' ').trim() : '',
				// The chip carries the band and its reason; the article carries the
				// band too, and `querySelectorAll` on an element never returns it.
				confidence: follows(item.querySelector('[data-band]')),
				listen: follows(item.querySelector('button[aria-label*="aloud"]')),
				out: follows(item.querySelector('a[target="_blank"]'))
			};
		});
	});
}

test.describe('the item splits its facts above the title and below the summary', () => {
	for (const width of WIDTHS) {
		test(`${width}px: the eyebrow holds at most four elements and the footer follows the summary`, async ({
			page
		}) => {
			const published = loadDay(DAY, CANARY)?.items.length ?? 0;
			expect(published, `the canary tree published nothing on ${DAY}`).toBeGreaterThan(0);

			await page.setViewportSize({ width, height: 900 });
			await page.goto(`/${DAY}/`);
			await everyItem(page, published);

			const seen = await placements(page);
			expect(seen.length, `no item rendered at ${width}px`).toBe(published);

			for (const item of seen) {
				expect(item.hasEyebrow, `${item.id} has no eyebrow at ${width}px`).toBe(true);
				expect(item.hasSummary, `${item.id} has no summary at ${width}px`).toBe(true);
				// The cap, and the whole reason this file exists.
				expect(
					item.eyebrowChildren,
					`${item.id} put ${item.eyebrowChildren} elements above the title at ${width}px: ` +
						`"${item.eyebrowText}"`
				).toBeLessThanOrEqual(4);
				// An empty line would pass the cap and say nothing. Who is speaking
				// is the fact the line exists for.
				expect(item.eyebrowChildren, `${item.id} has an empty eyebrow`).toBeGreaterThan(0);
				expect(item.eyebrowText, `${item.id} names no source above the title`).not.toBe('');

				expect(item.out, `${item.id} puts its link to the source above the summary`).toBe(true);
				if (item.confidence !== null) {
					expect(
						item.confidence,
						`${item.id} puts the confidence sentence above the summary`
					).toBe(true);
				}
				if (item.listen !== null) {
					expect(item.listen, `${item.id} puts Listen above the summary`).toBe(true);
				}
			}

			// What the run actually covered, so a pass over a seed cannot be read
			// as a pass over a day.
			const withConfidence = seen.filter((item) => item.confidence !== null).length;
			const withListen = seen.filter((item) => item.listen !== null).length;
			console.log(
				`${width}px: ${seen.length} items, ${withConfidence} carrying a confidence ` +
					`sentence, ${withListen} carrying Listen`
			);
		});
	}

	test('the home page splits the same way, with the whole day inline', async ({ page }) => {
		// A different loader and a different document: the home page carries the
		// day rather than seeding it. The split is a property of the item, so it
		// has to hold on both or it is a property of one route's data.
		const published = loadDay(DAY, CANARY)?.items.length ?? 0;
		await page.setViewportSize({ width: 1280, height: 900 });
		await page.goto('/');
		await everyItem(page, published);

		const seen = await placements(page);
		expect(seen.length).toBe(published);
		for (const item of seen) {
			expect(item.eyebrowChildren, `${item.id} above the title`).toBeLessThanOrEqual(4);
			expect(item.out, `${item.id} link to the source`).toBe(true);
		}
	});
});

test.describe('the item names the speaker only where the speaker has a stake', () => {
	test('four kinds, each with copy, and never the one that is most of the tree', () => {
		// Decision 4 of row #16. `government` is a ministry announcing its own
		// policy and `research` is a paper nobody has reviewed - both a speaker
		// with something to gain, both arriving in a reporter's typeface until
		// 2026-09-01.
		//
		// Excluding `reporting` is the whole lever, and it is checked here rather
		// than by measuring the share of labelled stories in the committed tree.
		// That share moves when the news moves, so it went red on a day that
		// arrived rather than on a change that broke, and it read every published
		// day to say so (`CLAUDE.md` Rule #12).
		expect([...KIND_WORTH_SAYING].sort()).toEqual([
			'announcement',
			'community',
			'government',
			'research'
		]);
		for (const kind of KIND_WORTH_SAYING) {
			expect(SOURCE_KINDS[kind], `${kind} has no copy to print`).toBeTruthy();
		}
		expect(KIND_WORTH_SAYING, 'labelling reporting would label most of the page').not.toContain(
			'reporting'
		);
	});
});
