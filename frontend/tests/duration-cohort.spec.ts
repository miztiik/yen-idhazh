/** Duration means use the same recorded clocks and never hide overlapping rows by cancellation. */
import { test, expect } from '@playwright/test';
import { durationCohort } from '../src/lib/console/duration-cohort';
import { dateSeries } from '../src/lib/charts/d3/dateSeries';
import { frame } from '../src/lib/charts/frame';
import type { Row } from '../src/lib/data/ledger';

function clock(extra: Row = {}): Row {
	return { date: '2026-09-01', fetch_ms: 1, extract_ms: 2, summarize_ms: 6,
		faithfulness_ms: 1, item_total_ms: 10, stage_gap_ms: 0,
		label_ms: 3, summary_ms: 3, visual_plan_ms: 1, ...extra };
}

test('summarization is counted once; its calls are non-additive detail', () => {
	const result = durationCohort([clock()], ['2026-09-01']);
	expect(result.series.map((series) => series.points[0].value)).toEqual([1, 2, 6, 1, 0]);
	expect(result.meanMs).toBe(10);
	expect(result.days[0].details.map((detail) => detail.value)).toEqual([3, 3, 1]);
	expect(result.series.map((series) => series.label)).not.toContain('Label call');
	expect(result.days[0]).toMatchObject({ count: 1, recorded: 1, missing: 0, invalid: 0, inconsistent: 0 });
});

test('opposite gaps retain positive unnamed duration and overlap even when their signed mean is zero', () => {
	const result = durationCohort([
		clock({ stage_gap_ms: 2, item_total_ms: 12 }),
		clock({ stage_gap_ms: -2, item_total_ms: 8 })
	], ['2026-09-01']);
	expect(result.days[0]).toMatchObject({ count: 2, elapsed: 10, unattributed: 1, overlap: 1, signedGap: 0, overlapping: 1 });
	const geometry = dateSeries(result.series, {
		frame: frame(390, 220), density: 6, valueTicks: 4, padding: 0.2, stacked: true,
		rule: { declined: 'This fixture has no settings comparison record.' },
		reconciliation: result.reconciliation
	});
	expect(geometry?.bars.reduce((sum, bar) => sum + bar.value, 0)).toBe(11);
	expect(geometry?.reconciliation?.marks[0]).toMatchObject({ elapsed: 10, overlap: 1 });
});

test('missing and non-reconciling clocks are counted explicitly and excluded from every comparable mean', () => {
	const result = durationCohort([
		clock(),
		clock({ fetch_ms: null }),
		clock({ item_total_ms: 90 }),
		clock({ fetch_ms: -1, item_total_ms: 8 })
	], ['2026-09-01']);
	expect(result.days[0]).toMatchObject({ recorded: 4, count: 1, missing: 1, inconsistent: 1, invalid: 1, elapsed: 10 });
	expect(result.series.map((series) => series.points[0].value)).toEqual([1, 2, 6, 1, 0]);
});

test('an unknown call detail does not change the stage cohort or become a zero', () => {
	const result = durationCohort([clock(), clock({ label_ms: null })], ['2026-09-01']);
	expect(result.count).toBe(2);
	expect(result.days[0].details[0]).toMatchObject({ timed: 1, value: null });
	expect(result.days[0].details[1]).toMatchObject({ timed: 2, value: 3 });
});

test('recorded zero draws elapsed at zero; an absent day has no mean or marker', () => {
	const result = durationCohort([clock({
		fetch_ms: 0, extract_ms: 0, summarize_ms: 0, faithfulness_ms: 0,
		item_total_ms: 0, label_ms: 0, summary_ms: 0, visual_plan_ms: 0
	})], ['2026-09-01', '2026-09-02']);
	expect(result.meanMs).toBe(0);
	expect(result.reconciliation.elapsed.points.map((point) => point.value)).toEqual([0, null]);
	expect(result.days[1]).toMatchObject({ count: 0, recorded: 0, elapsed: null, overlap: null });
});

test('the mean and cohort contain only the named window, with count weighting across days', () => {
	const result = durationCohort([
		clock(), clock(), clock({ date: '2026-09-02', stage_gap_ms: 3, item_total_ms: 13 }),
		clock({ date: '2026-09-03', stage_gap_ms: 90, item_total_ms: 100 })
	], ['2026-09-01', '2026-09-02']);
	expect(result.count).toBe(3);
	expect(result.recorded).toBe(3);
	expect(result.meanMs).toBe(11);
	expect(() => durationCohort([], ['2026-02-30'])).toThrow(/UTC days/);
	expect(() => durationCohort([], ['2026-09-01', '2026-09-01'])).toThrow(/distinct/);
	expect(() => durationCohort([clock({ date: null })], ['2026-09-01'])).toThrow(/UTC date/);
});
