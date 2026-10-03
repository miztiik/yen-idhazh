/**
 * What does the query door ask the engine, and how does the answer come back as rows?
 *
 * One statement a slice: the requested columns, from the chosen files, between
 * two UTC days, under the caller's filter. Every column name was checked against
 * `COLUMN_NAME` before it reaches here and is then double-quoted, and every value
 * the caller supplied is a bound parameter, so no text a panel passes can become
 * SQL (Guardrail #11). The file names are minted by the engine, never taken from
 * an index or a caller.
 *
 * **Files are read by column name**, so a day written before a column existed
 * reads that column as null. A column no file in the span holds reads as null in
 * every row, the same answer, and the console says which column that was - a
 * name nobody wrote would otherwise look exactly like a reading nobody took.
 *
 * **An integer comes back as a `number`.** The engine hands a 64-bit integer
 * back as a `BigInt`, and one outside the safe range is refused by name rather
 * than rounded, because a rounded count is a wrong count nobody can see.
 *
 * Imports nothing tied to one environment, so a Node test loads it as it is.
 */

import type { DateStamp, Predicate, Row, SliceOptions } from './slice-shapes';

/** The cell every compacted row carries its UTC day in: `ledger.keys.DATE_CELL`. */
export const DATE_COLUMN = 'date';

/** A value a statement binds. */
export type Bound = string | number;

/** A file the engine reads by byte range: the name it reads it under, and the
 *  length in bytes the host gave when the engine opened it. */
export interface OpenedAddress {
	name: string;
	bytes: number;
}

/** The engine, as the door needs it: bytes in, a name out, and rows out of a
 *  statement over names. */
export interface QueryEngine {
	/** Hands `bytes` to the engine and answers the name it now reads them under,
	 *  which the engine mints. A browser's engine takes the buffer and leaves
	 *  `bytes` empty, so a caller hands one buffer over once. */
	register(bytes: Uint8Array): Promise<string>;
	/** Has the engine read the file at `url` by byte range, opens it, and answers
	 *  the name it now reads it under, which the engine mints, and the length the
	 *  host gave. Only an engine that reads a host itself has it. */
	registerAddress?(url: string): Promise<OpenedAddress>;
	/** Forgets files registered earlier, by the names `register` or
	 *  `registerAddress` gave them. */
	drop(names: readonly string[]): Promise<void>;
	/** Every row `sql` returns with `params` bound in order, as the engine hands them back. */
	rows(sql: string, params: readonly Bound[]): Promise<Record<string, unknown>[]>;
}

/** An engine value a `Row` cannot hold as it is. */
export class SliceValueError extends Error {
	constructor(message: string) {
		super(message);
		this.name = 'SliceValueError';
	}
}

const quoted = (column: string): string => `"${column}"`;

/** The SQL list naming every file, in the order given. The engine minted every
 *  name, and each is still quoted as a string literal rather than trusted. */
export function listOf(names: readonly string[]): string {
	return `[${names.map((name) => `'${name.replaceAll("'", "''")}'`).join(', ')}]`;
}

/** The table every statement reads: the files, matched by column name. */
function source(files: string): string {
	return `read_parquet(${files}, union_by_name = true)`;
}

function clause(predicate: Predicate, present: ReadonlySet<string>, params: Bound[]): string {
	const column = present.has(predicate.column) ? quoted(predicate.column) : 'NULL';
	if (predicate.op === 'in') {
		const values = predicate.value as readonly Bound[];
		params.push(...values);
		return `${column} IN (${values.map(() => '?').join(', ')})`;
	}
	params.push(predicate.value as Bound);
	return `${column} ${predicate.op} ?`;
}

/** The one statement a slice runs, and the values it binds, in order. `until` is
 *  the last day asked for, already clamped to the newest day compacted. */
export function statementFor(
	files: string,
	present: ReadonlySet<string>,
	request: Required<SliceOptions>,
	until: DateStamp
): { sql: string; params: Bound[] } {
	const params: Bound[] = [request.from, until];
	const select = request.columns
		.map((column) => (present.has(column) ? quoted(column) : `NULL AS ${quoted(column)}`))
		.join(', ');
	const day = present.has(DATE_COLUMN) ? quoted(DATE_COLUMN) : 'NULL';
	const where = [`${day} >= ?`, `${day} <= ?`, ...request.where.map((p) => clause(p, present, params))];
	// Sorted by every requested column, left to right, so the same files give the
	// same rows in the same order whichever engine read them and however it split
	// the work.
	return { sql: `SELECT ${select} FROM ${source(files)} WHERE ${where.join(' AND ')} ORDER BY ALL`, params };
}

/** One engine value as a `Row` holds it, or a `SliceValueError` naming the column. */
export function cellOf(column: string, value: unknown): Row[string] {
	if (value === null || value === undefined) return null;
	if (typeof value === 'bigint') {
		if (value > BigInt(Number.MAX_SAFE_INTEGER) || value < BigInt(Number.MIN_SAFE_INTEGER)) {
			throw new SliceValueError(`${column} holds ${value}, which is outside the range a number holds exactly`);
		}
		return Number(value);
	}
	if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value;
	throw new SliceValueError(`${column} holds a value of type ${typeof value}, and a row holds strings, numbers, booleans and nulls`);
}

/** Every row the files the engine holds under `names` hold for this request,
 *  each keyed by the requested columns in order. */
export async function rowsFor(
	engine: QueryEngine,
	names: readonly string[],
	request: Required<SliceOptions>,
	until: DateStamp,
	warn: (message: string) => void
): Promise<Row[]> {
	const files = listOf(names);
	const described = await engine.rows(`DESCRIBE SELECT * FROM ${source(files)}`, []);
	const present = new Set(described.map((row) => String(row.column_name)));
	const named = new Set([...request.columns, ...request.where.map((p) => p.column), DATE_COLUMN]);
	for (const column of named) {
		if (!present.has(column)) warn(`no file in this span holds the column ${column}, so it reads as null`);
	}
	const { sql, params } = statementFor(files, present, request, until);
	const raw = await engine.rows(sql, params);
	return raw.map((cells) =>
		Object.fromEntries(request.columns.map((column) => [column, cellOf(column, cells[column])]))
	);
}
