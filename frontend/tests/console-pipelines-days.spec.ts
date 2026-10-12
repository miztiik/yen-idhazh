/** Native failure and timing words refer only to the selected days. */
import { expect, test, type Page } from './support/door-page';

import { resolve } from 'node:path';

import { windowOfDays } from '../src/lib/charts/viewport';

import { failureRuleRows } from '../src/lib/console/failure-rules';

import { windowDates, said } from './support/console-window/readout';
import { DRAWN_THROUGH as JUDGED_THROUGH, DRAWN_AT } from './support/console-window/readout';

import { serverPanels } from './support/console-window/server-panels';
import { clientCode, drawClient } from './support/console-window/client-render';

test.describe("at one day no sentence needs a second day, on days the test builds", () => {

const drawn: Record<string, (props: Record<string, unknown>) => string> = {};
let stripStyles = '';
test.beforeAll(async ({}, testInfo) => {
  const panels = await serverPanels(resolve(process.cwd(), 'test-results', "FailureList", String(testInfo.workerIndex)), [['src/lib/components/FailureList.svelte', 'FailureList']]);
  Object.assign(drawn, panels.drawn);
  stripStyles = panels.stripStyles;
});
async function draw(page: Page, name: string, props: Record<string, unknown>) {
  await page.setContent(`<style>${stripStyles}</style><main>${drawn[name](props)}</main>`);
}

function failureProps(preset: number): Record<string, unknown> {
	return {
		ranking: failureRuleRows([
			{
				date: JUDGED_THROUGH,
				stage: 'fetch',
				outcome: 'failed',
				code: 'timeout', failed_rule: 'Fetch rule'
			},
			{ date: JUDGED_THROUGH, stage: 'fetch', outcome: 'ok', code: null, failed_rule: null }
		]),
		stages: { options: ['fetch'], chosen: 'fetch' },
		window: windowOfDays(JUDGED_THROUGH, preset, 'right'),
		max: 10,
		readoutMaxShare: 1
	};
}

test('THE ORACLE: one-day identity-free rules name their actual stage and recorded date', async ({
	page
}) => {
	await draw(page, 'FailureList', failureProps(1));
	expect(await said(page, '[data-ranked-row="Fetch rule"] [data-ranked-cell="context"]')).toBe(`at fetch; last ${JUDGED_THROUGH}`);
	await expect(page.locator('[data-source-losses], [data-failure-rows]')).toHaveCount(0);
	// One dated count is not a trend; the native sparkline requires two points.
	await expect(page.locator('[data-failure-ranking] [data-sparkline="empty"]')).toHaveCount(1);
	await expect(page.locator('[data-failure-ranking] [data-sparkline="line"]')).toHaveCount(0);
	await expect(page.locator('[data-readout="failed-rule-trends"]')).toHaveCount(0);
});

test('a seven-day identity-free ranking retains the same last measured date and its full calendar', async ({
	page
}) => {
	await draw(page, 'FailureList', failureProps(7));
	expect(await said(page, '[data-ranked-row="Fetch rule"] [data-ranked-cell="context"]')).toBe(`at fetch; last ${JUDGED_THROUGH}`);
	await expect(page.locator('[data-failure-ranking]')).toHaveAttribute('data-readout-columns', '7');
});
test.describe("remaining one-day words and keys on generated records", () => {

let browserCode: string;
test.beforeAll(async () => { browserCode = await clientCode([["StageTimings","./src/lib/components/StageTimings.svelte"]]); });
async function drawRecord(page: Page, name: string, props: Record<string, unknown>) {
  await drawClient(page, browserCode, name, props);
}

test('THE ORACLE: the stage note names the items within one day and keeps seven-day words', async ({ page }) => {
	for (const preset of [1, 7]) {
		const timing = { ms: 100, timed: 2 };
		await drawRecord(page, 'StageTimings', {
			days: windowDates(preset).map((date) => ({ date, items: 2, fetch: timing, extract: timing, summarize: timing })),
			span: windowOfDays(JUDGED_THROUGH, preset, 'right'), ...DRAWN_AT
		});
		await expect(page.locator('h2 + p')).toHaveText(
			(preset === 1 ? 'Median time per item for this one day.' : 'Median per item, each day.') +
			' Each gridline is ten times the one below, so the same slowdown looks the same at 40 ms and at 100 s.' +
			(preset === 1 ? ' Nothing changed about how the summaries are written inside this one day.' : ' Nothing changed about how the summaries are written inside these 7 days.')
		);
	}
});
});
});
