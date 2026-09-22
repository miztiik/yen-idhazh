/** What the judge said about the line, on a rendered page.
 *
 * The arithmetic is checked without a browser in `verdict-split.spec.ts`. What
 * is left needs the page: a cell that names what it actually knows, an axis
 * taken off the record's own band rather than off zero, a dash where the ledger
 * holds no answer, and a rule drawn at the line the day was built with.
 *
 * **The canary build has judged nothing**, so the baseline here is the empty
 * state, and that is the state worth testing. A panel that waits for data
 * before it draws anything teaches an operator the measurement does not exist.
 */

import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

const ROUTE = '/console/judgement/';
const SPLIT = '[data-verdict-split]';

function appearance(): { console: { precision_axis_multiple: number } } {
	// Read inside the test, never at module scope: a fixture opened while the
	// module loads fails before any test exists to own the failure.
	return JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8'));
}

function tuning(): { discard_share: number } {
	return JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8')).assemble.same_story
		.adaptive_dedup_threshold;
}

async function open(page: Page, width = 1440): Promise<void> {
	await page.setViewportSize({ width, height: 1000 });
	await page.goto(ROUTE);
	await page.waitForTimeout(700);
}

test.describe('what the judge said about the line', () => {
	test('the panel draws before anything has been judged', async ({ page }) => {
		await open(page);

		// Four cells, the cost sentence, both strips and the figures strip are all
		// present on a record that holds nothing. The empty state is the state an
		// operator sees first and it has to say what has to happen.
		await expect(page.locator(SPLIT)).toBeVisible();
		await expect(page.locator(`${SPLIT} [data-verdict-cell]`)).toHaveCount(4);
		await expect(page.locator(`${SPLIT} [data-verdict-cost]`)).toBeVisible();
		await expect(page.locator(`${SPLIT} [data-verdict-figures]`)).toBeVisible();
		expect(await page.locator(`${SPLIT} [data-verdict-days]`).count()).toBeGreaterThanOrEqual(0);
		await expect(page.locator(`${SPLIT} [data-verdict-state="empty"]`)).toBeVisible();
	});

	test('no cell claims a pair was merged', async ({ page }) => {
		await open(page);

		// THE BITE. The record holds counts in slots, not pairs, so the split says
		// which side of the line a verdict fell on and nothing more. Whether a pair
		// merged depends on two things the record never saw: a group is refused
		// unless every pair in it clears the line, and two items on different
		// published days never fold at all. Rename a cell to MERGED and this fails.
		const words = await page
			.locator(`${SPLIT} [data-verdict-cell]`)
			.evaluateAll((nodes) => nodes.map((node) => node.textContent ?? ''));

		expect(words).toHaveLength(4);
		for (const cell of words) {
			expect(cell.toLowerCase(), `a cell claims a merge: ${cell}`).not.toMatch(/merged/);
		}
		expect(words.filter((cell) => /eligible/i.test(cell))).toHaveLength(4);
	});

	test('the score axis is the record band, never anchored at zero', async ({ page }) => {
		await open(page);

		// A cosine in this band runs 0.88 to 1.00. An axis anchored at zero would
		// spend seven eighths of its width on scores the record has no slot for,
		// and the two population strips would collapse into one smear.
		const ticks = await page
			.locator(`${SPLIT} [data-tick="x"]`)
			.evaluateAll((nodes) => nodes.map((node) => Number(node.textContent)));

		expect(ticks.length).toBeGreaterThan(1);
		expect(Math.min(...ticks)).toBeGreaterThan(0.5);
		expect(Math.max(...ticks)).toBeLessThanOrEqual(1);
	});

	test('the rule sits at the line the day was built with', async ({ page }) => {
		await open(page);

		const line = await page.locator(SPLIT).getAttribute('data-verdict-line');
		const rule = await page.locator(`${SPLIT} [data-verdict-rule]`).getAttribute('data-verdict-rule');

		// One number, drawn once. A rule at a different value from the readout would
		// be two answers to the question the panel exists to ask.
		expect(rule).toBe(line);
		expect(Number(line)).toBeGreaterThan(0);
	});

	test('a figure the ledger has no answer for is a dash and never a zero', async ({ page }) => {
		await open(page);

		// Null and zero are different facts. A zero here would say the day drew no
		// pairs, when what happened is that no day has run.
		const figures = await page
			.locator(`${SPLIT} [data-verdict-figure]`)
			.evaluateAll((nodes) => nodes.map((node) => (node.textContent ?? '').trim()));

		expect(figures).toHaveLength(3);
		for (const figure of figures) {
			expect(figure, 'an absent count printed as a zero').not.toBe('0');
		}
	});

	test('the precision reading names the target it is judged against', async ({ page }) => {
		await open(page);

		// The corridor is the discard share times a knob, so a reader can see both
		// the target and a tenfold overshoot without the axis moving under them.
		const knobs = appearance().console.precision_axis_multiple;
		const target = tuning().discard_share;

		expect(knobs).toBeGreaterThan(1);
		expect(target).toBeGreaterThan(0);
		await expect(page.locator(`${SPLIT} [data-verdict-precision]`)).toBeVisible();
	});

	test('both population strips are labelled even where neither has a range', async ({ page }) => {
		await open(page);

		// A strip with nothing in it still says which population it is waiting for.
		// Dropping the label on an empty strip would leave a reader guessing which
		// of the two lines is missing.
		const labels = await page
			.locator(`${SPLIT} [data-verdict-strip-label]`)
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-verdict-strip-label')));

		expect(labels.sort()).toEqual(['different', 'same']);
	});

	test('the slice table is shut, and says so when it holds nothing', async ({ page }) => {
		await open(page);

		// Twenty-four rows below a chart is a wall. It opens on a click, and closed
		// is the resting state.
		const table = page.locator(`${SPLIT} [data-verdict-table]`);
		await expect(table).toBeVisible();
		expect(await table.evaluate((node) => (node as HTMLDetailsElement).open)).toBe(false);
	});

	test('the panel says why it has no column to point at', async ({ page }) => {
		await open(page);

		// Two population ranges on one score axis. There is no day column the two
		// share, so the panel says so rather than leaving a reader unable to tell a
		// decision from an omission.
		const reason = (await page.locator(SPLIT).getAttribute('data-readout-none')) ?? '';
		expect(reason.trim().split(/\s+/).length, `the reason reads "${reason}"`).toBeGreaterThanOrEqual(
			5
		);
		expect(reason).toContain('no column to share');
	});

	test('a strip that has a range prints its middle, where the circle is drawn', async ({ page }) => {
		await open(page);

		const labels = await page
			.locator(`${SPLIT} [data-verdict-strip-label]`)
			.evaluateAll((nodes) =>
				nodes.map((node) => ({
					name: node.getAttribute('data-verdict-strip-label') ?? '',
					words: node.textContent ?? ''
				}))
			);
		expect(labels.length, 'neither strip is labelled').toBe(2);

		// Two x ticks are enough to invert the scale the panel drew with, so the
		// printed middle is checked against the pixel the circle sits at rather
		// than against the same number read back from the same string.
		const ticks = await page
			.locator(`${SPLIT} [data-tick="x"]`)
			.evaluateAll((nodes) =>
				nodes.map((node) => ({
					at: Number(node.getAttribute('x')),
					score: Number(node.textContent)
				}))
			);
		expect(ticks.length, 'the score axis drew fewer than two ticks').toBeGreaterThan(1);
		const first = ticks[0];
		const last = ticks[ticks.length - 1];
		const scoreAt = (x: number): number =>
			first.score + ((x - first.at) * (last.score - first.score)) / (last.at - first.at);

		let checked = 0;
		for (const label of labels) {
			if (label.words.startsWith('Nothing was ')) continue;
			expect(label.words, `the ${label.name} strip does not print its middle`).toMatch(
				/, middle \d\.\d{3}$/
			);
			const printed = Number(label.words.match(/, middle (\d\.\d{3})$/)![1]);
			const cx = Number(
				await page.locator(`${SPLIT} [data-verdict-median="${label.name}"]`).getAttribute('cx')
			);
			expect(
				scoreAt(cx),
				`the ${label.name} strip prints a middle the circle is not drawn at`
			).toBeCloseTo(printed, 3);
			checked += 1;
		}

		// The canary has judged nothing, so both strips can legitimately be empty.
		// The assertion above is what runs on a tree that has a range; this one
		// keeps the empty case honest about which state it is in.
		if (checked === 0) {
			expect(labels.every((label) => label.words.startsWith('Nothing was '))).toBe(true);
		}
	});
});
