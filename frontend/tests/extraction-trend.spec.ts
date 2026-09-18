import { expect, test } from '@playwright/test';
import { extractionTrend, type ExtractionDay } from '../src/lib/charts/extraction-trend';

/** The direction under the Extraction panel's four levels.
 *
 * A pure builder, so this runs in Node with no browser and no canary. The days
 * are built rather than read off `state/day-metrics/`: a run appends another
 * record every four hours, and a test whose cost rises with the archive is the
 * thing Guardrail #12 forbids. Building them is also the only way to reach the
 * cases the archive has never produced - a window holding one day, and a window
 * where nothing published a chart at all.
 */

function day(date: string, chartable: number, charted: number): ExtractionDay {
	return { date, chartable, charted };
}

/** The engine's category axis, which is where the dates land. */
function categories(option: Record<string, unknown>): string[] {
	const axis = option.xAxis as { type: string; data: string[] };
	return axis.data;
}

function series(option: Record<string, unknown>) {
	return option.series as { name: string; type: string; data: number[]; showSymbol: boolean }[];
}

test('the trend draws a time axis, one column a day, oldest first', () => {
	const trend = extractionTrend([
		day('2026-09-11', 160, 17),
		day('2026-09-09', 225, 20),
		day('2026-09-10', 181, 18)
	]);

	const option = trend.option as Record<string, unknown>;
	expect((option.xAxis as { type: string }).type).toBe('category');
	expect(categories(option)).toEqual(['9 Sep', '10 Sep', '11 Sep']);
	// The rows come back in the order they are drawn, whatever order they arrived.
	expect(trend.days.map((entry) => entry.date)).toEqual([
		'2026-09-09',
		'2026-09-10',
		'2026-09-11'
	]);
});

test('every series carries one point a day, and nothing is dropped', () => {
	const days = [day('2026-09-15', 149, 0), day('2026-09-16', 172, 0), day('2026-09-17', 117, 0)];
	const drawn = series(extractionTrend(days).option as Record<string, unknown>);

	expect(drawn.length, 'the yield lost one of its two series').toBe(2);
	for (const one of drawn) {
		expect(one.data.length, `${one.name} drew a different number of days from the window`).toBe(3);
	}
	expect(drawn[0].data).toEqual([149, 172, 117]);
	expect(drawn[1].data).toEqual([0, 0, 0]);
});

test('one day is a point, not an empty plot', () => {
	const trend = extractionTrend([day('2026-09-17', 117, 0)]);

	expect(trend.empty, 'one measured day read as nothing measured').toBe(false);
	expect(trend.single).toBe(true);
	expect(categories(trend.option as Record<string, unknown>)).toEqual(['17 Sep']);
	for (const one of series(trend.option as Record<string, unknown>)) {
		expect(one.data.length, `${one.name} drew no point for the one day it has`).toBe(1);
		// A line through one point paints nothing. The symbol is what draws it.
		expect(one.showSymbol, `${one.name} would draw an invisible single day`).toBe(true);
	}
});

test('a window that measured nothing is flagged rather than drawn empty', () => {
	const trend = extractionTrend([]);

	expect(trend.empty).toBe(true);
	expect(trend.single).toBe(false);
	expect(trend.days).toEqual([]);
	expect(trend.ratio).toBeNull();
});

test('both series share one value domain, and it is not fixed', () => {
	// Two counts of articles, so a per-series axis would delete the comparison
	// the panel exists for, and a fixed maximum would waste the plot on a quiet
	// day. The domain comes from the data drawn.
	const option = extractionTrend([day('2026-09-09', 225, 20), day('2026-09-17', 117, 0)])
		.option as Record<string, unknown>;
	const axis = option.yAxis as Record<string, unknown>;

	expect(Array.isArray(option.yAxis), 'the panel grew a second value axis').toBe(false);
	expect(axis.min, 'the value domain was pinned at the bottom').toBeUndefined();
	expect(axis.max, 'the value domain was pinned at the top').toBeUndefined();
	for (const one of series(option) as unknown as { yAxisIndex?: number }[]) {
		expect(one.yAxisIndex ?? 0, 'a series left the shared domain').toBe(0);
	}
});

test('the ratio between the two series is measured, and the committed days are inside 20', () => {
	// Measured 2026-09-17 over the nine committed day records that carry an
	// extraction block: `chartable` peaks at 225 and `chartable_charted` at 20.
	const trend = extractionTrend([day('2026-09-09', 225, 20), day('2026-09-13', 123, 4)]);

	expect(trend.ratio).toBeCloseTo(225 / 20, 6);
	expect(trend.ratio ?? 0, 'the two series no longer belong on one axis').toBeLessThan(20);
});

test('a window where nothing published a chart has no ratio, and is not called zero', () => {
	const trend = extractionTrend([day('2026-09-16', 172, 0), day('2026-09-17', 117, 0)]);

	expect(trend.ratio, 'a flat-zero series was given a ratio it cannot have').toBeNull();
	expect(trend.empty, 'a real window read as nothing measured').toBe(false);
});
