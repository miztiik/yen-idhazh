/** The native extraction yield keeps every calendar day, zero and unknown on one scale. */
import { expect, test } from '@playwright/test';
import { extractionYield, type ExtractionDay } from '../src/lib/console/pipelines/extraction';
import { dateSeries } from '../src/lib/charts/d3/dateSeries';
import { frame } from '../src/lib/charts/frame';

const options = {
	frame: frame(760, 220), density: 6, valueTicks: 5, padding: 0.2,
	rule: { changes: [], note: null }
};
function day(date: string, chartable: number, charted: number): ExtractionDay {
	return { date, chartable, charted };
}
function yieldIn(days: ExtractionDay[], start: string, end: string) {
	return extractionYield(days, { start, end });
}

test('the trend draws the selected calendar oldest first, regardless of input order', () => {
	const series = yieldIn([
		day('2026-09-11', 160, 17), day('2026-09-09', 225, 20), day('2026-09-10', 181, 18)
	], '2026-09-09', '2026-09-11');
	expect(series[0].points).toEqual([
		{ date: '2026-09-09', value: 225 }, { date: '2026-09-10', value: 181 }, { date: '2026-09-11', value: 160 }
	]);
	expect(dateSeries(series, options)?.dates).toEqual(['2026-09-09', '2026-09-10', '2026-09-11']);
});

test('both series retain every measured point, including a flat measured zero', () => {
	const series = yieldIn([
		day('2026-09-15', 149, 0), day('2026-09-16', 172, 0), day('2026-09-17', 117, 0)
	], '2026-09-15', '2026-09-17');
	expect(series.map((one) => one.points.map((point) => point.value))).toEqual([[149, 172, 117], [0, 0, 0]]);
	const geometry = dateSeries(series, options)!;
	expect(geometry.lines).toHaveLength(2);
	expect(geometry.lines.map((line) => line.points.length)).toEqual([3, 3]);
});

test('one measured day draws two singleton points, not an empty plot', () => {
	const geometry = dateSeries(yieldIn([day('2026-09-17', 117, 0)], '2026-09-17', '2026-09-17'), options)!;
	expect(geometry.dates).toEqual(['2026-09-17']);
	expect(geometry.lines.map((line) => line.points.map(({ value, alone }) => ({ value, alone })))).toEqual([
		[{ value: 117, alone: true }], [{ value: 0, alone: true }]
	]);
});

test('a calendar day nobody measured stays unknown and an unmeasured window has no geometry', () => {
	const empty = yieldIn([], '2026-09-16', '2026-09-17');
	expect(empty.map((one) => one.points.map((point) => point.value))).toEqual([[null, null], [null, null]]);
	expect(dateSeries(empty, options)).toBeNull();
	const measured = dateSeries(yieldIn([day('2026-09-17', 117, 0)], '2026-09-16', '2026-09-17'), options)!;
	expect(measured.dates).toEqual(['2026-09-16', '2026-09-17']);
	expect(measured.lines[0].points).toHaveLength(1);
	expect(measured.lines[0].points[0].alone).toBe(true);
});

test('both counts share one data-fitted domain and the authored peaks remain comparable', () => {
	const series = yieldIn([day('2026-09-09', 225, 20), day('2026-09-13', 123, 4)], '2026-09-09', '2026-09-13');
	const geometry = dateSeries(series, options)!;
	const sameValue = dateSeries(yieldIn([day('2026-09-09', 20, 20)], '2026-09-09', '2026-09-09'), options)!;
	expect(sameValue.lines[0].points[0].y).toBe(sameValue.lines[1].points[0].y);
	expect(geometry.axis.domain[1]).toBeGreaterThanOrEqual(225);
	expect(geometry.axis.domain[1]).toBeLessThan(1000);
	const peaks = series.map((one) => Math.max(...one.points.map((point) => point.value ?? 0)));
	expect(peaks).toEqual([225, 20]);
	expect(peaks[0] / peaks[1]).toBeLessThan(20);
});
