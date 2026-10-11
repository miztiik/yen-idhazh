import { daysInWindow, windowOfDays } from '$lib/charts/viewport';
import type { ExtractionDay } from '$lib/charts/extraction-trend';
import type { RunYieldSource } from '$lib/charts/run-yield';
import { extraction } from '$lib/console/extraction';
import { runHealthGrid } from '$lib/console/pipelines/run-health';
import { chartDays } from '$lib/server/chart-days';
import { chartConfig, consoleConfig, runConfig } from '$lib/server/config';
import { dayMetrics, loadManifests, publishedCharts } from '$lib/server/payload';
import { windowDay } from '$lib/server/window-day';

export const prerender = true;

/** Only the explicitly private BUILD_TIME panels read files here. Native item
 * clocks and evaluator readings arrive through the query door in the browser. */
export function load() {
	const knobs = consoleConfig();
	const widest = Math.max(...knobs.window_presets);
	const day = windowDay();
	const widestSpan = windowOfDays(day, widest, knobs.today_anchor);
	const manifests = loadManifests(undefined, widest);
	const visuals = publishedCharts(undefined, widest);
	const charts = chartDays(manifests, visuals);
	const recordsByDate = dayMetrics(charts.map((row) => row.date)
		.filter((date) => date >= widestSpan.start && date <= widestSpan.end));
	const extractionPublishedByWindow = daysInWindow(widestSpan).flatMap((through) => knobs.window_presets.map((days) => {
		const span = windowOfDays(through, days, knobs.today_anchor);
		const inside = charts.filter((row) => row.date >= span.start && row.date <= span.end);
		const shaped = extraction(inside.map((row) => recordsByDate.get(row.date)?.extraction ?? null), days);
		return {
			through, days, measuredDays: shaped.measuredDays, unused: shaped.unused,
			chartablePublished: shaped.chartablePublished, unusedPct: shaped.unusedPct
		};
	}));
	const extractionDays: ExtractionDay[] = [...recordsByDate].flatMap(([date, record]) => {
		const block = record.extraction;
		return block === null || block === undefined ? [] :
			[{ date, chartable: block.chartable, charted: block.chartableCharted }];
	});
	const runYieldDays: RunYieldSource[] = [...recordsByDate].map(([date, record]) => ({
		date, itemsPlanned: record.itemsPlanned, itemsPublished: record.itemsPublished, itemsFailed: record.itemsFailed
	}));
	const floorPct = runConfig().success_floor_pct;
	return {
		manifests, charts, publishedItems: Object.fromEntries([...visuals].map(([date, counts]) => [date, counts.items])),
		grid: runHealthGrid(manifests, floorPct), floorPct, extractionPublishedByWindow, extractionDays, runYieldDays,
		chart: chartConfig(), windowDay: day
	};
}
