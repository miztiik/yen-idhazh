/** A shared one-column day readout keeps its blank hint room and exact keys. */
import { expect, test, type Page } from './support/browser';

import { resolve } from 'node:path';

import { STEP_KEYS, windowDates, dayStrip, stripOf, said } from './support/console-window/readout';
import { DRAWN_THROUGH as JUDGED_THROUGH } from './support/console-window/readout';

import { serverPanels } from './support/console-window/server-panels';

test.describe("at one day no sentence needs a second day, on days the test builds", () => {

const drawn: Record<string, (props: Record<string, unknown>) => string> = {};
let stripStyles = '';
test.beforeAll(async ({}, testInfo) => {
  const panels = await serverPanels(resolve(process.cwd(), 'test-results', "ChartReadout", String(testInfo.workerIndex)), ["ChartReadout"]);
  Object.assign(drawn, panels.drawn);
  stripStyles = panels.stripStyles;
});
async function draw(page: Page, name: string, props: Record<string, unknown>) {
  await page.setContent(`<style>${stripStyles}</style><main>${drawn[name](props)}</main>`);
}

test('THE ORACLE: a strip of one column heads its day alone and keeps its hint line blank', async ({
	page
}) => {
	await draw(page, 'ChartReadout', {
		readout: dayStrip([JUDGED_THROUGH]),
		name: 'day',
		maxShare: 1,
		restingNote: ', the newest day',
		hint: STEP_KEYS
	});
	expect(await said(page, '[data-readout="day"] [data-readout-day]')).toBe('15 Jun 2030');
	await expect(page.locator('[data-readout-hint="day"]')).toHaveCount(0);
	// Jony's ruling: the room stays, blank and unread, so no strip changes
	// height with the window.
	const held = page.locator('[data-readout-hint-held="day"]');
	await expect(held).toHaveAttribute('aria-hidden', 'true');
	await expect(held).toHaveCSS('visibility', 'hidden');
	expect(((await held.textContent()) ?? '').trim(), 'the kept room carries words').toBe('');
	expect((await held.boundingBox())?.height ?? 0, 'the kept room has no height').toBeGreaterThan(0);
});

test('a strip of seven columns rests on the newest and names its keys', async ({ page }) => {
	await draw(page, 'ChartReadout', {
		readout: dayStrip(windowDates(7)),
		name: 'week',
		maxShare: 1,
		restingNote: ', the newest day',
		hint: STEP_KEYS
	});
	expect(await stripOf(page, 'week')).toEqual({
		heading: '15 Jun 2030, the newest day',
		hint: STEP_KEYS
	});
});

test('THE ORACLE: a strip of one column says only what it still offers, and a strip with no hint line grows none', async ({
	page
}) => {
	await draw(page, 'ChartReadout', {
		readout: dayStrip([JUDGED_THROUGH]),
		name: 'jobs',
		maxShare: 1,
		hint: STEP_KEYS,
		hintOne: "Click or Enter lists this one day's jobs."
	});
	expect(await stripOf(page, 'jobs')).toEqual({
		heading: '15 Jun 2030',
		hint: "Click or Enter lists this one day's jobs."
	});

	await draw(page, 'ChartReadout', {
		readout: dayStrip([JUDGED_THROUGH]),
		name: 'card',
		maxShare: 1,
		hint: ''
	});
	await expect(page.locator('[data-readout-hint="card"], [data-readout-hint-held="card"]')).toHaveCount(0);
});
});
