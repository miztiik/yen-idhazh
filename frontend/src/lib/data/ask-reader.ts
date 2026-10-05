/** How does the written-question door turn selected ledgers and days into one answer? */

import { COMPACT_PERIODS, type CompactEntry, type Period } from './compact-index';
import type { PageKeeper, WantedFile } from './page-keeper';
import { coveredDays, filesFor, firstNamed, newestFile, newestNamed, writerDaysFor, type ChosenFile } from './slice';
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
import { siteMayHaveTrimmed } from './site-window';
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
	type SetAsideFiles,
	type SpanCost,
	type SpanGap
} from './slice-shapes';

export type RawListedThrough = Readonly<Partial<Record<LedgerName, DateStamp>>>;

/** The archive, and how many UTC days of each ledger the site copy keeps. The archive holds
 *  the days the copy dropped, so it is read only when `site-window.ts` says the copy may have
 *  dropped some. */
export type ArchiveTier = { keeper: PageKeeper; siteWindowDays: number };

type Indexes = { daily: CompactEntry[]; monthly: CompactEntry[]; yearly: CompactEntry[] };
type FileMeta = { ledger: LedgerName; day: DateStamp | null };
/** The days a packed file is read for, or `null` when every row it holds is in the span. */
type DayWindow = { from: DateStamp; to: DateStamp } | null;
type PlannedFile = { file: WantedFile; meta: FileMeta; keeper: 'site' | 'archive'; window: DayWindow };
type HeldSource = { name: string; window: DayWindow };
/** The packed files a span reads, the days in it recorded lost, the files its periods set aside,
 *  and the day the span is read from: `null` when the indexes name no day. */
type CompactChoice = { chosen: ChosenFile[]; lostDays: DateStamp[]; setAside: SetAsideFiles; start: DateStamp | null };
type LedgerPlan = {
	ledger: LedgerName;
	through: DateStamp | null;
	files: PlannedFile[];
	emptySource: PlannedFile[];
	unpackedDays: DateStamp[];
	siteFrom: DateStamp | null;
	lostDays: DateStamp[];
	setAside: SetAsideFiles;
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

/** Files read whole: a writer's file, which holds one day, and an empty view's source. */
function addPlanned(files: WantedFile[], metas: FileMeta[], keeper: 'site' | 'archive'): PlannedFile[] {
	return files.map((file, at) => {
		const meta = metas[at];
		if (meta === undefined) throw new Error(`${file.path} was planned without its ledger and day`);
		return { file, meta, keeper, window: null };
	});
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

function earlier(a: DateStamp | null, b: DateStamp | null): DateStamp | null {
	if (a === null) return b;
	if (b === null) return a;
	return a < b ? a : b;
}

/** Each chosen file that holds a row, and the days it is read for. `filesFor()` picks the
 *  coarsest file that holds a day, so a month or year file can reach outside the span, or
 *  into days the other keeper reads; such a file is read for its own days alone, and a file
 *  wholly inside them is read whole. The site opens a year file by address and fetches every
 *  other file; the page alone reads the archive's host, so every archive file is fetched. */
function addCompactPlanned(
	files: readonly ChosenFile[],
	ledger: LedgerName,
	keeper: 'site' | 'archive',
	until: DateStamp
): PlannedFile[] {
	return files
		.filter((file) => file.entry.rows > 0)
		.map((file) => {
			const covered = coveredDays(file.period, file.entry.covers);
			const to = covered.last < until ? covered.last : until;
			const whole = file.firstDay === covered.first && to === covered.last;
			return {
				file: wanted(file.period, ledger, file, keeper === 'site' && RANGED_PERIODS.has(file.period)),
				meta: { ledger, day: file.firstDay },
				keeper,
				window: whole ? null : { from: file.firstDay, to }
			};
		});
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

/** The packed files one keeper's indexes give a span. A span that begins before the indexes' first
 *  day is read from that day: the days before it are outside the ledger, so they are cut rather
 *  than failing. A day after it that no index names is a hole, `day-missing`. */
function compactSelection(
	ledger: LedgerName,
	from: DateStamp,
	until: DateStamp,
	indexes: Indexes
): CompactChoice | AskResult {
	const first = compactFirst(indexes);
	if (first === null) return { chosen: [], lostDays: [], setAside: {}, start: null };
	const start = from < first ? first : from;
	const selection = filesFor(start, until, indexes.daily, indexes.monthly, indexes.yearly);
	if ('hole' in selection) return { state: 'unreachable', ledger, at: selection.hole, fault: 'day-missing' };
	return { chosen: selection.files, lostDays: selection.lostDays, setAside: selection.setAside, start };
}

/** The files an empty view takes its columns from: the ledger's newest day, from its listing
 *  when the build listed a day after the newest packed one, else from the newest packed file.
 *  A zero-row packed file is kept, because a view that reads no rows needs only the file's
 *  columns, and a ledger whose packed days all hold zero rows would otherwise have no file.
 *  An `empty` or `lost` entry has no file, so the newest entry that has one is taken. */
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
	const newest = newestFile(indexes.daily, indexes.monthly, indexes.yearly);
	if (newest === null) return { files: [], metas: [] };
	return { files: [wanted(newest.period, ledger, newest)], metas: [{ ledger, day: newest.firstDay }] };
}

async function planLedger(
	keeper: PageKeeper,
	archive: ArchiveTier | null,
	ledger: LedgerName,
	from: DateStamp,
	to: DateStamp,
	rawListed: RawListedThrough
): Promise<LedgerPlan> {
	const indexed = await compactIndexes(keeper, ledger, from, to);
	if ('state' in indexed) {
		return { ledger, through: null, files: [], emptySource: [], unpackedDays: [], siteFrom: null, lostDays: [], setAside: {}, unreachable: indexed };
	}

	const newestPacked = newestNamed(indexed.daily, indexed.monthly, indexed.yearly);
	const siteFirst = compactFirst(indexed);
	const through = later(newestPacked, rawListed[ledger] ?? null);
	const files: PlannedFile[] = [];
	const lostDays: DateStamp[] = [];
	const setAside: Record<string, number> = {};
	let unreachable: AskResult | null = null;
	let siteFrom: DateStamp | null = null;
	let siteStart = from;
	/** One keeper's packed files for its part of the span, and what that part is missing.
	 *  The archive's part comes first, so the lost days stay in order. */
	const take = (choice: CompactChoice, held: 'site' | 'archive', until: DateStamp): void => {
		files.push(...addCompactPlanned(choice.chosen, ledger, held, until));
		lostDays.push(...choice.lostDays);
		Object.assign(setAside, choice.setAside);
	};

	// When the selected window begins before the site's first day, the days before the first day a
	// tier names are cut from it, and `siteFrom` names that day; no end moves. The archive is a
	// tier only for days the site copy may have dropped (`site-window.ts`).
	if (siteFirst !== null && newestPacked !== null && from < siteFirst) {
		siteFrom = siteFirst;
		if (archive !== null && siteMayHaveTrimmed(siteFirst, newestPacked, archive.siteWindowDays)) {
			const archiveTo = to < siteFirst ? to : previousDay(siteFirst);
			const archiveIndexed = await compactIndexes(archive.keeper, ledger, from, archiveTo);
			const choice = 'state' in archiveIndexed ? archiveIndexed : compactSelection(ledger, from, archiveTo, archiveIndexed);
			if ('state' in choice) unreachable = choice;
			else {
				take(choice, 'archive', archiveTo);
				siteFrom = choice.start === from ? null : earlier(choice.start, siteFirst);
			}
		}
		siteStart = siteFirst;
	}

	if (newestPacked !== null && siteStart <= newestPacked && siteStart <= to) {
		const until = to < newestPacked ? to : newestPacked;
		const compact = compactSelection(ledger, siteStart, until, indexed);
		if ('state' in compact) unreachable = compact;
		else take(compact, 'site', until);
	}

	const rawDays = siteStart <= to ? writerDaysFor(siteStart, to, newestPacked, rawListed[ledger] ?? null) : [];
	for (const day of rawDays) {
		const listed = await rawListing(keeper, ledger, day);
		if ('state' in listed) {
			unreachable ??= listed;
			continue;
		}
		files.push(...addPlanned(listed.files, listed.metas, 'site'));
	}

	// A ledger with no file in the span is read through an empty view over its newest day's
	// files, so only such a ledger needs that day planned, and its listing fetched.
	const needsEmptyView = files.length === 0 && unreachable === null && through !== null;
	const empty = needsEmptyView ? await viewSource(keeper, ledger, newestPacked, indexed, rawListed) : { files: [], metas: [] };
	return {
		ledger,
		through,
		files,
		emptySource: addPlanned(empty.files, empty.metas, 'site'),
		unpackedDays: rawDays,
		siteFrom,
		lostDays,
		setAside,
		unreachable
	};
}

/** Each selected ledger that is missing something inside the span, in the order chosen. */
function gapsOf(plans: readonly LedgerPlan[]): SpanGap[] {
	return plans
		.filter((one) => one.lostDays.length > 0 || Object.keys(one.setAside).length > 0)
		.map((one) => ({ ledger: one.ledger, lostDays: one.lostDays, setAside: one.setAside }));
}

async function plan(
	keeper: PageKeeper,
	archive: ArchiveTier | null,
	ledgers: readonly LedgerName[],
	from: DateStamp,
	to: DateStamp,
	rawListed: RawListedThrough
): Promise<Plan | AskResult> {
	const chosen = [...new Set(ledgers)];
	if (chosen.length === 0) {
		return { state: 'quiet', columns: [], read: { files: 0, bytes: 0, alreadyHeld: 0, ms: 0 }, siteFrom: null, gaps: [] };
	}
	for (const ledger of chosen) {
		if (!(LEDGER_NAMES as readonly string[]).includes(ledger)) return { state: 'missing', ledger };
	}

	const ledgersPlanned = await Promise.all(chosen.map((ledger) => planLedger(keeper, archive, ledger, from, to, rawListed)));
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

/** The day a row was filed under. Every packed row carries it, even inside a month or year
 *  file, and the files and keepers divide a ledger's days by it, so it says which rows of a
 *  wide file a span reads. `date` would not: some ledgers have no such column. */
const FILED_DAY = 'covers';
const DAY_STAMP = /^\d{4}-\d{2}-\d{2}$/;

/** A day as a SQL literal. The day comes from an index, so its shape is checked first. */
function dayLiteral(day: DateStamp): string {
	if (!DAY_STAMP.test(day)) throw new Error(`${day} is not a UTC day`);
	return `'${day}'`;
}

function viewPart(names: readonly string[], window: DayWindow): string {
	const read = `SELECT * FROM read_parquet(${listOf(names)}, union_by_name = true)`;
	return window === null
		? read
		: `${read} WHERE "${FILED_DAY}" >= ${dayLiteral(window.from)} AND "${FILED_DAY}" <= ${dayLiteral(window.to)}`;
}

/** One view over a ledger's held files, in planned order. Neighbouring files read whole share
 *  one read; a file read for part of its days gets its own, and the reads join by column name,
 *  as `union_by_name` joins the files inside one read. */
function viewStatement(ledger: LedgerName, sources: readonly HeldSource[], empty: boolean): string {
	const parts: string[] = [];
	let whole: string[] = [];
	for (const source of sources) {
		if (source.window === null) {
			whole.push(source.name);
			continue;
		}
		if (whole.length > 0) parts.push(viewPart(whole, null));
		whole = [];
		parts.push(viewPart([source.name], source.window));
	}
	if (whole.length > 0) parts.push(viewPart(whole, null));
	return `CREATE OR REPLACE VIEW ${quoteIdent(ledger)} AS ${parts.join(' UNION ALL BY NAME ')}${empty ? ' LIMIT 0' : ''}`;
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

/** What a question over these ledgers and days would fetch. Days before the first day a tier
 *  names are cut from the window, and `siteFrom` names that day; `archive` is read only for days
 *  the site copy may have dropped. */
export async function readAskCost(
	keeper: PageKeeper,
	archive: ArchiveTier | null,
	ledgers: readonly LedgerName[],
	from: DateStamp,
	to: DateStamp,
	rawListed: RawListedThrough
): Promise<SpanCost> {
	const planned = await plan(keeper, archive, ledgers, from, to, rawListed);
	return 'state' in planned ? { files: 0, bytes: 0, unpackedDays: [], siteFrom: 'siteFrom' in planned ? planned.siteFrom : null, through: {} } : planned.cost;
}

/** One read-only statement over the chosen ledgers and days. Days before the first day a tier
 *  names are cut from the window, and `siteFrom` names that day; `archive` is read only for days
 *  the site copy may have dropped. */
export async function readAsk(
	keeper: PageKeeper,
	archive: ArchiveTier | null,
	opts: AskOptions,
	rawListed: RawListedThrough
): Promise<AskResult> {
	const checked = checkStatement(opts.sql, opts.maxChars);
	if (checked.refusal !== null) return { state: 'refused', because: checked.refusal };
	return serial(async () => {
		const started = Date.now();
		const planned = await plan(keeper, archive, opts.ledgers, opts.from, opts.to, rawListed);
		if ('state' in planned) return planned;
		if (planned.cost.bytes > opts.maxFetchBytes) {
			return { state: 'refused', because: { kind: 'over-ceiling', bytes: planned.cost.bytes, files: planned.cost.files, max: opts.maxFetchBytes } };
		}
		const noFilesInSpan = planned.ledgers.every((one) => one.files.length === 0);
		if (noFilesInSpan) {
			return { state: 'quiet', columns: [], read: { files: 0, bytes: 0, alreadyHeld: 0, ms: Date.now() - started }, siteFrom: planned.cost.siteFrom, gaps: gapsOf(planned.ledgers) };
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
				if (archive === null) throw new Error('archive files planned without an archive');
				archiveHeld = await archive.keeper.hold(archiveFiles.map((one) => one.file));
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
					const name = held.names[group.indexOf(plannedFile)];
					if (name === undefined) throw new Error('planned file was not held');
					return { name, window: plannedFile.window };
				}));
			}
			await prepareViews(siteHeld.engine, planned.ledgers, sourcesByLedger);
			const columns = await describe(siteHeld.engine, checked.sql);
			const answer = await runRows(siteHeld.engine, checked.sql, opts.maxRows, columns);
			const read = sumCost([
				readCost(siteFiles.map((one) => one.file), siteHeld.fetched, started),
				archiveHeld === null ? { files: 0, bytes: 0, alreadyHeld: 0, ms: 0 } : readCost(archiveFiles.map((one) => one.file), archiveHeld.fetched, started)
			], started);
			const gaps = gapsOf(planned.ledgers);
			return answer.rows.length === 0
				? { state: 'quiet', columns, read, siteFrom: planned.cost.siteFrom, gaps }
				: { state: 'ok', columns, rows: answer.rows, capped: answer.capped, read, unpackedDays: planned.cost.unpackedDays, siteFrom: planned.cost.siteFrom, gaps };
		} catch (error) {
			return { state: 'refused', because: { kind: 'engine-error', message: error instanceof Error ? error.message : String(error) } };
		} finally {
			if (siteHeld !== null && !('failed' in siteHeld)) await siteHeld.done();
			if (archiveHeld !== null && !('failed' in archiveHeld)) await archiveHeld.done();
		}
	});
}
