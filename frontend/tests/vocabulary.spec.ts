import { expect, test } from '@playwright/test';
import { frame } from '../src/lib/charts/frame';
import { type SeriesInput } from '../src/lib/charts/d3/dateSeries';
import { dateSeries } from './support/number-format';
import { partsOfOne } from '../src/lib/charts/d3/partsOfOne';
import { sparklineShape } from '../src/lib/charts/sparkline';
import { targetGeometry } from '../src/lib/charts/targetbar';

/**
 * A chart that draws a plausible but wrong shape is the failure mode worth a
 * test, because nothing about it looks broken. So every assertion here
 * recomputes the geometry from the inputs independently, and compares that to
 * what the specification says - never to a number copied out of the output.
 *
 * The actual native geometry carries the same measured values as its readout.
 */

test.describe('the target bar', () => {
	test('the marker sits at the target fraction of the track', () => {
		const t = targetGeometry(4.1, 6, 'lower-is-better');
		expect(t.empty).toBe(false);
		// Track is the larger end plus 15 percent headroom: max(4.1, 6) * 1.15.
		expect(t.markerFraction).toBeCloseTo(6 / (6 * 1.15), 10);
		expect(t.band).toBe('good');
	});

	test('past the target reads as past, whichever way better is', () => {
		expect(targetGeometry(7.2, 6, 'lower-is-better').band).toBe('past');
		expect(targetGeometry(0.03, 0.05, 'higher-is-better').band).toBe('past');
		expect(targetGeometry(0.09, 0.05, 'higher-is-better').band).toBe('good');
	});

	test('within a tenth of the target is a warning, not a pass', () => {
		// 5.6 against 6 is 6.7 percent away - inside the near band.
		expect(targetGeometry(5.6, 6, 'lower-is-better').band).toBe('near');
		expect(targetGeometry(5.0, 6, 'lower-is-better').band).toBe('good');
	});

	test('a value nobody measured draws nothing', () => {
		expect(targetGeometry(null, 6, 'lower-is-better').empty).toBe(true);
	});
});

test.describe('native dated parts', () => {
	const dates = ['2026-09-01', '2026-09-02'];
	const series: SeriesInput[] = [
		{ label: 'Fetch', token: '--chart-1', points: dates.map((date, index) => ({ date, value: [2, 0][index] })) },
		{ label: 'Extract', token: '--chart-2', points: dates.map((date, index) => ({ date, value: [1, 5][index] })) }
	];
	const options = { frame: frame(600, 240), density: 6, valueTicks: 4, padding: 0.2, rule: { changes: [], note: null } };

	test('each dated stack conserves its measured total and fixed part order', () => {
		const geometry = dateSeries(series, { ...options, stacked: true });
		expect(geometry?.dates).toEqual(dates);
		expect(dates.map((date) => geometry?.bars.filter((bar) => bar.date === date).reduce((sum, bar) => sum + bar.value, 0)))
			.toEqual([3, 5]);
		expect(geometry?.bars.filter((bar) => bar.date === dates[0]).map((bar) => [bar.label, bar.value])).toEqual([
			['Fetch', 2], ['Extract', 1]
		]);
		expect(geometry?.readout.series.map((one) => [one.label, one.values])).toEqual([
			['Fetch', ['2', '0']], ['Extract', ['1', '5']]
		]);
	});

	test('zero is measured and null is absent in both the marks and their key', () => {
		const geometry = dateSeries([
			{ label: 'Measured', token: '--chart-1', points: [{ date: dates[0], value: 0 }, { date: dates[1], value: null }] },
			{ label: 'Absent', token: '--chart-2', points: dates.map((date) => ({ date, value: null })) }
		], options);
		expect(geometry?.lines[0].points.map((point) => [point.date, point.value])).toEqual([[dates[0], 0]]);
		expect(geometry?.readout.series.map((one) => [one.label, one.values])).toEqual([['Measured', ['0', null]]]);
		expect(dateSeries([{ ...series[0], points: dates.map((date) => ({ date, value: null })) }], options)).toBeNull();
	});

	test('parts of one add to the row while overlapping readings never invent a total', () => {
		const rows = [{ label: 'One run', parts: [{ label: 'Write', value: 1 }, { label: 'Read', value: 2 }, { label: 'Other', value: 0 }] }];
		const geometry = partsOfOne(rows, { order: ['Read', 'Write', 'Other'] });
		expect(geometry?.rows[0].total).toBe(3);
		expect(geometry?.rows[0].segments.map((part) => [part.label, part.value, part.token])).toEqual([
			['Read', 2, '--chart-1'], ['Write', 1, '--chart-2']
		]);
		expect(partsOfOne(rows, { order: ['Read', 'Write', 'Other'], overlapping: true })?.rows[0].total).toBeNull();
		expect(partsOfOne([{ label: 'Quiet', parts: [{ label: 'Read', value: 0 }] }], { order: ['Read'] })).toBeNull();
	});
});

test.describe('the sparkline', () => {
	test('movement is the change against where it started', () => {
		const s = sparklineShape([100, 110, 130]);
		expect(s.empty).toBe(false);
		expect(s.movement).toBeCloseTo((130 - 100) / 100, 10);
		expect(s.rising).toBe(true);
	});

	test('a fall is a fall even when it ends above zero', () => {
		const s = sparklineShape([200, 150]);
		expect(s.rising).toBe(false);
		expect(s.movement).toBeCloseTo(-0.25, 10);
	});

	test('starting from zero has no percentage, and says so', () => {
		expect(sparklineShape([0, 5]).movement).toBeNull();
	});

	test('one point has no direction', () => {
		expect(sparklineShape([5]).empty).toBe(true);
	});

	test('the domain is the drawn extent, never zero', () => {
		const s = sparklineShape([980, 1000, 990]);
		expect(s.min).toBe(980);
		expect(s.max).toBe(1000);
	});
});
