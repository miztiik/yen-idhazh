/** How does the written-question door turn selected ledgers and days into one answer? */

import { COMPACT_PERIODS, type CompactEntry, type Period } from './compact-index';
import type { PageKeeper, WantedFile } from './page-keeper';
import { filesFor, firstNamed, newestNamed, writerDaysFor, type ChosenFile } from './slice';
import { listOf, type QueryEngine } from './slice-query';
import {
	dataPath,
	dataVersion,
	rawDataPath,
	rawIndexPath,
	explainRefusal,
	faultLine,
	LOG_PREFIX,
	readIndexFrom,
	RANGED_PERIODS
} from './slice-reader';
import { readRawDayIndex } from './raw-day-index';
import { checkStatement, statementKind } from './statement';
import {
	LEDGER_NAMES,
	type AskOptions,
	type AskResult,
	type Column,
	type DateStamp,
	type FetchCost,
	type LedgerName,
	type Row,
	type SpanCost
} from './slice-shapes';

export type RawListedThrough = Readonly<Partial<Record<LedgerName, DateStamp>>>;

type Indexes = { daily: CompactEntry[]; monthly: CompactEntry[]; yearly: CompactEntry[] };
type FileMeta = { ledger: LedgerName; day: DateStamp | null };
type LedgerPlan = {
	ledger: LedgerName;
	through: DateStamp | null;
	files: WantedFile[];
	metas: FileMeta[];
	emptySource: WantedFile[];
	emptyMetas: FileMeta[];
	unpackedDays: DateStamp[];
	unreachable: AskResult | null;
};
type Plan = { ledgers: LedgerPlan[]; cost: SpanCost; files: WantedFile[]; metas: FileMeta[] };

let queue: Promise<void> = Promise.resolve();

async function serial<T>(work: () => Promise<T>): Promise<T> {
	const previous = queue;
	let release!: () => void;
	queue = new Promise<void>((resolve) => {
		release = resolve;
	});
	await previous;
	try {
		return await work();
	} finally {
		release();
	}
}

function later(a: DateStamp | null, b: DateStamp | null): DateStamp | null {
	if (a === null) return b;
	if (b === null) return a;
	return a > b ? a : b;
}

function wanted(period: Period, ledger: LedgerName, file: ChosenFile): WantedFile {
	return {
		path: dataPath(ledger, period, file.entry.covers),
		version: dataVersion(file.entry),
		bytes: file.entry.bytes,
		byRange: RANGED_PERIODS.has(period)
	};
}

async function rawListing(
	keeper: PageKeeper,
	ledger: LedgerName,
	day: DateStamp
): Promise<{ files: WantedFile[]; metas: FileMeta[] } | AskResult> {
	let bytes: Uint8Array | null;
	try {
		bytes = await keeper.index(rawIndexPath(ledger, day));
	} catch {
		return { state: 'unreachable', ledger, at: day, fault: 'index-missing' };
	}
	if (bytes === null) return { state: 'unreachable', ledger, at: day, fault: 'file-missing' };

	let parsed: unknown;
	try {
		parsed = JSON.parse(new TextDecoder().decode(bytes));
	} catch {
		return { state: 'unreachable', ledger, at: day, fault: 'index-missing' };
	}
	const read = readRawDayIndex(parsed, ledger, day);
	if ('refused' in read) return { state: 'unreachable', ledger, at: day, fault: 'index-missing' };
	if (read.index.files.some((file) => !file.endsWith('.parquet'))) {
		return { state: 'unreachable', ledger, at: day, fault: 'index-missing' };
	}

	return {
		files: read.index.files.map((file, at) => ({
			path: rawDataPath(ledger, day, file),
			version: `${read.index.bytes[at]}`,
			bytes: read.index.bytes[at] ?? 0,
			byRange: false
		})),
		metas: read.index.files.map(() => ({ ledger, day }))
	};
}

/** A ledger's three compact indexes, or the answer that says why the question cannot run.
 *  The build refuses to publish a ledger that lacks any of the three, so on the site an
 *  absent or refused index is a broken deploy, and none is ever read as an empty list. */
async function compactIndexes(
	keeper: PageKeeper,
	ledger: LedgerName,
	from: DateStamp,
	to: DateStamp
): Promise<Indexes | AskResult> {
	const indexes: Indexes = { daily: [], monthly: [], yearly: [] };
	for (const period of COMPACT_PERIODS) {
		const reading = await readIndexFrom(keeper, ledger, period);
		if (reading === null) {
			if (period === 'daily') return { state: 'missing', ledger };
			keeper.warn(faultLine(ledger, { fault: 'index-missing', period }));
			return { state: 'unreachable', ledger, at: from, fault: 'index-missing' };
		}
		if ('refused' in reading) {
			keeper.warn(`${LOG_PREFIX} ${ledger} ${from} to ${to}: ${explainRefusal(period, reading.refused)}, so the question did not run`);
			return { state: 'unreachable', ledger, at: from, fault: 'index-missing' };
		}
		indexes[period] = reading.index.entries;
	}
	return indexes;
}

function compactSelection(
	ledger: LedgerName,
	from: DateStamp,
	until: DateStamp,
	indexes: Indexes
): { files: WantedFile[]; metas: FileMeta[] } | AskResult {
	const first = newestNamed(indexes.daily, indexes.monthly, indexes.yearly) === null
		? null
		: firstNamed(indexes.daily, indexes.monthly, indexes.yearly);
	if (first === null) return { files: [], metas: [] };
	if (from < first && indexes.monthly.length === 0 && indexes.yearly.length === 0) {
		return { state: 'unreachable', ledger, at: from, fault: 'index-missing' };
	}
	const selection = filesFor(from, until, indexes.daily, indexes.monthly, indexes.yearly);
	if ('hole' in selection) return { state: 'unreachable', ledger, at: selection.hole, fault: 'day-missing' };
	return {
		files: selection.files.filter((file) => file.entry.rows > 0).map((file) => wanted(file.period, ledger, file)),
		metas: selection.files
			.filter((file) => file.entry.rows > 0)
			.map((file) => ({ ledger, day: file.firstDay }))
	};
}

async function filesForDay(
	keeper: PageKeeper,
	ledger: LedgerName,
	day: DateStamp,
	indexes: Indexes,
	rawListed: RawListedThrough
): Promise<{ files: WantedFile[]; metas: FileMeta[] }> {
	if ((rawListed[ledger] ?? '') >= day) {
		const raw = await rawListing(keeper, ledger, day);
		if (!('state' in raw)) return raw;
	}
	const compact = compactSelection(ledger, day, day, indexes);
	return 'state' in compact ? { files: [], metas: [] } : compact;
}

async function planLedger(
	keeper: PageKeeper,
	ledger: LedgerName,
	from: DateStamp,
	to: DateStamp,
	rawListed: RawListedThrough
): Promise<LedgerPlan> {
	const indexed = await compactIndexes(keeper, ledger, from, to);
	if ('state' in indexed) {
		return { ledger, through: null, files: [], metas: [], emptySource: [], emptyMetas: [], unpackedDays: [], unreachable: indexed };
	}

	const newestPacked = newestNamed(indexed.daily, indexed.monthly, indexed.yearly);
	const through = later(newestPacked, rawListed[ledger] ?? null);
	const files: WantedFile[] = [];
	const metas: FileMeta[] = [];
	let unreachable: AskResult | null = null;

	if (newestPacked !== null && from <= newestPacked) {
		const until = to < newestPacked ? to : newestPacked;
		const compact = compactSelection(ledger, from, until, indexed);
		if ('state' in compact) unreachable = compact;
		else {
			files.push(...compact.files);
			metas.push(...compact.metas);
		}
	}

	const rawDays = writerDaysFor(from, to, newestPacked, rawListed[ledger] ?? null);
	for (const day of rawDays) {
		const listed = await rawListing(keeper, ledger, day);
		if ('state' in listed) {
			unreachable ??= listed;
			continue;
		}
		files.push(...listed.files);
		metas.push(...listed.metas);
	}

	// A ledger with no file in the span is read through an empty view over its newest day's
	// files, so only such a ledger needs that day planned, and its listing fetched.
	const needsEmptyView = files.length === 0 && unreachable === null && through !== null;
	const empty = needsEmptyView ? await filesForDay(keeper, ledger, through, indexed, rawListed) : { files: [], metas: [] };
	return {
		ledger,
		through,
		files,
		metas,
		emptySource: empty.files,
		emptyMetas: empty.metas,
		unpackedDays: rawDays,
		unreachable
	};
}

async function plan(
	keeper: PageKeeper,
	ledgers: readonly LedgerName[],
	from: DateStamp,
	to: DateStamp,
	rawListed: RawListedThrough
): Promise<Plan | AskResult> {
	const chosen = [...new Set(ledgers)];
	if (chosen.length === 0) {
		return { state: 'quiet', columns: [], read: { files: 0, bytes: 0, alreadyHeld: 0, ms: 0 } };
	}
	for (const ledger of chosen) {
		if (!(LEDGER_NAMES as readonly string[]).includes(ledger)) return { state: 'missing', ledger };
	}

	const ledgersPlanned = await Promise.all(chosen.map((ledger) => planLedger(keeper, ledger, from, to, rawListed)));
	const failed = ledgersPlanned.find((one) => one.unreachable !== null);
	if (failed?.unreachable) return failed.unreachable;
	const noDays = ledgersPlanned.find((one) => one.through === null);
	if (noDays) return { state: 'missing', ledger: noDays.ledger };
	const files = ledgersPlanned.flatMap((one) => one.files);
	const metas = ledgersPlanned.flatMap((one) => one.metas);
	return {
		ledgers: ledgersPlanned,
		files,
		metas,
		cost: {
			files: files.length,
			bytes: files.reduce((sum, file) => sum + file.bytes, 0),
			unpackedDays: [...new Set(ledgersPlanned.flatMap((one) => one.unpackedDays))],
			through: Object.fromEntries(ledgersPlanned.flatMap((one) => (one.through === null ? [] : [[one.ledger, one.through]])))
		}
	};
}

function quoteIdent(name: LedgerName): string {
	return `"${name.replaceAll('"', '""')}"`;
}

function viewStatement(ledger: LedgerName, names: readonly string[], empty: boolean): string {
	return `CREATE OR REPLACE VIEW ${quoteIdent(ledger)} AS SELECT * FROM read_parquet(${listOf(names)}, union_by_name = true)${empty ? ' LIMIT 0' : ''}`;
}

async function prepareViews(engine: QueryEngine, plans: readonly LedgerPlan[], heldNames: readonly string[][]): Promise<void> {
	const selected = new Set(plans.map((one) => one.ledger));
	for (const ledger of LEDGER_NAMES) {
		if (!selected.has(ledger)) await engine.rows(`DROP VIEW IF EXISTS ${quoteIdent(ledger)}`, []);
	}
	for (const [at, one] of plans.entries()) {
		await engine.rows(viewStatement(one.ledger, heldNames[at] ?? [], one.files.length === 0), []);
	}
}

function columnsOf(rows: Record<string, unknown>[]): Column[] {
	return rows.map((row) => ({
		name: String(row.column_name ?? row.explain_key ?? ''),
		type: String(row.column_type ?? row.explain_value ?? 'VARCHAR')
	}));
}

function textRows(rows: Record<string, unknown>[], columns: readonly Column[]): Row[] {
	return rows.map((row) => Object.fromEntries(columns.map((column) => [column.name, row[column.name] == null ? null : String(row[column.name])]))) as Row[];
}

async function describe(engine: QueryEngine, sql: string): Promise<Column[]> {
	if (statementKind(sql) === 'EXPLAIN') {
		return [{ name: 'explain_key', type: 'VARCHAR' }, { name: 'explain_value', type: 'VARCHAR' }];
	}
	return columnsOf(await engine.rows(`DESCRIBE SELECT * FROM (\n${sql}\n)`, []));
}

async function runRows(
	engine: QueryEngine,
	sql: string,
	maxRows: number,
	columns: readonly Column[]
): Promise<{ rows: Row[]; capped: boolean }> {
	const statement = statementKind(sql) === 'EXPLAIN' ? sql : `SELECT COLUMNS(*)::VARCHAR FROM (\n${sql}\n) LIMIT ${maxRows + 1}`;
	const rows = await engine.rows(statement, []);
	return { rows: textRows(rows.slice(0, maxRows), columns), capped: rows.length > maxRows };
}

function readCost(files: readonly WantedFile[], fetched: readonly boolean[], started: number): FetchCost {
	return {
		files: fetched.filter(Boolean).length,
		bytes: files.reduce((sum, file, at) => sum + (fetched[at] ? file.bytes : 0), 0),
		alreadyHeld: fetched.filter((one) => !one).length,
		ms: Date.now() - started
	};
}

export async function readAskCost(
	keeper: PageKeeper,
	ledgers: readonly LedgerName[],
	from: DateStamp,
	to: DateStamp,
	rawListed: RawListedThrough
): Promise<SpanCost> {
	const planned = await plan(keeper, ledgers, from, to, rawListed);
	return 'state' in planned ? { files: 0, bytes: 0, unpackedDays: [], through: {} } : planned.cost;
}

export async function readAsk(keeper: PageKeeper, opts: AskOptions, rawListed: RawListedThrough): Promise<AskResult> {
	const checked = checkStatement(opts.sql, opts.maxChars);
	if (checked.refusal !== null) return { state: 'refused', because: checked.refusal };
	return serial(async () => {
		const started = Date.now();
		const planned = await plan(keeper, opts.ledgers, opts.from, opts.to, rawListed);
		if ('state' in planned) return planned;
		if (planned.cost.bytes > opts.maxFetchBytes) {
			return { state: 'refused', because: { kind: 'over-ceiling', bytes: planned.cost.bytes, files: planned.cost.files, max: opts.maxFetchBytes } };
		}
		const noFilesInSpan = planned.ledgers.every((one) => one.files.length === 0);
		if (noFilesInSpan) {
			return { state: 'quiet', columns: [], read: { files: 0, bytes: 0, alreadyHeld: 0, ms: Date.now() - started } };
		}

		const files = planned.ledgers.flatMap((one) => (one.files.length > 0 ? one.files : one.emptySource));
		const metas = planned.ledgers.flatMap((one) => (one.files.length > 0 ? one.metas : one.emptyMetas));
		let held: Awaited<ReturnType<PageKeeper['hold']>>;
		try {
			held = await keeper.hold(files);
		} catch {
			return { state: 'unreachable', ledger: null, at: null, fault: 'engine' };
		}
		if ('failed' in held) {
			const meta = metas[held.failed];
			return { state: 'unreachable', ledger: meta?.ledger ?? null, at: meta?.day ?? null, fault: null };
		}

		try {
			const namesByLedger: string[][] = [];
			let offset = 0;
			for (const one of planned.ledgers) {
				const count = one.files.length > 0 ? one.files.length : one.emptySource.length;
				namesByLedger.push(held.names.slice(offset, offset + count));
				offset += count;
			}
			await prepareViews(held.engine, planned.ledgers, namesByLedger);
			const columns = await describe(held.engine, checked.sql);
			const answer = await runRows(held.engine, checked.sql, opts.maxRows, columns);
			const read = readCost(files, held.fetched, started);
			return answer.rows.length === 0
				? { state: 'quiet', columns, read }
				: { state: 'ok', columns, rows: answer.rows, capped: answer.capped, read, unpackedDays: planned.cost.unpackedDays };
		} catch (error) {
			return { state: 'refused', because: { kind: 'engine-error', message: error instanceof Error ? error.message : String(error) } };
		} finally {
			await held.done();
		}
	});
}
