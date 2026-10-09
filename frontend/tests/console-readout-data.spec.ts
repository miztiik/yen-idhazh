/** How a chart builds its readout without a second key or invented readings. */
import { expect, test } from '@playwright/test';
import { readoutOf } from '../src/lib/charts/readout';
import { clocksChart } from '../src/lib/charts/machine';
import { stacked } from '../src/lib/charts/stacked';

test.describe('the strip is the key', () => {
	test('no chart option carries a legend', () => {
		// The engine drew a key above three of its charts. The strip below the
		// plot prints the same swatch and the same label at the column the reader
		// is on, so the key was the same pair a second time - and a second copy is
		// how two of them drift.
		const stack = stacked(
			['Mon', 'Tue'],
			[
				{ label: 'fetch', token: '--chart-1', values: [2, 1] },
				{ label: 'extract', token: '--chart-2', values: [1, 5] }
			]
		);
		expect(stack.option.legend, 'the stacked chart draws a legend').toBeUndefined();

		const clocks = clocksChart([
			{ label: 'shard 0', ledger: 12.5, server: 12.4, gapPct: 0.8, agrees: true },
			{ label: 'shard 1', ledger: 9.5, server: 9.9, gapPct: 4.0, agrees: true }
		]);
		expect(clocks.option.legend, 'the clock chart draws a legend').toBeUndefined();
	});

	test('a strip is built from the labels, so it cannot be a different length', () => {
		const strip = readoutOf({
			type: 'dateSeries',
			columns: ['Mon', 'Tue', 'Wed'],
			series: [
				{
					label: 'Read',
					swatch: 'var(--chart-1)',
					values: [0, 10, 20],
					format: (value) => `${value}`
				},
				{
					label: 'Written',
					swatch: 'var(--chart-4)',
					values: [0, 1, 2],
					format: (value) => `${value}`
				}
			],
			notMeasured: 'Nothing was read on this day',
			resting: 'last'
		});
		expect(strip.columns).toEqual(['Mon', 'Tue', 'Wed']);
		expect(strip.series.map((one) => [one.label, one.swatch, one.values[2]])).toEqual([
			['Read', 'var(--chart-1)', '20'],
			['Written', 'var(--chart-4)', '2']
		]);
		expect(strip.resting).toBe(2);
		// A series one reading short is one day's numbers under another day's
		// heading, so the builder refuses it rather than printing it.
		expect(() =>
			readoutOf({
				type: 'dateSeries',
				columns: ['Mon', 'Tue'],
				series: [{ label: 'Read', swatch: null, values: [1], format: String }],
				notMeasured: 'Nothing was read on this day',
				resting: 'last'
			})
		).toThrow(/1 readings for 2 columns/);
	});

	test('a missing reading prints the not-measured word, never a dash or a zero', () => {
		const strip = readoutOf({
			type: 'dateSeries',
			columns: ['Mon', 'Tue'],
			series: [
				{ label: 'Read', swatch: null, values: [null, 4], format: String },
				{ label: 'Never read', swatch: null, values: [null, null], format: String }
			],
			notMeasured: 'Nothing was read on this day',
			resting: 'newest'
		});
		expect(strip.series[0].values).toEqual([null, '4']);
		expect(strip.notMeasured).toBe('Nothing was read on this day');
		// A key for a series the window never measured is a claim the data does
		// not support, so it has no entry at all.
		expect(strip.series.map((one) => one.label)).toEqual(['Read']);
		expect(() =>
			readoutOf({
				type: 'dateSeries',
				columns: ['Mon'],
				series: [{ label: 'Read', swatch: null, values: ['-'], format: String }],
				notMeasured: 'Nothing was read on this day',
				resting: 'last'
			})
		).toThrow(/hand null/);
	});

	test("a column's own reason overrides the shared not-measured word", () => {
		// Judgement's agreement chart carries two reasons a column holds no
		// reading: a day whose row read no pair, and a day with no row at all
		// (row L55). One word for every chart that does not need the distinction,
		// a reason per column for the one that does.
		const strip = readoutOf({
			type: 'dateSeries',
			columns: ['Mon', 'Tue', 'Wed'],
			series: [{ label: 'Read', swatch: null, values: [1, null, null], format: String }],
			notMeasured: 'Nothing was read on this day',
			notMeasuredAt: [null, 'No readings came in for this day', null],
			resting: 'first'
		});
		// Omitted at Mon, where there is a reading to print instead. Named at
		// Tue. Falls back to the shared word at Wed, where the chart named none.
		expect(strip.notMeasuredAt).toEqual([null, 'No readings came in for this day', null]);

		expect(() =>
			readoutOf({
				type: 'dateSeries',
				columns: ['Mon', 'Tue'],
				series: [{ label: 'Read', swatch: null, values: [null, null], format: String }],
				notMeasured: 'Nothing was read on this day',
				notMeasuredAt: [null],
				resting: 'last'
			})
		).toThrow(/1 reasons for 2 columns/);
	});
});
