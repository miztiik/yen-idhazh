/** What does each published day's chart-drawing row hold, over runs and payload counts a test writes? */
import { expect, test } from '@playwright/test';
import { chartDays } from '../src/lib/server/chart-days';
import type { RunRecord, RunSummary } from '../src/lib/server/payload';
import { readChartEvidence } from '../src/lib/chart-evidence';

/** One run of a day, with the planner's counts a case names and nothing else. */
function run(date: string, n: number, cells: Partial<RunRecord>): RunRecord {
	return {
		runId: `${date}-${n}`,
		n,
		status: 'completed',
		planned: 0,
		succeeded: 0,
		failed: 0,
		skipped: 0,
		startedAt: `${date}T06:00:00Z`,
		sourceListStale: false,
		shards: null,
		decided: 0,
		prefiltered: 0,
		chartsDrafted: 0,
		chartEvidence: null,
		decisionMs: null,
		inputs: null,
		...cells
	};
}

function day(date: string, records: RunRecord[]): RunSummary {
	return { date, runs: records.length, planned: 0, failed: 0, siteBytes: 0, siteFiles: 0, models: [], records };
}

test('chart evidence keeps unmeasured history separate from measured zero figures', () => {
	expect(readChartEvidence(undefined)).toBeNull();
	expect(readChartEvidence(null)).toBeNull();
	const empty = {
		displayed_values: 0, derived_values: 0, trusted_values: 0,
		derived_value_rate: null, trusted_data_ratio: null
	};
	expect(readChartEvidence(empty)).toEqual(empty);
	const measured = {
		displayed_values: 7, derived_values: 1, trusted_values: 6,
		derived_value_rate: 1 / 7, trusted_data_ratio: 6 / 7
	};
	expect(readChartEvidence(measured)).toEqual(measured);
	for (const invalid of [
		{},
		{ ...empty, derived_value_rate: 0 },
		{ ...measured, derived_values: 1.5 },
		{ ...measured, trusted_values: 8 },
		{ ...measured, derived_value_rate: 1 / 6 },
		{ ...measured, trusted_data_ratio: null }
	]) expect(() => readChartEvidence(invalid)).toThrow(/chart_evidence/);
});

test('a day sums its runs, and only a run that timed the planner adds minutes', () => {
	const rows = chartDays(
		[
			// Two runs: one timed the planner at 3 minutes, and one wrote no time down.
			day('2030-06-15', [
				run('2030-06-15', 1, { decided: 5, prefiltered: 3, chartsDrafted: 3, decisionMs: 180_000 }),
				run('2030-06-15', 2, { decided: 1, chartsDrafted: 1, decisionMs: null })
			]),
			// No run timed the planner, so the day has no minutes and no cost a chart.
			day('2030-06-14', [run('2030-06-14', 1, { decided: 2, prefiltered: 1, chartsDrafted: 1 })]),
			// Timed, and no chart reached the page: minutes, and no cost a chart.
			day('2030-06-13', [run('2030-06-13', 1, { decided: 1, chartsDrafted: 1, decisionMs: 60_000 })]),
			// A day the payload counts do not name published nothing a reader can see.
			day('2030-06-12', [run('2030-06-12', 1, { decisionMs: 120_000 })])
		],
		new Map([
			['2030-06-15', { items: 8, charts: 2 }],
			['2030-06-14', { items: 4, charts: 1 }],
			['2030-06-13', { items: 3, charts: 0 }]
		])
	);
	expect(rows).toEqual([
		{ date: '2030-06-15', reached: 9, asked: 6, drafted: 4, published: 2, items: 8, plannerMinutes: 3, minutesPerChart: 1.5 },
		{ date: '2030-06-14', reached: 3, asked: 2, drafted: 1, published: 1, items: 4, plannerMinutes: null, minutesPerChart: null },
		{ date: '2030-06-13', reached: 1, asked: 1, drafted: 1, published: 0, items: 3, plannerMinutes: 1, minutesPerChart: null },
		{ date: '2030-06-12', reached: 0, asked: 0, drafted: 0, published: 0, items: 0, plannerMinutes: 2, minutesPerChart: null }
	]);
});
