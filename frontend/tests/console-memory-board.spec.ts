/** The native low-water memory reading, from one article's own kernel cells. */
import { expect, test } from '@playwright/test';
import { closestToMemory } from '../src/lib/console/machine/records';
import { rankedList } from '../src/lib/charts/d3/rankedList';
import type { Row } from '../src/lib/data/ledger';

const GIB = 2 ** 30;
const DATE = '2026-09-04';

function item(id: string, floor: number | null, total: number | null = 16 * GIB): Row {
	return {
		date: DATE, item_id: id, source_id: 'source-a', source_words: 400,
		os_mem_total_bytes: total, os_mem_available_min_bytes: floor,
		llama_rss_bytes: 12 * GIB, python_rss_bytes: GIB, llama_rss_peak_bytes: 15 * GIB
	};
}

test('the tightest article has the fewest GiB available, not the most in use', () => {
	const rows = [item('a', 4 * GIB, 64 * GIB), item('b', 2 * GIB, 8 * GIB), item('c', 3 * GIB)];
	const readings = closestToMemory(rows);
	expect(readings.map((one) => [one.value, one.capacity])).toEqual([[4, 64], [2, 8], [3, 16]]);
	expect(rankedList(readings, { max: 1, order: 'smallest-first' })?.rows[0]).toMatchObject({
		label: `b \u00b7 source-a \u00b7 ${DATE}`, value: 2
	});
	// Neither process owns the kernel's available-memory instrument.
	const changed = rows.map((row) => ({ ...row, llama_rss_bytes: 64 * GIB, llama_rss_peak_bytes: 128 * GIB }));
	expect(closestToMemory(changed)).toEqual(readings);
});

test('an absent or non-finite kernel cell is not a zero; a measured zero is retained', () => {
	const invalid: Row[] = [
		item('missing-floor', null), item('missing-total', GIB, null),
		{ ...item('bad-floor', GIB), os_mem_available_min_bytes: 'Infinity' },
		{ ...item('bad-total', GIB), os_mem_total_bytes: 'NaN' },
		item('negative', -GIB), item('past-total', 17 * GIB), item('zero-total', 0, 0)
	];
	expect(closestToMemory(invalid)).toEqual([]);
	const measuredZero = closestToMemory([item('none-left', 0)]);
	expect(rankedList(measuredZero, { scaleFloor: measuredZero[0].capacity })?.rows[0]).toMatchObject({ value: 0, fraction: 0 });
	expect(closestToMemory([item('all-free', 16 * GIB)])[0]).toMatchObject({ value: 16, capacity: 16 });
	expect(closestToMemory([])).toEqual([]);
});

test('multiple attempts of one dated article keep its tightest reading in either order', () => {
	const rows = [
		item('same', 4 * GIB), item('same', 2 * GIB), item('other', 3 * GIB),
		{ ...item('same', GIB), date: '2026-09-03' }
	];
	for (const input of [rows, [...rows].reverse()]) {
		const readings = closestToMemory(input);
		expect(readings).toHaveLength(3);
		expect(readings.find((one) => one.label === `same \u00b7 source-a \u00b7 ${DATE}`)?.value).toBe(2);
		expect(readings.find((one) => one.label.endsWith('2026-09-03'))?.value).toBe(1);
	}
});
