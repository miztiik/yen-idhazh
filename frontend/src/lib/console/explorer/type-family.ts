/** Which family a column's engine type belongs to: the one answer every part of the Data explorer
 * reads when it treats a column by its type.
 *
 * The engine is DuckDB, and these are the names it prints for a column's type: `VARCHAR`,
 * `BIGINT`, `DECIMAL(18,4)`, `TIMESTAMP_NS`, `TIMESTAMP WITH TIME ZONE`, `VARCHAR[]`,
 * `STRUCT(a INTEGER)`. It prints an alias by its own name - `INT` as `INTEGER`, `TIMESTAMPTZ` as
 * `TIMESTAMP WITH TIME ZONE` - so no alias is listed. The answer table prints and sorts a cell by
 * its column's family, the chart picks its shape from the families of the answer's columns, and a
 * type label is painted in its family's colour. A list or a struct is `nested` whatever it holds,
 * because `TIMESTAMP[]` is a list rather than a time, so that test comes first. A name no rule
 * knows is `other`.
 */

export type TypeFamily = 'whole' | 'decimal' | 'date' | 'timestamp' | 'time' | 'interval' | 'truth' | 'text' | 'bytes' | 'nested' | 'other';

const NESTED = /\[\d*\]$|^(STRUCT|MAP|UNION)\(/;

const RULES: readonly (readonly [TypeFamily, RegExp])[] = [
	['whole', /^U?(TINYINT|SMALLINT|INTEGER|BIGINT|HUGEINT)$|^BIGNUM$/],
	['decimal', /^(FLOAT|DOUBLE)$|^DECIMAL\(/],
	['date', /^DATE$/],
	['timestamp', /^TIMESTAMP(_S|_MS|_NS)?$|^TIMESTAMP WITH TIME ZONE$/],
	['time', /^TIME(_NS)?$|^TIME WITH TIME ZONE$/],
	['interval', /^INTERVAL$/],
	['truth', /^BOOLEAN$/],
	['text', /^(VARCHAR|UUID)$|^ENUM\(/],
	['bytes', /^BLOB$/]
];

/** The family of one engine type name. Case and the space around the name do not change it. */
export function classifyType(engineType: string): TypeFamily {
	const type = engineType.trim().toUpperCase();
	if (NESTED.test(type)) return 'nested';
	return RULES.find(([, rule]) => rule.test(type))?.[0] ?? 'other';
}

/** A whole number or a decimal: a chart can draw it, and the table sorts it high to low first. */
export function isNumber(family: TypeFamily): boolean {
	return family === 'whole' || family === 'decimal';
}

/** A date or a timestamp: it falls on one UTC day, so it can be a date chart's axis, and the
 * table sorts it newest first. */
export function isDay(family: TypeFamily): boolean {
	return family === 'date' || family === 'timestamp';
}
