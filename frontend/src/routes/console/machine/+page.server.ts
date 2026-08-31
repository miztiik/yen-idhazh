import { renderToSvg } from '$lib/server/chart-render';
import {
	cacheByDay,
	cacheChart,
	clockAgreement,
	clocksChart,
	contextHeadroom,
	costOf,
	percentileChart,
	percentileCurves,
	readingAgainstWriting,
	shardBoard,
	tokenChart,
	tokensByRun,
	type CostRate
} from '$lib/charts/machine';
import { defaultWindow } from '$lib/charts/viewport';
import {
	chartConfig,
	consoleConfig,
	inferenceConfig,
	observabilityConfig,
	runConfig
} from '$lib/server/config';
import { itemHealthRows } from '$lib/server/payload';
import { CLOCKS_AGREE_WITHIN_PCT, loadMachineCounters, machineLimits } from '$lib/server/runtime-counters';

export const prerender = true;

/** The span of a figure across the runs that reported it, and how many did.
 *
 * A range and not a mean: the whole finding this route exists to publish is
 * that two shards of one run differ by more than 4x, and a mean of a lottery
 * reports neither end of it. `from` of zero means nothing measured it, which is
 * a different fact from a measurement of zero.
 */
function spanOf(
	values: readonly (number | null)[]
): { low: number | null; high: number | null; from: number; outOf: number } {
	const known = values.filter((value): value is number => value !== null);
	return {
		low: known.length === 0 ? null : Math.min(...known),
		high: known.length === 0 ? null : Math.max(...known),
		from: known.length,
		outOf: values.length
	};
}

/** What the model server counted, read once at build time.
 *
 * The whole route reads `state/runtime-counters.csv` and `state/item-health/`,
 * both of which sit under `state/` and are never published, through
 * `$lib/server/` - the same place and for the same reason `model-work.ts` reads
 * `state/scores.csv`. No cell of either crosses to a reader and this route adds
 * no published telemetry column.
 *
 * **Every figure here reads one fixed span**, `console.default_window_days`.
 * There is no days control on this route yet, so the span is stated on the page
 * rather than offered as a choice - a figure whose span a reader cannot see is
 * worse than one he cannot change. The bound is what stops a chart growing a
 * column per run forever as the ledgers fill.
 */
export async function load() {
	const console_ = consoleConfig();
	const chart = chartConfig();
	const limits = machineLimits();
	const counters = loadMachineCounters();
	const health = itemHealthRows().rows;
	const today = new Date().toISOString().slice(0, 10);

	const dates = [
		...new Set([...counters.runs.map((run) => run.date), ...health.map((row) => row.date ?? '')])
	].filter((date) => date !== '');
	const window = defaultWindow(dates, today, console_);
	const inWindow = <T extends { date: string }>(rows: readonly T[]): T[] =>
		rows.filter((row) => row.date >= window.start && row.date <= window.end);

	// Newest first, as the reader hands them over. The board and the two splits
	// read the newest run; everything else reads the span.
	const runs = inWindow(counters.runs);
	const newest = runs[0] ?? null;
	const healthRows = health.filter(
		(row) => (row.date ?? '') >= window.start && (row.date ?? '') <= window.end
	);

	const board = shardBoard(newest, limits.jobTimeoutSeconds);
	const split = readingAgainstWriting(newest);
	const cacheDays = cacheByDay(runs);
	const cache = cacheChart(cacheDays);
	const context = contextHeadroom(runs, limits.contextWindow);
	const clocks = clockAgreement(newest, healthRows, CLOCKS_AGREE_WITHIN_PCT);
	const clocksPlot = clocksChart(clocks.pairs);

	// The newest day the item ledger reached, which is not always the newest day
	// the counters reached: a run can publish before its shards scrape.
	const percentileDate =
		[...new Set(healthRows.map((row) => row.date ?? ''))].filter((date) => date !== '').sort().at(-1) ??
		null;
	const percentiles = percentileCurves(healthRows, percentileDate, console_.min_attempts_for_rate);
	const percentilePlot = percentileChart(percentiles.curves);

	const tokens = tokensByRun(healthRows);
	const observability = observabilityConfig();
	const rate: CostRate = {
		currency: observability.cost_currency,
		inputPerMillion: observability.cost_input_per_million,
		outputPerMillion: observability.cost_output_per_million
	};
	const totals = tokens.reduce(
		(carry, run) => ({
			input: carry.input + run.input,
			output: carry.output + run.output,
			items: carry.items + run.items
		}),
		{ input: 0, output: 0, items: 0 }
	);
	const inputPlot = tokenChart(tokens, (run) => run.input, 'prompt tokens', '--chart-1');
	const outputPlot = tokenChart(tokens, (run) => run.output, 'written tokens', '--chart-4');

	// Batching is one line of text and not a chart. It reads 1.0 on every row the
	// ledger holds, because `models.inference.n_parallel` is 1, and it earns a
	// chart the day that knob moves.
	const slots = runs
		.map((run) => run.slotsPerDecode)
		.filter((reading) => reading.value !== null);
	const batching = {
		highest: slots.length === 0 ? null : Math.max(...slots.map((reading) => reading.value ?? 0)),
		from: slots.length,
		outOf: runs.length
	};

	// Three cells that landed on 2026-08-30 and that no page has printed. The
	// newest run's own reading, and the span across the window beside it - one
	// says what happened today and the other says whether today was unusual.
	const host = {
		runId: newest?.runId ?? null,
		cpuModels: newest?.cpuModels ?? null,
		cpuBusy: newest?.lowestCpuBusyPct ?? null,
		peakRss: newest?.peakRssBytes ?? null,
		modelLoad: newest?.slowestModelLoadMs ?? null,
		cpuBusySpan: spanOf(runs.map((run) => run.lowestCpuBusyPct.value)),
		peakRssSpan: spanOf(runs.map((run) => run.peakRssBytes.value)),
		modelLoadSpan: spanOf(runs.map((run) => run.slowestModelLoadMs.value))
	};

	// Drawn on the server so every mark is on the page before a script runs, and
	// stays there if none ever does. Colour leaves as a custom-property
	// reference, so both themes work with no JavaScript at all.
	//
	// Only the SVG crosses. The `option` a live chart hydrates from is rebuilt in
	// the component from the same arrays, because everything a `load` returns is
	// serialised into the prerendered document - and an option carries the
	// magenta sentinels `toCssVariables` swaps out of the SVG, which
	// `charts.spec.ts` fails the build over. It also keeps the payload to the
	// numbers rather than to a drawing of them.
	const draw = async (
		plot: { option: import('echarts').EChartsOption; empty: boolean },
		height: number
	) => (plot.empty ? null : await renderToSvg(plot.option, { width: chart.width_px, height }));

	return {
		window: { days: console_.default_window_days, start: window.start, end: window.end },
		board,
		// Never dropped silently: a run whose rows cannot be made into one run is
		// named on the page with the reason, because a run count that quietly
		// excludes one is a run count nobody can check.
		refused: inWindow(counters.refused),
		runsRead: runs.length,
		split,
		cacheDays,
		cacheSvg: await draw(cache, chart.height_px),
		context,
		clocks,
		clocksSvg: await draw(clocksPlot, chart.height_px),
		batching,
		host,
		percentiles,
		percentileSvg: await draw(percentilePlot, chart.height_px),
		tokens,
		tokenTotals: totals,
		inputSvg: await draw(inputPlot, chart.height_px),
		outputSvg: await draw(outputPlot, chart.height_px),
		rate,
		windowCost: costOf(totals, rate),
		limits,
		shardTimeoutMinutes: runConfig().shard_timeout_minutes,
		contextWindow: inferenceConfig().n_ctx,
		clocksTolerancePct: CLOCKS_AGREE_WITHIN_PCT,
		chart
	};
}
