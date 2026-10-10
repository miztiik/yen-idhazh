/** Pipelines failure and timing words refer only to the selected days. */
import { expect, test, type Page } from './support/browser';

import { resolve } from 'node:path';

import { windowOfDays } from '../src/lib/charts/viewport';

import { telemetryRow } from './support/telemetry-row';

import { windowDates, said } from './support/console-window/readout';
import { DRAWN_THROUGH as JUDGED_THROUGH, DRAWN_AT } from './support/console-window/readout';

import { serverPanels } from './support/console-window/server-panels';
import { clientCode, drawClient } from './support/console-window/client-render';

test.describe("at one day no sentence needs a second day, on days the test builds", () => {

const drawn: Record<string, (props: Record<string, unknown>) => string> = {};
let stripStyles = '';
test.beforeAll(async ({}, testInfo) => {
  const panels = await serverPanels(resolve(process.cwd(), 'test-results', "FailureList", String(testInfo.workerIndex)), ["FailureList"]);
  Object.assign(drawn, panels.drawn);
  stripStyles = panels.stripStyles;
});
async function draw(page: Page, name: string, props: Record<string, unknown>) {
  await page.setContent(`<style>${stripStyles}</style><main>${drawn[name](props)}</main>`);
}

function failureProps(preset: number): Record<string, unknown> {
	return {
		rows: [
			telemetryRow({
				date: JUDGED_THROUGH,
				item_id: 'a',
				source_id: 'alpha',
				stage: 'fetch',
				outcome: 'failed',
				code: 'timeout'
			}),
			telemetryRow({ date: JUDGED_THROUGH, item_id: 'b', source_id: 'beta', outcome: 'ok' })
		],
		window: windowOfDays(JUDGED_THROUGH, preset, 'right'),
		selectedCode: null,
		max: 10,
		sourceMax: 10,
		readoutMaxShare: 1
	};
}

test('THE ORACLE: a failure cause, and a source that lost articles, say nothing about when at one day', async ({
	page
}) => {
	await draw(page, 'FailureList', failureProps(1));
	expect(await said(page, '[data-ranked-row="fetch/timeout"] [data-ranked-cell="context"]')).toBe(
		'sources hit: 1 of 2'
	);
	expect(await said(page, '[data-ranked-row="alpha"] [data-ranked-cell="context"]')).toBe(
		'fetch/timeout'
	);
});

test('a failure cause, and a source that lost articles, say they were last seen on the newest day in view', async ({
	page
}) => {
	await draw(page, 'FailureList', failureProps(7));
	expect(await said(page, '[data-ranked-row="fetch/timeout"] [data-ranked-cell="context"]')).toBe(
		'sources hit: 1 of 2 - last on the newest day in view'
	);
	expect(await said(page, '[data-ranked-row="alpha"] [data-ranked-cell="context"]')).toBe(
		'fetch/timeout - last on the newest day in view'
	);
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
