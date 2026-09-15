/** Where an item's time went: the arithmetic under the console's time-split panel.
 *
 * The panel draws eight bands as one stacked column, so the one thing that can
 * make it lie is bands that do not add up to the bar. Everything here is that
 * claim from a different angle: per item, per day, with a step unmeasured, with
 * two clocks that disagreed, and through the chart option the engine is handed.
 *
 * Every row is BUILT rather than read off a committed shard. A test that walks
 * the archive costs more every published day (Guardrail #12), and the shapes
 * that matter most here - a run with no per-call split, a negative gap - are
 * ones the committed archive has never produced.
 */

import { expect, test } from '@playwright/test';

import {
	TELEMETRY_COLUMNS,
	TIME_BANDS,
	itemTimeBands,
	timeSplit,
	type TelemetryRow
} from '../src/lib/charts/series';
import { timeSplitChart, timeSplitColumns } from '../src/lib/charts/glance';
import { telemetryRow } from './support/telemetry-row';

/** One item whose every step was timed and whose two calls were published.
 *
 * The numbers are chosen so each band is distinct and the identity the panel
 * rests on holds: fetch + extract + summarize + faithfulness + gap = total.
 */
function fullyTimed(over: Partial<TelemetryRow> = {}): TelemetryRow {
	return telemetryRow({
		fetch_ms: 100,
		extract_ms: 20,
		summarize_ms: 600,
		label_ms: 150,
		summary_ms: 430,
		visual_plan_ms: 60,
		faithfulness_ms: 30,
		item_total_ms: 800,
		stage_gap_ms: 50,
		...over
	});
}

function sum(values: readonly number[]): number {
	return values.reduce((total, value) => total + value, 0);
}

test('every band the panel draws is a cell the projection publishes', () => {
	// The panel is worth nothing if it reads a column the browser never receives.
	// This is the tie between the two halves of the change: widen the contract and
	// the header below grows, drop a cell from it and this goes red rather than
	// the chart quietly drawing zeroes.
	const read = [
		'fetch_ms',
		'extract_ms',
		'summarize_ms',
		'label_ms',
		'summary_ms',
		'visual_plan_ms',
		'faithfulness_ms',
		'item_total_ms',
		'stage_gap_ms'
	];
	for (const name of read) {
		expect(TELEMETRY_COLUMNS, `${name} is not published`).toContain(name);
	}
});

test('one item"s bands add up to its whole clock', () => {
	const row = fullyTimed();

	const bands = itemTimeBands(row);

	expect(bands).toHaveLength(TIME_BANDS.length);
	expect(sum(bands)).toBe(row.item_total_ms);
	// Named, so a band that moved is a band this test can point at.
	const at = (key: string) => bands[TIME_BANDS.findIndex((band) => band.key === key)];
	expect(at('fetch')).toBe(100);
	expect(at('extract')).toBe(20);
	expect(at('label')).toBe(150);
	expect(at('summary')).toBe(370); // 430 the call took, less the 60 the plan did
	expect(at('plan')).toBe(60);
	expect(at('model')).toBe(20); // 600 the stage took, less the 580 the two calls did
	expect(at('faithfulness')).toBe(30);
	expect(at('gap')).toBe(50);
});

test('a run that published no per-call split keeps its model time', () => {
	// The whole summarize stage lands in `model` rather than in `gap`, and that is
	// the honest reading: the stage was timed, the calls inside it were not. Every
	// row the projection published before 2026-09-15 is this shape, so a split
	// that lost their model time would have drawn the archive wrong.
	const row = fullyTimed({ label_ms: null, summary_ms: null, visual_plan_ms: null });

	const bands = itemTimeBands(row);
	const at = (key: string) => bands[TIME_BANDS.findIndex((band) => band.key === key)];

	expect(at('model')).toBe(600);
	expect(at('label')).toBe(0);
	expect(at('gap')).toBe(50);
	expect(sum(bands)).toBe(800);
});

test('a negative gap stays negative', () => {
	// Below zero means two named stages overlapped or two clocks disagreed. The
	// bar drawn from it looks wrong, which is correct - clamping it would hide
	// the one fault this band exists to show.
	const row = fullyTimed({ item_total_ms: 700, stage_gap_ms: -50 });

	const bands = itemTimeBands(row);

	expect(bands[TIME_BANDS.findIndex((band) => band.key === 'gap')]).toBe(-50);
	expect(sum(bands)).toBe(700);
});

test('a day is the mean item, and the bands still add up to the bar', () => {
	// Means, not medians, and this is the test that says why. Medians do not add:
	// a stack of per-stage medians draws a column whose height is not the median
	// item, so every share it prints is wrong by an amount nobody can see.
	const rows = [
		fullyTimed({ date: '2026-09-14' }),
		fullyTimed({
			date: '2026-09-14',
			item_id: 'ai-02',
			fetch_ms: 300,
			extract_ms: 40,
			summarize_ms: 1200,
			label_ms: 200,
			summary_ms: 900,
			visual_plan_ms: 100,
			faithfulness_ms: 60,
			item_total_ms: 1700,
			stage_gap_ms: 100
		})
	];

	const days = timeSplit(rows, { start: '2026-09-14', end: '2026-09-14' });

	expect(days).toHaveLength(1);
	expect(days[0].items).toBe(2);
	expect(days[0].total).toBe(1250); // (800 + 1700) / 2
	expect(sum(days[0].ms)).toBeCloseTo(days[0].total, 6);
	expect(days[0].ms[TIME_BANDS.findIndex((band) => band.key === 'fetch')]).toBe(200);
});

test('an item nothing timed is not in the average', () => {
	// Counting it would divide real milliseconds by items nobody timed, and every
	// band would shrink on the day a new instrument was rolled out - which reads
	// as the pipeline getting faster.
	const rows = [
		fullyTimed({ date: '2026-09-14' }),
		telemetryRow({ date: '2026-09-14', item_id: 'ai-02' })
	];

	const days = timeSplit(rows, { start: '2026-09-14', end: '2026-09-14' });

	expect(days[0].items).toBe(1);
	expect(days[0].total).toBe(800);
});

test('a day with no timed row keeps its place on the axis', () => {
	// Dropped from the array, it would shift every day after it and draw a gap as
	// if it were the next day along.
	const rows = [fullyTimed({ date: '2026-09-14' })];

	const days = timeSplit(rows, { start: '2026-09-13', end: '2026-09-15' });

	expect(days.map((day) => day.date)).toEqual(['2026-09-13', '2026-09-14', '2026-09-15']);
	expect(days.map((day) => day.items)).toEqual([0, 1, 0]);
	expect(days[0].ms).toEqual(TIME_BANDS.map(() => 0));
});

test('the chart hands the engine one series a band, and the column is the total', () => {
	const rows = [fullyTimed({ date: '2026-09-14' })];
	const days = timeSplit(rows, { start: '2026-09-14', end: '2026-09-14' });

	const chart = timeSplitChart(days);

	expect(chart.empty).toBe(false);
	const series = chart.option.series as { name: string; data: number[] }[];
	// `stacked` drops a band that is zero on every column, so the labels drawn are
	// the non-zero ones in band order rather than all eight.
	expect(series.map((one) => one.name)).toEqual(
		TIME_BANDS.filter((_, index) => days[0].ms[index] !== 0).map((band) => band.label)
	);
	expect(chart.totals).toEqual([800]);
	expect(sum(series.map((one) => one.data[0]))).toBe(800);
});

test('the strip prints every band with its share', () => {
	// A stack is the hardest shape to read one band off, so the band a reader
	// wants is the one the eye cannot measure. All eight, every time, and each
	// with the share a reader would otherwise have to divide off the chart.
	const rows = [fullyTimed({ date: '2026-09-14' })];
	const days = timeSplit(rows, { start: '2026-09-14', end: '2026-09-14' });

	const columns = timeSplitColumns(days);

	expect(columns).toHaveLength(1);
	expect(columns[0].date).toBe('2026-09-14');
	expect(columns[0].rows.map((row) => row.label)).toEqual(TIME_BANDS.map((band) => band.label));
	expect(columns[0].rows[0].value).toBe('100 ms, 13%');
	// Bound to the band and never to its size, so a colour cannot move when the
	// mix does.
	expect(new Set(columns[0].rows.map((row) => row.colour)).size).toBe(TIME_BANDS.length);
});

test('a day that timed nothing prints milliseconds and no share', () => {
	// Zero over zero is not zero percent. A share taken against a total of nothing
	// is a number nobody measured.
	const days = timeSplit([], { start: '2026-09-14', end: '2026-09-14' });

	const columns = timeSplitColumns(days);

	expect(columns[0].rows.every((row) => row.value === '0 ms')).toBe(true);
	expect(timeSplitChart(days).empty).toBe(true);
});
