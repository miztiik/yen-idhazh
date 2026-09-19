/** The merge-line panel on Judgement: a fixed corridor, two lines, and a gap that means something.
 *
 * The arithmetic is checked without a browser in `merge-line.spec.ts`. What is
 * left needs a rendered page, and it is the half that goes wrong quietly: an
 * axis that follows the data instead of the config, a dotted line drawn through
 * a day nothing was fitted on, and a sentence counting a different slice from
 * the chart above it.
 *
 * **The canary build has never fitted a line**, so this file's baseline state is
 * K1 - the state that proves the design. A panel that only worked once there
 * were rows would open as a blank box for the first ten days of the feature's
 * life, which is exactly when somebody is watching it.
 */

import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const CONFIG = JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8'));
const APPEARANCE = JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8'));

/** Read from the committed config rather than typed in. A test carrying its own
 * copy of a knob passes when the knob moves and the page does not follow it. */
const TUNING = CONFIG.assemble.same_story.adaptive_dedup_threshold;
const FLOOR: number = CONFIG.assemble.same_story.floor_min;
const PRESETS: number[] = APPEARANCE.console.window_presets;

const ROUTE = '/console/judgement/';
const PANEL = '[data-windowed="merge-line"]';

/** Every word the config file uses for a knob this panel reads. None of them is
 * a word a reader knows, and a panel that printed one would be asking the reader
 * to learn the pipeline's vocabulary to read a chart. */
const CONFIG_WORDS = [
	'max_down_bins',
	'max_up_bins',
	'fall_weight',
	'rise_weight',
	'band_low',
	'band_high',
	'clamp_kind',
	'held_reason',
	'discard_share',
	'step_change_multiple'
];

/** The server draws at `console.chart_width` and the client redraws once it has
 * measured the column. Reading before that measures the wrong chart. */
async function open(page: Page, width = 1440): Promise<void> {
	await page.setViewportSize({ width, height: 1000 });
	await page.goto(ROUTE);
	await page.waitForTimeout(700);
}

async function domain(page: Page): Promise<string> {
	return (await page.locator(PANEL).getAttribute('data-line-domain')) ?? '';
}

test.describe('the corridor is the config band', () => {
	test('the corridor is the config band and never the data', async ({ page }) => {
		await open(page);

		expect(await domain(page), 'the axis followed the data instead of the config').toBe(
			`${TUNING.band_low},${TUNING.band_high}`
		);

		// The labels, not just the attribute. The attribute is what this file
		// reads; the labels are what a person reads, and a domain that reached the
		// attribute and not the scale would pass on the attribute alone.
		const ticks = await page
			.locator(`${PANEL} [data-tick="y"]`)
			.allTextContents();
		const numbers = ticks.map(Number);
		expect(Math.min(...numbers)).toBeCloseTo(TUNING.band_low, 3);
		expect(Math.max(...numbers)).toBeCloseTo(TUNING.band_high, 3);
	});

	test('the corridor does not move when the window moves', async ({ page }) => {
		await open(page);
		const fixed = await domain(page);

		// The radio is visually hidden inside its label, so the label is what a
		// reader presses and what this presses.
		for (const preset of PRESETS) {
			await page.locator(`[data-window-preset="${preset}"]`).click();
			await page.waitForTimeout(250);
			expect(
				await page.locator(PANEL).getAttribute('data-window-days'),
				`the ${preset}-day preset did not reach the panel`
			).not.toBeNull();
			expect(await domain(page), `the axis moved at the ${preset}-day span`).toBe(fixed);
		}
	});

	test('every tick is written at the resolution the fit can produce', async ({ page }) => {
		await open(page);

		// One bin is 0.001, so a fourth decimal would print a precision the fit
		// cannot answer to and a reader would compare two numbers that differ by
		// less than the chart's own step.
		for (const label of await page.locator(`${PANEL} [data-tick="y"]`).allTextContents()) {
			expect(label, `"${label}" is not written to three places`).toMatch(/^\d\.\d{3}$/);
		}
	});
});

test.describe('the two series say different things', () => {
	test('the proposed line is dashed and the applied line is not', async ({ page }) => {
		await open(page);

		const applied = page.locator(`${PANEL} [data-line-series="applied"]`);
		const proposed = page.locator(`${PANEL} [data-line-series="proposed"]`);
		if ((await applied.count()) === 0) {
			// K1: no day has fitted a line, so neither series is drawn. The rule is
			// what stands in for them, and it is what the panel says it is.
			expect(await page.locator(`${PANEL} [data-line-rule]`).count()).toBe(1);
			return;
		}

		// Read off the rendered attribute rather than off a class name: a class
		// that stopped applying its dash would leave this test green.
		expect(await applied.first().getAttribute('stroke-dasharray')).toBeNull();
		expect(await proposed.first().getAttribute('stroke-dasharray')).not.toBeNull();
	});

	test('a held day breaks the proposed series and keeps the applied one', async ({ page }) => {
		await open(page);

		const held = await page.locator(`${PANEL} [data-line-held-mark]`).count();
		const applied = await page.locator(`${PANEL} [data-line-series="applied"]`).count();
		const proposed = await page.locator(`${PANEL} [data-line-series="proposed"]`).count();
		if (applied === 0) {
			expect(held, 'no line was fitted, so no day can be marked held').toBe(0);
			return;
		}

		// One applied polyline whatever happened, because the line really was
		// applied on every day in the window. The proposed series is one polyline
		// per unbroken run, so a held day in the middle makes two.
		expect(applied, 'the applied line was broken at a held day').toBe(1);
		if (held > 0) expect(proposed, 'the proposed line was drawn through a held day').not.toBe(1);
	});
});

test.describe('the sentences count what the chart drew', () => {
	test('the clamp sentence counts the same days the chart draws', async ({ page }) => {
		await open(page);

		const note = await page.locator('[data-line-clamp-note]').count();
		if (note === 0) {
			// K1. The panel says so in words rather than printing a count of nothing.
			await expect(page.locator('[data-line-state="no-days"]')).toBeVisible();
			return;
		}

		const clamped = await page
			.locator(`${PANEL} [data-line-clamp]`)
			.evaluateAll((nodes) =>
				nodes.filter((node) => node.getAttribute('data-line-clamp') !== 'none').length
			);
		const text = (await page.locator('[data-line-clamp-note]').innerText()).trim();
		if (clamped === 0) {
			expect(text).toContain('has not held the line back on any');
		} else {
			expect(text, 'the sentence and the chart disagree about the clamp').toContain(
				`on ${clamped} of the last`
			);
		}
	});

	test('the panel draws a full axis with no fitted day', async ({ page }) => {
		await open(page);

		if ((await page.locator(`${PANEL} [data-line-rule]`).count()) === 0) return;

		// K1 is the state that proves the design: a full axis, a labelled
		// corridor, and the line in force - never a blank box with an apology.
		expect(await domain(page)).toBe(`${TUNING.band_low},${TUNING.band_high}`);
		expect(Number(await page.locator(`${PANEL} [data-line-rule]`).getAttribute('data-line-rule')))
			.toBeCloseTo(FLOOR, 3);
		await expect(page.locator('[data-line-state="no-days"]')).toContainText(
			'No day has fitted a line yet'
		);

		const box = await page.locator(`${PANEL} svg`).boundingBox();
		expect(box?.height, 'the panel is a different height with no data').toBeCloseTo(
			APPEARANCE.console.chart_height,
			0
		);
	});
});

test.describe('the pairs marked two stories are a zone on this chart', () => {
	test('the zone spans the marked-apart pairs, on the one chart with a date axis', async ({
		page
	}) => {
		// The owner asked for time on one axis and score on the other, and this is
		// the chart that already is that: a line walking down into this zone is a
		// pair somebody read as two stories being folded into one, drawn while it
		// happens. The holdout panel draws the same marks at a scale where the
		// distance is legible and the date is not.
		await open(page);

		const zone = page.locator(`${PANEL} [data-line-holdout]`);
		const marked = await zone.count();
		// Read inside the test: a fixture opened while the module loads fails
		// before any test exists to own the failure.
		const band = JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8')).assemble
			.same_story.adaptive_dedup_threshold;

		if (marked === 0) {
			// Either nobody has marked a pair apart, or every mark is outside the
			// corridor this chart draws - which the canary is, at 0.13 and 0.56
			// against a corridor that starts at 0.88. No zone rather than a
			// rectangle painted past the bottom of the plot.
			expect(await page.locator(`${PANEL} [data-line-holdout-label]`).count()).toBe(0);
			const note = await page.locator('[data-console-panel="Where the merge line sits"]').innerText();
			expect(note, 'the note promises a strip the chart did not draw').not.toContain(
				'tinted strip'
			);
			return;
		}

		const span = ((await zone.getAttribute('data-line-holdout')) ?? '').split(',').map(Number);
		expect(span[0]).toBeLessThanOrEqual(span[1]);
		expect(Number(await zone.getAttribute('data-line-holdout-count'))).toBeGreaterThan(0);

		// Inside the corridor the chart draws, so it is a region of this axis
		// rather than a rectangle clipped by it.
		expect(span[0]).toBeGreaterThanOrEqual(band.band_low);
		expect(span[1]).toBeLessThanOrEqual(band.band_high);

		// And inside the plot, not hanging out of an overflow-visible svg.
		const zoneBox = await zone.boundingBox();
		const plot = await page.locator(`${PANEL} svg`).boundingBox();
		if (zoneBox === null || plot === null) throw new Error('the zone or the plot has no box');
		expect(zoneBox.y).toBeGreaterThanOrEqual(plot.y - 1);
		expect(zoneBox.y + zoneBox.height).toBeLessThanOrEqual(plot.y + plot.height + 1);

		await expect(page.locator(`${PANEL} [data-line-holdout-label]`)).toContainText(
			'marked two stories'
		);
	});
});

test('no config key reaches the screen', async ({ page }) => {
	await open(page);

	const text = await page.locator('[data-console-panels="judgement"]').innerText();
	for (const word of CONFIG_WORDS) {
		expect(text, `the panel printed the config key "${word}"`).not.toContain(word);
	}
});
