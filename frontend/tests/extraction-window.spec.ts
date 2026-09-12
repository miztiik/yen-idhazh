import { expect, test } from '@playwright/test';
import { extraction } from '../src/lib/console/extraction';
import type { DayExtraction } from '../src/lib/server/payload';

/** The window reduction behind the console's extraction panel.
 *
 * A pure reduction over built day blocks, so this runs in Node with no browser
 * and no canary. The blocks are built rather than read off `state/day-metrics/`:
 * a run appends another record every four hours, and a test whose cost rises
 * with the archive is the thing Guardrail #12 forbids. Building them is also the only
 * way to reach the cases the archive has never produced - a day where a span
 * stopped holding, and a window that measured nothing at all.
 */

function day(over: Partial<DayExtraction> = {}): DayExtraction {
	return {
		items: 10,
		spanIntegrityPass: 10,
		elementsFound: 40,
		chartable: 4,
		narrative: 3,
		unclassified: 3,
		chartablePublished: 4,
		chartableCharted: 3,
		...over
	};
}

test('a window is the sum of its days, and the rates come off the sums', () => {
	const found = extraction([day(), day(), day()], 7);

	expect(found.days).toBe(7);
	expect(found.measuredDays).toBe(3);
	expect(found.items).toBe(30);
	expect(found.elementsFound).toBe(120);
	expect(found.chartablePublished).toBe(12);
	expect(found.chartableCharted).toBe(9);
	expect(found.unused).toBe(3);
	expect(found.unusedPct).toBe(25);
	expect(found.integrityPct).toBe(100);
});

test('a day with no record is counted and skipped, never read as a zero', () => {
	const found = extraction([day(), null, day()], 7);

	expect(found.measuredDays).toBe(2);
	expect(found.items).toBe(20);
	// Two days of four chartable, three charted. A null read as zeros would put
	// the same numbers over three days and report the same rate off a wrong
	// denominator, which is why `measuredDays` is printed beside them.
	expect(found.unusedPct).toBe(25);
});

test('a window that measured nothing has no rate and no verdict', () => {
	const found = extraction([null, null], 30);

	expect(found.measuredDays).toBe(0);
	expect(found.items).toBe(0);
	expect(found.unusedPct).toBeNull();
	expect(found.integrityPct).toBeNull();
	expect(found.verdict).toBeNull();
});

test('a rate over nothing chartable is not zero', () => {
	const found = extraction([day({ chartable: 0, chartablePublished: 0, chartableCharted: 0 })], 1);

	expect(found.unusedPct).toBeNull();
	expect(found.verdict).toContain('nothing to pass over');
});

test('a drifted span leads the verdict, before anything about charts', () => {
	const found = extraction([day({ spanIntegrityPass: 8 })], 1);

	expect(found.integrityPct).toBe(80);
	expect(found.verdict).toContain('2 of 10 articles');
	expect(found.verdict).toContain('degraded');
});

test('a window that drew every chart it could says so', () => {
	const found = extraction([day({ chartableCharted: 4 })], 1);

	expect(found.unused).toBe(0);
	expect(found.unusedPct).toBe(0);
	expect(found.verdict).toContain('carries one');
});

test('the verdict names the counts, never a bare percentage', () => {
	const found = extraction([day()], 1);

	expect(found.verdict).toContain('1 of 4 articles');
	expect(found.verdict).toContain('planner is passing over material');
});
