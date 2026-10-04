/**
 * What may a caller ask the query door for, and what can it get back?
 *
 * A caller names a ledger, the columns it draws, a closed date range and, if it
 * wants, a filter. It gets back one of four answers, so a panel draws the right
 * one of four nothings without inspecting an error. A request the door cannot
 * answer is the caller's defect rather than the data's, so it is refused by name
 * before anything is fetched: that refusal is `SliceRequestError`. A file the
 * ledger should hold and does not is the data's defect, and the answer names
 * which of four faults it is.
 *
 * Every day here is a UTC day, written `YYYY-MM-DD` (CLAUDE.md section 2).
 * Imports nothing tied to one environment, so a Node test loads it as it is.
 */

/** A UTC day, `YYYY-MM-DD`. */
export type DateStamp = string;

/** The ledgers the console may query. A closed set: a panel names a ledger, never a path. */
export const LEDGER_NAMES = ['seen', 'feed-health', 'item-health', 'host-fingerprint', 'summary-quality-evals', 'candidate-models', 'item-health-summary', 'published', 'feed-retirements', 'visual-prunes', 'counterfactual-scores', 'scored-pairs', 'fitted-thresholds', 'holdout-pairs', 'score-distribution', 'archive', 'shard-outcomes', 'metrics', 'merge-line-holdout-scores', 'traces', 'day-metrics', 'digest-fragments', 'gardener', 'run-plan'] as const;

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

/** The four ways a packed ledger can be missing a file, declared once. The door
 *  carries them on its answers, the console's readers and notes take them from
 *  here, and the gardener's logs use the same words (`LedgerFault` in
 *  `backend/idhazh/contracts/ledger_fault.py`, held to this list by a backend test).
 *
 *  - `not-packed`: there is no `daily.json`, so no day of the ledger is packed.
 *  - `index-missing`: `daily.json` is there and `monthly.json` or `yearly.json`
 *    is not. The packing writes the three together, so the months or years it
 *    may have packed are out of sight.
 *  - `file-missing`: an index names a file that is not there.
 *  - `day-missing`: a day between the first and the newest packed day that no
 *    index names, so its rows are in no file a reader can find.
 *
 *  Some gaps are expected and are none of these: a day after the newest packed
 *  day, an entry with `rows: 0`, an entry `empty`, which held no row and has no
 *  file, a `monthly.json` or `yearly.json` with no entries, and a day an index
 *  records lost, which an answer names in `lostDays`. */
export const LEDGER_FAULTS = ['not-packed', 'index-missing', 'file-missing', 'day-missing'] as const;

export type LedgerFault = (typeof LEDGER_FAULTS)[number];

/** How many files the packing set aside unread, by the period it set them aside
 *  from: an entry's `covers`, a day, a month or a year. Only a period that set at
 *  least one file aside is named. Keyed by period, so two reads that meet the
 *  same month count its files once. */
export type SetAsideFiles = Readonly<Record<string, number>>;

/** What the door hands a panel. `rows` is empty for every state but `ok`.
 *  `through` is the newest day `daily.json` names, or `null` before the first
 *  compaction, so a panel can say how far its data reaches. `lostDays` names
 *  the days in the span an index records lost - a daily entry `lost`, or a day
 *  in a month's or a year's `lost_days` - ascending: each has no record, so a panel
 *  says so rather than drawing it as a day with no rows. `setAside` names the
 *  periods the span is read from whose packing set files aside unread, so a
 *  panel can say its rows may be short. `fault` names the
 *  missing file behind a `missing` or an `unreachable`, and is `null` for an
 *  `unreachable` with another cause: an index this build will not act on, a file
 *  that did not arrive whole, an engine that could not answer, or a span that
 *  starts before the oldest day any index names. */
export type SliceResult =
	| { state: 'ok'; rows: Row[]; through: DateStamp; lostDays: DateStamp[]; setAside: SetAsideFiles }
	| { state: 'quiet'; rows: []; through: DateStamp | null; lostDays: DateStamp[]; setAside: SetAsideFiles }
	| { state: 'missing'; rows: []; fault: Extract<LedgerFault, 'not-packed'> }
	| { state: 'unreachable'; rows: []; at: DateStamp; fault: Exclude<LedgerFault, 'not-packed'> | null };

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

/** Whether `stamp` is a real UTC day, `YYYY-MM-DD`, and not merely the shape of one.
 *  A day past 31 has no time at all, so it is answered before it is printed. */
export function isDay(stamp: unknown): stamp is DateStamp {
	if (typeof stamp !== 'string' || !DAY.test(stamp)) return false;
	const at = new Date(`${stamp}T00:00:00Z`);
	return !Number.isNaN(at.getTime()) && at.toISOString().slice(0, 10) === stamp;
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

/** One column of an answer, as the engine describes it. */
export type Column = { name: string; type: string };

/** What the keeper fetched for this call.
 *
 * A whole file counts at the bytes that arrived. A file read by byte range counts
 * at its whole indexed length, because the page cannot see which ranges the
 * engine read and that length is the most the read can cost. */
export type FetchCost = { files: number; bytes: number; alreadyHeld: number; ms: number };

/** What a span will cost before it is paid, and how far each selected ledger reaches. */
export type SpanCost = {
	files: number;
	bytes: number;
	unpackedDays: readonly DateStamp[];
	siteFrom: DateStamp | null;
	through: Readonly<Partial<Record<LedgerName, DateStamp>>>;
};

export type AskOptions = {
	ledgers: readonly LedgerName[];
	from: DateStamp;
	to: DateStamp;
	sql: string;
	maxChars: number;
	maxRows: number;
	maxFetchBytes: number;
};

export type AskFault = Exclude<LedgerFault, 'not-packed'> | 'engine' | null;

export type AskRefusal =
	| { kind: 'statements'; count: number }
	| { kind: 'not-read-only'; word: string }
	| { kind: 'too-long'; chars: number; max: number }
	| { kind: 'over-ceiling'; bytes: number; files: number; max: number }
	| { kind: 'engine-error'; message: string };

/** What one selected ledger is missing inside the span a written question read:
 *  the days its indexes record lost, ascending, and the files its periods set
 *  aside unread. An answer names only a ledger that is missing either. */
export type SpanGap = { ledger: LedgerName; lostDays: readonly DateStamp[]; setAside: SetAsideFiles };

export type AskResult =
	| { state: 'ok'; columns: readonly Column[]; rows: Row[]; capped: boolean; read: FetchCost; unpackedDays: readonly DateStamp[]; siteFrom: DateStamp | null; gaps: readonly SpanGap[] }
	| { state: 'quiet'; columns: readonly Column[]; read: FetchCost; siteFrom: DateStamp | null; gaps: readonly SpanGap[] }
	| { state: 'missing'; ledger: LedgerName }
	| { state: 'unreachable'; ledger: LedgerName | null; at: DateStamp | null; fault: AskFault }
	| { state: 'refused'; because: AskRefusal };
