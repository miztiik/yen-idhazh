/** How does a written question read one session's consented compact ledgers? */

import { COMPACT_PERIODS, type CompactEntry, type Period } from './compact-index';
import type { FileShortfall, PageKeeper, WantedFile } from './page-keeper';
import { coveredDays, filesFor, firstNamed, newestFile, newestNamed } from './slice';
import { listOf, type QueryEngine } from './slice-query';
import { dataPath, dataVersion, explainRefusal, explainShortfall, indexPath, LOG_PREFIX, readIndexFrom } from './slice-reader';
import { checkStatement, statementKind } from './statement';
import { isDay, type AskOptions, type AskRefusal, type AskResult, type Column, type CutDays, type DateStamp, type LedgerName, type Row, type SetAsideFiles, type SpanCost, type SpanGap } from './slice-shapes';

type Indexes = Record<Period, CompactEntry[]>;
type IndexFailure = { failed: Period; refusal: string; absent: boolean };
type DayWindow = { from: DateStamp; to: DateStamp } | null;
type PlannedFile = { file: WantedFile; ledger: LedgerName; day: DateStamp; window: DayWindow };
type HeldSource = { name: string; window: DayWindow };
type LedgerPlan = {
	ledger: LedgerName;
	through: DateStamp | null;
	files: PlannedFile[];
	emptySource: PlannedFile[];
	cutBefore: DateStamp | null;
	lostDays: DateStamp[];
	setAside: SetAsideFiles;
};
export type QuestionPlan = { ledgers: LedgerPlan[]; files: PlannedFile[]; cost: SpanCost };

let queue: Promise<void> = Promise.resolve();
const ownedViews = new WeakMap<QueryEngine, Set<LedgerName>>();

/** Serialize all users of the engine's single connection, including Refresh. */
export async function serial<T>(work: () => Promise<T>): Promise<T> {
	const previous = queue;
	let release!: () => void;
	queue = new Promise<void>((resolve) => { release = resolve; });
	await previous;
	try { return await work(); } finally { release(); }
}

/** Drop views we created, not names inferred from a possibly newer catalog. */
export async function dropOwnedViews(engine: QueryEngine): Promise<void> {
	const owned = ownedViews.get(engine);
	if (owned === undefined) return;
	for (const ledger of [...owned]) {
		await engine.rows(`DROP VIEW IF EXISTS ${quoteIdent(ledger)}`, []);
		owned.delete(ledger);
	}
}

export async function createOwnedView(engine: QueryEngine, ledger: LedgerName, sources: readonly HeldSource[], empty: boolean): Promise<void> {
	await engine.rows(viewStatement(ledger, sources, empty), []);
	let owned = ownedViews.get(engine);
	if (owned === undefined) {
		owned = new Set();
		ownedViews.set(engine, owned);
	}
	owned.add(ledger);
}

/** All three absent means not packed; any partial or invalid set is a failure. */
export async function readIndexes(keeper: PageKeeper, ledger: LedgerName): Promise<Indexes | IndexFailure> {
	const readings = await Promise.all(COMPACT_PERIODS.map(async (period) => {
		try { return { period, reading: await readIndexFrom(keeper, ledger, period) }; }
		catch (error) { return { period, error }; }
	}));
	const allAbsent = readings.every((one) => 'reading' in one && one.reading === null);
	for (const one of readings) {
		const path = indexPath(keeper.catalog, ledger, one.period);
		if ('error' in one) return { failed: one.period, absent: false, refusal: `${path}: ${String(one.error)}` };
		if (one.reading === null) return { failed: one.period, absent: allAbsent, refusal: `${path} is not there` };
		if ('refused' in one.reading) return { failed: one.period, absent: false, refusal: `${path}: ${explainRefusal(one.period, one.reading.refused)}` };
	}
	const indexes: Indexes = { daily: [], monthly: [], yearly: [] };
	for (const one of readings) {
		if (one.reading != null && 'index' in one.reading) indexes[one.period] = one.reading.index.entries;
	}
	return indexes;
}

function wanted(keeper: PageKeeper, ledger: LedgerName, period: Period, entry: CompactEntry): WantedFile {
	return { path: dataPath(keeper.catalog, ledger, period, entry.covers), version: dataVersion(entry), bytes: entry.bytes, byRange: false };
}

/** Even a zero-row file supplies columns; empty and lost entries supply no file. */
export function viewSource(keeper: PageKeeper, ledger: LedgerName, indexes: Indexes): PlannedFile[] {
	const newest = newestFile(indexes.daily, indexes.monthly, indexes.yearly);
	return newest === null ? [] : [{ file: wanted(keeper, ledger, newest.period, newest.entry), ledger, day: newest.firstDay, window: null }];
}

async function planLedger(keeper: PageKeeper, ledger: LedgerName, from: DateStamp, to: DateStamp): Promise<LedgerPlan | AskResult> {
	const indexed = await readIndexes(keeper, ledger);
	if ('failed' in indexed) {
		keeper.warn(`${LOG_PREFIX} ${ledger}: ${indexed.refusal}; ${indexed.absent ? 'not packed yet' : 'the question did not run'}`);
		return indexed.absent ? { state: 'missing', ledger } : { state: 'unreachable', ledger, at: from, fault: 'index-missing' };
	}
	const through = newestNamed(indexed.daily, indexed.monthly, indexed.yearly);
	if (through === null) return { state: 'missing', ledger };
	const first = firstNamed(indexed.daily, indexed.monthly, indexed.yearly);
	const start = first !== null && from < first ? first : from;
	const until = through !== null && through < to ? through : to;
	const selection = filesFor(start, until, indexed.daily, indexed.monthly, indexed.yearly);
	if ('hole' in selection) {
		keeper.warn(`${LOG_PREFIX} ${ledger}: no compact record for ${selection.hole}; the question did not run`);
		return { state: 'unreachable', ledger, at: selection.hole, fault: 'day-missing' };
	}
	const files = selection.files.filter((one) => one.entry.rows > 0).map((one): PlannedFile => {
		const covered = coveredDays(one.period, one.entry.covers);
		const end = covered.last < until ? covered.last : until;
		return {
			file: wanted(keeper, ledger, one.period, one.entry), ledger, day: one.firstDay,
			window: one.firstDay === covered.first && end === covered.last ? null : { from: one.firstDay, to: end }
		};
	});
	return { ledger, through, files, emptySource: viewSource(keeper, ledger, indexed), cutBefore: first !== null && from < first ? first : null, lostDays: selection.lostDays, setAside: selection.setAside };
}

/** One shared selection prices query files and automatic column reads before either fetches. */
export async function planQuestion(keeper: PageKeeper, ledgers: readonly LedgerName[], from: DateStamp, to: DateStamp): Promise<QuestionPlan | AskResult> {
	for (const ledger of new Set(ledgers)) {
		const entry = keeper.catalog.get(ledger);
		if (entry === undefined) return { state: 'missing', ledger };
		if (!entry.publish_to_data_explorer) return { state: 'refused', because: { kind: 'ledger-not-enabled', ledger } };
	}
	if (!isDay(from) || !isDay(to) || from > to) throw new Error('A question needs ordered UTC dates.');
	const planned = await Promise.all([...new Set(ledgers)].map((ledger) => planLedger(keeper, ledger, from, to)));
	const failed = planned.find((one): one is AskResult => 'state' in one);
	if (failed !== undefined) return failed;
	const plans = planned.filter((one): one is LedgerPlan => !('state' in one));
	const candidates = plans.flatMap((one) => [...one.files, ...one.emptySource]);
	const files = [...new Map(candidates.map((one) => [one.file.path, one])).values()];
	const bounds = plans.flatMap((one) => {
		const start = one.cutBefore ?? from;
		const end = one.through !== null && one.through < to ? one.through : to;
		return one.through !== null && start <= end ? [{ start, end }] : [];
	});
	return {
		ledgers: plans, files,
		cost: {
			files: files.length, bytes: files.reduce((sum, one) => sum + one.file.bytes, 0),
			readFrom: bounds.map((one) => one.start).sort()[0] ?? null,
			readTo: bounds.map((one) => one.end).sort().at(-1) ?? null,
			cut: plans.flatMap((one): CutDays[] => one.cutBefore === null ? [] : [{ ledger: one.ledger, before: one.cutBefore }]),
			through: Object.fromEntries(plans.flatMap((one) => one.through === null ? [] : [[one.ledger, one.through]]))
		}
	};
}

export function preflight(cost: SpanCost, maxFiles: number, maxFetchBytes: number): AskRefusal | null {
	if (!Number.isSafeInteger(maxFiles) || maxFiles < 1) throw new Error('maxFiles must be a positive integer.');
	if (cost.files > maxFiles) return { kind: 'too-many-files', files: cost.files, max: maxFiles };
	return cost.bytes > maxFetchBytes ? { kind: 'over-ceiling', bytes: cost.bytes, files: cost.files, max: maxFetchBytes } : null;
}

export async function readAskCost(keeper: PageKeeper, ledgers: readonly LedgerName[], from: DateStamp, to: DateStamp): Promise<SpanCost> {
	const planned = await planQuestion(keeper, ledgers, from, to);
	return 'state' in planned ? { files: 0, bytes: 0, readFrom: null, readTo: null, cut: [], through: {}, failure: planned } : planned.cost;
}

export function quoteIdent(name: LedgerName): string { return `"${name.replaceAll('"', '""')}"`; }

function dayLiteral(day: DateStamp): string {
	if (!isDay(day)) throw new Error(`${day} is not a UTC day`);
	return `'${day}'`;
}

function viewPart(names: readonly string[], window: DayWindow): string {
	const read = `SELECT * FROM read_parquet(${listOf(names)}, union_by_name = true)`;
	return window === null ? read : `${read} WHERE "covers" >= ${dayLiteral(window.from)} AND "covers" <= ${dayLiteral(window.to)}`;
}

export function viewStatement(ledger: LedgerName, sources: readonly HeldSource[], empty: boolean): string {
	const parts: string[] = [];
	let whole: string[] = [];
	for (const source of sources) {
		if (source.window === null) { whole.push(source.name); continue; }
		if (whole.length > 0) parts.push(viewPart(whole, null));
		whole = [];
		parts.push(viewPart([source.name], source.window));
	}
	if (whole.length > 0) parts.push(viewPart(whole, null));
	return `CREATE OR REPLACE VIEW ${quoteIdent(ledger)} AS ${parts.join(' UNION ALL BY NAME ')}${empty ? ' LIMIT 0' : ''}`;
}

export function columnsOf(rows: Record<string, unknown>[]): Column[] {
	return rows.map((row) => ({ name: String(row.column_name ?? row.explain_key ?? ''), type: String(row.column_type ?? row.explain_value ?? 'VARCHAR') }));
}

export function explainMissedFile(file: WantedFile, shortfall: FileShortfall): string {
	return shortfall.reason === 'absent' ? `${file.path} is not there` : explainShortfall(file, shortfall);
}

export async function readAsk(keeper: PageKeeper, opts: AskOptions): Promise<AskResult> {
	const checked = checkStatement(opts.sql, opts.maxChars);
	if (checked.refusal !== null) return { state: 'refused', because: checked.refusal };
	return serial(async () => {
		const started = Date.now();
		const planned = await planQuestion(keeper, opts.ledgers, opts.from, opts.to);
		if ('state' in planned) return planned;
		const refusal = preflight(planned.cost, opts.maxFiles, opts.maxFetchBytes);
		if (refusal !== null) return { state: 'refused', because: refusal };
		const gaps: SpanGap[] = planned.ledgers.filter((one) => one.lostDays.length > 0 || Object.keys(one.setAside).length > 0).map((one) => ({ ledger: one.ledger, lostDays: one.lostDays, setAside: one.setAside }));
		const named = { cut: planned.cost.cut, gaps };
		if (planned.ledgers.every((one) => one.files.length === 0)) {
			return { state: 'quiet', columns: [], read: { files: 0, bytes: 0, alreadyHeld: 0, ms: Date.now() - started }, ...named };
		}
		const sourceless = planned.ledgers.find((one) => one.files.length === 0 && one.emptySource.length === 0);
		if (sourceless !== undefined) return { state: 'missing', ledger: sourceless.ledger };
		const sources = planned.ledgers.map((one) => one.files.length > 0 ? one.files : one.emptySource);
		const files = [...new Map(sources.flat().map((one) => [one.file.path, one])).values()];
		let holding;
		try { holding = await keeper.hold(files.map((one) => one.file)); }
		catch (error) {
			keeper.warn(`${LOG_PREFIX} engine: ${String(error)}`);
			return { state: 'unreachable', ledger: null, at: null, fault: 'engine' };
		}
		if ('failed' in holding) {
			const missed = files[holding.failed];
			keeper.warn(`${LOG_PREFIX} ${missed.ledger}: ${explainMissedFile(missed.file, holding.shortfall)}; the question did not run`);
			return { state: 'unreachable', ledger: missed.ledger, at: missed.day, fault: holding.shortfall.reason === 'absent' ? 'file-missing' : null };
		}
		try {
			await dropOwnedViews(holding.engine);
			const names = new Map(files.map((one, at) => [one.file.path, holding.names[at]]));
			for (const [at, one] of planned.ledgers.entries()) {
				const held = sources[at].map((file) => {
					const name = names.get(file.file.path);
					if (name === undefined) throw new Error('A planned compact file was not held.');
					return { name, window: file.window };
				});
				await createOwnedView(holding.engine, one.ledger, held, one.files.length === 0);
			}
			const columns = statementKind(checked.sql) === 'EXPLAIN'
				? [{ name: 'explain_key', type: 'VARCHAR' }, { name: 'explain_value', type: 'VARCHAR' }]
				: columnsOf(await holding.engine.rows(`DESCRIBE SELECT * FROM (\n${checked.sql}\n)`, []));
			const sql = statementKind(checked.sql) === 'EXPLAIN' ? checked.sql : `SELECT COLUMNS(*)::VARCHAR FROM (\n${checked.sql}\n) LIMIT ${opts.maxRows + 1}`;
			const rows = await holding.engine.rows(sql, []);
			const text = rows.slice(0, opts.maxRows).map((row): Row => Object.fromEntries(columns.map((column) => [column.name, row[column.name] == null ? null : String(row[column.name])])));
			const read = { files: holding.fetched.filter(Boolean).length, bytes: files.reduce((sum, one, at) => sum + (holding.fetched[at] ? one.file.bytes : 0), 0), alreadyHeld: holding.fetched.filter((one) => !one).length, ms: Date.now() - started };
			return text.length === 0 ? { state: 'quiet', columns, read, ...named }
				: { state: 'ok', columns, rows: text, capped: rows.length > opts.maxRows, read, readFrom: planned.cost.readFrom ?? opts.from, readTo: planned.cost.readTo ?? opts.to, ...named };
		} catch (error) {
			return { state: 'refused', because: { kind: 'engine-error', message: error instanceof Error ? error.message : String(error) } };
		} finally { await holding.done(); }
	});
}
