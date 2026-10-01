/**
 * What may a caller ask the query door for, and what can it get back?
 *
 * A caller names a ledger, the columns it draws, a closed date range and, if it
 * wants, a filter. It gets back one of four answers, so a panel draws the right
 * one of four nothings without inspecting an error. A request the door cannot
 * answer is the caller's defect rather than the data's, so it is refused by name
 * before anything is fetched: that refusal is `SliceRequestError`.
 *
 * Every day here is a UTC day, written `YYYY-MM-DD` (CLAUDE.md section 2).
 * Imports nothing tied to one environment, so a Node test loads it as it is.
 */

/** A UTC day, `YYYY-MM-DD`. */
export type DateStamp = string;

/** The ledgers the console may query. A closed set: a panel names a ledger, never a path. */
export const LEDGER_NAMES = ['host-fingerprint', 'item-health', 'summary-quality-evals'] as const;

export type LedgerName = (typeof LEDGER_NAMES)[number];

/** A structured filter, never raw SQL. The door binds `value` as a query parameter,
 *  so no text a panel passes can become SQL (Guardrail #11). */
export type Predicate = {
	column: string;
	op: '=' | '!=' | '<' | '<=' | '>' | '>=' | 'in';
	value: string | number | readonly (string | number)[];
};

/** What a caller asks for. `columns` is required and non-empty; the range is
 *  closed at both ends. */
export type SliceOptions = {
	columns: readonly string[];
	from: DateStamp;
	to: DateStamp;
	where?: readonly Predicate[];
};

/** One parquet row as the door hands it back. An integer is a `number`. */
export type Row = Record<string, string | number | boolean | null>;

/** What the door hands a panel. `rows` is empty for every state but `ok`.
 *  `through` is the newest day `daily.json` names, or `null` before the first
 *  compaction, so a panel can say how far its data reaches. */
export type SliceResult =
	| { state: 'ok'; rows: Row[]; through: DateStamp }
	| { state: 'quiet'; rows: []; through: DateStamp | null }
	| { state: 'missing'; rows: [] }
	| { state: 'unreachable'; rows: []; at: DateStamp };

/** A request the door refuses before it fetches anything. */
export class SliceRequestError extends Error {
	constructor(message: string) {
		super(`the query door refuses this request: ${message}`);
		this.name = 'SliceRequestError';
	}
}

/** A column name the door will quote into a query. Anything else is refused. */
export const COLUMN_NAME = /^[a-z_][a-z0-9_]*$/;

const DAY = /^\d{4}-\d{2}-\d{2}$/;

const OPERATORS: ReadonlySet<string> = new Set(['=', '!=', '<', '<=', '>', '>=', 'in']);

/** Whether `stamp` is a real UTC day, `YYYY-MM-DD`, and not merely the shape of one. */
export function isDay(stamp: unknown): stamp is DateStamp {
	if (typeof stamp !== 'string' || !DAY.test(stamp)) return false;
	return new Date(`${stamp}T00:00:00Z`).toISOString().slice(0, 10) === stamp;
}

function checkedColumn(column: unknown, where: string): string {
	if (typeof column !== 'string' || !COLUMN_NAME.test(column)) {
		throw new SliceRequestError(
			`${where} ${JSON.stringify(column)} is not a column name (lower case, digits and _)`
		);
	}
	return column;
}

function isBindable(value: unknown): value is string | number {
	return typeof value === 'string' || (typeof value === 'number' && Number.isFinite(value));
}

function checkedPredicate(predicate: Predicate): Predicate {
	const column = checkedColumn(predicate?.column, 'the filter column');
	if (!OPERATORS.has(predicate.op)) {
		throw new SliceRequestError(`the filter on ${column} uses ${JSON.stringify(predicate.op)}`);
	}
	if (predicate.op === 'in') {
		if (!Array.isArray(predicate.value) || predicate.value.length === 0) {
			throw new SliceRequestError(`the "in" filter on ${column} needs a non-empty list of values`);
		}
		if (!predicate.value.every(isBindable)) {
			throw new SliceRequestError(`the "in" filter on ${column} holds a value that is not a string or a number`);
		}
		return { column, op: 'in', value: [...predicate.value] };
	}
	if (!isBindable(predicate.value)) {
		throw new SliceRequestError(`the filter on ${column} compares with something that is not a string or a number`);
	}
	return { column, op: predicate.op, value: predicate.value };
}

/** The request as the door will run it, or a `SliceRequestError` naming what is wrong. */
export function checkedRequest(options: SliceOptions): Required<SliceOptions> {
	if (!Array.isArray(options?.columns) || options.columns.length === 0) {
		throw new SliceRequestError('it names no columns, and the door never reads every column');
	}
	const columns = options.columns.map((column) => checkedColumn(column, 'the column'));
	if (new Set(columns).size !== columns.length) {
		throw new SliceRequestError(`it names a column twice: ${columns.join(', ')}`);
	}
	for (const [end, stamp] of [['from', options.from], ['to', options.to]] as const) {
		if (!isDay(stamp)) throw new SliceRequestError(`"${end}" is ${JSON.stringify(stamp)}, not a YYYY-MM-DD UTC day`);
	}
	if (options.from > options.to) {
		throw new SliceRequestError(`"from" ${options.from} comes after "to" ${options.to}`);
	}
	return { columns, from: options.from, to: options.to, where: (options.where ?? []).map(checkedPredicate) };
}
