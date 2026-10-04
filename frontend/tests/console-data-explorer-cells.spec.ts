
import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { nextSort, printCell, sortedRows } from '../src/lib/console/explorer/answer';
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

test('THE ORACLE: the Records route and explorer components never render cell text as HTML', () => {
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
