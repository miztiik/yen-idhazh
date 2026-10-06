import { expect, test } from '@playwright/test';

import { typeColour } from '../src/lib/console/explorer/type-colour';

/**
 * The colour token each engine type is printed in, pinned by name. The type
 * names are the ones the engine printed for DESCRIBE on 2026-10-05 (DuckDB
 * 1.5.4), so a renamed type fails here rather than turning grey on the page.
 */

test('text prints in --type-text', () => {
	for (const type of ['VARCHAR', 'UUID', "ENUM('a', 'b')"]) expect(typeColour(type), type).toBe('--type-text');
});

test('every whole number and decimal prints in --type-number', () => {
	for (const type of [
		'TINYINT', 'SMALLINT', 'INTEGER', 'BIGINT', 'HUGEINT', 'UTINYINT', 'USMALLINT', 'UINTEGER', 'UBIGINT', 'UHUGEINT', 'BIGNUM',
		'FLOAT', 'DOUBLE', 'DECIMAL(18,4)', 'DECIMAL(18,3)'
	]) expect(typeColour(type), type).toBe('--type-number');
});

test('every date, time and interval prints in --type-time', () => {
	for (const type of [
		'DATE', 'TIME', 'TIME_NS', 'TIME WITH TIME ZONE', 'TIMESTAMP', 'TIMESTAMP_S', 'TIMESTAMP_MS', 'TIMESTAMP_NS',
		'TIMESTAMP WITH TIME ZONE', 'INTERVAL'
	]) expect(typeColour(type), type).toBe('--type-time');
});

test('true/false prints in --type-truth', () => {
	expect(typeColour('BOOLEAN')).toBe('--type-truth');
});

test('a list or a struct prints in --color-text-tertiary whatever it holds', () => {
	for (const type of [
		'INTEGER[]', 'INTEGER[2]', 'VARCHAR[]', 'TIMESTAMP[]', 'DECIMAL(18,4)[]', "ENUM('a', 'b')[]", 'BOOLEAN[3]',
		'STRUCT(a INTEGER)', 'STRUCT(t TIMESTAMP)', 'MAP(VARCHAR, INTEGER)', 'UNION(n INTEGER)'
	]) expect(typeColour(type), type).toBe('--color-text-tertiary');
});

test('a blob, a bit string, an empty name or a name that only resembles a type prints in --color-text-tertiary', () => {
	for (const type of ['BLOB', 'BIT', '', 'INTERVALS', 'VARCHARS', 'BIGINTEGER', 'DATETIME', 'BOOLEANS', 'STRUCT']) {
		expect(typeColour(type), type).toBe('--color-text-tertiary');
	}
});

test('case and padding do not change the colour', () => {
	expect(typeColour('decimal(18,4)')).toBe('--type-number');
	expect(typeColour(' timestamp with time zone ')).toBe('--type-time');
	expect(typeColour('varchar')).toBe('--type-text');
	expect(typeColour('varchar[]')).toBe('--color-text-tertiary');
});
