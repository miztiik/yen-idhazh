import { expect, test } from '@playwright/test';

import { classifyType, isDay, isNumber, type TypeFamily } from '../src/lib/console/explorer/type-family';

/**
 * The family each engine type name belongs to, pinned by name. The names are the
 * ones the engine printed for DESCRIBE on 2026-10-05 (DuckDB 1.5.5), so a renamed
 * type fails here rather than changing how the table prints it, how the chart
 * draws it or which colour labels it.
 */

const FAMILIES: Record<TypeFamily, readonly string[]> = {
	whole: ['TINYINT', 'SMALLINT', 'INTEGER', 'BIGINT', 'HUGEINT', 'UTINYINT', 'USMALLINT', 'UINTEGER', 'UBIGINT', 'UHUGEINT', 'BIGNUM'],
	decimal: ['FLOAT', 'DOUBLE', 'DECIMAL(18,4)', 'DECIMAL(18,3)'],
	date: ['DATE'],
	timestamp: ['TIMESTAMP', 'TIMESTAMP_S', 'TIMESTAMP_MS', 'TIMESTAMP_NS', 'TIMESTAMP WITH TIME ZONE'],
	time: ['TIME', 'TIME_NS', 'TIME WITH TIME ZONE'],
	interval: ['INTERVAL'],
	truth: ['BOOLEAN'],
	text: ['VARCHAR', 'UUID', "ENUM('a', 'b')"],
	bytes: ['BLOB'],
	nested: [
		'INTEGER[]', 'INTEGER[2]', 'VARCHAR[]', 'TIMESTAMP[]', 'TIMESTAMP_NS[]', 'DECIMAL(18,4)[]', "ENUM('a', 'b')[]", 'BOOLEAN[3]',
		'STRUCT(a INTEGER)', 'STRUCT(t TIMESTAMP)', 'MAP(VARCHAR, INTEGER)', 'UNION(n INTEGER)'
	],
	other: ['BIT', '', 'INTERVALS', 'VARCHARS', 'BIGINTEGER', 'DATETIME', 'BOOLEANS', 'STRUCT']
};

for (const [family, types] of Object.entries(FAMILIES)) {
	test(`${family}: every name in it classifies as ${family}`, () => {
		for (const type of types) expect(classifyType(type), type).toBe(family);
	});
}

test('case and padding do not change the family', () => {
	expect(classifyType('decimal(18,4)')).toBe('decimal');
	expect(classifyType(' timestamp_ns ')).toBe('timestamp');
	expect(classifyType('enum(\'a\')')).toBe('text');
	expect(classifyType('varchar[]')).toBe('nested');
});

test('a number is a whole number or a decimal, and a day is a date or a timestamp', () => {
	const all = Object.keys(FAMILIES) as TypeFamily[];
	expect(all.filter(isNumber)).toEqual(['whole', 'decimal']);
	expect(all.filter(isDay)).toEqual(['date', 'timestamp']);
});
