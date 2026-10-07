/** How does the written-question door turn selected ledgers and days into one answer? */

import { COMPACT_PERIODS, type CompactEntry, type Period } from './compact-index';
import type { FileShortfall, Holding, PageKeeper, WantedFile } from './page-keeper';
import { coveredDays, filesFor, firstNamed, newestFile, newestNamed, writerDaysFor, type ChosenFile } from './slice';
import { listOf, type QueryEngine } from './slice-query';
import {
	dataPath,
	dataVersion,
	rawDataPath,
	rawIndexPath,
	explainRefusal,
	explainShortfall,
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
	type CutDays,
	type DateStamp,
	type FetchCost,
	type LedgerName,
	type Row,
	type SetAsideFiles,
	type SpanCost,
	type SpanGap,
	type UnansweredDays
} from './slice-shapes';

export type RawListedThrough = Readonly<Partial<Record<LedgerName, DateStamp>>>;

/** The archive, and how many UTC days of each ledger the site copy keeps. The archive holds
 *  the days the copy dropped, so it is read only when `site-window.ts` says the copy may have
 *  dropped some. */
export type ArchiveTier = { keeper: PageKeeper; siteWindowDays: number };

type Indexes = { daily: CompactEntry[]; monthly: CompactEntry[]; yearly: CompactEntry[] };
/** The first of a ledger's indexes a keeper could not read: its period, and why in the console's
 *  words, or `null` when the index is not there. */
type IndexFailure = { failed: Period; refusal: string | null };
type FileMeta = { ledger: LedgerName; day: DateStamp | null };
/** The days a packed file is read for, or `null` when every row it holds is in the span. */
type DayWindow = { from: DateStamp; to: DateStamp } | null;
type PlannedFile = { file: WantedFile; meta: FileMeta; keeper: 'site' | 'archive'; window: DayWindow };
type HeldSource = { name: string; window: DayWindow };
/** Files one keeper holds for a question, and the holding that names them, in planned order. */
type HeldFiles = { files: readonly PlannedFile[]; holding: Extract<Holding, { engine: QueryEngine }> };
/** The packed files a span reads, the days in it recorded lost, the files its periods set aside,
 *  and the day the span is read from: `null` when the indexes name no day. */
type CompactChoice = { chosen: ChosenFile[]; lostDays: DateStamp[]; setAside: SetAsideFiles; start: DateStamp | null };
type LedgerPlan = {
	ledger: LedgerName;
	through: DateStamp | null;
	files: PlannedFile[];
	emptySource: PlannedFile[];
	unpackedDays: DateStamp[];
	cutBefore: DateStamp | null;
	unanswered: UnansweredDays | null;
	lostDays: DateStamp[];
	setAside: SetAsideFiles;
	unreachable: AskResult | null;
};
type Plan = { ledgers: LedgerPlan[]; cost: SpanCost; files: PlannedFile[]; unanswered: UnansweredDays[] };

/** What a console line about the archive says happened next. */
const SITE_ALONE = 'so the question reads this ledger from this site alone';

let queue: Promise<void> = Promise.resolve();

/** Runs `work` once every call queued before it has ended. The engine has one connection, and
 *  each call rewrites the ledger views it holds, so no two calls may overlap. */
export async function serial<T>(work: () => Promise<T>): Promise<T> {
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

/** A ledger's three compact indexes as one keeper reads them, or the first it could not read. */
export async function readIndexes(keeper: PageKeeper, ledger: LedgerName): Promise<Indexes | IndexFailure> {
	const indexes: Indexes = { daily: [], monthly: [], yearly: [] };
	for (const period of COMPACT_PERIODS) {
		const reading = await readIndexFrom(keeper, ledger, period);
		if (reading === null) return { failed: period, refusal: null };
		if ('refused' in reading) return { failed: period, refusal: explainRefusal(period, reading.refused) };
		indexes[period] = reading.index.entries;
	}
	return indexes;
}

/** A ledger's three compact indexes on the site, or the answer that says why the question cannot run.
 *  The build refuses to publish a ledger that lacks any of the three, so on the site an
 *  absent or refused index is a broken deploy, and none is ever read as an empty list. */
async function compactIndexes(
	keeper: PageKeeper,
	ledger: LedgerName,
	from: DateStamp,
	to: DateStamp
): Promise<Indexes | AskResult> {
	const read = await readIndexes(keeper, ledger);
	if (!('failed' in read)) return read;
	if (read.refusal !== null) {
		keeper.warn(`${LOG_PREFIX} ${ledger} ${from} to ${to}: ${read.refusal}, so the question did not run`);
	} else if (read.failed === 'daily') {
		return { state: 'missing', ledger };
	} else {
		keeper.warn(faultLine(ledger, { fault: 'index-missing', period: read.failed }));
	}
	return { state: 'unreachable', ledger, at: from, fault: 'index-missing' };
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

/** The archive's packed files for the days the site copy may have dropped, chosen as the site's
 *  are, so a hole its indexes name is still `day-missing`. `unanswered` when one of its indexes
 *  could not be read: not there, refused, or not fetched. The console line says which, and the
 *  ledger is then read from the site's days alone. */
async function archiveSelection(
	keeper: PageKeeper,
	ledger: LedgerName,
	from: DateStamp,
	until: DateStamp
): Promise<CompactChoice | AskResult | 'unanswered'> {
	const read = await readIndexes(keeper, ledger);
	if (!('failed' in read)) return compactSelection(ledger, from, until, read);
	keeper.warn(`${LOG_PREFIX} ${ledger} ${from} to ${until}: the repository's ${read.refusal ?? `${read.failed}.json is not there`}, ${SITE_ALONE}`);
	return 'unanswered';
}

/** The files an empty view takes its columns from: the ledger's newest day, from its listing
 *  when the build listed a day after the newest packed one, else from the newest packed file.
 *  A zero-row packed file is kept, because a view that reads no rows needs only the file's
 *  columns, and a ledger whose packed days all hold zero rows would otherwise have no file.
 *  An `empty` or `lost` entry has no file, so the newest entry that has one is taken. */
export async function viewSource(
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

/** One selected ledger's part of a question. `archiveAnswers` is false once the archive could not
 *  give this ledger's files, so the ledger is planned again from the site's days alone. */
async function planLedger(
	keeper: PageKeeper,
	archive: ArchiveTier | null,
	ledger: LedgerName,
	from: DateStamp,
	to: DateStamp,
	rawListed: RawListedThrough,
	archiveAnswers = true
): Promise<LedgerPlan> {
	const indexed = await compactIndexes(keeper, ledger, from, to);
	if ('state' in indexed) {
		return { ledger, through: null, files: [], emptySource: [], unpackedDays: [], cutBefore: null, unanswered: null, lostDays: [], setAside: {}, unreachable: indexed };
	}

	const newestPacked = newestNamed(indexed.daily, indexed.monthly, indexed.yearly);
	const siteFirst = compactFirst(indexed);
	const through = later(newestPacked, rawListed[ledger] ?? null);
	const files: PlannedFile[] = [];
	const lostDays: DateStamp[] = [];
	const setAside: Record<string, number> = {};
	let unreachable: AskResult | null = null;
	let cutBefore: DateStamp | null = null;
	let unanswered: UnansweredDays | null = null;
	let siteStart = from;
	/** One keeper's packed files for its part of the span, and what that part is missing.
	 *  The archive's part comes first, so the lost days stay in order. */
	const take = (choice: CompactChoice, held: 'site' | 'archive', until: DateStamp): void => {
		files.push(...addCompactPlanned(choice.chosen, ledger, held, until));
		lostDays.push(...choice.lostDays);
		Object.assign(setAside, choice.setAside);
	};

	// When the selected window begins before the site's first day, the days before the first day a
	// tier names are cut from it, and `cutBefore` names that day; no end moves. The archive is a
	// tier only for days the site copy may have dropped (`site-window.ts`). When it does not answer
	// for them, the ledger is read from the site's first day, and `unanswered` names that day.
	if (siteFirst !== null && newestPacked !== null && from < siteFirst) {
		cutBefore = siteFirst;
		if (archive !== null && siteMayHaveTrimmed(siteFirst, newestPacked, archive.siteWindowDays)) {
			const archiveTo = to < siteFirst ? to : previousDay(siteFirst);
			const choice = archiveAnswers ? await archiveSelection(archive.keeper, ledger, from, archiveTo) : 'unanswered';
			if (choice === 'unanswered') {
				unanswered = { tier: 'archive', ledger, before: siteFirst };
				cutBefore = null;
			} else if ('state' in choice) unreachable = choice;
			else {
				take(choice, 'archive', archiveTo);
				cutBefore = choice.start === from ? null : earlier(choice.start, siteFirst);
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
		cutBefore,
		unanswered,
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

/** Each selected ledger whose days before its first day were cut from the window, with that day,
 *  in the order chosen. */
function cutOf(plans: readonly LedgerPlan[]): CutDays[] {
	return plans.flatMap((one) => (one.cutBefore === null ? [] : [{ ledger: one.ledger, before: one.cutBefore }]));
}

/** The first day any selected ledger's answer reads. A ledger's answer starts on `from`, the
 *  window's first day, unless its earlier days were cut or the repository could not give them;
 *  then it starts on the day `cutBefore` or `unanswered` names. */
function firstDayRead(plans: readonly LedgerPlan[], from: DateStamp): DateStamp {
	return plans.map((one) => one.cutBefore ?? one.unanswered?.before ?? from).sort()[0] ?? from;
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
		return { state: 'quiet', columns: [], read: { files: 0, bytes: 0, alreadyHeld: 0, ms: 0 }, cut: [], unanswered: [], gaps: [] };
	}
	for (const ledger of chosen) {
		if (!(LEDGER_NAMES as readonly string[]).includes(ledger)) return { state: 'missing', ledger };
	}
	return planOf(await Promise.all(chosen.map((ledger) => planLedger(keeper, archive, ledger, from, to, rawListed))));
}

/** A question's plan from its ledgers' plans, in the order chosen, or the answer one of them gives first. */
function planOf(ledgersPlanned: LedgerPlan[]): Plan | AskResult {
	const failed = ledgersPlanned.find((one) => one.unreachable !== null);
	if (failed?.unreachable) return failed.unreachable;
	const noDays = ledgersPlanned.find((one) => one.through === null);
	if (noDays) return { state: 'missing', ledger: noDays.ledger };
	const files = ledgersPlanned.flatMap((one) => one.files);
	return {
		ledgers: ledgersPlanned,
		files,
		unanswered: ledgersPlanned.flatMap((one) => (one.unanswered === null ? [] : [one.unanswered])),
		cost: {
			files: files.length,
			bytes: files.reduce((sum, plannedFile) => sum + plannedFile.file.bytes, 0),
			unpackedDays: [...new Set(ledgersPlanned.flatMap((one) => one.unpackedDays))],
			cut: cutOf(ledgersPlanned),
			through: Object.fromEntries(ledgersPlanned.flatMap((one) => (one.through === null ? [] : [[one.ledger, one.through]])))
		}
	};
}

export function quoteIdent(name: LedgerName): string {
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
export function viewStatement(ledger: LedgerName, sources: readonly HeldSource[], empty: boolean): string {
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

/** The columns a `DESCRIBE` names, each with its type. */
export function columnsOf(rows: Record<string, unknown>[]): Column[] {
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
 *  names are cut from the window, and `cut` names each such ledger with that day; `archive` is read
 *  only for days the site copy may have dropped. */
export async function readAskCost(
	keeper: PageKeeper,
	archive: ArchiveTier | null,
	ledgers: readonly LedgerName[],
	from: DateStamp,
	to: DateStamp,
	rawListed: RawListedThrough
): Promise<SpanCost> {
	const planned = await plan(keeper, archive, ledgers, from, to, rawListed);
	return 'state' in planned ? { files: 0, bytes: 0, unpackedDays: [], cut: 'cut' in planned ? planned.cut : [], through: {} } : planned.cost;
}

/** What a plan answers before any file is held: `quiet` when no selected ledger holds a file in the
 *  span, which starts no engine, or `missing` for a ledger an empty view has no file to take its
 *  columns from. `null` when there are files to read. */
function answeredUnheld(planned: Plan, started: number): AskResult | null {
	if (planned.ledgers.every((one) => one.files.length === 0)) {
		return { state: 'quiet', columns: [], read: { files: 0, bytes: 0, alreadyHeld: 0, ms: Date.now() - started }, cut: planned.cost.cut, unanswered: planned.unanswered, gaps: gapsOf(planned.ledgers) };
	}
	// An empty view over no file would reach the engine as `read_parquet([])`, which it refuses.
	const sourceless = planned.ledgers.find((one) => one.files.length === 0 && one.emptySource.length === 0);
	return sourceless ? { state: 'missing', ledger: sourceless.ledger } : null;
}

/** Why a wanted file could not be had, as the console says it. */
export function explainMissedFile(file: WantedFile, shortfall: FileShortfall): string {
	return shortfall.reason === 'absent' ? `${file.path} is not there` : explainShortfall(file, shortfall);
}

/** The console line for an archive file a question could not read. */
function archiveFileLine(planned: PlannedFile, shortfall: FileShortfall, from: DateStamp, to: DateStamp): string {
	return `${LOG_PREFIX} ${planned.meta.ledger} ${from} to ${to}: the repository's ${explainMissedFile(planned.file, shortfall)}, ${SITE_ALONE}`;
}

/** The plan with each ledger's archive files held, one ledger at a time, before any site file is
 *  fetched. A ledger whose archive files did not all arrive is planned again from the site's days
 *  alone, and keeps none of them; every other ledger keeps its own. Each holding joins `held`. */
async function holdArchive(
	keeper: PageKeeper,
	archive: ArchiveTier,
	asked: Plan,
	opts: AskOptions,
	rawListed: RawListedThrough,
	held: HeldFiles[]
): Promise<Plan | AskResult> {
	const ledgers: LedgerPlan[] = [];
	for (const one of asked.ledgers) {
		const files = one.files.filter((planned) => planned.keeper === 'archive');
		const holding = files.length === 0 ? null : await archive.keeper.hold(files.map((planned) => planned.file));
		if (holding === null || !('failed' in holding)) {
			if (holding !== null) held.push({ files, holding });
			ledgers.push(one);
			continue;
		}
		const failed = files[holding.failed];
		if (failed !== undefined) archive.keeper.warn(archiveFileLine(failed, holding.shortfall, opts.from, opts.to));
		ledgers.push(await planLedger(keeper, archive, one.ledger, opts.from, opts.to, rawListed, false));
	}
	return ledgers.every((one, at) => one === asked.ledgers[at]) ? asked : planOf(ledgers);
}

/** The answer to a planned question: each ledger's archive files held first, then the site's,
 *  then one view a ledger and the statement run over them. Each holding joins `held`, which the
 *  caller drops once the answer is in. */
async function answerHeld(
	keeper: PageKeeper,
	archive: ArchiveTier | null,
	asked: Plan,
	opts: AskOptions,
	rawListed: RawListedThrough,
	sql: string,
	held: HeldFiles[],
	started: number
): Promise<AskResult> {
	let planned: Plan | AskResult;
	let site: Holding;
	try {
		planned = archive === null ? asked : await holdArchive(keeper, archive, asked, opts, rawListed, held);
		if ('state' in planned) return planned;
		const siteAlone = planned === asked ? null : answeredUnheld(planned, started);
		if (siteAlone !== null) return siteAlone;
		const sources = planned.ledgers.map((one) => (one.files.length > 0 ? one.files : one.emptySource));
		const siteFiles = sources.flat().filter((one) => one.keeper === 'site');
		site = await keeper.hold(siteFiles.map((one) => one.file));
		if ('failed' in site) {
			const meta = siteFiles[site.failed]?.meta;
			const fault = site.shortfall.reason === 'absent' ? 'file-missing' : null;
			return { state: 'unreachable', ledger: meta?.ledger ?? null, at: meta?.day ?? null, fault };
		}
		held.push({ files: siteFiles, holding: site });
	} catch {
		return { state: 'unreachable', ledger: null, at: null, fault: 'engine' };
	}

	try {
		const names = new Map(held.flatMap((group) => group.files.map((one, at) => [one, group.holding.names[at]] as const)));
		const sources: HeldSource[][] = planned.ledgers.map((one) => (one.files.length > 0 ? one.files : one.emptySource).map((plannedFile) => {
			const name = names.get(plannedFile);
			if (name === undefined) throw new Error('planned file was not held');
			return { name, window: plannedFile.window };
		}));
		await prepareViews(site.engine, planned.ledgers, sources);
		const columns = await describe(site.engine, sql);
		const answer = await runRows(site.engine, sql, opts.maxRows, columns);
		const read = sumCost(held.map((group) => readCost(group.files.map((one) => one.file), group.holding.fetched, started)), started);
		const named = { cut: planned.cost.cut, unanswered: planned.unanswered, gaps: gapsOf(planned.ledgers) };
		return answer.rows.length === 0
			? { state: 'quiet', columns, read, ...named }
			: { state: 'ok', columns, rows: answer.rows, capped: answer.capped, read, readFrom: firstDayRead(planned.ledgers, opts.from), unpackedDays: planned.cost.unpackedDays, ...named };
	} catch (error) {
		return { state: 'refused', because: { kind: 'engine-error', message: error instanceof Error ? error.message : String(error) } };
	}
}

/** One read-only statement over the chosen ledgers and days. Days before the first day a tier
 *  names are cut from the window, and `cut` names each such ledger with that day; `archive` is read
 *  only for days the site copy may have dropped. A ledger the archive cannot give those days for is
 *  read from the site's days alone, and `unanswered` names it with the day its answer starts on. An
 *  answer with rows names in `readFrom` the first day it read. */
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
		const asked = await plan(keeper, archive, opts.ledgers, opts.from, opts.to, rawListed);
		if ('state' in asked) return asked;
		if (asked.cost.bytes > opts.maxFetchBytes) {
			return { state: 'refused', because: { kind: 'over-ceiling', bytes: asked.cost.bytes, files: asked.cost.files, max: opts.maxFetchBytes } };
		}
		const unheld = answeredUnheld(asked, started);
		if (unheld !== null) return unheld;
		const held: HeldFiles[] = [];
		try {
			return await answerHeld(keeper, archive, asked, opts, rawListed, checked.sql, held, started);
		} finally {
			for (const group of held) await group.holding.done();
		}
	});
}
