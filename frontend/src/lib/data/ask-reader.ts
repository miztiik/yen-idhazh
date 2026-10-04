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
type PlannedFile = { file: WantedFile; meta: FileMeta; keeper: 'site' | 'archive'; from: DateStamp; to: DateStamp };
type HeldSource = { name: string; from: DateStamp; to: DateStamp };
type LedgerPlan = {
	ledger: LedgerName;
	through: DateStamp | null;
	files: PlannedFile[];
	emptySource: PlannedFile[];
	unpackedDays: DateStamp[];
	siteFrom: DateStamp | null;
	unreachable: AskResult | null;
};
type Plan = { ledgers: LedgerPlan[]; cost: SpanCost; files: PlannedFile[] };

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

function previousDay(day: DateStamp): DateStamp {
	const at = new Date(`${day}T00:00:00Z`);
	at.setUTCDate(at.getUTCDate() - 1);
	return at.toISOString().slice(0, 10);
}

function addPlanned(files: WantedFile[], metas: FileMeta[], keeper: 'site' | 'archive', from: DateStamp, to: DateStamp): PlannedFile[] {
	return files.map((file, at) => ({ file, meta: metas[at] ?? { ledger: 'seen', day: null }, keeper, from, to }));
}

function compactFirst(indexes: Indexes): DateStamp | null {
	return newestNamed(indexes.daily, indexes.monthly, indexes.yearly) === null
		? null
		: firstNamed(indexes.daily, indexes.monthly, indexes.yearly);
}

function later(a: DateStamp | null, b: DateStamp | null): DateStamp | null {
	if (a === null) return b;
	if (b === null) return a;
	return a > b ? a : b;
}

function periodLastDay(period: Period, covers: string): DateStamp {
	if (period === 'daily') return covers;
	if (period === 'yearly') return `${covers}-12-31`;
	const [year, oneBased] = covers.split('-').map(Number);
	return new Date(Date.UTC(year ?? 0, oneBased ?? 0, 0)).toISOString().slice(0, 10);
}

function addCompactPlanned(
	files: readonly ChosenFile[],
	ledger: LedgerName,
	keeper: 'site' | 'archive',
	until: DateStamp,
	byRange: boolean
): PlannedFile[] {
	return files
		.filter((file) => file.entry.rows > 0)
		.map((file) => ({
			file: wanted(file.period, ledger, file, byRange),
			meta: { ledger, day: file.firstDay },
			keeper,
			from: file.firstDay,
			to: periodLastDay(file.period, file.entry.covers) < until ? periodLastDay(file.period, file.entry.covers) : until
		}));
}

function wanted(period: Period, ledger: LedgerName, file: ChosenFile, byRange = RANGED_PERIODS.has(period)): WantedFile {
	return {
		path: dataPath(ledger, period, file.entry.covers),
		version: dataVersion(file.entry),
		bytes: file.entry.bytes,
		byRange
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
	indexes: Indexes,
	_byRange = true
): { chosen: ChosenFile[] } | AskResult {
	const first = newestNamed(indexes.daily, indexes.monthly, indexes.yearly) === null
		? null
		: firstNamed(indexes.daily, indexes.monthly, indexes.yearly);
	if (first === null) return { chosen: [] };
	if (from < first && indexes.monthly.length === 0 && indexes.yearly.length === 0) {
		return { state: 'unreachable', ledger, at: from, fault: 'index-missing' };
	}
	const selection = filesFor(from, until, indexes.daily, indexes.monthly, indexes.yearly);
	if ('hole' in selection) return { state: 'unreachable', ledger, at: selection.hole, fault: 'day-missing' };
	return { chosen: selection.files };
}

/** The files an empty view takes its columns from: the ledger's newest day, from its listing
 *  when the build listed a day after the newest packed one, else from the packed tier.
 *  A zero-row packed file is kept, because a view that reads no rows needs only the file's
 *  columns, and a ledger whose packed days all hold zero rows would otherwise have no file. */
async function viewSource(
	keeper: PageKeeper,
	ledger: LedgerName,
	newestPacked: DateStamp | null,
	indexes: Indexes,
	rawListed: RawListedThrough
): Promise<{ files: WantedFile[]; metas: FileMeta[] }> {
	const listedThrough = rawListed[ledger] ?? null;
	if (listedThrough !== null && (newestPacked === null || listedThrough > newestPacked)) {
		const raw = await rawListing(keeper, ledger, listedThrough);
		if (!('state' in raw) && raw.files.length > 0) return raw;
	}
	if (newestPacked === null) return { files: [], metas: [] };
	const selection = filesFor(newestPacked, newestPacked, indexes.daily, indexes.monthly, indexes.yearly);
	if ('hole' in selection) return { files: [], metas: [] };
	return {
		files: selection.files.map((file) => wanted(file.period, ledger, file)),
		metas: selection.files.map((file) => ({ ledger, day: file.firstDay }))
	};
}

async function planLedger(
	keeper: PageKeeper,
	archiveKeeper: PageKeeper | null,
	clampWithoutArchive: boolean,
	ledger: LedgerName,
	from: DateStamp,
	to: DateStamp,
	rawListed: RawListedThrough
): Promise<LedgerPlan> {
	const indexed = await compactIndexes(keeper, ledger, from, to);
	if ('state' in indexed) {
		return { ledger, through: null, files: [], emptySource: [], unpackedDays: [], siteFrom: null, unreachable: indexed };
	}

	const newestPacked = newestNamed(indexed.daily, indexed.monthly, indexed.yearly);
	const siteFirst = compactFirst(indexed);
	const through = later(newestPacked, rawListed[ledger] ?? null);
	const files: PlannedFile[] = [];
	let unreachable: AskResult | null = null;
	let siteFrom: DateStamp | null = null;
	let siteStart = from;

	if (siteFirst !== null && from < siteFirst) {
		if (archiveKeeper === null && clampWithoutArchive) {
			siteFrom = siteFirst;
			siteStart = siteFirst;
		} else if (archiveKeeper === null) {
			const compact = compactSelection(ledger, from, to < siteFirst ? to : previousDay(siteFirst), indexed);
			unreachable = 'state' in compact ? compact : { state: 'unreachable', ledger, at: from, fault: null };
		} else {
			const archiveTo = to < siteFirst ? to : previousDay(siteFirst);
			const archiveIndexed = await compactIndexes(archiveKeeper, ledger, from, archiveTo);
			if ('state' in archiveIndexed) unreachable = archiveIndexed;
			else {
				const archive = compactSelection(ledger, from, archiveTo, archiveIndexed, false);
				if ('state' in archive) unreachable = archive;
				else files.push(...addCompactPlanned(archive.chosen, ledger, 'archive', archiveTo, false));
			}
			siteStart = siteFirst;
		}
	}

	if (newestPacked !== null && siteStart <= newestPacked && siteStart <= to) {
		const until = to < newestPacked ? to : newestPacked;
		const compact = compactSelection(ledger, siteStart, until, indexed);
		if ('state' in compact) unreachable = compact;
		else {
			files.push(...addCompactPlanned(compact.chosen, ledger, 'site', until, true));
		}
	}

	const rawDays = siteStart <= to ? writerDaysFor(siteStart, to, newestPacked, rawListed[ledger] ?? null) : [];
	for (const day of rawDays) {
		const listed = await rawListing(keeper, ledger, day);
		if ('state' in listed) {
			unreachable ??= listed;
			continue;
		}
		files.push(...addPlanned(listed.files, listed.metas, 'site', day, day));
	}

	// A ledger with no file in the span is read through an empty view over its newest day's
	// files, so only such a ledger needs that day planned, and its listing fetched.
	const needsEmptyView = files.length === 0 && unreachable === null && through !== null;
	const empty = needsEmptyView ? await viewSource(keeper, ledger, newestPacked, indexed, rawListed) : { files: [], metas: [] };
	return {
		ledger,
		through,
		files,
		emptySource: addPlanned(empty.files, empty.metas, 'site', through ?? to, through ?? to),
		unpackedDays: rawDays,
		siteFrom,
		unreachable
	};
}

async function plan(
	keeper: PageKeeper,
	archiveKeeper: PageKeeper | null,
	clampWithoutArchive: boolean,
	ledgers: readonly LedgerName[],
	from: DateStamp,
	to: DateStamp,
	rawListed: RawListedThrough
): Promise<Plan | AskResult> {
	const chosen = [...new Set(ledgers)];
	if (chosen.length === 0) {
		return { state: 'quiet', columns: [], read: { files: 0, bytes: 0, alreadyHeld: 0, ms: 0 }, siteFrom: null };
	}
	for (const ledger of chosen) {
		if (!(LEDGER_NAMES as readonly string[]).includes(ledger)) return { state: 'missing', ledger };
	}

	const ledgersPlanned = await Promise.all(chosen.map((ledger) => planLedger(keeper, archiveKeeper, clampWithoutArchive, ledger, from, to, rawListed)));
	const failed = ledgersPlanned.find((one) => one.unreachable !== null);
	if (failed?.unreachable) return failed.unreachable;
	const noDays = ledgersPlanned.find((one) => one.through === null);
	if (noDays) return { state: 'missing', ledger: noDays.ledger };
	const files = ledgersPlanned.flatMap((one) => one.files);
	return {
		ledgers: ledgersPlanned,
		files,
		cost: {
			files: files.length,
			bytes: files.reduce((sum, plannedFile) => sum + plannedFile.file.bytes, 0),
			unpackedDays: [...new Set(ledgersPlanned.flatMap((one) => one.unpackedDays))],
			siteFrom: ledgersPlanned.map((one) => one.siteFrom).filter((day): day is DateStamp => day !== null).sort()[0] ?? null,
			through: Object.fromEntries(ledgersPlanned.flatMap((one) => (one.through === null ? [] : [[one.ledger, one.through]])))
		}
	};
}

function quoteIdent(name: LedgerName): string {
	return `"${name.replaceAll('"', '""')}"`;
}

function viewStatement(ledger: LedgerName, sources: readonly HeldSource[], empty: boolean): string {
	const parts = sources.map((source) =>
		`SELECT * FROM read_parquet(${listOf([source.name])}, union_by_name = true) WHERE "date" >= '${source.from}' AND "date" <= '${source.to}'`
	);
	return `CREATE OR REPLACE VIEW ${quoteIdent(ledger)} AS ${parts.join(' UNION ALL ')}${empty ? ' LIMIT 0' : ''}`;
}

async function prepareViews(
	engine: QueryEngine,
	plans: readonly LedgerPlan[],
	heldSources: readonly HeldSource[][]
): Promise<void> {
	const selected = new Set(plans.map((one) => one.ledger));
	for (const ledger of LEDGER_NAMES) {
		if (!selected.has(ledger)) await engine.rows(`DROP VIEW IF EXISTS ${quoteIdent(ledger)}`, []);
	}
	for (const [at, one] of plans.entries()) {
		await engine.rows(viewStatement(one.ledger, heldSources[at] ?? [], one.files.length === 0), []);
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

function sumCost(parts: readonly FetchCost[], started: number): FetchCost {
	return {
		files: parts.reduce((sum, part) => sum + part.files, 0),
		bytes: parts.reduce((sum, part) => sum + part.bytes, 0),
		alreadyHeld: parts.reduce((sum, part) => sum + part.alreadyHeld, 0),
		ms: Date.now() - started
	};
}

export function readAskCost(
	keeper: PageKeeper,
	ledgers: readonly LedgerName[],
	from: DateStamp,
	to: DateStamp,
	rawListed: RawListedThrough
): Promise<SpanCost>;
export function readAskCost(
	keeper: PageKeeper,
	archiveKeeper: PageKeeper | null,
	ledgers: readonly LedgerName[],
	from: DateStamp,
	to: DateStamp,
	rawListed: RawListedThrough
): Promise<SpanCost>;
export async function readAskCost(
	keeper: PageKeeper,
	archiveOrLedgers: PageKeeper | null | readonly LedgerName[],
	ledgersOrFrom: readonly LedgerName[] | DateStamp,
	fromOrTo: DateStamp,
	toOrRaw: DateStamp | RawListedThrough,
	maybeRaw?: RawListedThrough
): Promise<SpanCost> {
	const archiveKeeper = maybeRaw === undefined ? null : (archiveOrLedgers as PageKeeper | null);
	const clampWithoutArchive = maybeRaw !== undefined;
	const ledgers = maybeRaw === undefined ? (archiveOrLedgers as readonly LedgerName[]) : (ledgersOrFrom as readonly LedgerName[]);
	const from = maybeRaw === undefined ? (ledgersOrFrom as DateStamp) : fromOrTo;
	const to = maybeRaw === undefined ? (fromOrTo as DateStamp) : (toOrRaw as DateStamp);
	const rawListed = maybeRaw === undefined ? (toOrRaw as RawListedThrough) : maybeRaw;
	const planned = await plan(keeper, archiveKeeper, clampWithoutArchive, ledgers, from, to, rawListed);
	return 'state' in planned ? { files: 0, bytes: 0, unpackedDays: [], siteFrom: 'siteFrom' in planned ? planned.siteFrom : null, through: {} } : planned.cost;
}

export function readAsk(keeper: PageKeeper, opts: AskOptions, rawListed: RawListedThrough): Promise<AskResult>;
export function readAsk(keeper: PageKeeper, archiveKeeper: PageKeeper | null, opts: AskOptions, rawListed: RawListedThrough): Promise<AskResult>;
export async function readAsk(
	keeper: PageKeeper,
	archiveOrOpts: PageKeeper | null | AskOptions,
	optsOrRaw: AskOptions | RawListedThrough,
	maybeRaw?: RawListedThrough
): Promise<AskResult> {
	const archiveKeeper = maybeRaw === undefined ? null : (archiveOrOpts as PageKeeper | null);
	const clampWithoutArchive = maybeRaw !== undefined;
	const opts = maybeRaw === undefined ? (archiveOrOpts as AskOptions) : (optsOrRaw as AskOptions);
	const rawListed = maybeRaw === undefined ? (optsOrRaw as RawListedThrough) : maybeRaw;
	const checked = checkStatement(opts.sql, opts.maxChars);
	if (checked.refusal !== null) return { state: 'refused', because: checked.refusal };
	return serial(async () => {
		const started = Date.now();
		const planned = await plan(keeper, archiveKeeper, clampWithoutArchive, opts.ledgers, opts.from, opts.to, rawListed);
		if ('state' in planned) return planned;
		if (planned.cost.bytes > opts.maxFetchBytes) {
			return { state: 'refused', because: { kind: 'over-ceiling', bytes: planned.cost.bytes, files: planned.cost.files, max: opts.maxFetchBytes } };
		}
		const noFilesInSpan = planned.ledgers.every((one) => one.files.length === 0);
		if (noFilesInSpan) {
			return { state: 'quiet', columns: [], read: { files: 0, bytes: 0, alreadyHeld: 0, ms: Date.now() - started }, siteFrom: planned.cost.siteFrom };
		}
		// An empty view over no file would reach the engine as `read_parquet([])`, which it refuses.
		const sourceless = planned.ledgers.find((one) => one.files.length === 0 && one.emptySource.length === 0);
		if (sourceless) return { state: 'missing', ledger: sourceless.ledger };

		const plannedFiles = planned.ledgers.flatMap((one) => (one.files.length > 0 ? one.files : one.emptySource));
		const siteFiles = plannedFiles.filter((one) => one.keeper === 'site');
		const archiveFiles = plannedFiles.filter((one) => one.keeper === 'archive');
		let siteHeld: Awaited<ReturnType<PageKeeper['hold']>> | null = null;
		let archiveHeld: Awaited<ReturnType<PageKeeper['hold']>> | null = null;
		try {
			siteHeld = siteFiles.length > 0 ? await keeper.hold(siteFiles.map((one) => one.file)) : { engine: await keeper.hold([]).then((holding) => 'engine' in holding ? holding.engine : Promise.reject(new Error('empty hold failed'))), names: [], fetched: [], done: async () => {} };
			if (archiveFiles.length > 0) {
				if (archiveKeeper === null) throw new Error('archive files planned without an archive keeper');
				archiveHeld = await archiveKeeper.hold(archiveFiles.map((one) => one.file));
			}
		} catch {
			return { state: 'unreachable', ledger: null, at: null, fault: 'engine' };
		}
		if ('failed' in siteHeld) {
			const meta = siteFiles[siteHeld.failed]?.meta;
			const fault = siteHeld.shortfall.reason === 'absent' ? 'file-missing' : null;
			return { state: 'unreachable', ledger: meta?.ledger ?? null, at: meta?.day ?? null, fault };
		}
		if (archiveHeld !== null && 'failed' in archiveHeld) {
			const meta = archiveFiles[archiveHeld.failed]?.meta;
			const fault = archiveHeld.shortfall.reason === 'absent' ? 'file-missing' : null;
			return { state: 'unreachable', ledger: meta?.ledger ?? null, at: meta?.day ?? null, fault };
		}

		try {
			const sourcesByLedger: HeldSource[][] = [];
			for (const one of planned.ledgers) {
				const files = one.files.length > 0 ? one.files : one.emptySource;
				sourcesByLedger.push(files.map((plannedFile) => {
					const group = plannedFile.keeper === 'site' ? siteFiles : archiveFiles;
					const held = plannedFile.keeper === 'site' ? siteHeld : archiveHeld;
					if (held === null || 'failed' in held) throw new Error('planned file was not held');
					const at = group.indexOf(plannedFile);
					return { name: held.names[at] ?? '', from: plannedFile.from, to: plannedFile.to };
				}));
			}
			await prepareViews(siteHeld.engine, planned.ledgers, sourcesByLedger);
			const columns = await describe(siteHeld.engine, checked.sql);
			const answer = await runRows(siteHeld.engine, checked.sql, opts.maxRows, columns);
			const read = sumCost([
				readCost(siteFiles.map((one) => one.file), siteHeld.fetched, started),
				archiveHeld === null ? { files: 0, bytes: 0, alreadyHeld: 0, ms: 0 } : readCost(archiveFiles.map((one) => one.file), archiveHeld.fetched, started)
			], started);
			return answer.rows.length === 0
				? { state: 'quiet', columns, read, siteFrom: planned.cost.siteFrom }
				: { state: 'ok', columns, rows: answer.rows, capped: answer.capped, read, unpackedDays: planned.cost.unpackedDays, siteFrom: planned.cost.siteFrom };
		} catch (error) {
			return { state: 'refused', because: { kind: 'engine-error', message: error instanceof Error ? error.message : String(error) } };
		} finally {
			if (siteHeld !== null && !('failed' in siteHeld)) await siteHeld.done();
			if (archiveHeld !== null && !('failed' in archiveHeld)) await archiveHeld.done();
		}
	});
}
