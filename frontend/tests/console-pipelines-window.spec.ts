/** Pipelines draws only the windowed telemetry and refuses a too-narrow rule. */
import { expect, test } from './support/browser';

import { serverCompiler } from './support/server-render';

import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { render } from 'svelte/server';

import { windowOfDays } from '../src/lib/charts/viewport';

import { failureSeries, telemetryCsv, timeSplit, type TelemetryRow } from '../src/lib/charts/series';
import { failureMix, failureMixColumns, timeSplitChart, timeSplitColumns } from '../src/lib/charts/glance';

import { telemetryRow } from './support/telemetry-row';
import { hydrated, setWindow, windowed, routeHref } from './support/console-window/controls';

import { JUDGED_THROUGH } from './support/console-window/judgement-fixtures';

const RULE_DAYS = 14;
const PIPELINE_WINDOW = {
	panelCases: [
		{ state: 'two items failed and one was timed', mix: { 1: 1, 7: 7 }, split: { 1: 1, 7: 7 } },
		{
			state: 'three items were timed and none failed',
			mix: {
				1: 'Nothing failed in this one day, out of 3 items planned.',
				7: 'Nothing failed in these 7 days, out of 21 items planned.'
			},
			split: { 1: 1, 7: 7 }
		},
		{
			state: 'one item failed and two had no end-to-end clock',
			mix: { 1: 1, 7: 7 },
			split: {
				1: 'No item was timed from start to finish in this one day, so there is no time to split.',
				7: 'No item was timed from start to finish in these 7 days, so there is no time to split.'
			}
		},
		{
			state: 'no item was planned',
			mix: {
				1: 'No item was planned in this one day, so nothing could fail.',
				7: 'No item was planned in these 7 days, so nothing could fail.'
			},
			split: {
				1: 'No item was planned in this one day, so there is no time to split.',
				7: 'No item was planned in these 7 days, so there is no time to split.'
			}
		}
	],
	panelWords: {
		'failure-mix': {
			section: {
				1: 'What is failing, by stage, over 1 day',
				7: 'What is failing, by stage, over 7 days'
			},
			chart: {
				1: "Failures by stage in this one day. The column's height is the day's failures, and the bands are the stages they stopped at. Drawn as lines instead, each stage is its own count and the total is not shown.",
				7: "Failures per day by stage, over 7 days. One column is one day, its height is that day's failures, and the bands are the stages they stopped at. A day with no column is a day on which nothing was planned or nothing failed, and the numbers below the chart say which. Drawn as lines instead, each stage is its own count a day and the total is not shown."
			},
			empty: '[data-mix-empty]'
		},
		'time-split': {
			section: {
				1: "Where an item's time went, over 1 day",
				7: "Where an item's time went, over 7 days"
			},
			chart: {
				1: "Mean milliseconds an item spent in each step, in this one day. The column's height is the mean item's whole clock. The bands from the bottom are fetch, extract, the label call, the summary, the visual plan, the model time neither call claimed, the faithfulness scorers, and at the top the time no named step claimed. Drawn as lines instead, each step is its own milliseconds and the whole clock is not shown.",
				7: "Mean milliseconds an item spent in each step, per day, over 7 days. One column is one day and its height is the mean item's whole clock. A day with no column is a day on which no item was timed from start to finish. The bands from the bottom are fetch, extract, the label call, the summary, the visual plan, the model time neither call claimed, the faithfulness scorers, and at the top the time no named step claimed. Drawn as lines instead, each step is its own milliseconds a day and the whole clock is not shown."
			},
			empty: '[data-time-split-empty]'
		}
	}
} as const;

const TELEMETRY_SHARDS = '**/telemetry/*.csv';

/** Every day of the month a telemetry request names, and the first day of the
 * next. Whatever day the window ends on, the page then holds rows on days past
 * it, as a real month does once a run has written the day after the newest
 * published one, so a panel that drew every day it holds would draw them. */
function daysServed(month: string): string[] {
	const [year, index] = month.split('-').map(Number);
	const last = new Date(Date.UTC(year, index, 0)).getUTCDate();
	const days = Array.from(
		{ length: last },
		(_, day) => `${month}-${String(day + 1).padStart(2, '0')}`
	);
	return [...days, new Date(Date.UTC(year, index, 1)).toISOString().slice(0, 10)];
}

/** An item that published, timed from start to finish: 800 ms in all. */
function timedItem(date: string, item: string): TelemetryRow {
	return telemetryRow({
		date,
		run_id: `${date}-1`,
		item_id: item,
		fetch_ms: 100,
		extract_ms: 20,
		summarize_ms: 600,
		label_ms: 150,
		summary_ms: 430,
		visual_plan_ms: 60,
		faithfulness_ms: 30,
		item_total_ms: 800,
		stage_gap_ms: 50
	});
}

/** An item that stopped at a stage, with no clock of its own. */
function failedItem(date: string, item: string, stage: 'fetch' | 'extract'): TelemetryRow {
	return telemetryRow({
		date,
		run_id: `${date}-1`,
		item_id: item,
		stage,
		outcome: 'failed',
		code: 'timeout'
	});
}

/** An item that published with its fetch timed and no end-to-end clock. */
function untimedItem(date: string, item: string): TelemetryRow {
	return telemetryRow({ date, run_id: `${date}-1`, item_id: item, fetch_ms: 100 });
}

/** What every served day holds, case by case. */
const SERVED_DAYS = {
	'two items failed and one was timed': (date: string) => [
		timedItem(date, 'a'),
		failedItem(date, 'b', 'fetch'),
		failedItem(date, 'c', 'extract')
	],
	'three items were timed and none failed': (date: string) => [
		timedItem(date, 'a'),
		timedItem(date, 'b'),
		timedItem(date, 'c')
	],
	'one item failed and two had no end-to-end clock': (date: string) => [
		failedItem(date, 'a', 'fetch'),
		untimedItem(date, 'b'),
		untimedItem(date, 'c')
	],
	'no item was planned': (): TelemetryRow[] => []
} as const;

/** Each panel at the 1-day and the 7-day window: the number of columns it
 * draws, or the sentence in its chart's place. The sentences are Reader's,
 * written out whole. */
const WINDOW_PANEL_CASES = PIPELINE_WINDOW.panelCases;

/** Each panel's own label, at each window. Reader's words, written out whole. */
const WINDOW_PANEL_WORDS = PIPELINE_WINDOW.panelWords;

test.describe("Pipelines' failure mix and time split draw the window's days, on telemetry the test builds", () => {
	for (const one of WINDOW_PANEL_CASES) {
		test(`THE ORACLE: at 1 day and at 7, each panel draws the window's days when ${one.state}`, async ({
			page
		}) => {
			// Every month the page asks for is served from rows built here, on every
			// day of it and the day after it ends, so the page always holds more days
			// than either window.
			await page.route(TELEMETRY_SHARDS, (route) => {
				const month = /(\d{4}-\d{2})\.csv$/.exec(new URL(route.request().url()).pathname)?.[1];
				if (month === undefined) return route.abort();
				const rows = daysServed(month).flatMap((date) => SERVED_DAYS[one.state](date));
				return route.fulfill({ status: 200, contentType: 'text/csv', body: telemetryCsv(rows) });
			});
			await page.goto(routeHref('pipelines'));
			await hydrated(page);

			for (const preset of [1, 7] as const) {
				await setWindow(page, preset);
				const surface = page.locator('[data-console-panels="pipelines"]');
				await expect(surface).toHaveAttribute('data-telemetry-fetching', 'no');
				await expect(surface).not.toHaveAttribute('data-telemetry-state', 'loading');

				for (const [name, drawn] of [
					['failure-mix', one.mix[preset]],
					['time-split', one.split[preset]]
				] as const) {
					const words = WINDOW_PANEL_WORDS[name];
					const section = page.locator(`[data-windowed="${name}"]`);
					await expect(section, `${name} follows a different window`).toHaveAttribute(
						'data-window-days',
						String(preset)
					);
					await expect(section).toHaveAttribute('aria-label', words.section[preset]);
					const figure = section.locator('figure.chart');
					if (typeof drawn === 'number') {
						await expect(figure, `${name} draws days outside the window`).toHaveAttribute(
							'data-readout-columns',
							String(drawn)
						);
						await expect(figure).toHaveAttribute('aria-label', words.chart[preset]);
						await expect(section.locator(words.empty)).toHaveCount(0);
						// The strip heads the window's newest day, and at one day that day alone.
						const heading = section.locator(`[data-readout="${name}"] [data-readout-day]`);
						if (preset === 1) await expect(heading).not.toContainText('newest');
						else await expect(heading).toContainText(', the newest day');
					} else {
						await expect(figure, `${name} drew a chart over a window with nothing in it`).toHaveCount(0);
						const sentence = section.locator(`${words.empty} .empty-sentence`);
						await expect(sentence).toHaveText(drawn);
						// Centred and wrapped on a phone, its lines are evened out rather than
						// leaving the last word alone.
						await expect(sentence).toHaveCSS('text-wrap-style', 'balance');
					}
				}
			}
		});
	}

	test('THE ORACLE: before a script reads the window, each panel holds its waiting box and says nothing of the window', async ({
		page
	}) => {
		// The document as served, before any script has fetched a month. A sentence
		// about the window's days would be false here: no row has been read.
		const document = await (await page.request.get(routeHref('pipelines'))).text();
		for (const name of ['failure-mix', 'time-split']) {
			expect(document, `${name} has no waiting box before its rows are read`).toContain(
				`data-reserved="${name}"`
			);
		}
		expect(document).not.toContain('data-mix-empty');
		expect(document).not.toContain('data-time-split-empty');
	});

	test("a day with no row draws no column, and its strip says so, while a day that ran clean is a real zero", () => {
		// Three days ending on the pinned day: an item failed at fetch on the first,
		// nothing ran on the second, and the third timed one item and failed none.
		const window = windowOfDays(JUDGED_THROUGH, 3, 'right');
		const rows = [failedItem('2030-06-13', 'a', 'fetch'), timedItem('2030-06-15', 'b')];

		const series = failureSeries(rows, window);
		const mixStrip = failureMixColumns(series);
		expect(mixStrip.columns).toEqual(['13 Jun 2030', '14 Jun 2030', '15 Jun 2030']);
		expect(mixStrip.series.map((stage) => [stage.label, stage.values])).toEqual([
			['fetch', ['1', null, '0']],
			['extract', ['0', null, '0']],
			['summarize', ['0', null, '0']]
		]);
		expect(mixStrip.notMeasured).toBe('No item was planned on this day');
		const mixBars = failureMix(series).option.series as { name: string; data: (number | null)[] }[];
		expect(mixBars.map((bar) => [bar.name, bar.data])).toEqual([['fetch', [1, null, 0]]]);
		// Drawn as lines, the same array: the day with no row breaks the line.
		const mixLines = failureMix(series, 'lines').option.series as { data: (number | null)[] }[];
		expect(mixLines.map((line) => line.data)).toEqual([[1, null, 0]]);

		const days = timeSplit(rows, window);
		const splitStrip = timeSplitColumns(days);
		expect(splitStrip.series.map((band) => band.values)).toEqual([
			[null, null, '100 ms, 13%'],
			[null, null, '20 ms, 3%'],
			[null, null, '150 ms, 19%'],
			[null, null, '370 ms, 46%'],
			[null, null, '60 ms, 8%'],
			[null, null, '20 ms, 3%'],
			[null, null, '30 ms, 4%'],
			[null, null, '50 ms, 6%']
		]);
		expect(splitStrip.notMeasured).toBe('No item was timed from start to finish on this day');
		const splitBars = timeSplitChart(days).option.series as { data: (number | null)[] }[];
		expect(splitBars.map((bar) => bar.data)).toEqual([
			[null, null, 100],
			[null, null, 20],
			[null, null, 150],
			[null, null, 370],
			[null, null, 60],
			[null, null, 20],
			[null, null, 30],
			[null, null, 50]
		]);
	});

	test.describe('a strip keeps room only for what each entry prints', () => {
		/** The strip rendered on the server, as a page draws it. */
		let strip: (props: Record<string, unknown>) => string;

		test.beforeAll(async ({}, testInfo) => {
			// One directory a worker: a module rewritten while another worker imports
			// it is read half-written.
			const compiled = serverCompiler(
				resolve(process.cwd(), 'test-results', 'strip-reserve', String(testInfo.workerIndex))
			);
			const module = await compiled('src/lib/components/ChartReadout.svelte', 'ChartReadout', []);
			const component = (await import(pathToFileURL(module).href)).default;
			strip = (props) => render(component, { props }).body;
		});

		test('a day nothing measured holds no room in the entries of a day that was', async ({
			page
		}) => {
			// Two days that timed nothing, then one that did. The two print "No item
			// was timed from start to finish on this day" once each, in place of every
			// entry, so each entry keeps room for its own widest reading and no more.
			// Kept for the sentence, every value would wrap onto a line of its own on
			// a phone.
			const window = windowOfDays(JUDGED_THROUGH, 3, 'right');
			const rows = [failedItem('2030-06-13', 'a', 'fetch'), timedItem('2030-06-15', 'b')];
			await page.setContent(
				`<main>${strip({ readout: timeSplitColumns(timeSplit(rows, window)), name: 'time-split', maxShare: 1 })}</main>`
			);

			const entries = await page
				.locator('[data-readout="time-split"] [data-readout-row]')
				.evaluateAll((nodes) =>
					nodes.map((node) => [
						node.getAttribute('data-readout-row'),
						node.querySelector('.readout-value')?.getAttribute('style') ?? ''
					])
				);
			expect(entries).toEqual([
				['Fetch', '--readout-reserve: 11ch'],
				['Extract', '--readout-reserve: 9ch'],
				['Label call', '--readout-reserve: 11ch'],
				['Summary', '--readout-reserve: 11ch'],
				['Visual plan', '--readout-reserve: 9ch'],
				['Model, unsplit', '--readout-reserve: 9ch'],
				['Faithfulness', '--readout-reserve: 9ch'],
				['Unattributed', '--readout-reserve: 9ch']
			]);
		});
	});
});
test('a rule stated over 14 days prints no median in a 7-day window', async ({ page }) => {
	await page.goto(routeHref('pipelines'));
	await hydrated(page);

	const section = page.locator('[data-windowed="chart-drawing"]');
	await setWindow(page, RULE_DAYS);
	await expect(section.locator('[data-window-too-narrow="chart-drawing"]')).toHaveCount(0);

	await setWindow(page, 7);
	// The exact sentence, because a median of the wrong span is the same figure
	// with a different meaning and nothing on the page to say which one it is.
	await expect(section.locator('[data-window-too-narrow="chart-drawing"]')).toHaveText(
		'The rule reads 14 days. Widen the window to see it.'
	);
	await expect(section.locator('[data-charts-verdict]')).toHaveCount(0);
});
