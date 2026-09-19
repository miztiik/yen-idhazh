/** The pairs a person marked apart, on a rendered page.
 *
 * The arithmetic is checked without a browser in `holdout.spec.ts`, and that is
 * where the violation state lives: the canary's own articles are eight
 * unrelated fixtures, so no pair of them scores anywhere near the merge line
 * and the worst state cannot be reached from this tree. What is left needs the
 * page: an axis that is the band whatever the data does, a rule at the line the
 * day was built with, a dot drawn where the arithmetic puts it rather than
 * where it would look tidy, a mark the day tree cannot answer for counted with
 * its reason, and a panel that keeps its box at every width.
 *
 * **`build_canary_day.py` writes four hand marks.** The day's own
 * highest-scoring pair marked apart, its lowest marked apart, a third marked as
 * one story, and one naming a date the tree holds no day for.
 */

import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

const ROUTE = '/console/judgement/';
const PANEL = '[data-holdout]';

function band(): { band_low: number; band_high: number } {
	// Read inside the test, never at module scope: a fixture opened while the
	// module loads fails before any test exists to own the failure.
	return JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8')).assemble.same_story
		.adaptive_dedup_threshold;
}

async function open(page: Page, width = 1440): Promise<void> {
	await page.setViewportSize({ width, height: 1400 });
	await page.goto(ROUTE);
	await page.waitForTimeout(700);
}

async function boxOf(page: Page): Promise<{ width: number; height: number }> {
	const box = await page.locator('[data-console-panel="The pairs a person marked apart"]').boundingBox();
	if (box === null) throw new Error('the holdout panel has no box');
	return { width: box.width, height: box.height };
}

test.describe('the pairs a person marked apart', () => {
	test('the panel draws its axis, its rule and its margin', async ({ page }) => {
		await open(page);

		await expect(page.locator(PANEL)).toBeVisible();
		await expect(page.locator(`${PANEL} [data-holdout-figure]`)).toBeVisible();
		await expect(page.locator(`${PANEL} [data-holdout-rule]`)).toHaveCount(1);
		await expect(page.locator(`${PANEL} [data-holdout-note]`)).toBeVisible();
		await expect(page.locator(`${PANEL} [data-holdout-weights]`)).toBeVisible();
	});

	test('the score axis holds the band whatever the data does', async ({ page }) => {
		// The domain is two knobs and never the marks. An axis fitted to four
		// fixture scores would redraw itself every time somebody marked a pair,
		// and two days of this panel would not be comparable.
		const knobs = band();
		for (const width of [1440, 390]) {
			await open(page, width);
			await expect(page.locator(`${PANEL}`)).toHaveAttribute(
				'data-holdout-domain',
				`${knobs.band_low},${knobs.band_high}`
			);
			const ticks = await page
				.locator(`${PANEL} [data-tick="x"]`)
				.evaluateAll((nodes) => nodes.map((node) => Number(node.textContent)));
			expect(ticks.length).toBeGreaterThan(1);
			expect(Math.min(...ticks)).toBeGreaterThanOrEqual(knobs.band_low);
			expect(Math.max(...ticks)).toBeLessThanOrEqual(knobs.band_high);
		}
	});

	test('the dot is drawn where the arithmetic puts it, not where it would look tidy', async ({
		page
	}) => {
		// THE BITE. The margin goes negative when the closest marked-apart pair
		// scores above the line, and the panel exists to say so. The dot has to sit
		// on the side of the rule its own score puts it, and the figure beside it
		// has to be the score rather than whatever the axis could fit.
		await open(page);

		const dot = page.locator(`${PANEL} [data-holdout-dot]`);
		await expect(dot).toHaveCount(1);
		const score = Number(await dot.getAttribute('data-holdout-dot'));
		const rule = page.locator(`${PANEL} [data-holdout-rule]`);
		const line = Number(await rule.getAttribute('data-holdout-rule'));

		const dotBox = await dot.boundingBox();
		const ruleBox = await rule.boundingBox();
		if (dotBox === null || ruleBox === null) throw new Error('the dot or the rule has no box');

		const dotAt = dotBox.x + dotBox.width / 2;
		const ruleAt = ruleBox.x + ruleBox.width / 2;
		expect(score > line).toBe(dotAt > ruleAt);

		// The label under the dot is the score, to four places, whether or not the
		// axis could reach it.
		const label = (await page.locator(`${PANEL} [data-holdout-dot-label]`).textContent()) ?? '';
		expect(Number(label)).toBeCloseTo(score, 4);

		// And it is inside the plot rather than half off the edge of it.
		const plot = await page.locator(`${PANEL} svg`).boundingBox();
		if (plot === null) throw new Error('the plot has no box');
		expect(dotAt).toBeGreaterThanOrEqual(plot.x);
		expect(dotAt).toBeLessThanOrEqual(plot.x + plot.width);
	});

	test('a mark that scores off the scale says it is pinned rather than pretending', async ({
		page
	}) => {
		// The axis is the span a fitted LINE may take, and a hand mark is not a
		// line: two articles about nothing in common score well under it. Pinning
		// the dot silently would draw a mark sitting at 0.88 that is nowhere near
		// it. The canary's closest call is exactly this case.
		await open(page);

		const knobs = band();
		const score = Number(
			await page.locator(`${PANEL} [data-holdout-dot]`).getAttribute('data-holdout-dot')
		);
		const pinned = page.locator(`${PANEL} [data-holdout-pinned]`);
		const outside = score < knobs.band_low || score > knobs.band_high;
		expect(await pinned.count()).toBe(outside ? 1 : 0);

		if (outside) {
			const said = (await page.locator(`${PANEL} [data-holdout-pinned-note]`).textContent()) ?? '';
			expect(said).toContain('off this scale');
			expect(said).toContain(score.toFixed(4));
		}
	});

	test('the state, the margin and the violation count agree with each other', async ({ page }) => {
		// The three attributes are one answer written three ways, and a panel whose
		// headline and sentence disagree is worse than one that says nothing.
		await open(page);

		const panel = page.locator(PANEL);
		const reading = await panel.getAttribute('data-holdout-state');
		const violations = Number(await panel.getAttribute('data-holdout-violations'));
		const note = (await page.locator(`${PANEL} [data-holdout-note]`).textContent()) ?? '';
		const figure = (await page.locator(`${PANEL} [data-holdout-figure]`).textContent()) ?? '';

		expect(reading === 'violation').toBe(violations > 0);
		expect(note.includes('BELOW')).toBe(violations > 0);
		// Whatever the state, the headline figure is a distance and carries no sign.
		expect(figure.trim()).not.toContain('-');
		expect(Number(figure)).toBeGreaterThanOrEqual(0);
		expect(Number(figure).toFixed(4)).toBe(await panel.getAttribute('data-holdout-margin'));
	});

	test('a mark the day tree cannot answer for is counted and not drawn', async ({ page }) => {
		// The canary marks one pair on a date it holds no day for. A blank dot
		// would say the margin is fine; the count says the mark could not be
		// checked, which is a different fact.
		await open(page);

		const skips = page.locator(`${PANEL} [data-holdout-skips]`);
		await expect(skips).toHaveCount(1);
		expect(Number(await skips.getAttribute('data-holdout-skips'))).toBeGreaterThan(0);
		expect(await skips.textContent()).toContain('could not be checked');

		// One dot, whatever the file holds. The panel draws the closest call and
		// lists the rest.
		await expect(page.locator(`${PANEL} [data-holdout-dot]`)).toHaveCount(1);
	});

	test('the weights the score was taken under are printed beside it', async ({ page }) => {
		// A score with no weights beside it is a number that rots quietly: a
		// reader who changes a weight has to see that the margin moved because
		// the ruler moved.
		await open(page);

		const weights = (await page.locator(`${PANEL} [data-holdout-weights]`).textContent()) ?? '';
		expect(weights).toContain('on the cosine');
		expect(weights).toContain('on the key points');
	});

	test('the panel names no ledger column', async ({ page }) => {
		// A column name is a fact about the file the ledger is stored in, and an
		// operator reading this page has never opened that file.
		await open(page);

		const words = (await page.locator(PANEL).textContent()) ?? '';
		for (const column of ['same_story', 'left_date', 'right_date', 'floor_min', 'applied']) {
			expect(words, `the panel names ${column}`).not.toContain(column);
		}
	});

	test('the panel keeps its box at every width the console draws at', async ({ page }) => {
		// A panel that shrinks to one sentence on a quiet day is a panel an
		// operator stops opening, and one that changes height between two reads
		// of the same build is a layout shift.
		await open(page, 1440);
		const wide = await boxOf(page);
		await open(page, 1440);
		expect(Math.abs((await boxOf(page)).height - wide.height)).toBeLessThanOrEqual(1);

		await open(page, 390);
		const narrow = await boxOf(page);
		expect(narrow.height).toBeGreaterThan(0);
		expect(narrow.width).toBeLessThan(wide.width);
	});
});
