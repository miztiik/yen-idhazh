/** Run one written question over chosen ledgers and days. */

import type { CompactEntry, Period } from './compact-index';
import type { PageKeeper, WantedFile } from './page-keeper';
import { filesFor, firstNamed, writerDaysFor, type ChosenFile } from './slice';
import { listOf, type QueryEngine } from './slice-query';
import { dataPath, dataVersion, rawDataPath, rawIndexPath, readIndexFrom, RANGED_PERIODS } from './slice-reader';
import { checkStatement, statementKind } from './statement';
import { readRawDayIndex } from './raw-day-index';
import { LEDGER_NAMES, type AskOptions, type AskResult, type Column, type DateStamp, type FetchCost, type LedgerName, type Row, type SpanCost } from './slice-shapes';

export type RawListedThrough = Readonly<Partial<Record<LedgerName, DateStamp>>>;

type LedgerPlan = { ledger: LedgerName; through: DateStamp | null; files: WantedFile[]; unpackedDays: DateStamp[]; emptySource: WantedFile[]; unreachable: AskResult | null };
type Plan = { ledgers: LedgerPlan[]; cost: SpanCost };
let queue: Promise<void> = Promise.resolve();

async function serial<T>(work: () => Promise<T>): Promise<T> {
	const previous = queue;
	let release!: () => void;
	queue = new Promise<void>((resolve) => { release = resolve; });
	await previous;
	try { return await work(); }
	finally { release(); }
}

function wanted(period: Period, ledger: LedgerName, file: ChosenFile): WantedFile {
	return { path: dataPath(ledger, period, file.entry.covers), version: dataVersion(file.entry), bytes: file.entry.bytes, byRange: RANGED_PERIODS.has(period) };
}

async function rawListing(keeper: PageKeeper, ledger: LedgerName, day: DateStamp): Promise<WantedFile[] | AskResult> {
	let bytes: Uint8Array | null;
	try { bytes = await keeper.index(rawIndexPath(ledger, day)); }
	catch { return { state: 'unreachable', ledger, at: day, fault: 'index-missing' }; }
	if (bytes === null) return { state: 'unreachable', ledger, at: day, fault: 'file-missing' };
	let parsed: unknown;
	try { parsed = JSON.parse(new TextDecoder().decode(bytes)); }
	catch { return { state: 'unreachable', ledger, at: day, fault: 'index-missing' }; }
	const read = readRawDayIndex(parsed, ledger, day);
	if ('refused' in read) return { state: 'unreachable', ledger, at: day, fault: 'index-missing' };
	return read.index.files.map((file, at) => ({ path: rawDataPath(ledger, day, file), version: `${read.index.bytes[at]}`, bytes: read.index.bytes[at] ?? 0, byRange: false }));
}

async function compactIndexes(keeper: PageKeeper, ledger: LedgerName): Promise<{ daily: CompactEntry[]; monthly: CompactEntry[]; yearly: CompactEntry[] } | AskResult> {
	const daily = await readIndexFrom(keeper, ledger, 'daily');
	if (daily === null) return { state: 'missing', ledger };
	if ('refused' in daily) return { state: 'unreachable', ledger, at: null, fault: 'index-missing' };
	const monthly = await readIndexFrom(keeper, ledger, 'monthly');
	const yearly = await readIndexFrom(keeper, ledger, 'yearly');
	return { daily: daily.index.entries, monthly: monthly !== null && 'index' in monthly ? monthly.index.entries : [], yearly: yearly !== null && 'index' in yearly ? yearly.index.entries : [] };
}

async function planLedger(keeper: PageKeeper, ledger: LedgerName, from: DateStamp, to: DateStamp, rawListed: RawListedThrough): Promise<LedgerPlan> {
	const indexed = await compactIndexes(keeper, ledger);
	if ('state' in indexed) return { ledger, through: null, files: [], unpackedDays: [], emptySource: [], unreachable: indexed };
	const through = indexed.daily.at(-1)?.covers ?? null;
	const files: WantedFile[] = [];
	let unreachable: AskResult | null = null;
	if (through !== null && from <= through) {
		const until = to < through ? to : through;
		if (from < (indexed.daily[0]?.covers ?? from) && indexed.monthly.length === 0) unreachable = { state: 'unreachable', ledger, at: from, fault: 'index-missing' };
		else if (from < firstNamed(indexed.daily, indexed.monthly, []) && indexed.yearly.length === 0) unreachable = { state: 'unreachable', ledger, at: from, fault: 'index-missing' };
		else {
			const selection = filesFor(from, until, indexed.daily, indexed.monthly, indexed.yearly);
			if ('hole' in selection) unreachable = { state: 'unreachable', ledger, at: selection.hole, fault: 'day-missing' };
			else files.push(...selection.files.filter((file) => file.entry.rows > 0).map((file) => wanted(file.period, ledger, file)));
		}
	}
	const rawDays = writerDaysFor(from, to, through, rawListed[ledger] ?? null);
	for (const day of rawDays) {
		const listed = await rawListing(keeper, ledger, day);
		if ('state' in listed) { unreachable ??= listed; continue; }
		files.push(...listed);
	}
	let emptySource: WantedFile[] = [];
	if (files.length === 0 && through !== null) {
		const selection = filesFor(through, through, indexed.daily, indexed.monthly, indexed.yearly);
		if ('files' in selection) emptySource = selection.files.filter((file) => file.entry.rows > 0).map((file) => wanted(file.period, ledger, file));
	}
	return { ledger, through: rawListed[ledger] ?? through, files, unpackedDays: rawDays, emptySource, unreachable };
}

async function plan(keeper: PageKeeper, ledgers: readonly LedgerName[], from: DateStamp, to: DateStamp, rawListed: RawListedThrough): Promise<Plan | AskResult> {
	const chosen = [...new Set(ledgers)];
	if (chosen.length === 0) return { state: 'quiet', columns: [], read: { files: 0, bytes: 0, alreadyHeld: 0, ms: 0 } };
	for (const ledger of chosen) if (!(LEDGER_NAMES as readonly string[]).includes(ledger)) return { state: 'missing', ledger };
	const plans = await Promise.all(chosen.map((ledger) => planLedger(keeper, ledger, from, to, rawListed)));
	const failed = plans.find((one) => one.unreachable !== null);
	if (failed?.unreachable) return failed.unreachable;
	const allFiles = plans.flatMap((one) => one.files);
	return { ledgers: plans, cost: { files: allFiles.length, bytes: allFiles.reduce((sum, file) => sum + file.bytes, 0), unpackedDays: [...new Set(plans.flatMap((one) => one.unpackedDays))], through: Object.fromEntries(plans.flatMap((one) => one.through === null ? [] : [[one.ledger, one.through]])) } };
}

function quoteIdent(name: LedgerName): string { return `"${name.replaceAll('"', '""')}"`; }
function viewStatement(ledger: LedgerName, names: readonly string[], empty: boolean): string { return `CREATE OR REPLACE VIEW ${quoteIdent(ledger)} AS SELECT * FROM read_parquet(${listOf(names)}, union_by_name = true)${empty ? ' LIMIT 0' : ''}`; }

async function prepareViews(engine: QueryEngine, plans: readonly LedgerPlan[], heldNames: readonly string[][]): Promise<void> {
	const selected = new Set(plans.map((one) => one.ledger));
	for (const ledger of LEDGER_NAMES) if (!selected.has(ledger)) await engine.rows(`DROP VIEW IF EXISTS ${quoteIdent(ledger)}`, []);
	for (const [at, one] of plans.entries()) await engine.rows(viewStatement(one.ledger, heldNames[at] ?? [], one.files.length === 0), []);
}

function columnsOf(rows: Record<string, unknown>[]): Column[] { return rows.map((row) => ({ name: String(row.column_name ?? row.explain_key ?? ''), type: String(row.column_type ?? row.explain_value ?? 'VARCHAR') })); }
function textRows(rows: Record<string, unknown>[], columns: readonly Column[]): Row[] { return rows.map((row) => Object.fromEntries(columns.map((column) => [column.name, row[column.name] == null ? null : String(row[column.name])]))) as Row[]; }
async function describe(engine: QueryEngine, sql: string): Promise<Column[]> { return statementKind(sql) === 'EXPLAIN' ? [{ name: 'explain_key', type: 'VARCHAR' }, { name: 'explain_value', type: 'VARCHAR' }] : columnsOf(await engine.rows(`DESCRIBE SELECT * FROM (\n${sql}\n)`, [])); }
async function runRows(engine: QueryEngine, sql: string, maxRows: number, columns: readonly Column[]): Promise<{ rows: Row[]; capped: boolean }> { const statement = statementKind(sql) === 'EXPLAIN' ? sql : `SELECT COLUMNS(*)::VARCHAR FROM (\n${sql}\n) LIMIT ${maxRows + 1}`; const rows = await engine.rows(statement, []); return { rows: textRows(rows.slice(0, maxRows), columns), capped: rows.length > maxRows }; }

export async function readAskCost(keeper: PageKeeper, ledgers: readonly LedgerName[], from: DateStamp, to: DateStamp, rawListed: RawListedThrough): Promise<SpanCost> {
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
		if (planned.cost.bytes > opts.maxFetchBytes) return { state: 'refused', because: { kind: 'over-ceiling', bytes: planned.cost.bytes, files: planned.cost.files, max: opts.maxFetchBytes } };
		if (planned.ledgers.every((one) => one.files.length === 0 && one.emptySource.length === 0)) return { state: 'quiet', columns: [], read: { files: 0, bytes: 0, alreadyHeld: 0, ms: Date.now() - started } };
		const viewFiles = planned.ledgers.map((one) => one.files.length > 0 ? one.files : one.emptySource);
		const held = await Promise.all(viewFiles.map((files) => keeper.hold(files)));
		const failedAt = held.findIndex((one) => 'failed' in one);
		if (failedAt !== -1) {
			for (const one of held) if (!('failed' in one)) await one.done();
			return { state: 'unreachable', ledger: planned.ledgers[failedAt]?.ledger ?? null, at: null, fault: null };
		}
		try {
			const okHeld = held as Extract<Awaited<ReturnType<PageKeeper['hold']>>, { names: string[] }>[];
			const engine = okHeld[0]?.engine;
			if (engine === undefined) return { state: 'unreachable', ledger: null, at: null, fault: 'engine' };
			await prepareViews(engine, planned.ledgers, okHeld.map((one) => one.names));
			const columns = await describe(engine, checked.sql);
			const answer = await runRows(engine, checked.sql, opts.maxRows, columns);
			const read: FetchCost = { files: planned.cost.files, bytes: planned.cost.bytes, alreadyHeld: 0, ms: Date.now() - started };
			return answer.rows.length === 0 ? { state: 'quiet', columns, read } : { state: 'ok', columns, rows: answer.rows, capped: answer.capped, read, unpackedDays: planned.cost.unpackedDays };
		} catch (error) {
			return { state: 'refused', because: { kind: 'engine-error', message: error instanceof Error ? error.message : String(error) } };
		} finally {
			await Promise.all(held.map((one) => 'failed' in one ? Promise.resolve() : one.done()));
		}
	});
}