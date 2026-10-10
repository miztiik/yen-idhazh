/** Record bars stand on the newest selected evidence, including earlier cumulative rows. */
import { expect, test, type Page } from './support/browser';

import { resolve } from 'node:path';

import type { JudgeDay } from '../src/lib/console/merge-line';

import { windowed } from './support/console-window/controls';
import { said } from './support/console-window/readout';
import { JUDGED_THROUGH, FILLING, judgeDay, propsOf, SAID } from './support/console-window/judgement-fixtures';

import { serverPanels } from './support/console-window/server-panels';

interface BarsCase {
	surface: 'record-gates';
	preset: number;
	state: string;
	days: JudgeDay[];
	bars: string[];
	words: string;
}

/** The bars stand on the record's newest row on or before the window's last day,
 * so only a record that never held a row, or one that emptied, draws them at
 * zero. Every count and every word is written out. */
const BARS_CASES: BarsCase[] = [
	{
		surface: 'record-gates',
		preset: 1,
		state: 'the window holds no row, after earlier rows counted readings, days and pairs',
		days: [
			judgeDay('2030-06-12', { ...FILLING, negativesOnRecord: 100, daysOnRecord: 5, aboveLineOnRecord: 9 }),
			judgeDay('2030-06-14', FILLING)
		],
		bars: ['120', '6', '12'],
		words:
			'The bars show what the record held on 14 Jun 2030, before this one day. No run has recorded anything since.'
	},
	{
		surface: 'record-gates',
		preset: 1,
		state: 'the record never held a row',
		days: [],
		bars: ['0', '0', '0'],
		words:
			'Nothing was judged in this one day. The three bars are what the record needs before a line may be fitted at all.'
	},
	{
		surface: 'record-gates',
		preset: 1,
		state: "the record emptied on the window's day",
		days: [judgeDay('2030-06-14', FILLING), judgeDay(JUDGED_THROUGH, { heldReason: 'inputs_changed' })],
		bars: ['0', '0', '0'],
		words:
			'The record has 0 readings, 0 days, and 0 pairs above the line; it needs at least 200 readings, 10 days, and 30 pairs above the line. No line was fitted in this one day.'
	}
];
test.describe("the record's bars stand on its newest row, on days the test builds", () => {
	/** The record panel rendered on the server with its real children, never a stub. */
const drawn: Record<string, (props: Record<string, unknown>) => string> = {};
let stripStyles = '';
test.beforeAll(async ({}, testInfo) => {
  const panels = await serverPanels(resolve(process.cwd(), 'test-results', "RecordGates", String(testInfo.workerIndex)), [['src/routes/console/judgement/RecordGates.svelte', 'RecordGates']]);
  Object.assign(drawn, panels.drawn);
  stripStyles = panels.stripStyles;
});
async function draw(page: Page, name: string, props: Record<string, unknown>) {
  await page.setContent(`<style>${stripStyles}</style><main>${drawn[name](props)}</main>`);
}

const drawGates = (props: Record<string, unknown>) => drawn.RecordGates(props);

	for (const one of BARS_CASES) {
		test(`THE ORACLE: the record's bars and note when ${one.state}`, async ({ page }) => {
			await page.setContent(`<main>${drawGates(propsOf(one))}</main>`);

			const panel = page.locator('[data-windowed="record-gates"]');
			await expect(panel).toHaveAttribute('data-window-days', String(one.preset));
			// Three tracks: each bar is drawn at its count, never replaced by a dash.
			await expect(panel.locator('[data-target-cell="track"]')).toHaveCount(3);
			const bars = await panel.locator('[data-target-cell="value"]').allTextContents();
			expect(bars.map((bar) => bar.trim()), 'the bars stand on a different row').toEqual(one.bars);
			expect(await said(page, SAID['record-gates'])).toBe(one.words);
		});
	}
});
