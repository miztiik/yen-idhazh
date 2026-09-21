/** The pairs a person marked apart, on a rendered page.
 *
 * The arithmetic is checked without a browser in `holdout.spec.ts` and the
 * scale under it in `holdout-domain.spec.ts`. That is where the violation state
 * lives: the canary's own articles are eight unrelated fixtures, so no pair of
 * them scores anywhere near the merge line and the worst state cannot be
 * reached from this tree. What is left needs the page: an axis that is the line
 * and one day's legal fall whatever the data does, a tinted zone one day deep
 * below the rule, marks drawn where the arithmetic puts them rather than where
 * they would look tidy, a mark the day tree cannot answer for counted with its
 * reason, and a panel that keeps its box at every width.
 *
 * **Nothing has ever scored this tree's line against its marks**, because a
 * person types the verb that writes that row and the canary build has no
 * committed one. So this file owns the absent case; the four cells themselves
 * are checked in `backend/tests/test_merge_line_holdout.py`, where a reading can
 * be produced.
 *
 * **`build_canary_day.py` writes four hand marks.** The day's own
 * highest-scoring pair marked apart, its lowest marked apart, a third marked as
 * one story, and one naming a date the tree holds no day for. All three scored
 * marks land far under the merge line, so this tree is also the off-scale case
 * and every drawing here has to survive having nothing on the axis.
 */

import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

const ROUTE = '/console/judgement/';
const PANEL = '[data-holdout]';

function knobs(): { applied: number; maxDownStep: number; bandLow: number; bandHigh: number } {
	// Read inside the test, never at module scope: a fixture opened while the
	// module loads fails before any test exists to own the failure.
	const block = JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8')).assemble
		.same_story;
	const threshold = block.adaptive_dedup_threshold;
	// The committed config leaves `bin_width` unset, so the contract's own default
	// stands in for it - the same fallback `similarity-ledger.ts` uses.
	return {
		applied: block.floor_min,
		maxDownStep: threshold.max_down_bins * (threshold.bin_width ?? 0.001),
		bandLow: threshold.band_low,
		bandHigh: threshold.band_high
	};
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
	test('the panel draws its axis, its rule, its zone and its margin', async ({ page }) => {
		await open(page);

		await expect(page.locator(PANEL)).toBeVisible();
		await expect(page.locator(`${PANEL} [data-holdout-figure]`)).toBeVisible();
		await expect(page.locator(`${PANEL} [data-holdout-rule]`)).toHaveCount(1);
		await expect(page.locator(`${PANEL} [data-holdout-zone-mark]`)).toHaveCount(1);
		await expect(page.locator(`${PANEL} [data-holdout-note]`)).toBeVisible();
		await expect(page.locator(`${PANEL} [data-holdout-weights]`)).toBeVisible();
	});

	test('the score axis is the line and one day of legal fall, never the band', async ({ page }) => {
		// The domain is the line and one knob, never the marks: an axis fitted to
		// four fixture scores would redraw itself every time somebody marked a
		// pair, and two days of this panel would not be comparable. The band is
		// already the axis of `Where the merge line sits` further up the route,
		// and on it this panel's margin drew at half a percent of the plot.
		const { applied, maxDownStep, bandLow, bandHigh } = knobs();
		for (const width of [1440, 390]) {
			await open(page, width);
			const domain = ((await page.locator(PANEL).getAttribute('data-holdout-domain')) ?? '')
				.split(',')
				.map(Number);

			expect(domain[0]).toBeCloseTo(applied - 2 * maxDownStep, 6);
			expect(domain[1]).toBeCloseTo(applied + maxDownStep, 6);
			expect(domain[0]).toBeGreaterThan(bandLow);
			expect(domain[1]).toBeLessThan(bandHigh);

			const ticks = await page
				.locator(`${PANEL} [data-tick="x"]`)
				.evaluateAll((nodes) => nodes.map((node) => Number(node.textContent)));
			expect(ticks.length).toBeGreaterThan(1);
			expect(Math.min(...ticks)).toBeGreaterThanOrEqual(domain[0]);
			expect(Math.max(...ticks)).toBeLessThanOrEqual(domain[1]);
		}
	});

	test('the zone runs one day of legal fall DOWN from the rule and no further', async ({
		page
	}) => {
		// THE BITE. The clamp caps both directions, but only a fall folds a pair
		// the line refuses today, so a zone drawn either side of the line would
		// tint scores tomorrow cannot reach. Its right edge is the rule and its
		// width is the step, measured in pixels off the rendered plot rather than
		// trusted from the attribute.
		await open(page);

		const { applied, maxDownStep } = knobs();
		const zone = ((await page.locator(PANEL).getAttribute('data-holdout-zone')) ?? '')
			.split(',')
			.map(Number);
		expect(zone[1]).toBeCloseTo(applied, 6);
		expect(zone[0]).toBeCloseTo(applied - maxDownStep, 6);

		const zoneBox = await page.locator(`${PANEL} [data-holdout-zone-mark]`).boundingBox();
		const ruleBox = await page.locator(`${PANEL} [data-holdout-rule]`).boundingBox();
		const plot = await page.locator(`${PANEL} svg`).boundingBox();
		if (zoneBox === null || ruleBox === null || plot === null) {
			throw new Error('the zone, the rule or the plot has no box');
		}

		// The zone ends at the rule, within a pixel, and starts to the left of it.
		expect(Math.abs(zoneBox.x + zoneBox.width - (ruleBox.x + ruleBox.width / 2))).toBeLessThan(2);
		expect(zoneBox.x).toBeLessThan(ruleBox.x);
		// And it is a third of the axis, because the axis is three of these steps.
		expect(zoneBox.width / plot.width).toBeGreaterThan(0.25);
	});

	test('the margin is drawn wide enough for the dot to clear the rule', async ({ page }) => {
		// THE BITE, and the finding that failed review. With the band as the axis
		// the committed margin drew at 5.8 px, a dot is 13 px across, and the dot
		// sat on top of the rule - so a reader could not tell which side of the
		// line the closest call was on. Every drawn dot has to clear the rule by
		// its own radius, or the panel cannot answer the one question it is for.
		await open(page);

		const rule = page.locator(`${PANEL} [data-holdout-rule]`);
		const ruleBox = await rule.boundingBox();
		if (ruleBox === null) throw new Error('the rule has no box');
		const ruleAt = ruleBox.x + ruleBox.width / 2;
		const line = Number(await rule.getAttribute('data-holdout-rule'));

		const dots = page.locator(`${PANEL} [data-holdout-dot]`);
		for (let index = 0; index < (await dots.count()); index += 1) {
			const dot = dots.nth(index);
			const score = Number(await dot.getAttribute('data-holdout-dot'));
			const dotBox = await dot.boundingBox();
			if (dotBox === null) throw new Error(`the dot at ${score} has no box`);

			// Drawn on the side of the rule its own score puts it.
			expect(score > line).toBe(dotBox.x + dotBox.width / 2 > ruleAt);
			// And not overlapping it. A dot covering the rule is the defect.
			const clear = score > line ? dotBox.x - ruleAt : ruleAt - (dotBox.x + dotBox.width);
			expect(clear, `the dot at ${score} overlaps the rule`).toBeGreaterThan(0);
		}
	});

	test('every mark is on the plot, labelled or titled, and none is invented', async ({ page }) => {
		// Four marks in the committed file and three scored ones in the canary. A
		// mark off the scale is counted at the edge it left, never pinned to a
		// place it is not - a dot sitting at the axis floor would say a pair scores
		// there when it does not.
		await open(page);

		const domain = ((await page.locator(PANEL).getAttribute('data-holdout-domain')) ?? '')
			.split(',')
			.map(Number);
		const drawn = await page
			.locator(`${PANEL} [data-holdout-dot]`)
			.evaluateAll((nodes) => nodes.map((node) => Number(node.getAttribute('data-holdout-dot'))));
		for (const score of drawn) {
			expect(score).toBeGreaterThanOrEqual(domain[0]);
			expect(score).toBeLessThanOrEqual(domain[1]);
		}

		// The rows of the shut table are every marked-apart pair, drawn or not, so
		// the two counts together account for all of them.
		const rows = await page
			.locator(`${PANEL} [data-holdout-row]`)
			.evaluateAll((nodes) => nodes.map((node) => Number(node.getAttribute('data-holdout-row'))));
		const offScale = await page
			.locator(`${PANEL} [data-holdout-offscale-count]`)
			.evaluateAll((nodes) =>
				nodes.reduce((total, node) => total + Number(node.getAttribute('data-holdout-offscale-count')), 0)
			);
		expect(drawn.length + offScale).toBe(rows.length);

		// Whatever is off the scale is named with its score rather than left blank.
		if (offScale > 0) {
			const said = (await page.locator(`${PANEL} [data-holdout-offscale-note]`).first().textContent()) ?? '';
			expect(said).toContain('this scale');
			expect(said).toMatch(/0\.\d{4}/);
		}
	});

	test('the headline says what one more day costs, not just the distance', async ({ page }) => {
		// A distance says how much room there is and never how fast it can be
		// spent, and it can be spent in one night. The count is the whole reason
		// the margin is worth printing.
		await open(page);

		const { maxDownStep } = knobs();
		const said = (await page.locator(`${PANEL} [data-holdout-reach-note]`).textContent()) ?? '';
		expect(said).toContain(maxDownStep.toFixed(3));

		const reach = ((await page.locator(PANEL).getAttribute('data-holdout-reach')) ?? '')
			.split(',')
			.map(Number);
		// Today, tomorrow, the day after. The count can only rise as the line falls.
		expect(reach[1]).toBeGreaterThanOrEqual(reach[0]);
		expect(reach[2]).toBeGreaterThanOrEqual(reach[1]);
		expect(reach[0]).toBe(Number(await page.locator(PANEL).getAttribute('data-holdout-violations')));
	});

	test('the pairs read as one story are drawn too, with the ones below the line counted', async ({
		page
	}) => {
		// The line has two costs and the panel used to report one. A pair read as
		// ONE story scoring under the line is a story the reader sees twice, and
		// the strip is where that population is.
		await open(page);

		const agreed = page.locator(`${PANEL} [data-holdout-agreed]`);
		await expect(agreed).toHaveCount(1);
		const count = Number(await agreed.getAttribute('data-holdout-agreed'));
		const said = (await agreed.textContent()) ?? '';

		if (count === 0) {
			expect(said).toContain('No pair has been read as one story yet');
			return;
		}
		expect(said).toContain('below the line');
		// Either the strip reaches this scale or a chip says which way it went.
		// One of the two is always drawn, and never both.
		const strip = await page.locator(`${PANEL} [data-holdout-strip]`).count();
		const off = await page.locator(`${PANEL} [data-holdout-strip-offscale]`).count();
		expect(strip + off).toBe(1);
		await expect(page.locator(`${PANEL} [data-holdout-strip-label]`)).toBeVisible();
	});

	test('the panel takes the hue of what it means', async ({ page }) => {
		// A panel that looks the same reporting a fault as reporting a clear day
		// is the one thing this one may not be. The rule stays neutral either way:
		// a setting is not a fault.
		await open(page);

		const tone = await page.locator(PANEL).getAttribute('data-holdout-tone');
		const violations = Number(await page.locator(PANEL).getAttribute('data-holdout-violations'));
		expect(['neutral', 'warn', 'bad']).toContain(tone);
		expect(tone === 'bad').toBe(violations > 0);
		await expect(
			page.locator('[data-console-panel="The pairs a person marked apart"]')
		).toHaveAttribute('data-tone', tone ?? 'neutral');
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

	test('a tree nobody has scored says so rather than printing four zeros', async ({ page }) => {
		// THE BITE. A person types the verb that writes the committed row, so this
		// tree has none - and four zeros would read as a line that merged nothing
		// rather than as a reading nobody has taken. The panel keeps drawing the
		// margin either way, which is what says the two are different questions.
		await open(page);

		const scored = page.locator(`${PANEL} [data-holdout-scored]`);
		await expect(scored).toHaveAttribute('data-holdout-scored', 'none');
		const said = (await scored.textContent()) ?? '';
		expect(said).toContain('has not been scored');
		expect(said).toContain('score-merge-line-holdout');
		expect(said).not.toContain('0 of the');
		// A reader is not shown markdown.
		expect(said).not.toContain('`');
		await expect(page.locator(`${PANEL} [data-holdout-figure]`)).toBeVisible();
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
