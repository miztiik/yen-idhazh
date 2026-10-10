/** Summaries speed charts name one day and require a second only when the window can hold it. */
import { expect, test, type Page } from './support/browser';

import { resolve } from 'node:path';

import { STEP_KEYS, labelOf, stripOf, said } from './support/console-window/readout';
import { DRAWN_THROUGH as JUDGED_THROUGH, DRAWN_AT } from './support/console-window/readout';

import { serverPanels } from './support/console-window/server-panels';

function throughputDay(date: string) {
	const spread = (median: number) => ({
		min: median - 2,
		p25: median - 1,
		median,
		p75: median + 1,
		max: median + 2
	});
	return {
		date,
		items: 40,
		read: spread(12.34),
		write: spread(5.67),
		readTps: 12.34,
		writeTps: 5.67,
		cacheHitPct: 38,
		runs: [
			{ runId: `${date}-1`, items: 20, read: 12, write: 5.5 },
			{ runId: `${date}-2`, items: 20, read: 12.6, write: 5.8 }
		],
		model: 'model-a'
	};
}
const CHART = { width_px: 760, height_px: 220, tick_density: 6, readout_max_share: 1 };
test.describe("at one day no sentence needs a second day, on days the test builds", () => {

const drawn: Record<string, (props: Record<string, unknown>) => string> = {};
let stripStyles = '';
test.beforeAll(async ({}, testInfo) => {
  const panels = await serverPanels(resolve(process.cwd(), 'test-results', "ThroughputTrend", String(testInfo.workerIndex)), ["ThroughputTrend"]);
  Object.assign(drawn, panels.drawn);
  stripStyles = panels.stripStyles;
});
async function draw(page: Page, name: string, props: Record<string, unknown>) {
  await page.setContent(`<style>${stripStyles}</style><main>${drawn[name](props)}</main>`);
}

function speedProps(preset: number, dates: readonly string[]): Record<string, unknown> {
	return {
		days: dates.map(throughputDay),
		height: DRAWN_AT.height,
		width: DRAWN_AT.width,
		reference: '#',
		tickDensity: DRAWN_AT.tickDensity,
		readoutMaxShare: DRAWN_AT.readoutMaxShare,
		windowDays: preset
	};
}

const SPEED = '2030-06-15, over the whole day: read 12.34 tok/s, write 5.67 tok/s, from 40 items across 2 runs.';

test('THE ORACLE: the speed chart names its one day, and waits for no second day at one day', async ({
	page
}) => {
	await draw(page, 'ThroughputTrend', speedProps(1, [JUDGED_THROUGH]));
	expect(await labelOf(page, '[data-throughput-days]')).toBe('Model tokens per second, 15 Jun 2030');
	expect(await said(page, '[data-throughput="verdict"]')).toBe(SPEED);
	expect(await stripOf(page, 'throughput')).toEqual({ heading: '15 Jun 2030', hint: null });
});

test('the speed chart waits for a second day only where the window can hold one', async ({ page }) => {
	await draw(page, 'ThroughputTrend', speedProps(7, [JUDGED_THROUGH]));
	expect(await labelOf(page, '[data-throughput-days]')).toBe('Model tokens per second, 15 Jun 2030');
	expect(await said(page, '[data-throughput="verdict"]')).toBe(
		`${SPEED} One day so far. A second day gives it something to move against.`
	);

	await draw(page, 'ThroughputTrend', speedProps(7, ['2030-06-10', JUDGED_THROUGH]));
	expect(await labelOf(page, '[data-throughput-days]')).toBe(
		'Model tokens per second per day, 10 Jun 2030 to 15 Jun 2030, oldest day on the left'
	);
	expect(await stripOf(page, 'throughput')).toEqual({
		heading: '15 Jun 2030, the newest day',
		hint: STEP_KEYS
	});
});
});
