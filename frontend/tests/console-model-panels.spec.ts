import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { grouped, swapScale } from '../src/lib/charts/series';
import {
	modelSwap,
	runLengths,
	scoreCost,
	writeTimes,
	type DayWindow
} from '../src/lib/server/model-work';

/**
 * The three panels the model route gained on 2026-08-31, and the figure that
 * moved onto it.
 *
 * Split from `console-model.spec.ts`, which protects the eleven labels and the
 * daily table. These are the panels under them: what one summary cost, how long
 * the summaries came out, and whether the model change moved anything.
 *
 * Each one is checked twice - once as arithmetic over rows built here, where a
 * percentile and a bin edge can be stated exactly, and once against the built
 * page, where the assertions are derived from what the page publishes about
 * itself rather than from a fixture's own numbers. A count typed into a test is
 * the thing a fixture change breaks.
 */

const WEEK: DayWindow = { start: '2026-08-15', end: '2026-08-21', days: 7 };

/** The three bands the committed config carries at the ends of its range, so a
 * fixture article picks an ask the way a real one does. */
const BANDS = [
	{ min_source_words: 0, target_words_min: 30, target_words_max: 45 },
	{ min_source_words: 60, target_words_min: 50, target_words_max: 90 },
	{ min_source_words: 700, target_words_min: 70, target_words_max: 150 }
];

function timed(date: string, ms: number): Record<string, string> {
	return { date, summarize_ms: String(ms) };
}

/** The daily figures sit behind a disclosure, and opening it is an action. */
async function openDailyFigures(page: Page) {
	await page.locator('[data-model-table-control] > summary').click();
	await expect(page.locator('[data-model="table"]')).toBeVisible();
}

test.describe('what one summary cost, as a distribution', () => {
	test('the bars double, the first one holds everything under a second', () => {
		const times = writeTimes(
			[
				timed('2026-08-20', 300),
				timed('2026-08-20', 20_000),
				timed('2026-08-21', 40_000),
				timed('2026-08-21', 40_000),
				timed('2026-08-21', 100_000)
			],
			WEEK
		);
		expect(times, 'a window with five timed articles drew nothing').not.toBeNull();
		const bins = (times as NonNullable<typeof times>).bins;

		// The first bar has no lower edge to print, because there is no doubling
		// below a second worth a label. Every other edge is the one before it
		// doubled, and the bars touch, so no article can fall between two of them.
		expect(bins[0].from).toBe(0);
		expect(bins[0].to).toBe(1);
		for (let index = 1; index < bins.length; index += 1) {
			expect(bins[index].from).toBe(bins[index - 1].to);
			expect(bins[index].to).toBe(bins[index].from * 2);
		}

		// Every article is in exactly one bar.
		expect(bins.reduce((total, bin) => total + bin.n, 0)).toBe(5);
		expect((times as NonNullable<typeof times>).n).toBe(5);

		// Leading and trailing empties are axis, not data - but the gap between
		// the sub-second article and the sixteen-second one is the distribution
		// saying nothing landed there, so it stays.
		expect(bins[0].n).toBeGreaterThan(0);
		expect(bins[bins.length - 1].n).toBeGreaterThan(0);
		expect(bins.some((bin) => bin.n === 0), 'the empty span between the two ends was dropped').toBe(
			true
		);

		// The curve is cumulative, so it never falls and it finishes at everything.
		const through = bins.map((bin) => bin.throughPct);
		expect(through).toEqual([...through].sort((a, b) => a - b));
		expect(through[through.length - 1]).toBe(100);
	});

	test('the two rules are taken over the values, never off a bar', () => {
		// Five values, so the median is the third and the 95th interpolates
		// between the fourth and the fifth. A percentile read out of a bin would
		// have to guess where inside a doubling it fell, and these two numbers are
		// the ones somebody quotes.
		const times = writeTimes(
			[10_000, 20_000, 30_000, 40_000, 200_000].map((ms) => timed('2026-08-20', ms)),
			WEEK
		) as NonNullable<ReturnType<typeof writeTimes>>;
		expect(times.median).toBe(30_000);
		expect(times.p95).toBeCloseTo(168_000, 6);
		expect(times.fastest).toBe(10_000);
		expect(times.slowest).toBe(200_000);
	});

	test('a window is a filter on the rows and a day outside it is not counted', () => {
		const rows = [timed('2026-08-14', 5_000), timed('2026-08-20', 5_000)];
		expect((writeTimes(rows, WEEK) as NonNullable<ReturnType<typeof writeTimes>>).n).toBe(1);
		expect(
			(
				writeTimes(rows, { start: '2026-08-08', end: '2026-08-21', days: 14 }) as NonNullable<
					ReturnType<typeof writeTimes>
				>
			).n
		).toBe(2);
	});

	test('a window nothing was timed in draws nothing, and that is not a zero', () => {
		expect(writeTimes([], WEEK)).toBeNull();
		// A row with no clock is not a summary written instantly.
		expect(writeTimes([{ date: '2026-08-20' }], WEEK)).toBeNull();
		expect(writeTimes([timed('2026-08-20', 0)], WEEK)).toBeNull();
	});

	test('the chart on the page draws one bar a bin and says what it is out of', async ({ page }) => {
		await page.goto('/console/model/');

		const chart = page.locator('[data-write-times="chart"]');
		await expect(chart, 'the model route draws no per-item cost chart').toHaveCount(1);

		const drawn = await chart.locator('[data-write-bin]').evaluateAll((nodes) =>
			nodes.map((node) => ({
				from: Number(node.getAttribute('data-write-bin')),
				n: Number(node.getAttribute('data-write-bin-n'))
			}))
		);
		expect(drawn.length, 'a distribution of one bar is a number').toBeGreaterThan(1);

		// The bars are the whole population, so they sum to the figure printed
		// under the chart. A bar chart whose bars do not add up to its own
		// denominator is two measurements pretending to be one.
		const total = Number(await chart.getAttribute('data-write-times-n'));
		expect(drawn.reduce((sum, bin) => sum + bin.n, 0)).toBe(total);
		await expect(page.locator('[data-write-times="readout"]')).toContainText(
			`${grouped(total)} summaries`
		);

		// Every edge doubles, on the page and not only in the module.
		for (let index = 1; index < drawn.length; index += 1) {
			expect(drawn[index].from).toBe(drawn[index - 1].from === 0 ? 1 : drawn[index - 1].from * 2);
		}
	});

	test('each rule prints its own value, in whole seconds', async ({ page }) => {
		await page.goto('/console/model/');

		for (const key of ['median', 'p95']) {
			const rule = page.locator(`[data-write-rule="${key}"]`);
			await expect(rule, `the ${key} rule is not drawn`).toHaveCount(1);
			const seconds = Number(await rule.getAttribute('data-write-rule-seconds'));
			expect(seconds, `the ${key} rule carries no value`).toBeGreaterThan(0);
			// The label is the number, so nobody has to read it off the axis.
			await expect(page.locator(`[data-write-rule-label="${key}"]`)).toContainText(`${seconds} s`);
		}

		// The 95th is at or past the median by definition, and a chart that drew
		// them the other way round would be drawing the wrong two values.
		const at = async (key: string) =>
			Number(await page.locator(`[data-write-rule="${key}"]`).getAttribute('x1'));
		expect(await at('p95')).toBeGreaterThanOrEqual(await at('median'));
	});

	test('the panels follow the window without claiming to be windowed surfaces', async ({
		page
	}) => {
		// `console-window.spec.ts` holds an exact sorted list of every surface that
		// declares `data-windowed`, and six rows of two plans are in flight against
		// that one line. These panels honour the control and assert it here
		// instead, which is the precedent row #4 set.
		const config = JSON.parse(
			readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
		) as { console?: { window_presets?: number[]; default_window_days?: number } };
		const presets = config.console?.window_presets ?? [7, 14, 30, 90];
		const fallback = config.console?.default_window_days ?? 30;

		await page.goto('/console/model/');
		// Every preset is disabled in the prerendered document and enabled on
		// mount, so waiting for one is waiting for the control to be able to do
		// anything at all. Clicking before that just times out.
		await expect(page.locator(`[data-window-preset="${fallback}"] input`)).toBeEnabled();

		for (const preset of presets) {
			await page.locator(`[data-window-preset="${preset}"]`).click();
			await expect(page.locator('[data-window-control]')).toHaveAttribute(
				'data-window-days',
				String(preset)
			);
			await expect(
				page.locator('[data-model-cards-note]'),
				'the cards stopped following the control'
			).toHaveAttribute('data-window-days', String(preset));
			// Every sentence under the new panels names the same span the control
			// does. Two windows on one page is the defect the oracle exists for.
			for (const readout of ['[data-write-times="readout"]', '[data-score-cost="readout"]']) {
				const found = page.locator(readout);
				if ((await found.count()) === 0) continue;
				await expect(found, `${readout} names a different span`).toContainText(`${preset} days`);
			}
		}
	});
});

test.describe('what checking a summary cost, off the critical path', () => {
	function scored(date: string, ms: string): Record<string, string> {
		return { date, score_ms: ms };
	}

	test('a zero is a row nothing timed, and it is counted as that', () => {
		// Ten committed rows carry the zero this column defaulted to before it was
		// written. Reading those as instant would say the scorer ran for nothing.
		const cost = scoreCost(
			[scored('2026-08-20', '1000'), scored('2026-08-20', '3000'), scored('2026-08-20', '0')],
			WEEK
		) as NonNullable<ReturnType<typeof scoreCost>>;
		expect(cost.n).toBe(2);
		expect(cost.untimed).toBe(1);
		expect(cost.median).toBe(2000);
	});

	test('nothing timed at all draws nothing', () => {
		expect(scoreCost([scored('2026-08-20', '0')], WEEK)).toBeNull();
		expect(scoreCost([], WEEK)).toBeNull();
	});

	test('the model route prints both figures and never the column name', async ({ page }) => {
		await page.goto('/console/model/');

		const readout = page.locator('[data-score-cost="readout"]');
		await expect(readout, 'the scoring cost is not on the model route').toHaveCount(1);
		await expect(page.locator('[data-score-cost="median"]')).toHaveText(/^(<1 s|\d+ s)$/);
		await expect(page.locator('[data-score-cost="p95"]')).toHaveText(/^(<1 s|\d+ s)$/);

		// It is here because nothing waits on it, and the sentence has to say so
		// or the reader is left with a fourth number and no place to put it.
		await expect(readout).toContainText('after the model has finished');
		expect((await readout.innerText()).toLowerCase()).not.toContain('score_ms');
	});

	test('it is no longer a stage of the run on the pipelines route', async ({ page }) => {
		await page.goto('/console/');

		// The timing chart is titled `Time per item, by stage`, so every line on it
		// is a thing the run waits on. Scoring is not one.
		await expect(page.locator('[data-stage="score"]')).toHaveCount(0);
		await expect(page.locator('[data-stage-mark="score"]')).toHaveCount(0);
		await expect(page.locator('[data-timing-note="score"]')).toHaveCount(0);

		const series = Number(
			await page.locator('[data-timing="plot"]').getAttribute('data-timing-series')
		);
		expect(series, 'the chart draws more than the three stages an item waits on').toBeLessThanOrEqual(
			3
		);
	});
});

test.describe('how long the summaries came out', () => {
	function summary(
		runId: string,
		date: string,
		words: number,
		sourceWords: number
	): Record<string, string> {
		return {
			run_id: runId,
			date,
			model_id: 'a-model',
			summary_word_count: String(words),
			source_word_count: String(sourceWords)
		};
	}

	test('a run is three marks and the ask is read off its own articles', () => {
		const runs = runLengths(
			[
				summary('2026-08-20-1', '2026-08-20', 40, 100),
				summary('2026-08-20-1', '2026-08-20', 90, 100),
				summary('2026-08-20-1', '2026-08-20', 200, 1000),
				summary('2026-08-21-1', '2026-08-21', 60, 100)
			],
			BANDS
		);
		expect(runs.map((run) => run.runId)).toEqual(['2026-08-20-1', '2026-08-21-1']);

		const first = runs[0];
		expect(first.items).toBe(3);
		expect([first.low, first.median, first.high]).toEqual([40, 90, 200]);
		// Two of its articles fall in the 60-word band and one in the 700-word
		// band, so the run was asked for 50 words at its narrowest and 150 at its
		// widest. Reading the ask off the setting alone would give one band for
		// every run whatever it read.
		expect([first.askLow, first.askHigh]).toEqual([50, 150]);
		expect([runs[1].askLow, runs[1].askHigh]).toEqual([50, 90]);
	});

	test('a run whose articles recorded no length has no ask, and says so', () => {
		const runs = runLengths(
			[{ run_id: 'r', date: '2026-08-20', summary_word_count: '70' }],
			BANDS
		);
		expect(runs).toHaveLength(1);
		expect(runs[0].askLow).toBeNull();
		expect(runs[0].askHigh).toBeNull();
	});

	test('the chart draws three marks a run and no mark an article', async ({ page }) => {
		await page.goto('/console/model/');

		const chart = page.locator('[data-run-lengths="chart"]');
		await expect(chart, 'the model route draws no per-run length chart').toHaveCount(1);

		const runs = Number(await chart.getAttribute('data-run-lengths-runs'));
		expect(runs, 'no run was drawn').toBeGreaterThan(0);

		// The whole ruling: three marks a run. The scatter this replaced drew one
		// a summary, and its dense middle rendered as a solid block that hid the
		// only marks anybody acts on.
		await expect(chart.locator('[data-run-length]')).toHaveCount(runs);
		await expect(chart.locator('[data-run-cell="range"]')).toHaveCount(runs);
		await expect(chart.locator('[data-run-cell="median"]')).toHaveCount(runs);

		const items = await chart
			.locator('[data-run-length]')
			.evaluateAll((nodes) =>
				nodes.reduce((total, node) => total + Number(node.getAttribute('data-run-items')), 0)
			);
		expect(items, 'the runs behind the marks hold no summaries').toBeGreaterThan(runs);
		// A mark an article would put `items` circles on the plot. There are none.
		await expect(chart.locator('circle')).toHaveCount(0);
	});

	test('the band prints its two bounds, so the shading can be checked', async ({ page }) => {
		await page.goto('/console/model/');

		const ask = page.locator('[data-run-ask]');
		await expect(ask, 'the band is shaded and says nothing about itself').toHaveCount(1);
		if ((await ask.getAttribute('data-run-ask')) === 'unmeasured') return;

		const low = Number(await page.locator('[data-run-ask-low]').innerText());
		const high = Number(await page.locator('[data-run-ask-high]').innerText());
		expect(low).toBeGreaterThan(0);
		expect(high).toBeGreaterThan(low);

		// The printed pair is the extent of what was actually drawn, not a
		// separate reading of the setting.
		const drawn = await page.locator('[data-run-band]').count();
		expect(drawn, 'the bounds print for a band nothing drew').toBeGreaterThan(0);
	});
});

test.describe('did the model change move anything', () => {
	function row(date: string, model: string, extra: Record<string, string> = {}) {
		return { date, model_id: model, summary_word_count: '100', source_word_count: '800', ...extra };
	}

	function pair(count: number, date: string, model: string, extra: Record<string, string> = {}) {
		return Array.from({ length: count }, () => row(date, model, extra));
	}

	test('each measure is the after over the before, and both values are kept', () => {
		const swap = modelSwap(
			[
				...pair(10, '2026-08-20', 'old', { band: 'low' }),
				...pair(10, '2026-08-21', 'new', { summary_word_count: '50' })
			],
			[
				...Array.from({ length: 10 }, () => timed('2026-08-20', 100_000)),
				...Array.from({ length: 10 }, () => timed('2026-08-21', 50_000))
			],
			BANDS,
			5
		) as NonNullable<ReturnType<typeof modelSwap>>;

		expect(swap.at).toBe('2026-08-21');
		expect(swap.before.model).toBe('old');
		expect(swap.after.model).toBe('new');
		// Both counts, always. Two models over two article sets is two
		// measurements, not a trend, and the counts are what say so.
		expect(swap.before.articles).toBe(10);
		expect(swap.after.articles).toBe(10);
		expect(swap.enough).toBe(true);

		const by = new Map(swap.measures.map((measure) => [measure.label, measure]));
		expect(by.get('Time to write one')?.ratio).toBeCloseTo(0.5, 6);
		expect(by.get('Summary length')?.before).toBe(100);
		expect(by.get('Summary length')?.after).toBe(50);
		// Every one of the ten older summaries was in the lowest band and none of
		// the newer ones was, so the rate goes to nothing.
		expect(by.get('Marked "not sure"')?.before).toBe(100);
		expect(by.get('Marked "not sure"')?.after).toBe(0);
		expect(swap.measures).toHaveLength(7);
	});

	test('a thin side draws nothing, and the counts are the whole answer', () => {
		const swap = modelSwap(
			[...pair(2, '2026-08-20', 'old'), ...pair(30, '2026-08-21', 'new')],
			[],
			BANDS,
			5
		) as NonNullable<ReturnType<typeof modelSwap>>;
		expect(swap.before.articles).toBe(2);
		expect(swap.enough).toBe(false);
	});

	test('no change of model is no panel at all', () => {
		expect(modelSwap(pair(30, '2026-08-20', 'one'), [], BANDS, 5)).toBeNull();
		expect(modelSwap([], [], BANDS, 5)).toBeNull();
	});

	test('a measure that was nothing before has no ratio, because a move away from nothing has no size', () => {
		const swap = modelSwap(
			[
				...pair(10, '2026-08-20', 'old'),
				...pair(10, '2026-08-21', 'new', { hedge_dropped: 'True' })
			],
			[],
			BANDS,
			5
		) as NonNullable<ReturnType<typeof modelSwap>>;
		const hedge = swap.measures.find((measure) => measure.label === '"Maybe" told as fact');
		expect(hedge?.before).toBe(0);
		expect(hedge?.after).toBe(100);
		expect(hedge?.ratio).toBeNull();
	});

	test('the axis is symmetric about no change, so equal moves draw equal tracks', () => {
		const scale = swapScale([50, 100, 130]);
		expect(scale.half).toBe(50);
		expect(scale.ticks).toEqual([50, 100, 150]);
		expect(scale.at(100)).toBeCloseTo(0.5, 6);
		// A fifth off and a fifth on are the same track length either side.
		expect(0.5 - scale.at(80)).toBeCloseTo(scale.at(120) - 0.5, 6);
		// A page of tiny moves still gets a readable axis rather than one that
		// magnifies a rounding error into a bar.
		expect(swapScale([99, 100, 101]).half).toBe(25);
	});

	test('the panel and the daily table agree about whether the model changed', async ({ page }) => {
		await page.goto('/console/model/');
		await openDailyFigures(page);

		// This is the assertion that bites on any fixture. The daily table draws a
		// divider row per change and the panel draws for the newest one, so a page
		// carrying one and not the other is a page disagreeing with itself.
		const dividers = await page.locator('[data-model-swap]').count();
		const section = page.locator('[data-model-swap-section]');
		await expect(section).toHaveCount(dividers > 0 ? 1 : 0);
		if (dividers === 0) return;

		// Both counts print above the chart, drawn or not.
		await expect(page.locator('[data-model-swap-counts]')).toContainText(/\d+ summaries/);

		const plot = page.locator('[data-model-swap-plot]');
		if ((await plot.count()) === 0) {
			await expect(page.locator('[data-model-swap="thin"]')).toHaveCount(1);
			return;
		}

		const rows = await plot.locator('[data-swap-row]').evaluateAll((nodes) =>
			nodes.map((node) => ({
				label: node.getAttribute('data-swap-row') ?? '',
				pct: Number(node.getAttribute('data-swap-pct')),
				fills: [...node.querySelectorAll('polygon, line[data-swap-cell="track"]')].map((mark) =>
					mark.getAttribute('fill') ?? mark.getAttribute('stroke')
				),
				values: node.querySelector('[data-swap-cell="values"]')?.textContent ?? '',
				head: node.querySelector('polygon')?.getAttribute('points') ?? ''
			}))
		);
		expect(rows.length, 'the swap panel drew no measure').toBeGreaterThan(0);

		const up = rows.filter((entry) => entry.pct > 100);
		const down = rows.filter((entry) => entry.pct < 100);
		// Direction is the arrowhead and never the hue: an arrow that rose and one
		// that fell are painted the same, so a reader has to read the shape.
		if (up.length > 0 && down.length > 0) {
			expect(new Set([...up, ...down].flatMap((entry) => entry.fills)).size).toBe(1);
		}
		for (const entry of rows) {
			// A ratio with no magnitude behind it can be a rounding error wearing a
			// percentage, so both absolute values print on the row.
			expect(entry.values, `${entry.label} printed no absolute values`).toMatch(/, then /);
			expect(entry.head, `${entry.label} drew no arrowhead`).not.toBe('');
		}
	});
});
