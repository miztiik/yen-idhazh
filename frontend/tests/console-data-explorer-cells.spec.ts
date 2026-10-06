
import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { nextSort, numericBarShare, printCell, sortedRows, type PrintedCell } from '../src/lib/console/explorer/answer';
import type { Column, Row } from '../src/lib/data/ledger';

test('THE ORACLE: cells print by engine column type, not by JavaScript value', () => {
	const cases: [Column, Row[string], string][] = [
		[{ name: 'year', type: 'INTEGER' }, '2026', '2026'],
		[{ name: 'items', type: 'BIGINT' }, '12000', '12,000'],
		[{ name: 'share', type: 'DOUBLE' }, '0.12500', '0.125'],
		[{ name: 'tiny', type: 'DOUBLE' }, '0.0000123', '1.23e-5'],
		[{ name: 'day', type: 'DATE' }, '2026-10-03T00:00:00.000Z', '2026-10-03'],
		[{ name: 'empty', type: 'VARCHAR' }, null, 'null']
	];
	for (const [column, value, expected] of cases) {
		expect(printCell(column, value).text, `${column.name} did not print as its type says`).toBe(expected);
	}
});

test('THE ORACLE: sorting is total, nulls stay last, and third press restores engine order', () => {
	const column = { name: 'rows', type: 'INTEGER' };
	const rows: Row[] = [{ rows: '2' }, { rows: null }, { rows: '10' }, { rows: '2' }];
	const desc = nextSort({ column: '', direction: null }, column);
	expect(sortedRows(rows, [column], desc)).toEqual([{ rows: '10' }, { rows: '2' }, { rows: '2' }, { rows: null }]);
	const asc = nextSort(desc, column);
	expect(sortedRows(rows, [column], asc)).toEqual([{ rows: '2' }, { rows: '2' }, { rows: '10' }, { rows: null }]);
	const original = nextSort(asc, column);
	expect(sortedRows(rows, [column], original)).toEqual(rows);
});

test('a cell prints by its column type family: every whole number groups, and a list or a struct is its JSON text', () => {
	const cases: [Column, Row[string], PrintedCell][] = [
		[{ name: 'n', type: 'HUGEINT' }, '123456', { text: '123,456', kind: 'number' }],
		[{ name: 'n', type: 'USMALLINT' }, '60000', { text: '60,000', kind: 'number' }],
		[{ name: 'xs', type: 'INTEGER[]' }, '[1, 2]', { text: '[1, 2]', kind: 'json' }],
		[{ name: 's', type: 'STRUCT(a DOUBLE)' }, "{'a': 1.5}", { text: "{'a': 1.5}", kind: 'json' }],
		[{ name: 'bs', type: 'BLOB[]' }, '[ab, cd]', { text: '[ab, cd]', kind: 'json' }]
	];
	for (const [column, value, expected] of cases) expect(printCell(column, value), column.type).toEqual(expected);
});

test('the first press sorts numbers and days high to low and everything else A to Z, by the column type family', () => {
	const first = (type: string) => nextSort({ column: '', direction: null }, { name: 'c', type }).direction;
	expect(['BIGNUM', 'DECIMAL(18,4)', 'DATE', 'TIMESTAMP_NS'].map(first)).toEqual(['desc', 'desc', 'desc', 'desc']);
	expect(['INTERVAL', 'INTEGER[]', 'STRUCT(a INTEGER)', 'VARCHAR', 'TIME'].map(first)).toEqual(['asc', 'asc', 'asc', 'asc', 'asc']);
	const big = { name: 'n', type: 'BIGNUM' };
	expect(sortedRows([{ n: '9' }, { n: '10' }, { n: '2' }], [big], { column: 'n', direction: 'desc' })).toEqual([{ n: '10' }, { n: '9' }, { n: '2' }]);
});

/** Runs `check` with this process's clock in `zone`, then puts the starting zone back. Node
 *  reads `TZ` the moment it is set, and deleting it does not bring the old zone back. */
function inZone(zone: string, check: () => void): void {
	const variable = process.env.TZ;
	const starting = Intl.DateTimeFormat().resolvedOptions().timeZone;
	process.env.TZ = zone;
	try {
		check();
	} finally {
		process.env.TZ = variable ?? starting;
		if (variable === undefined) delete process.env.TZ;
	}
}

test('a timestamp with no zone sorts by its UTC instant when the run is in another time zone', () => {
	const column = { name: 'at', type: 'TIMESTAMP' };
	// New York's clocks skip from 02:00 to 03:00 on 2026-03-08, so its local time reads these two as one instant.
	inZone('America/New_York', () => {
		expect(new Date('2026-03-08T12:00:00Z').getTimezoneOffset(), 'the run is not in New York time').toBe(240);
		const rows: Row[] = [{ at: '2026-03-08 02:30:00' }, { at: '2026-03-08 03:30:00' }];
		expect(sortedRows(rows, [column], { column: 'at', direction: 'desc' })).toEqual([{ at: '2026-03-08 03:30:00' }, { at: '2026-03-08 02:30:00' }]);
		expect(sortedRows([...rows].reverse(), [column], { column: 'at', direction: 'asc' })).toEqual([{ at: '2026-03-08 02:30:00' }, { at: '2026-03-08 03:30:00' }]);
	});
});

test('timestamp_ns values a few nanoseconds apart sort in time order', () => {
	const column = { name: 'at', type: 'TIMESTAMP_NS' };
	const rows: Row[] = [{ at: '2026-10-06 08:24:32.000000003' }, { at: '2026-10-06 08:24:32' }, { at: '2026-10-06 08:24:32.000000001' }];
	expect(sortedRows(rows, [column], { column: 'at', direction: 'desc' }).map((row) => row.at)).toEqual(['2026-10-06 08:24:32.000000003', '2026-10-06 08:24:32.000000001', '2026-10-06 08:24:32']);
	expect(sortedRows(rows, [column], { column: 'at', direction: 'asc' }).map((row) => row.at)).toEqual(['2026-10-06 08:24:32', '2026-10-06 08:24:32.000000001', '2026-10-06 08:24:32.000000003']);
});

test('a timestamp with a time zone sorts by its instant, not by the clock time it prints', () => {
	const column = { name: 'at', type: 'TIMESTAMP WITH TIME ZONE' };
	// 01:15-05 is 06:15 UTC, 01:30-04 is 05:30 UTC, and 10:45:00.5+05:30 is 05:15:00.5 UTC.
	const rows: Row[] = [{ at: '2026-11-01 01:30:00-04' }, { at: '2026-11-01 10:45:00.5+05:30' }, { at: '2026-11-01 01:15:00-05' }];
	expect(sortedRows(rows, [column], { column: 'at', direction: 'desc' }).map((row) => row.at)).toEqual(['2026-11-01 01:15:00-05', '2026-11-01 01:30:00-04', '2026-11-01 10:45:00.5+05:30']);
});

test('a timestamp in a year below 1000 sorts as the year it prints', () => {
	const column = { name: 'at', type: 'TIMESTAMP' };
	const rows: Row[] = [{ at: '2026-10-06 08:24:32' }, { at: '0044-03-15 12:00:00' }, { at: '1066-10-14 09:00:00' }];
	expect(sortedRows(rows, [column], { column: 'at', direction: 'asc' }).map((row) => row.at)).toEqual(['0044-03-15 12:00:00', '1066-10-14 09:00:00', '2026-10-06 08:24:32']);
});

test('text that names no instant sorts last with the NULLs, and a year past what a Date holds does not stop the sort', () => {
	const column = { name: 'at', type: 'TIMESTAMP' };
	const rows: Row[] = [{ at: 'infinity' }, { at: '2025-01-01 00:00:00' }, { at: null }, { at: '294247-01-10 04:00:54' }, { at: '2026-10-06 08:24:32' }, { at: '-infinity' }];
	expect(sortedRows(rows, [column], { column: 'at', direction: 'desc' }).map((row) => row.at)).toEqual(['2026-10-06 08:24:32', '2025-01-01 00:00:00', 'infinity', null, '294247-01-10 04:00:54', '-infinity']);
	expect(sortedRows(rows, [column], { column: 'at', direction: 'asc' }).map((row) => row.at)).toEqual(['2025-01-01 00:00:00', '2026-10-06 08:24:32', 'infinity', null, '294247-01-10 04:00:54', '-infinity']);
});

test('a date column sorts as before: newest first on the first press, oldest first on the second, NULLs last', () => {
	const column = { name: 'day', type: 'DATE' };
	const rows: Row[] = [{ day: '2026-10-02' }, { day: null }, { day: '2026-10-05' }, { day: '2025-12-31' }];
	const first = nextSort({ column: '', direction: null }, column);
	expect(sortedRows(rows, [column], first).map((row) => row.day)).toEqual(['2026-10-05', '2026-10-02', '2025-12-31', null]);
	expect(sortedRows(rows, [column], nextSort(first, column)).map((row) => row.day)).toEqual(['2025-12-31', '2026-10-02', '2026-10-05', null]);
});

test('a column draws in-cell bars only when its type is a number, so text that holds digits draws none', () => {
	const rows: Row[] = [{ n: '2' }, { n: '10' }];
	expect(numericBarShare({ name: 'n', type: 'INTEGER' }, rows, 0.5)).toBe(10);
	expect(numericBarShare({ name: 'n', type: 'VARCHAR' }, rows, 0.5)).toBeNull();
});

test('THE ORACLE: the Data explorer route and explorer components never render cell text as HTML', () => {
	const files = [
		'src/routes/console/data-explorer/+page.svelte',
		'src/lib/console/explorer/AnswerTable.svelte',
		'src/lib/console/explorer/ColumnList.svelte',
		'src/lib/console/explorer/QueryEditor.svelte'
	];
	for (const file of files) {
		const source = readFileSync(new URL(`../${file}`, import.meta.url), 'utf8');
		expect(source, `${file} uses raw HTML`).not.toContain('{@html');
	}
	const hostile = '<script>alert(1)</script> https://example.invalid/x =cmd| /c calc';
	expect(printCell({ name: 'hostile', type: 'VARCHAR' }, hostile).text).toBe(hostile);
});
