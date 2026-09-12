/** The throughput candles are bounded to the window before they are built, so
 * the shipped array never grows with the archive (Guardrail #12).
 *
 * Row 18 windowed the DRAWING of the chart, but the server still built a candle
 * for every timed day in history and inlined the lot into every prerendered
 * `console/model` document. `throughputWithin` bounds the build to the widest
 * span the control can reach - the same seed `reasonsWithin` and `evalWithin`
 * take - so a day older than the widest preset is never built, and the ceiling
 * on the shipped array is the preset's days whatever the archive holds.
 *
 * Nothing here reads a committed ledger. A test that walks the archive costs
 * more every published day (Guardrail #12), and the one thing this proves - which
 * days survive the bound, and that a kept day is unchanged - is reachable from a
 * built Map.
 */

import { expect, test } from '@playwright/test';

import { throughputWithin } from '../src/lib/server/model-work';

/** One item-health row carrying a valid read and a valid write, so the day it
 * sits on reduces to a candle rather than being dropped for having no rate. */
function healthRow(date: string): Record<string, string> {
	return {
		date,
		run_id: `${date}-1`,
		prefill_ms: '1000',
		decode_ms: '1000',
		input_tokens: '500',
		cached_tokens: '100',
		output_tokens: '200'
	};
}

/** A history that straddles the window on both ends: one day before the start,
 * three inside, one after the end. */
const SPAN = { start: '2026-08-10', end: '2026-08-20' };
const BEFORE = '2026-08-01';
const AFTER = '2026-08-25';
const INSIDE = ['2026-08-10', '2026-08-15', '2026-08-20'];

function history(): Map<string, Record<string, string>[]> {
	const map = new Map<string, Record<string, string>[]>();
	for (const date of [BEFORE, ...INSIDE, AFTER]) map.set(date, [healthRow(date)]);
	return map;
}

test('the built candles are bounded to the window, not the whole history', () => {
	const dates = throughputWithin(history(), new Map(), SPAN).map((day) => day.date);

	// The oracle. Before the bound the array carried every timed day; a day older
	// than the window start, or newer than its end, is now never built.
	expect(dates, 'a day older than the window was built into the payload').not.toContain(BEFORE);
	expect(dates, 'a day past the window end was built into the payload').not.toContain(AFTER);

	// What survives is exactly the days inside the window, oldest first.
	expect(dates).toEqual(INSIDE);
});

test('the ceiling is the window, whatever the archive holds', () => {
	// The whole array is the timed days; the window spans three of them. A wider
	// history behind the same window ships no more candles.
	const wider = history();
	for (const date of ['2026-07-01', '2026-07-15', '2026-06-01']) wider.set(date, [healthRow(date)]);
	const dates = throughputWithin(wider, new Map(), SPAN).map((day) => day.date);
	expect(dates).toEqual(INSIDE);
});

test('a bounded day still computes what it always did', () => {
	// The window bounds which days are kept and changes nothing a kept day holds.
	const day = throughputWithin(new Map([[INSIDE[1], [healthRow(INSIDE[1])]]]), new Map(), SPAN)[0];
	expect(day.date).toBe(INSIDE[1]);
	expect(day.items).toBe(1);
	// read rate = (input - cached) / (prefill_ms / 1000) = (500 - 100) / 1 = 400.
	expect(day.read.median).toBeCloseTo(400);
	// write rate = output / (decode_ms / 1000) = 200 / 1 = 200.
	expect(day.write.median).toBeCloseTo(200);
});
