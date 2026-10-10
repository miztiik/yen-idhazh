/** The judge's own health, and what the record still needs before it may fit.
 *
 * The arithmetic is checked without a browser in `merge-line.spec.ts`. What is
 * left needs a rendered page: an axis that follows the data instead of the two
 * knobs, a share printed with no denominator beside it, an expected hold painted
 * as a warning, and a strip that draws the days it has rows for instead of the
 * days the window spans.
 *
 * The private fixture provides a successful empty judge read. A gate without
 * recorded counts draws no zero bar. The populated
 * private route in `console-judgement-verdict` checks all three policy bars.
 */

import { expect, test, type Page } from './support/door-page';
import { chartsReady } from './support/charts-ready';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { agreementCorridor } from '../src/lib/console/merge-line';
import { BUILD_TIME } from './support/panel-drivers/judgement';
import { judgementRoute } from './support/judgement-route';

let emptyOrigin = '';
let emptyRoute: Awaited<ReturnType<typeof judgementRoute>>;
test.beforeAll(async ({}, info) => {
	test.setTimeout(180_000);
	emptyRoute = await judgementRoute(info.outputPath('empty-agreement-route'), { evidence: 'empty' });
	emptyOrigin = emptyRoute.origin;
});
test.afterAll(async () => { await emptyRoute?.close(); });

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
function tuning() {
	return JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8')).assemble.same_story.adaptive_dedup_threshold;
}
function presets(): number[] {
	return JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')).console.window_presets;
}

const ROUTE = '/console/judgement/';
const AGREEMENT = '[data-windowed="judge-agreement"]';
const GATES = '[data-windowed="record-gates"]';

async function open(page: Page, width = 1440): Promise<void> {
	await page.setViewportSize({ width, height: 1000 });
	await page.goto(`${emptyOrigin}${ROUTE.slice(1)}`);
	await chartsReady(page);
}

test.describe('whether the judge agrees with itself', () => {
	test('the agreement axis holds both marks, niced to a whole step', async ({ page }) => {
		await open(page);

		// Niced outward from the two marks rather than stopped at the looser one,
		// so a share past it has room to draw past it too - proved on days the
		// test builds in `merge-line.spec.ts`. The canary has judged nothing, so
		// no share widens the axis further here.
		const [low, high] = agreementCorridor({
			disagreementMax: tuning().disagreement_max,
			unclearMax: tuning().unclear_max
		});
		expect(await page.locator(AGREEMENT).getAttribute('data-agreement-domain')).toBe(
			`${low},${high}`
		);
	});

	test('the agreement axis does not move when the window moves', async ({ page }) => {
		await open(page);
		const fixed = await page.locator(AGREEMENT).getAttribute('data-agreement-domain');

		for (const preset of presets()) {
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
			[tuning().disagreement_max, tuning().unclear_max].sort((left, right) => left - right)
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
			'No judge readings were returned for'
		);
	});
});

test.describe('what the record still needs', () => {
	test('absent gate counts do not draw measured zeros', async ({ page }) => {
		await open(page);

		await expect(page.locator(`${GATES} [data-target-bar]`)).toHaveCount(0);
		await expect(page.locator('[data-gates-state="empty"]')).toContainText(
			'No gate counts were returned for'
		);
	});

	test('the squares strip names every date, including the silent ones', async ({ page }) => {
		await open(page);

		// A contiguous run of calendar days with no gap in it. A strip built from
		// the rows would draw a shorter, tidier picture of a record that had
		// stopped filling, and the gap is the fact this strip exists to show.
		const dates = await page
			.locator(`${GATES} [data-counted-day]`)
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-counted-day') ?? ''));

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

	for (const width of [390, 768, 1440]) {
		for (const theme of ['light', 'dark']) {
			test(`Judgement smoke: ${width}, ${theme}, absent judge record`, async ({ page }) => {
				await page.addInitScript((choice) => localStorage.setItem('idhazh:theme', choice), theme);
				const errors: string[] = [];
				page.on('pageerror', (error) => errors.push(error.message));
				page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
				page.on('response', (response) => { if (response.status() === 404) errors.push(`404 ${response.url()}`); });
				await open(page, width);
				await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
				expect(await page.locator('[data-console-panel-id]').evaluateAll(
					(nodes) => nodes.map((node) => node.getAttribute('data-console-panel-id'))
				)).toEqual(BUILD_TIME);
				for (const id of BUILD_TIME) {
					const panel = page.locator(`[data-console-panel-id="${id}"]`);
					await expect(panel.locator('[data-lede]')).toHaveCount(1);
					await expect(panel.locator('[data-lede]')).toBeVisible();
					await expect(panel.locator('[data-comparison]')).toHaveCount(1);
					await expect(panel.locator('[data-comparison]')).toHaveAttribute('data-comparison', / against /);
					await expect(panel.locator('[data-panel-question]')).toHaveAttribute('data-model-rule', 'no');
					await expect(panel.locator('[data-panel-question]')).toHaveAttribute(
						'data-model-rule-none', "the judge's record, not how summaries are written"
					);
				}
				await expect(page.locator('[data-console-empty="judgement"]')).toHaveCount(0);
				await expect(page.locator('[data-verdict-split] [data-empty="missing"]')).toBeVisible();
				expect(errors).toEqual([]);
			});
		}
	}

	test('a held day while filling is not painted as a warning', async ({ page }) => {
		await open(page);

		// Ten amber squares on the panel's first fortnight would burn the colour
		// before it ever meant anything. While the gates are unfilled a held day
		// takes the categorical hue, and the warning fill waits for the day a hold
		// stops being expected.
		if ((await page.locator(GATES).getAttribute('data-gates-met')) === 'yes') return;
		expect(await page.locator(`${GATES} [data-counted-state="held"]`).count()).toBe(0);
	});

	test('every square carries a sentence, so colour is never the only signal', async ({
		page
	}) => {
		await open(page);

		// The sentence is the square's accessible name, and the strip under the
		// squares prints it for the square a reader is on.
		const titles = await page
			.locator(`${GATES} [data-counted-day]`)
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('aria-label') ?? ''));

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

test('the resting heading separates the date from the note', async ({ page }) => {
	await open(page);

	const day = page.locator(`${AGREEMENT} [data-readout-day]`);
	if ((await day.count()) === 0) {
		// No pair has been read twice on this tree, so the panel declares it has no
		// column rather than printing a strip. Asserted rather than returned: a
		// branch that skips in silence hides the day the panel stops drawing at all.
		await expect(page.locator(`${AGREEMENT}[data-readout-none]`)).toHaveCount(1);
		return;
	}

	// Anchored on the end of the string. A substring match on the note alone
	// passes when the date runs straight into it, which is how `21 Septhe newest
	// day` reached the live site past five assertions that all used one.
	expect(
		(await day.innerText()).trim(),
		'the resting heading runs the date into the note'
	).toMatch(/, the newest day with numbers$/);
});
