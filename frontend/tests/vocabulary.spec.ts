import { expect, test } from '@playwright/test';
import { donut } from '../src/lib/charts/donut';
import { sparkline } from '../src/lib/charts/sparkline';
import { stacked } from '../src/lib/charts/stacked';
import { targetBar } from '../src/lib/charts/targetbar';
import { waterfall } from '../src/lib/charts/waterfall';
import { SENTINEL_PATTERN } from '../src/lib/charts/theme';

/**
 * A chart that draws a plausible but wrong shape is the failure mode worth a
 * test, because nothing about it looks broken. So every assertion here
 * recomputes the geometry from the inputs independently, and compares that to
 * what the specification says - never to a number copied out of the output.
 *
 * The arithmetic is ours and is tested. The drawing belongs to the engine and
 * is not.
 */

function colours(option: unknown): string[] {
	const found: string[] = [];
	const walk = (node: unknown) => {
		if (typeof node === 'string') {
			if (node.startsWith('#')) found.push(node);
		} else if (Array.isArray(node)) node.forEach(walk);
		else if (node !== null && typeof node === 'object') Object.values(node).forEach(walk);
	};
	walk(option);
	return found;
}

test.describe('the donut gauge', () => {
	test('the arc is the fraction, not the rank', () => {
		const d = donut(
			[
				{ label: 'clean', value: 37, token: '--band-high' },
				{ label: 'failed', value: 3, token: '--band-low' }
			],
			'clean'
		);
		expect(d.empty).toBe(false);
		expect(d.total).toBe(40);
		// Recomputed here, not read back from the option.
		expect(d.share).toBeCloseTo(37 / 40, 10);

		const series = (d.option.series as Record<string, unknown>[])[0];
		const data = series.data as { value: number }[];
		// A pie draws in data order, so the order in the argument is the order on
		// screen and the first slice is the one the centre label is about.
		expect(data.map((s) => s.value)).toEqual([37, 3]);
	});

	test('nothing measured is empty, not zero percent', () => {
		const d = donut(
			[
				{ label: 'clean', value: 0, token: '--band-high' },
				{ label: 'failed', value: 0, token: '--band-low' }
			],
			'clean'
		);
		expect(d.empty).toBe(true);
	});
});

test.describe('the target bar', () => {
	test('the marker sits at the target fraction of the track', () => {
		const t = targetBar(4.1, 6, 'lower-is-better', 'minutes per chart');
		expect(t.empty).toBe(false);
		// Track is the larger end plus 15 percent headroom: max(4.1, 6) * 1.15.
		expect(t.markerFraction).toBeCloseTo(6 / (6 * 1.15), 10);
		expect(t.band).toBe('good');
	});

	test('past the target reads as past, whichever way better is', () => {
		expect(targetBar(7.2, 6, 'lower-is-better', 'x').band).toBe('past');
		expect(targetBar(0.03, 0.05, 'higher-is-better', 'x').band).toBe('past');
		expect(targetBar(0.09, 0.05, 'higher-is-better', 'x').band).toBe('good');
	});

	test('within a tenth of the target is a warning, not a pass', () => {
		// 5.6 against 6 is 6.7 percent away - inside the near band.
		expect(targetBar(5.6, 6, 'lower-is-better', 'x').band).toBe('near');
		expect(targetBar(5.0, 6, 'lower-is-better', 'x').band).toBe('good');
	});

	test('a value nobody measured draws nothing', () => {
		expect(targetBar(null, 6, 'lower-is-better', 'x').empty).toBe(true);
	});
});

test.describe('the waterfall', () => {
	test('the last running total is the opening plus every delta', () => {
		const steps = [
			{ label: 'Mon', delta: 12 },
			{ label: 'Tue', delta: -4 },
			{ label: 'Wed', delta: 9 }
		];
		const w = waterfall(100, steps);
		expect(w.empty).toBe(false);
		const expected = 100 + steps.reduce((sum, s) => sum + s.delta, 0);
		expect(w.cumulative[w.cumulative.length - 1]).toBe(expected);
		expect(w.cumulative).toEqual([100, 112, 108, 117]);
	});

	test('a fall hangs from where it started', () => {
		const w = waterfall(100, [{ label: 'Tue', delta: -4 }]);
		const [spacer, bars] = w.option.series as Record<string, unknown>[];
		// The invisible base is the LOWER end, so the visible bar spans 96 to 100
		// rather than growing out of zero.
		expect((spacer.data as number[])[0]).toBe(96);
		expect((bars.data as { value: number }[])[0].value).toBe(4);
	});

	test('the spacer can never be pointed at', () => {
		const w = waterfall(10, [{ label: 'a', delta: 1 }]);
		const spacer = (w.option.series as Record<string, unknown>[])[0];
		expect(spacer.silent).toBe(true);
	});

	test('no steps is empty', () => {
		expect(waterfall(100, []).empty).toBe(true);
	});
});

test.describe('the stacked bars', () => {
	test('a column total is the sum of its series', () => {
		const s = stacked(
			['Mon', 'Tue'],
			[
				{ label: 'fetch', token: '--chart-1', values: [2, 0] },
				{ label: 'extract', token: '--chart-2', values: [1, 5] }
			]
		);
		expect(s.empty).toBe(false);
		expect(s.totals).toEqual([3, 5]);
	});

	test('a series with nothing in the window takes its legend entry with it', () => {
		const s = stacked(
			['Mon'],
			[
				{ label: 'fetch', token: '--chart-1', values: [2] },
				{ label: 'never ran', token: '--chart-2', values: [0] }
			]
		);
		const legend = s.option.legend as { data: string[] };
		expect(legend.data).toEqual(['fetch']);
	});

	test('a stack of nothing is empty', () => {
		expect(stacked(['Mon'], [{ label: 'a', token: '--chart-1', values: [0] }]).empty).toBe(true);
	});
});

test.describe('the sparkline', () => {
	test('movement is the change against where it started', () => {
		const s = sparkline([100, 110, 130]);
		expect(s.empty).toBe(false);
		expect(s.movement).toBeCloseTo((130 - 100) / 100, 10);
		expect(s.rising).toBe(true);
	});

	test('a fall is a fall even when it ends above zero', () => {
		const s = sparkline([200, 150]);
		expect(s.rising).toBe(false);
		expect(s.movement).toBeCloseTo(-0.25, 10);
	});

	test('starting from zero has no percentage, and says so', () => {
		expect(sparkline([0, 5]).movement).toBeNull();
	});

	test('one point has no direction', () => {
		expect(sparkline([5]).empty).toBe(true);
	});

	test('the domain is the drawn extent, never zero', () => {
		const s = sparkline([980, 1000, 990]);
		const y = s.option.yAxis as { min: number; max: number };
		expect(y.min).toBe(980);
		expect(y.max).toBe(1000);
	});
});

test.describe('every chart in the vocabulary', () => {
	const built = [
		donut([{ label: 'a', value: 3, token: '--band-high' }], 'a').option,
		targetBar(4, 6, 'lower-is-better', 'x').option,
		waterfall(10, [{ label: 'a', delta: 2 }]).option,
		stacked(['a'], [{ label: 's', token: '--chart-1', values: [1] }]).option,
		sparkline([1, 2]).option
	];

	test('paints with sentinels only, never a hex somebody typed', () => {
		for (const option of built) {
			const found = colours(option);
			expect(found.length).toBeGreaterThan(0);
			for (const colour of found) expect(colour).toMatch(SENTINEL_PATTERN);
		}
	});

	test('never animates', () => {
		// A reading surface that animates interrupts. The motion budget covers
		// arrival, not drawing.
		for (const option of built) expect(option.animation).toBe(false);
	});
});
