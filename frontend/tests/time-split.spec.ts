/** Authored clocks test the actual native cohort, additive stages and non-additive calls. */
import { expect, test } from '@playwright/test';
import { TELEMETRY_COLUMNS, type TelemetryRow } from '../src/lib/charts/series';
import { nativeTimeSplit, timeSplitReadout } from '../src/lib/console/pipelines/item-time-split';
import { dateSeries, numberFormat } from './support/number-format';
import { frame } from '../src/lib/charts/frame';
import { telemetryRow } from './support/telemetry-row';

function fullyTimed(over: Partial<TelemetryRow> = {}) {
	return { ...telemetryRow({
		date: '2026-09-14', fetch_ms: 100, extract_ms: 20, summarize_ms: 600,
		label_ms: 150, summary_ms: 430, visual_plan_ms: 60, faithfulness_ms: 30,
		item_total_ms: 800, stage_gap_ms: 50, ...over
	}) };
}
const calendar = ['2026-09-14'];
const options = {
	frame: frame(760, 220), density: 6, valueTicks: 5, padding: 0.2,
	rule: { changes: [], note: null }, stacked: true
};
const sum = (values: readonly number[]) => values.reduce((total, value) => total + value, 0);

test('every stage, elapsed, overlap and call detail is a published telemetry cell', () => {
	for (const name of ['fetch_ms', 'extract_ms', 'summarize_ms', 'label_ms', 'summary_ms',
		'visual_plan_ms', 'faithfulness_ms', 'item_total_ms', 'stage_gap_ms']) {
		expect(TELEMETRY_COLUMNS, `${name} is not published`).toContain(name);
	}
});

test('one item adds summarize once and conserves its whole clock', () => {
	const split = nativeTimeSplit([fullyTimed()], calendar);
	expect(split.series.map((one) => [one.label, one.points[0].value])).toEqual([
		['Fetch', 100], ['Extract', 20], ['Summarize', 600], ['Checking', 30], ['Unattributed duration', 50]
	]);
	expect(sum(split.series.map((one) => one.points[0].value!))).toBe(800);
	expect(split.days[0].elapsed).toBe(800);
	expect(split.days[0].details.map((detail) => detail.value)).toEqual([150, 430, 60]);
});

test('a run with no per-call split keeps all its model time and leaves calls unknown', () => {
	const split = nativeTimeSplit([fullyTimed({ label_ms: null, summary_ms: null, visual_plan_ms: null })], calendar);
	expect(split.count).toBe(1);
	expect(split.series[2].points[0].value).toBe(600);
	expect(split.days[0].details.map((detail) => detail.value)).toEqual([null, null, null]);
	expect(sum(split.series.map((one) => one.points[0].value!))).toBe(800);
});

test('a negative gap retains stage time and is deducted explicitly as overlap', () => {
	const split = nativeTimeSplit([fullyTimed({ item_total_ms: 700, stage_gap_ms: -50 })], calendar);
	expect(split.days[0].signedGap).toBe(-50);
	expect(split.days[0].unattributed).toBe(0);
	expect(split.days[0].overlap).toBe(50);
	expect(sum(split.series.map((one) => one.points[0].value!)) - split.days[0].overlap!).toBe(700);
	const geometry = dateSeries(split.series, { ...options, reconciliation: split.reconciliation })!;
	expect(geometry.reconciliation?.marks[0]).toMatchObject({ date: calendar[0], elapsed: 700, overlap: 50, top: geometry.axis.scale(750) });
});

test('a day is the mean item, and its stages still reconcile with the mean clock', () => {
	const split = nativeTimeSplit([fullyTimed(), fullyTimed({
		item_id: 'ai-02', fetch_ms: 300, extract_ms: 40, summarize_ms: 1200,
		label_ms: 200, summary_ms: 900, visual_plan_ms: 100, faithfulness_ms: 60,
		item_total_ms: 1700, stage_gap_ms: 100
	})], calendar);
	expect(split.days).toHaveLength(1);
	expect(split.count).toBe(2);
	expect(split.days[0].elapsed).toBe(1250);
	expect(sum(split.series.map((one) => one.points[0].value!))).toBeCloseTo(1250, 6);
	expect(split.series[0].points[0].value).toBe(200);
});

test('a row nothing timed is recorded but excluded from the comparable mean', () => {
	const split = nativeTimeSplit([fullyTimed(), { date: calendar[0] }], calendar);
	expect(split.recorded).toBe(2);
	expect(split.count).toBe(1);
	expect(split.days[0].missing).toBe(1);
	expect(split.meanMs).toBe(800);
});

test('an unmeasured calendar day remains unknown, not a measured zero', () => {
	const days = ['2026-09-13', ...calendar, '2026-09-15'];
	const split = nativeTimeSplit([fullyTimed()], days);
	expect(split.days.map((day) => day.date)).toEqual(days);
	expect(split.days.map((day) => day.count)).toEqual([0, 1, 0]);
	expect(split.series.map((one) => one.points[0].value)).toEqual([null, null, null, null, null]);
	const geometry = dateSeries(split.series, { ...options, reconciliation: split.reconciliation })!;
	expect(geometry.bars.every((bar) => bar.date === calendar[0])).toBe(true);
	expect(dateSeries(nativeTimeSplit([], days).series, options)).toBeNull();
});

test('the actual native stack contains only additive stages and totals the elapsed clock', () => {
	const split = nativeTimeSplit([fullyTimed()], calendar);
	const geometry = dateSeries(split.series, { ...options, reconciliation: split.reconciliation })!;
	expect(geometry.bars.map((bar) => bar.label)).toEqual(split.series.map((one) => one.label));
	expect(sum(geometry.bars.map((bar) => bar.value))).toBe(800);
	expect(geometry.reconciliation?.marks[0]).toMatchObject({ elapsed: 800, overlap: 0, top: geometry.axis.scale(800) });
});

test('the readout names every stage, calls as detail, and the complete-clock divisor', () => {
	const strip = timeSplitReadout(nativeTimeSplit([fullyTimed()], calendar), numberFormat);
	expect(strip.columns).toEqual(calendar);
	expect(strip.series.map((one) => one.label)).toEqual([
		'Fetch', 'Extract', 'Summarize', 'Checking', 'Unattributed duration',
		'Elapsed time', 'Overlap', 'Label call', 'Summary call', 'Visual plan', 'Complete clocks'
	]);
	expect(strip.series.map((one) => one.values[0])).toEqual([
		'0.1 s', '0.02 s', '0.6 s', '0.03 s', '0.05 s', '0.8 s', '0 s',
		'0.15 s', '0.43 s', '0.06 s', '1 of 1'
	]);
});

test('a day without a complete clock prints unknown durations and a zero complete-clock count', () => {
	const strip = timeSplitReadout(nativeTimeSplit([fullyTimed()], ['2026-09-13', ...calendar]), numberFormat);
	expect(strip.notMeasured).toBe('Not measured for the complete cohort');
	expect(strip.series.slice(0, 10).map((one) => one.values[0])).toEqual(Array(10).fill(null));
	expect(strip.series[10].values).toEqual(['0 of 0', '1 of 1']);
	expect(strip.series[0].values[1]).toBe('0.1 s');
});

test('a fully timed zero remains measured and does not disappear into the missing cohort', () => {
	const split = nativeTimeSplit([fullyTimed({
		fetch_ms: 0, extract_ms: 0, summarize_ms: 0, faithfulness_ms: 0, item_total_ms: 0, stage_gap_ms: 0
	})], calendar);
	expect(split.count).toBe(1);
	expect(split.meanMs).toBe(0);
	expect(split.series.map((one) => one.points[0].value)).toEqual([0, 0, 0, 0, 0]);
});
