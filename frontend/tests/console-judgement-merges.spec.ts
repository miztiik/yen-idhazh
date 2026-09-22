/** The merge panel on Judgement: one box, three states, and no ledger words.
 *
 * The arithmetic is checked without a browser in `merge-line.spec.ts`. What is
 * left needs a rendered page, and it is the half that has historically gone
 * wrong on this console: a sentence built from a different slice than the chart
 * beside it, a panel that changes height when the data does, and a figure
 * labelled with the column name the pipeline happens to store it under.
 *
 * Which state the canary build lands in is not pinned. The fixture is one
 * published day and nineteen quiet ones, and whether its eight articles group
 * is the grouping pass's business, not this file's. So the assertions are
 * invariants that hold in every state - which is also what makes them survive
 * the day the fixture changes.
 */

import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { grouped } from '../src/lib/charts/series';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const APPEARANCE = JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8'));
/** Declared in `config/appearance.json`, read here rather than typed in: a test
 * carrying its own copy of a knob passes when the knob moves and the page does
 * not follow it. */
const CHART_HEIGHT: number = APPEARANCE.console.chart_height;
const PRESETS: number[] = APPEARANCE.console.window_presets;

const ROUTE = '/console/judgement/';
const PANEL = 'Stories the day merged';

/** The server draws at `console.chart_width` and the client redraws once it has
 * measured the column. Reading before that measures the wrong chart. */
async function open(page: Page, width = 1440): Promise<void> {
	await page.setViewportSize({ width, height: 1000 });
	await page.goto(ROUTE);
	await page.waitForTimeout(700);
}

function plot(page: Page) {
	return page.locator('[data-windowed="merged-stories"] svg');
}

const STRIP = '[data-windowed="merged-stories"] [data-readout="merged-stories"]';
const NO_COLUMN = 'No column in this window, so there is nothing to point at.';

/** How many columns the panel declares, after scrolling to it so the plot is
 * somewhere a pointer can reach. Zero means the window holds no published day,
 * which is a state the fixture can land in and not a failure. */
async function columnsOn(page: Page): Promise<number> {
	const owner = page.locator('[data-windowed="merged-stories"]');
	await owner.evaluate((node) => node.scrollIntoView({ behavior: 'instant', block: 'center' }));
	return Number((await owner.getAttribute('data-readout-columns')) ?? 0);
}

/** The labels the strip is printing, in the order it prints them. */
async function stripRows(page: Page): Promise<(string | null)[]> {
	return page
		.locator(`${STRIP} [data-readout-row]`)
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-readout-row')));
}

/** What one row of the strip read. The label is the first `dd` and the value is
 * the second, so the value is the last one. */
async function stripValue(page: Page, label: string): Promise<string> {
	return (await page.locator(`${STRIP} [data-readout-row="${label}"] dd`).last().innerText()).trim();
}

test.describe('the merge panel says one thing, in whichever state it is in', () => {
	test('the sentence and the columns are built from one slice', async ({ page }) => {
		await open(page);

		const state = await page
			.locator('[data-windowed="merged-stories"]')
			.getAttribute('data-merge-state');
		const drawn = await page
			.locator('[data-merge-day]')
			.evaluateAll((nodes) =>
				nodes.map((node) => Number(node.getAttribute('data-merge-count') ?? '0'))
			);
		const note = (await page.locator('[data-merge-note]').innerText()).replace(/\s+/g, ' ').trim();
		const folded = drawn.reduce((total, count) => total + count, 0);

		// The state is a claim about the columns, so it is checked against them
		// rather than trusted. `merged` with nothing folded, or `no-merges` with a
		// column standing, is a sentence disagreeing with the chart above it.
		if (state === 'no-days') {
			expect(drawn, 'the panel says no day is in the window and drew columns').toHaveLength(0);
		} else if (state === 'no-merges') {
			expect(folded, 'the panel says nothing was folded and drew a column').toBe(0);
			expect(note).toContain('Every one ran on its own');
		} else {
			expect(state, `unknown state "${state}"`).toBe('merged');
			expect(folded, 'the panel says stories were folded and drew none').toBeGreaterThan(0);
			expect(note, 'the sentence does not carry the number the chart drew').toContain(
				grouped(folded)
			);
			// A share with no denominator is not a share.
			expect(note).toMatch(/of the \d+ stories (these \d+ days|this one day) published/);
		}

		// One sentence, not two. Two states rendering at once is how a reader is
		// told both that nothing can be counted and that something was.
		await expect(page.locator('[data-merge-note]')).toHaveCount(1);
	});

	test('the two empty states are different sentences', async ({ page }) => {
		await open(page);
		const note = (await page.locator('[data-merge-note]').innerText()).trim();

		// Whichever state the fixture lands in, the panel never prints the other
		// empty state's words. `no-days` means the record cannot answer and
		// `no-merges` means it answered no, and reading one as the other is
		// reading a null as a zero.
		const cannotCount = note.includes('nothing here can be counted');
		const answeredNone = note.includes('Every one ran on its own');
		expect(cannotCount && answeredNone, 'the panel printed both empty states at once').toBe(false);
	});

	test('the panel keeps its box at every span the control offers', async ({ page }) => {
		await open(page);
		// The radio itself is a 1px square behind its tile, so the tile is what a
		// person clicks and what a test clicks. Enabled first: the control does
		// nothing until a browser has run the page.
		await expect(page.locator('[data-window-preset] input').first()).toBeEnabled();

		const heights: number[] = [];
		for (const days of PRESETS) {
			await page.locator(`[data-window-preset="${days}"]`).click();
			await page.waitForTimeout(400);
			const box = await page.locator(`[data-console-panel="${PANEL}"]`).boundingBox();
			const svg = await plot(page).boundingBox();
			expect(svg?.height, `the plot is not ${CHART_HEIGHT}px tall at ${days} days`).toBeCloseTo(
				CHART_HEIGHT,
				0
			);
			heights.push(Math.round(box?.height ?? 0));
		}

		// A panel that shrinks on a quiet span is a panel an operator stops
		// opening, and a panel that grows pushes everything below it down the page
		// while he is reading it.
		expect(new Set(heights).size, `the panel box moved across spans: ${heights.join(', ')}`).toBe(
			1
		);
	});

	test('the panel names no ledger column', async ({ page }) => {
		await open(page);
		const text = await page.locator('[data-windowed="merged-stories"]').innerText();
		const panel = await page.locator(`[data-console-panel="${PANEL}"]`).innerText();

		// A term from a subsystem is not a term for a user (CLAUDE.md section 0b).
		// The operator reads what a day folded, not the field name it is stored in.
		for (const column of ['same_story_as', 'floor_min', 'item_id', 'collapse']) {
			expect(text, `the panel prints the column name "${column}"`).not.toContain(column);
			expect(panel, `the panel prints the column name "${column}"`).not.toContain(column);
		}
	});

	test('the route still names what it does not draw', async ({ page }) => {
		await open(page);

		// The panel counts what a day folded. The absence is about the desk and the
		// lenses the model chose, which it still does not record. A figure landing
		// on the route does not answer a different question, so the absence stays.
		await expect(page.locator('[data-console-empty="judgement"]')).toHaveCount(1);
		await expect(page.locator(`[data-console-panel="${PANEL}"]`)).toHaveCount(1);
	});
});

test.describe('the panel prints the column under the pointer', () => {
	test('pointing at a column prints both series at that column', async ({ page }) => {
		await open(page);
		if ((await columnsOn(page)) === 0) {
			// No published day in the window. The panel says so in words where the
			// strip would be, which is the other half of the rule.
			await expect(page.locator('[data-merge-no-column]')).toHaveText(NO_COLUMN);
			return;
		}

		const box = await plot(page).boundingBox();
		expect(box, 'the plot was not drawn').not.toBeNull();
		await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
		await page.waitForTimeout(200);

		// One strip under one chart, and the two marks it draws in the order it
		// draws them: the column, then the dot standing on it.
		await expect(page.locator(STRIP)).toHaveCount(1);
		expect(await stripRows(page), 'the strip does not print the chart it sits under').toEqual([
			'Merged',
			'Biggest group'
		]);
	});

	test('a column that folded nothing still prints both rows, with its denominator', async ({
		page
	}) => {
		await open(page);
		if ((await columnsOn(page)) === 0) {
			await expect(page.locator('[data-merge-no-column]')).toHaveText(NO_COLUMN);
			return;
		}

		// The columns in the order they are drawn, which is the order the strip
		// steps through. The published count is in the column's own title, so no
		// new attribute is minted to read it.
		const drawn = await page.locator('[data-merge-day]').evaluateAll((nodes) =>
			nodes.map((node) => ({
				merges: Number(node.getAttribute('data-merge-count') ?? '0'),
				title: node.querySelector('title')?.textContent ?? ''
			}))
		);

		// The keyboard rather than pointer arithmetic: a column is reached by
		// index, so the column read and the column asserted cannot be two
		// different ones. Bounded, because the cost of this block is the number of
		// steps and the rule it checks holds at every column.
		await plot(page).focus();
		await page.keyboard.press('Home');
		for (let index = 0; index < Math.min(drawn.length, 8); index += 1) {
			if (index > 0) await page.keyboard.press('ArrowRight');
			await page.waitForTimeout(120);

			// Both rows at every column. A row that disappears at zero makes the
			// reader compare a two-row strip with a one-row strip.
			expect(await stripRows(page), `column ${index} did not print both rows`).toEqual([
				'Merged',
				'Biggest group'
			]);

			const merged = await stripValue(page, 'Merged');
			expect(merged, `column ${index} read "${merged}"`).toMatch(
				/^(no story published|\d+ of \d+ published)$/
			);

			const published = drawn[index].title.match(/(\d+) stories (published|were published)/);
			if (drawn[index].merges === 0 && published !== null) {
				expect(merged, `a column that folded nothing dropped its denominator`).toBe(
					`0 of ${published[1]} published`
				);
			}
		}
	});

	test('the resting heading names the column it fell back to', async ({ page }) => {
		await open(page);
		if ((await columnsOn(page)) === 0) {
			await expect(page.locator('[data-merge-no-column]')).toHaveText(NO_COLUMN);
			return;
		}

		// Anchored on the end of the string. A substring match on the note alone
		// passes when the date runs straight into it, which is how
		// `21 Septhe newest day` reached the live site past five assertions.
		const heading = (await page.locator(`${STRIP} [data-readout-day]`).innerText()).trim();
		expect(heading, 'the resting heading runs the date into the note').toMatch(
			/, the newest published day$/
		);
	});
});
