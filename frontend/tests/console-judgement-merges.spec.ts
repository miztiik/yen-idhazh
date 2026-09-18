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
