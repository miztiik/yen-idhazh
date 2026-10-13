/** The native low-water memory reading, from one article's own kernel cells. */
import { expect, test } from '@playwright/test';
import { closestToMemory } from '../src/lib/console/machine/records';
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

test('the tightest article is total less the lowest available, not a process high-water mark', () => {
	const rows = [item('a', 4 * GIB), item('b', 2 * GIB), item('c', 3 * GIB)];
	const readings = closestToMemory(rows);
	expect(readings.map((one) => [one.value, one.ends?.end])).toEqual([[12, 16], [14, 16], [13, 16]]);
	const tightest = [...readings].sort((a, b) => b.value - a.value)[0];
	expect(tightest.label).toBe(`b \u00b7 source-a \u00b7 ${DATE}`);
	expect(tightest.value).toBe(14);
	expect(readings.map((one) => one.value)).not.toContain(15);
	// Neither process owns the kernel's available-memory instrument.
	const changed = rows.map((row) => ({ ...row, llama_rss_bytes: 64 * GIB, llama_rss_peak_bytes: 128 * GIB }));
	expect(closestToMemory(changed)).toEqual(readings);
});

test('the endpoint is the measured machine total, never the runner ceiling or another article', () => {
	const readings = closestToMemory([item('large', 2 * GIB, 64 * GIB), item('small', 3 * GIB, 8 * GIB)]);
	expect(readings.map((one) => [one.value, one.ends?.end])).toEqual([[62, 64], [5, 8]]);
});

test('an absent or non-finite kernel cell is not a zero; a measured zero is retained', () => {
	const invalid: Row[] = [
		item('missing-floor', null), item('missing-total', GIB, null),
		{ ...item('bad-floor', GIB), os_mem_available_min_bytes: 'Infinity' },
		{ ...item('bad-total', GIB), os_mem_total_bytes: 'NaN' },
		item('negative', -GIB), item('past-total', 17 * GIB), item('zero-total', 0, 0)
	];
	expect(closestToMemory(invalid)).toEqual([]);
	expect(closestToMemory([item('none-left', 0)])[0]).toMatchObject({ value: 16, ends: { end: 16 } });
	expect(closestToMemory([item('all-free', 16 * GIB)])[0]).toMatchObject({ value: 0, ends: { end: 16 } });
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
		expect(readings.find((one) => one.label === `same \u00b7 source-a \u00b7 ${DATE}`)?.value).toBe(14);
		expect(readings.find((one) => one.label.endsWith('2026-09-03'))?.value).toBe(15);
	}
});
