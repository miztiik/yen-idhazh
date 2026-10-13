/** The live native memory readers, not the retired board's page attributes. */
import { expect, test } from '@playwright/test';
import { memoryHeld, memoryHeldWithin } from '../src/lib/console/machine/memory-held';
import { textRows } from '../src/lib/console/machine/records';
import { memoryHeldQuery } from '../src/lib/console/queries/machine';
import { rangeFor, type RouteReach } from '../src/lib/console/queries/window';
import type { Row } from '../src/lib/data/ledger';

const GIB = 2 ** 30;

function row(cells: Row = {}): Row {
	return {
		date: '2030-06-15', item_id: 'tightest', os_mem_total_bytes: 16 * GIB,
		os_mem_available_bytes: 2 * GIB, llama_rss_bytes: 4 * GIB, python_rss_bytes: GIB,
		...cells
	};
}

test.describe('the memory-held native snapshot', () => {
	test('the newest-day query and its closed view use the common record end, not a later ledger day', () => {
		const reach: RouteReach = { through: '2030-06-15', ledgers: {
			'item-health': { state: 'ok', first: '2030-06-01', through: '2030-06-16', lastRows: null, fault: null }
		} };
		const range = rangeFor(memoryHeldQuery, 90, reach, [1, 7, 30, 90]);
		expect(range).toEqual({ from: '2030-06-15', to: '2030-06-15', days: 1, asked: 1 });
		const record = memoryHeld(textRows([
			row({ date: '2030-06-14', item_id: 'older' }),
			row(),
			row({ date: '2030-06-16', item_id: 'later', os_mem_available_bytes: 0 })
		]));
		const view = memoryHeldWithin(record, '2030-06-15', '2030-06-15');
		expect(view.days.map((day) => [day.date, day.itemId])).toEqual([['2030-06-15', 'tightest']]);
		expect(view).toMatchObject({ twoShape: 1, fourShape: 0, empty: false, daysRead: 3, firstDate: '2030-06-14' });
	});

	test('every bound comes from one tightest moment, not maxima from other articles', () => {
		const record = memoryHeld(textRows([
			row({ item_id: 'loose', os_mem_available_bytes: 8 * GIB, llama_rss_bytes: 12 * GIB, python_rss_bytes: 3 * GIB }),
			row({ item_id: 'z-tie', llama_rss_bytes: 9 * GIB }),
			row({ item_id: 'a-tie' }),
			row({ item_id: 'unknown', os_mem_total_bytes: null, os_mem_available_bytes: 0 })
		]));
		expect(record.days).toHaveLength(1);
		const day = record.days[0];
		expect(day.itemId).toBe('a-tie');
		expect(day.totalBytes).toBe(16 * GIB);
		expect(day.scaleBytes).toBe(16 * GIB);
		expect(day.segments.map((segment) => [segment.key, segment.bytes]))
			.toEqual([['free', 2 * GIB], ['held', 14 * GIB]]);
		expect(day.brackets.map((bracket) => [bracket.key, bracket.bytes, bracket.pastHeld]))
			.toEqual([['server', 4 * GIB, false], ['worker', GIB, false]]);
		expect(day.overlapBytes).toBe(GIB);
		expect(day.restBytes).toBeNull();
	});

	test('anonymous readings close with their signed remainder, and missing totals never use runner memory', () => {
		const day = memoryHeld(textRows([row({
			os_mem_available_bytes: 8 * GIB, llama_rss_anon_bytes: 9 * GIB, python_rss_anon_bytes: GIB,
			os_swap_total_bytes: 4 * GIB, os_swap_free_bytes: 4 * GIB
		})])).days[0];
		expect(day.shape).toBe('four');
		expect(day.segments.map((segment) => [segment.key, segment.bytes]))
			.toEqual([['free', 8 * GIB], ['server', 9 * GIB], ['worker', GIB], ['rest', -2 * GIB]]);
		expect(day.restBytes).toBe(-2 * GIB);
		expect(day.overBytes).toBe(2 * GIB);
		expect(day.scaleBytes).toBe(18 * GIB);
		expect(day.segments.reduce((sum, segment) => sum + segment.bytes, 0)).toBe(16 * GIB);
		expect(day.swap).toMatchObject({ usedBytes: 0, totalBytes: 4 * GIB, none: true });
		const absent = memoryHeld(textRows([
			row({ os_mem_total_bytes: null }),
			row({ date: '2030-06-16', os_mem_total_bytes: Infinity })
		]));
		expect(absent).toEqual({ days: [], firstDate: null, daysRead: 2 });
		expect(memoryHeldWithin(absent, '2030-06-15', '2030-06-16').empty).toBe(true);
	});
});
