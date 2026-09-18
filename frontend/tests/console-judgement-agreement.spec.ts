/** The judge's own health, and what the record still needs before it may fit.
 *
 * The arithmetic is checked without a browser in `merge-line.spec.ts`. What is
 * left needs a rendered page: an axis that follows the data instead of the two
 * knobs, a share printed with no denominator beside it, an expected hold painted
 * as a warning, and a strip that draws the days it has rows for instead of the
 * days the window spans.
 *
 * **The canary build has judged nothing**, so the baseline here is the empty
 * state - which on both panels is the state that proves the design. Three bars
 * draw, three markers are placed, and the panel says exactly what has to happen
 * before anything is fitted.
 */

import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const CONFIG = JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8'));
const APPEARANCE = JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8'));

const TUNING = CONFIG.assemble.same_story.adaptive_dedup_threshold;
const PRESETS: number[] = APPEARANCE.console.window_presets;

const ROUTE = '/console/judgement/';
const AGREEMENT = '[data-windowed="judge-agreement"]';
const GATES = '[data-windowed="record-gates"]';

async function open(page: Page, width = 1440): Promise<void> {
	await page.setViewportSize({ width, height: 1000 });
	await page.goto(ROUTE);
	await page.waitForTimeout(700);
}

test.describe('whether the judge agrees with itself', () => {
	test('the agreement axis is the two knobs and never the data', async ({ page }) => {
		await open(page);

		// Zero to the looser of the two limits. Not 0 to 1 - neither rate can reach
		// 1 without the run holding first, so half the plot would be a region the
		// data cannot enter.
		expect(await page.locator(AGREEMENT).getAttribute('data-agreement-domain')).toBe(
			`0,${Math.max(TUNING.disagreement_max, TUNING.unclear_max)}`
		);
	});

	test('the agreement axis does not move when the window moves', async ({ page }) => {
		await open(page);
		const fixed = await page.locator(AGREEMENT).getAttribute('data-agreement-domain');

		for (const preset of PRESETS) {
			await page.locator(`[data-window-preset="${preset}"]`).click();
			await page.waitForTimeout(200);
			expect(
				await page.locator(AGREEMENT).getAttribute('data-agreement-domain'),
				`the axis moved at the ${preset}-day span`
			).toBe(fixed);
		}
	});

	test('both markers are on the plot and both are labelled', async ({ page }) => {
		await open(page);

		const markers = await page
			.locator(`${AGREEMENT} [data-agreement-marker]`)
			.evaluateAll((nodes) =>
				nodes.map((node) => Number(node.getAttribute('data-agreement-marker-at')))
			);

		// Both, drawn whether or not a series is: they are what the panel is about,
		// and a reader should see where the run stops rather than subtract.
		expect(markers.sort((left, right) => left - right)).toEqual(
			[TUNING.disagreement_max, TUNING.unclear_max].sort((left, right) => left - right)
		);
		for (const label of await page
			.locator(`${AGREEMENT} [data-agreement-marker-label]`)
			.allTextContents()) {
			expect(label.trim().length, 'a marker was drawn with no words on it').toBeGreaterThan(0);
		}
	});

	test('every share prints its denominator in the same sentence', async ({ page }) => {
		await open(page);

		// A share over four pairs is not a measurement. Wherever a percent appears
		// on this panel, the count it is a share of appears beside it.
		const text = await page.locator(AGREEMENT).innerText();
		for (const percent of text.match(/\d+%/g) ?? []) {
			const sentence = text
				.split(/(?<=\.)\s/)
				.find((part) => part.includes(percent) && part.includes('pairs'));
			if (sentence === undefined) {
				// The axis labels and the two marker labels are percents with no
				// denominator, and they are not shares of anything - they are the
				// scale and the two rules.
				expect(
					(await page.locator(`${AGREEMENT} [data-tick="y"]`).allTextContents()).concat(
						await page.locator(`${AGREEMENT} [data-agreement-marker-label]`).allTextContents()
					).join(' '),
					`"${percent}" is a share with no denominator beside it`
				).toContain(percent);
			}
		}
	});

	test('a panel with nothing read twice says so rather than drawing a flat line', async ({
		page
	}) => {
		await open(page);

		if ((await page.locator(`${AGREEMENT} [data-agreement-day]`).count()) > 0) return;
		await expect(page.locator('[data-agreement-state="none"]')).toContainText(
			'No pair has been read twice yet'
		);
	});
});

test.describe('what the record still needs', () => {
	test('the three bars draw when the record is empty', async ({ page }) => {
		await open(page);

		// The panel's best day, not its worst: on the first run every bar draws,
		// every marker is placed, and the panel says what has to happen. A panel
		// that waits for data teaches an operator the measurement does not exist.
		expect(await page.locator(`${GATES} [data-target-bar]`).count()).toBe(3);
		if ((await page.locator('[data-gates-state="empty"]').count()) > 0) {
			await expect(page.locator('[data-gates-state="empty"]')).toContainText(
				'Nothing has been judged yet'
			);
		}
	});

	test('the gate bars take the policy tone', async ({ page }) => {
		await open(page);

		// A gate is a threshold somebody chose, not a health fact. Tinting it with
		// the confidence ramp would invent a verdict on the machine. The bite: set
		// tone to `health` and this goes red.
		const tones = await page
			.locator(`${GATES} [data-target-bar]`)
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-target-tone')));

		expect(tones).toEqual(['policy', 'policy', 'policy']);
	});

	test('the squares strip names every date, including the silent ones', async ({ page }) => {
		await open(page);

		// A contiguous run of calendar days with no gap in it. A strip built from
		// the rows would draw a shorter, tidier picture of a record that had
		// stopped filling, and the gap is the fact this strip exists to show.
		const dates = await page
			.locator(`${GATES} [data-fold-day]`)
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-fold-day') ?? ''));

		expect(dates.length).toBeGreaterThan(1);
		for (let index = 1; index < dates.length; index += 1) {
			const before = new Date(`${dates[index - 1]}T00:00:00Z`);
			before.setUTCDate(before.getUTCDate() + 1);
			expect(
				dates[index],
				`the strip skips from ${dates[index - 1]} to ${dates[index]}`
			).toBe(before.toISOString().slice(0, 10));
		}

		// And the run covers the span the window control is set to.
		const days = Number(await page.locator(GATES).getAttribute('data-window-days'));
		expect(dates.length).toBeGreaterThanOrEqual(days);
	});

	test('a held day while filling is not painted as a warning', async ({ page }) => {
		await open(page);

		// Ten amber squares on the panel's first fortnight would burn the colour
		// before it ever meant anything. While the gates are unfilled a held day
		// takes the categorical hue, and the warning fill waits for the day a hold
		// stops being expected.
		if ((await page.locator(GATES).getAttribute('data-gates-met')) === 'yes') return;
		expect(await page.locator(`${GATES} [data-fold-state="held"]`).count()).toBe(0);
	});

	test('every square carries a sentence, so colour is never the only signal', async ({
		page
	}) => {
		await open(page);

		const titles = await page
			.locator(`${GATES} [data-fold-day]`)
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('title') ?? ''));

		expect(titles.length).toBeGreaterThan(0);
		for (const title of titles) {
			expect(title.trim().length, 'a square was drawn with no sentence on it').toBeGreaterThan(0);
		}
	});
});

test('no config key reaches either panel', async ({ page }) => {
	await open(page);

	const text = (await page.locator(AGREEMENT).innerText()) + (await page.locator(GATES).innerText());
	for (const word of [
		'disagreement_max',
		'unclear_max',
		'minimum_negatives',
		'minimum_days',
		'minimum_above_line',
		'held_reason',
		'pairs_judged'
	]) {
		expect(text, `a panel printed the config key "${word}"`).not.toContain(word);
	}
});
