import { windowOfDays } from '$lib/charts/viewport';
import type { RunYieldSource } from '$lib/charts/run-yield';
import { runHealthGrid } from '$lib/console/pipelines/run-health';
import { chartDays } from '$lib/server/chart-days';
import { chartConfig, consoleConfig, runConfig } from '$lib/server/config';
import { dayMetrics, loadManifests, publishedCharts } from '$lib/server/payload';
import { windowDay } from '$lib/server/window-day';
import { visualAttemptRows } from '$lib/server/ledger-rows';
import { visualAttemptDays } from '$lib/console/pipelines/visual-attempts';

export const prerender = true;

/** Only the explicitly private BUILD_TIME panels read files here. Native item
 * clocks and evaluator readings arrive through the query door in the browser.
 * The attempt record is unpublished, so the refusal view reads it here as counts. */
export async function load() {
	const knobs = consoleConfig();
	const widest = Math.max(...knobs.window_presets);
	const day = windowDay();
	const widestSpan = windowOfDays(day, widest, knobs.today_anchor);
	const manifests = loadManifests(undefined, widest);
	const visuals = publishedCharts(undefined, widest);
	const charts = chartDays(manifests, visuals);
	const recordsByDate = dayMetrics(charts.map((row) => row.date)
		.filter((date) => date >= widestSpan.start && date <= widestSpan.end));
	const runYieldDays: RunYieldSource[] = [...recordsByDate].map(([date, record]) => ({
		date, itemsPlanned: record.itemsPlanned, itemsPublished: record.itemsPublished, itemsFailed: record.itemsFailed
	}));
	const attempts = await visualAttemptRows(widestSpan);
	const floorPct = runConfig().success_floor_pct;
	return {
		manifests, charts, publishedItems: Object.fromEntries([...visuals].map(([date, counts]) => [date, counts.items])),
		grid: runHealthGrid(manifests, floorPct), floorPct, runYieldDays,
		chart: chartConfig(), windowDay: day,
		visualAttempts: { days: visualAttemptDays(attempts.rows), read: attempts.read }
	};
}
