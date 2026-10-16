/** Native item cost and per-call reuse over bounded rows, with independent numeric oracles. */
import { expect, test } from '@playwright/test';
import { nativeItemCost } from '../src/lib/console/pipelines/item-cost';
import { labelHeldMedian, reuseChecks, reuseSeries } from '../src/lib/console/machine/records';
import { itemCostQuery } from '../src/lib/console/queries/pipelines';
import { rangeFor, type RouteReach } from '../src/lib/console/queries/window';
import type { Row } from '../src/lib/data/ledger';

function row(cells: Row): Row {
	return { date: '2026-08-10', ...cells };
}

test.describe('what one item cost, as native arithmetic', () => {
	test('each clock has its own measured population, not a both-clocks cohort', () => {
		const cost = nativeItemCost([
			row({ prefill_ms: 4000, decode_ms: null, input_tokens: 100, cached_tokens: 0, output_tokens: 10 }),
			row({ prefill_ms: null, decode_ms: 2000, input_tokens: null, output_tokens: 10 }),
			row({ prefill_ms: '', decode_ms: '', input_tokens: '', output_tokens: '' })
		]);
		expect(cost.rows).toBe(3);
		expect(cost.reading).toMatchObject({ n: 1, fastest: 4000, slowest: 4000 });
		expect(cost.writing).toMatchObject({ n: 1, fastest: 2000, slowest: 2000 });
		expect(cost.readPairs).toBe(1);
		expect(cost.writePairs).toBe(1);
		expect(cost.msPerReadToken).toBe(40);
		expect(cost.msPerWrittenToken).toBe(200);
		expect(cost.writeCostRatio).toBe(5);
	});

	test('a measured zero clock stays in its cohort and rate, while a zero read rate supplies no ratio', () => {
		const cost = nativeItemCost([
			row({ prefill_ms: 0, decode_ms: 0, input_tokens: 1000, cached_tokens: 0, output_tokens: 100 }),
			row({ prefill_ms: null, decode_ms: null, input_tokens: null, cached_tokens: null, output_tokens: null })
		]);
		expect(cost.reading).toMatchObject({ n: 1, fastest: 0, median: 0, slowest: 0 });
		expect(cost.writing).toMatchObject({ n: 1, fastest: 0, median: 0, slowest: 0 });
		expect(cost.readPairs).toBe(1);
		expect(cost.writePairs).toBe(1);
		expect(cost.msPerReadToken).toBe(0);
		expect(cost.msPerWrittenToken).toBe(0);
		expect(cost.writeCostRatio).toBeNull();
	});

	test('a window pooled share and the middle request are two different measurements', () => {
		const rows = [
			row({ label_input_tokens: 90000, label_cached_tokens: 0, label_cache_pct: 0 }),
			row({ label_input_tokens: 1000, label_cached_tokens: 900, label_cache_pct: 90 }),
			row({ label_input_tokens: 1000, label_cached_tokens: 900, label_cache_pct: 90 })
		];
		const check = reuseChecks(rows)[0];
		expect(check.count).toBe(3);
		expect(check.ours, '1800 held tokens out of 92000 requested tokens').toBeCloseTo(100 * 1800 / 92000, 10);
		expect(check.server, 'the middle request reused 90 percent').toBe(90);
		expect(labelHeldMedian(rows)).toBe(900);
	});

	test('rates pool their own complete pairs instead of averaging item rates or sharing divisors', () => {
		const cost = nativeItemCost([
			row({ prefill_ms: 1000, input_tokens: 10, cached_tokens: 0, decode_ms: 2000, output_tokens: 10 }),
			row({ prefill_ms: 1000, input_tokens: 100, cached_tokens: 0, decode_ms: 1000, output_tokens: 90 }),
			row({ prefill_ms: 9000, input_tokens: null, decode_ms: 1000, output_tokens: 100 }),
			row({ prefill_ms: null, input_tokens: 90000, cached_tokens: 0, decode_ms: 9000, output_tokens: null })
		]);
		expect(cost.reading?.n).toBe(3);
		expect(cost.writing?.n).toBe(4);
		expect(cost.readPairs).toBe(2);
		expect(cost.writePairs).toBe(3);
		expect(cost.msPerReadToken, '2000 milliseconds over 110 fresh tokens').toBeCloseTo(2000 / 110, 10);
		expect(cost.msPerWrittenToken, '4000 milliseconds over 200 written tokens').toBe(20);
		expect(cost.writeCostRatio).toBeCloseTo(1.1, 10);
	});

	test('cached tokens leave the read divisor, but unknown cache is never assumed to be zero', () => {
		const cost = nativeItemCost([
			row({ prefill_ms: 1000, input_tokens: 1000, cached_tokens: 900 }),
			row({ prefill_ms: 9000, input_tokens: 1000, cached_tokens: null })
		]);
		expect(cost.reading?.n).toBe(2);
		expect(cost.readPairs).toBe(1);
		expect(cost.unknownCache).toBe(1);
		expect(cost.msPerReadToken, '1000 milliseconds over 100 fresh tokens').toBe(10);
	});

	test('label and summary reuse remain separate calls rather than an item-total fallback', () => {
		const calls = [row({
			label_input_tokens: 1497, label_cached_tokens: 0, label_cache_pct: 0,
			summary_input_tokens: 2389, summary_cached_tokens: 1493, summary_cache_pct: 62.49
		})];
		const cost = nativeItemCost([row({ prefill_ms: 400872, input_tokens: 3886, cached_tokens: 1493 })]);
		expect(cost.readPairs).toBe(1);
		expect(cost.msPerReadToken, '400872 milliseconds over 2393 fresh tokens across both calls')
			.toBeCloseTo(400872 / 2393, 10);
		expect(labelHeldMedian(calls)).toBe(0);
		expect(reuseSeries(calls).map((series) => series.points[0].value)).toEqual([0, 896]);
		const checks = reuseChecks(calls);
		expect(checks[0]).toEqual({ call: 'label', ours: 0, server: 0, count: 1 });
		expect(checks[1].ours).toBeCloseTo(100 * 1493 / 2389, 10);
		expect(checks[1]).toMatchObject({ call: 'summary', server: 62.49, count: 1 });
	});

	test('an absent per-call reading is unknown even when item totals exist, and the server remains independent', () => {
		const rows = [row({
			input_tokens: 1000, cached_tokens: 400,
			label_input_tokens: null, label_cached_tokens: '', label_cache_pct: 40,
			summary_input_tokens: 1000, summary_cached_tokens: null
		})];
		expect(labelHeldMedian(rows)).toBeNull();
		expect(reuseChecks(rows)).toEqual([
			{ call: 'label', ours: null, server: 40, count: 0 },
			{ call: 'summary', ours: null, server: null, count: 0 }
		]);
		expect(reuseSeries(rows).map((series) => series.points[0].value)).toEqual([null, null]);
	});

	test('even token and held-text cohorts use the native upper middle, not a half token', () => {
		const rows = [
			row({ input_tokens: 1687, output_tokens: 10, label_cached_tokens: 843 }),
			row({ input_tokens: 1688, output_tokens: 11, label_cached_tokens: 845 })
		];
		const cost = nativeItemCost(rows);
		expect(cost.promptTokens).toBe(1688);
		expect(cost.writtenTokens).toBe(11);
		expect(labelHeldMedian(rows)).toBe(845);
	});

	test('invalid pairs and a fully cached prompt cannot provide a fresh-token rate', () => {
		const cost = nativeItemCost([
			row({ prefill_ms: 1000, input_tokens: 100, cached_tokens: 100, decode_ms: 1000, output_tokens: 0 }),
			row({ prefill_ms: 1000, input_tokens: 100, cached_tokens: 101 }),
			row({ prefill_ms: 1000, input_tokens: 100, cached_tokens: -1 }),
			row({ prefill_ms: -1, input_tokens: 100, cached_tokens: 0 }),
			row({ prefill_ms: 'Infinity', input_tokens: 100, cached_tokens: 0, decode_ms: NaN, output_tokens: 10 })
		]);
		expect(cost.reading?.n).toBe(3);
		expect(cost.writing?.n).toBe(1);
		expect(cost.readPairs).toBe(0);
		expect(cost.writePairs).toBe(0);
		expect(cost.msPerReadToken).toBeNull();
		expect(cost.msPerWrittenToken).toBeNull();
		expect(cost.writeCostRatio).toBeNull();
	});

	test('time distributions retain their own medians but share the seconds domain', () => {
		const cost = nativeItemCost([
			row({ prefill_ms: 1000, decode_ms: 4000 }),
			row({ prefill_ms: 2000, decode_ms: 8000 })
		]);
		expect(cost.reading).toMatchObject({ n: 2, fastest: 1000, median: 1500, slowest: 2000 });
		expect(cost.writing).toMatchObject({ n: 2, fastest: 4000, median: 6000, slowest: 8000 });
		expect(cost.reading?.bins.reduce((n, bin) => n + bin.n, 0)).toBe(2);
		expect(cost.writing?.bins.reduce((n, bin) => n + bin.n, 0)).toBe(2);
		expect(cost.domain).toEqual([1, 16]);
	});

	test('no query rows supply no distribution or ratio, and a missing writing rate stays absent', () => {
		const absent = nativeItemCost([]);
		expect(absent).toMatchObject({
			rows: 0, reading: null, writing: null, readPairs: 0, writePairs: 0,
			msPerReadToken: null, msPerWrittenToken: null, writeCostRatio: null
		});
		expect(absent.domain).toBeUndefined();
		const onlyReading = nativeItemCost([row({ prefill_ms: 1000, input_tokens: 100, cached_tokens: 0 })]);
		expect(onlyReading.msPerReadToken).toBe(10);
		expect(onlyReading.msPerWrittenToken).toBeNull();
		expect(onlyReading.writeCostRatio).toBeNull();
	});
});

test('the cost query window agrees with an independent UTC day walk, including leap days and first-day clipping', () => {
	const reach: RouteReach = { through: '2024-03-01', ledgers: {
		'item-health': { state: 'ok', first: '2023-01-01', through: '2024-03-04', lastRows: null, fault: null }
	} };
	for (const asked of [1, 2, 3, 7, 30, 90]) {
		const days: string[] = [];
		const cursor = new Date('2024-03-01T00:00:00Z');
		for (let remaining = asked; remaining > 0; remaining -= 1) {
			days.unshift(cursor.toISOString().slice(0, 10));
			cursor.setUTCDate(cursor.getUTCDate() - 1);
		}
		expect(rangeFor(itemCostQuery, asked, reach, [1, 7, 30, 90]))
			.toEqual({ from: days[0], to: '2024-03-01', days: days.length, asked });
	}
	const clipped: RouteReach = { ...reach, ledgers: {
		'item-health': { state: 'ok', first: '2024-02-28', through: '2024-03-04', lastRows: null, fault: null }
	} };
	expect(rangeFor(itemCostQuery, 90, clipped, [1, 7, 30, 90]))
		.toEqual({ from: '2024-02-28', to: '2024-03-01', days: 3, asked: 90 });
});
