/** Native route integration complements deterministic window arithmetic. */
import { expect, test } from './support/door-page';
import { serverCompiler } from './support/server-render';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { render } from 'svelte/server';
import { daysInWindow, windowOfDays } from '../src/lib/charts/viewport';
import { readoutOf } from '../src/lib/charts/readout';
import { nativeFailureMix } from '../src/lib/console/pipelines/failure-mix';
import { nativeTimeSplit, timeSplitReadout } from '../src/lib/console/pipelines/item-time-split';
import { telemetryRow } from './support/telemetry-row';
import { numberFormat } from './support/number-format';
import { hydrated, setWindow, routeHref } from './support/console-window/controls';
import { THROUGH, FIRST, dayBefore, nativeRow, timedRow, packedPipelines, servePipelines, settled } from './support/pipelines-ledgers';

const cases = [
	{ state: 'two items failed and one was timed', timed: 1, failures: 2 },
	{ state: 'three items were timed and none failed', timed: 3, failures: 0 },
	{ state: 'one item failed and two had no end-to-end clock', timed: 0, failures: 1 },
	{ state: 'no item was planned', timed: 0, failures: 0 }
] as const;
const roots = new Map<string, string>();
test.beforeAll(async () => {
	for (const one of cases) {
		const days = [{ covers: FIRST, rows: [] }, ...Array.from({ length: 15 }, (_, at) => {
			const date = dayBefore(THROUGH, 14 - at);
			const rows = one.state === 'no item was planned' ? [] : Array.from({ length: 3 }, (_, index) =>
				index < one.timed ? timedRow(date, { item_id: `${date}-${index}` }) :
				nativeRow(date, { item_id: `${date}-${index}`, ...(index < one.timed + one.failures
					? { stage: index % 2 === 0 ? 'extract' : 'fetch', outcome: 'failed', code: 'timeout' }
					: { fetch_ms: 100 }) }));
			return { covers: date, rows };
		})];
		roots.set(one.state, await packedPipelines(`window-${one.timed}-${one.failures}`, days,
			days.map((day) => ({ covers: day.covers, rows: [{ date: day.covers, url_key: 'checked', extraction_suspect: false }] }))));
	}
});

for (const one of cases) {
	test(`THE ORACLE: at 1 day and at 7, each panel draws the window's days when ${one.state}`, async ({ page }) => {
		await servePipelines(page, roots.get(one.state)!);
		await page.goto(routeHref('pipelines'));
		await hydrated(page);
		await setWindow(page, 90);
		await settled(page);
		await expect(page.locator('[data-window-status]')).toHaveText('Showing 90 days, to 15 Jun 2030.');
		for (const preset of [1, 7]) {
			await setWindow(page, preset);
			await settled(page);
			for (const name of ['failure-mix', 'item-time-split']) {
				const section = page.locator(`[data-windowed="${name}"]`);
				await expect(section).toHaveAttribute('data-window-days', String(preset));
				if (one.state === 'no item was planned') {
					await expect(section.locator(`[data-reserved="${name}"]`)).toHaveAttribute('data-panel-state', 'quiet');
					await expect(section.locator('[data-chart-type="dateSeries"]')).toHaveCount(0);
				} else if (name === 'item-time-split' && one.timed === 0) {
					await expect(section).toContainText('No whole item clock was measured.');
					await expect(section).toContainText('No complete reconciling item clock was measured.');
					await expect(section.locator('[data-chart-type="dateSeries"]')).toHaveCount(0);
				} else {
					await expect(section.locator('.date-series-plot')).toHaveAttribute('data-readout-columns', String(preset));
					const heading = section.locator(`[data-readout="${name}"] [data-readout-day]`);
					if (preset === 1) await expect(heading).not.toContainText('newest');
					else await expect(heading).toContainText(', the newest day');
					if (name === 'failure-mix') {
						await expect(section).toContainText(`${(one.failures / 3 * 100).toFixed(1)}% of recorded rows failed.`);
						if (one.failures === 0) await expect(section.locator('[data-nothing-fired]')).toBeVisible();
					} else {
						await expect(section.locator('[data-duration-cohort]')).toContainText(`${one.timed * preset} of ${3 * preset}`);
						await expect(section.locator('[data-stack-elapsed]')).toHaveCount(preset);
						await expect(section.locator('[data-readout="item-time-split"]')).toContainText('0.8 s');
					}
				}
			}
		}
	});
}

test('THE ORACLE: before a script reads the window, each panel holds its waiting box and says nothing of the window', async ({ page }) => {
	const document = await (await page.request.get(routeHref('pipelines'))).text();
	for (const name of ['failure-mix', 'item-time-split']) expect(document).toContain(`data-reserved="${name}"`);
	expect(document).not.toContain('data-nothing-fired');
	expect(document).not.toContain('data-duration-cohort');
});

const failedItem = (date: string) => telemetryRow({ date, stage: 'fetch', outcome: 'failed', code: 'timeout' });
const timedItem = (date: string) => telemetryRow({ date, fetch_ms: 100, extract_ms: 20, summarize_ms: 600,
	label_ms: 150, summary_ms: 430, visual_plan_ms: 60, faithfulness_ms: 30, item_total_ms: 800, stage_gap_ms: 50 });
test('a day with no row draws no column, and its strip says so, while a day that ran clean is a real zero', () => {
	const window = windowOfDays(THROUGH, 3, 'right');
	const rows = [failedItem('2030-06-13'), timedItem(THROUGH)];
	const calendar = daysInWindow(window);
	const nativeRows = rows.map((row) => ({ ...row }));
	const mix = nativeFailureMix(nativeRows, calendar);
	expect(mix.series.map((stage) => [stage.label, stage.points.map((point) => point.value)])).toEqual([
		['Fetch', [1, null, 0]], ['Extract', [0, null, 0]], ['Summarize', [0, null, 0]]
	]);
	expect(mix.recorded).toBe(2);
	expect(mix.failures).toBe(1);
	const split = nativeTimeSplit(nativeRows, calendar);
	const splitStrip = timeSplitReadout(split, numberFormat);
	expect(splitStrip.columns).toEqual(['2030-06-13', '2030-06-14', '2030-06-15']);
	expect(splitStrip.series.slice(0, 7).map((band) => band.values)).toEqual(
		['0.1 s', '0.02 s', '0.6 s', '0.03 s', '0.05 s', '0.8 s', '0 s'].map((value) => [null, null, value]));
	expect(splitStrip.notMeasured).toBe('Not measured for the complete cohort');
	expect(split.series.map((stage) => stage.points.map((point) => point.value))).toEqual(
		[100, 20, 600, 30, 50].map((value) => [null, null, value]));
});

test.describe('a strip keeps room only for what each entry prints', () => {
	let strip: (props: Record<string, unknown>) => string;
	test.beforeAll(async ({}, testInfo) => {
		const compiled = serverCompiler(resolve('test-results', 'strip-reserve', String(testInfo.workerIndex)));
		const module = await compiled('src/lib/components/ChartReadout.svelte', 'ChartReadout', []);
		const component = (await import(pathToFileURL(module).href)).default;
		strip = (props) => render(component, { props }).body;
	});
	test('a day nothing measured holds no room in the entries of a day that was', async ({ page }) => {
		const readout = readoutOf({
			type: 'dateSeries', columns: ['2030-06-13', '2030-06-14', THROUGH],
			series: [
				{ label: 'Fetch', swatch: '--chart-1', values: [null, null, 100], format: (ms) => `${(ms / 1000).toFixed(2)} s` },
				{ label: 'Extract', swatch: '--chart-2', values: [null, null, 20], format: (ms) => `${(ms / 1000).toFixed(2)} s` }
			], notMeasured: 'Not measured for the complete cohort', resting: 'newest'
		});
		await page.setContent(`<main>${strip({ readout, name: 'time-split', maxShare: 1 })}</main>`);
		const entries = await page.locator('[data-readout="time-split"] [data-readout-row]').evaluateAll((nodes) =>
			nodes.map((node) => [node.getAttribute('data-readout-row'), node.querySelector('.readout-value')?.getAttribute('style') ?? '']));
		expect(entries).toEqual([
			['Fetch', '--readout-reserve: 6ch'], ['Extract', '--readout-reserve: 6ch']
		]);
	});
});

test('a rule stated over 14 days prints no median in a 7-day window', async ({ page }) => {
	await servePipelines(page, roots.get(cases[0].state)!);
	await page.goto(routeHref('pipelines'));
	await hydrated(page);
	const section = page.locator('[data-windowed="chart-drawing"]');
	await setWindow(page, 14);
	await expect(section.locator('[data-window-too-narrow="chart-drawing"]')).toHaveCount(0);
	await setWindow(page, 7);
	await expect(section.locator('[data-window-too-narrow="chart-drawing"]')).toHaveText('The rule reads 14 days. Widen the window to see it.');
	await expect(section.locator('[data-charts-verdict]')).toHaveCount(0);
});

test('denied local and session storage cannot stop native loads or window changes', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(String(error)));
	await servePipelines(page, roots.get(cases[0].state)!);
	await page.addInitScript(() => {
		for (const name of ['localStorage', 'sessionStorage']) Object.defineProperty(window, name, {
			configurable: true, get() { throw new DOMException('Storage denied', 'SecurityError'); }
		});
	});
	await page.goto('/console/');
	await hydrated(page);
	await settled(page);
	await setWindow(page, 7);
	await settled(page);
	await expect(page.locator('[data-duration-cohort]')).toContainText('7 of 21 recorded item clocks');
	await expect(page.locator('[data-console-panel="What one more article costs"]')).toBeVisible();
	expect(errors).toEqual([]);
});

test('a late wide-window completion cannot replace a newer short request or its record beginning', async ({ page }) => {
	await servePipelines(page, roots.get(cases[0].state)!);
	await page.addInitScript(() => localStorage.setItem('idhazh:console-window', '1'));
	let release!: () => void;
	const held = new Promise<void>((resolve) => release = resolve);
	let requested = false;
	const older = dayBefore(THROUGH, 6);
	await page.route((url) => url.pathname.endsWith(`/state/compact/item-health/daily/${older.replaceAll('-', '/')}.parquet`), async (route) => {
		requested = true;
		await held;
		await route.fallback();
	});
	await page.goto('/console/');
	await hydrated(page);
	await settled(page);
	await setWindow(page, 7);
	await expect.poll(() => requested).toBe(true);
	await setWindow(page, 1);
	await settled(page);
	release();
	await expect(page.locator('[data-duration-cohort]')).toContainText('1 of 3 recorded item clocks');
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', '1');
	await expect(page.locator('[data-window-status]')).toHaveText('Showing 1 day, to 15 Jun 2030.');
});
