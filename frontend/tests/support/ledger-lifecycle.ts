/**
 * How does a test build a ledger in a lifecycle state, with no committed fixture?
 *
 * A test names a ledger, pins a UTC day, and lists the ledger's days counted back from it,
 * each packed with a number of rows, empty or lost. `buildLedger` writes what the gardener's
 * compaction leaves for those days, in the folder the readers look in for that ledger: the
 * three compact indexes, and one real Parquet file for
 * each packed day and each closed month that holds a row, written by the door's own query
 * engine with `COPY ... TO`. A packed day may hold no row, as the compaction once packed a
 * quiet day: its file holds every column and no row. A day the list leaves out is a hole.
 * Each file holds `covers`, the UTC day a row was filed under, and `date`, the same day in
 * the cell a panel slice keeps its rows by, as every dated packed file does, and `n`, the row's
 * number within its day, from 1. A test may choose more columns, each with one value every
 * row holds, typed by that value. A packed day or a lost one may name how many of its
 * writer's files the packing set aside unread.
 * `buildRows` packs a ledger whose rows carry no `date` and differ row by row, as the hand
 * marks of the holdout do: each row holds `covers` and the cells the test names.
 * Nothing here reads a committed fixture, so a test's expected values follow from what the
 * test built and nothing else.
 *
 * `siteCopy` stages the site's copy of a built ledger with the site build's own trim rule,
 * `servedFrom` answers a fetch from a built root the way a host serves a state tree, and
 * `serveToPage` answers a browser page's requests for one ledger from a built root.
 */

import type { BrowserContext } from '@playwright/test';
import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { ledgerCopy } from '../../scripts/published-ledgers.mjs';
import { COMPACT_INDEX_STAMP, type CompactEntry, type Period } from '../../src/lib/data/compact-index';
import { nodeEngine } from '../../src/lib/data/engine';
import type { Fetcher } from '../../src/lib/data/fetched-bytes';
import { ledgerFolder } from '../../src/lib/data/slice-reader';
import type { DateStamp, LedgerName } from '../../src/lib/data/slice-shapes';
import { engineExtensionRepository, ledgerArchiveBaseUrl } from '../../src/lib/server/config';

/** One day of a built ledger, `ago` days before the pinned day: a packed day holds `rows` rows,
 *  0 or more, an `empty` day held none, and a `lost` day lost its rows. A packed day and a lost
 *  one may have set `setAside` of their writer's files aside unread. */
export type BuiltDay =
	| { ago: number; rows: number; setAside?: number }
	| { ago: number; state: 'empty' }
	| { ago: number; state: 'lost'; setAside?: number };

/** The one value a chosen column holds in every row of a built ledger. A whole number is written
 *  as `BIGINT`, any other number as `DOUBLE`, a text as `VARCHAR`, and true or false as `BOOLEAN`. */
export type BuiltCell = number | string | boolean;

export interface BuiltLedger {
	ledger: LedgerName;
	/** The UTC day every `ago` counts back from. */
	pinned: DateStamp;
	/** Every day the ledger's indexes name; a day left out is a hole. */
	days: readonly BuiltDay[];
	/** Months the compaction has closed, `YYYY-MM`: each is one month entry, and its packed days one file. */
	closedMonths?: readonly string[];
	/** Columns every file holds beside `covers`, `date` and `n`, by name, each with its one value. */
	columns?: Readonly<Record<string, BuiltCell>>;
}

const DAY_MS = 86_400_000;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const MONTH = /^\d{4}-\d{2}$/;
/** The columns every built file holds, which a chosen column may not name again. */
const BUILT_COLUMNS = new Set(['covers', 'date', 'n']);
const resolver = createRequire(import.meta.url);

/** The UTC day `ago` days before `day`. */
export function daysBefore(day: DateStamp, ago: number): DateStamp {
	return new Date(Date.parse(`${day}T00:00:00Z`) - ago * DAY_MS).toISOString().slice(0, 10);
}

/** Every day from `oldest` days before the pinned day to `newest` days before it, each packed with `rows` rows. */
export function everyDay(oldest: number, newest: number, rows = 1): BuiltDay[] {
	const days: BuiltDay[] = [];
	for (let ago = oldest; ago >= newest; ago -= 1) days.push({ ago, rows });
	return days;
}

/** Every day from `oldest` days before the pinned day to `newest` days before it, each `empty`. */
export function quietDays(oldest: number, newest: number): BuiltDay[] {
	const days: BuiltDay[] = [];
	for (let ago = oldest; ago >= newest; ago -= 1) days.push({ ago, state: 'empty' });
	return days;
}

/** A chosen column's name, quoted for the statement. */
function quoted(name: string): string {
	return `"${name.replaceAll('"', '""')}"`;
}

/** A chosen column's value as a literal of the type the value names. */
function literal(value: BuiltCell): string {
	if (typeof value === 'boolean') return value ? 'TRUE' : 'FALSE';
	if (typeof value === 'string') return `'${value.replaceAll("'", "''")}'`;
	if (!Number.isFinite(value)) throw new Error(`${value} is not a number a file can hold`);
	return `CAST(${value} AS ${Number.isInteger(value) ? 'BIGINT' : 'DOUBLE'})`;
}

/** Write `rows` rows for each day into one Parquet file at `target`, through this process's own
 *  query engine, every row holding each chosen column's value, and return the file's size. A day of
 *  0 rows adds none, and a file of no row still holds every column. */
async function writeParquet(
	target: string,
	days: readonly [DateStamp, number][],
	columns: Readonly<Record<string, BuiltCell>>
): Promise<number> {
	for (const [day] of days) if (!DAY.test(day)) throw new Error(`${day} is not a UTC day`);
	mkdirSync(path.dirname(target), { recursive: true });
	const values = days.map(([day, rows]) => `('${day}', ${rows})`).join(', ');
	const chosen = Object.entries(columns)
		.map(([name, value]) => `, ${literal(value)} AS ${quoted(name)}`)
		.join('');
	const to = target.replaceAll('\\', '/').replaceAll("'", "''");
	const engine = await nodeEngine((specifier) => resolver.resolve(specifier), engineExtensionRepository());
	await engine.rows(
		`COPY (SELECT covers, covers AS "date", CAST(unnest(generate_series(1, rows)) AS BIGINT) AS n${chosen} FROM (VALUES ${values}) AS days(covers, rows) ORDER BY covers, n) TO '${to}' (FORMAT parquet)`,
		[]
	);
	return statSync(target).size;
}

function indexText(ledger: LedgerName, period: Period, entries: CompactEntry[]): string {
	return `${JSON.stringify({ entries, ledger, period, version: COMPACT_INDEX_STAMP }, null, 2)}\n`;
}

/** The files a packed or lost day set aside, as its entry carries them: absent when it set none aside. */
function setAsideOf(day: BuiltDay): { set_aside?: number } {
	return 'setAside' in day && day.setAside !== undefined ? { set_aside: day.setAside } : {};
}

/** Write a built ledger under `root` as `state/` holds one: three indexes and the files they name. */
export async function buildLedger(root: string, built: BuiltLedger): Promise<void> {
	const closed = new Set(built.closedMonths ?? []);
	for (const month of closed) if (!MONTH.test(month)) throw new Error(`${month} is not a UTC month`);
	const columns = built.columns ?? {};
	for (const name of Object.keys(columns)) {
		if (name === '' || BUILT_COLUMNS.has(name)) throw new Error(`${built.ledger} chooses a column named ${JSON.stringify(name)}`);
	}
	const named = new Map<DateStamp, BuiltDay>();
	for (const day of built.days) {
		const covers = daysBefore(built.pinned, day.ago);
		if (named.has(covers)) throw new Error(`${built.ledger} names ${covers} twice`);
		if ('rows' in day && !(Number.isInteger(day.rows) && day.rows >= 0)) throw new Error(`${covers} is packed with ${day.rows} rows`);
		const setAside = setAsideOf(day).set_aside;
		if (setAside !== undefined && !(Number.isInteger(setAside) && setAside > 0)) throw new Error(`${covers} set ${setAside} files aside`);
		named.set(covers, day);
	}
	const ascending = [...named.keys()].sort();
	const ledgerRoot = path.join(root, 'compact', ...ledgerFolder(built.ledger).split('/'));
	const daily: CompactEntry[] = [];
	const monthly: CompactEntry[] = [];
	for (const covers of ascending) {
		if (closed.has(covers.slice(0, 7))) continue;
		const day = named.get(covers)!;
		if ('state' in day) {
			daily.push({ covers, rows: 0, bytes: 0, state: day.state, ...setAsideOf(day) });
			continue;
		}
		const [year, month, date] = covers.split('-');
		const bytes = await writeParquet(path.join(ledgerRoot, 'daily', year!, month!, `${date}.parquet`), [[covers, day.rows]], columns);
		daily.push({ covers, rows: day.rows, bytes, ...setAsideOf(day) });
	}
	for (const month of [...closed].sort()) {
		const inMonth = ascending.filter((covers) => covers.startsWith(`${month}-`));
		const packed = inMonth.flatMap((covers) => {
			const day = named.get(covers)!;
			return 'rows' in day ? [[covers, day.rows] as [DateStamp, number]] : [];
		});
		const lost = inMonth.filter((covers) => {
			const day = named.get(covers)!;
			return 'state' in day && day.state === 'lost';
		});
		const lostDays = lost.length > 0 ? { lost_days: lost } : {};
		// A month counts every file its days set aside.
		const setAside = inMonth.reduce((sum, covers) => sum + (setAsideOf(named.get(covers)!).set_aside ?? 0), 0);
		const setAsideFiles = setAside > 0 ? { set_aside: setAside } : {};
		// A month that holds no row packs as `empty`, with no file, as the compaction packs one.
		if (packed.every(([, rows]) => rows === 0)) {
			monthly.push({ covers: month, rows: 0, bytes: 0, state: 'empty', ...lostDays });
			continue;
		}
		const [year, number] = month.split('-');
		const bytes = await writeParquet(path.join(ledgerRoot, 'monthly', year!, `${number}.parquet`), packed, columns);
		monthly.push({ covers: month, rows: packed.reduce((sum, [, rows]) => sum + rows, 0), bytes, ...lostDays, ...setAsideFiles });
	}
	mkdirSync(path.join(ledgerRoot, 'index'), { recursive: true });
	writeFileSync(path.join(ledgerRoot, 'index', 'daily.json'), indexText(built.ledger, 'daily', daily));
	writeFileSync(path.join(ledgerRoot, 'index', 'monthly.json'), indexText(built.ledger, 'monthly', monthly));
	writeFileSync(path.join(ledgerRoot, 'index', 'yearly.json'), indexText(built.ledger, 'yearly', []));
}

/** One packed day of a ledger whose rows each hold cells of their own. */
export interface BuiltRowsDay {
	covers: DateStamp;
	/** Every row of the day, each naming the same columns, none of them `covers`. A day of no
	 *  row is packed as the compaction packs a quiet day: an `empty` entry with no file. */
	rows: readonly Readonly<Record<string, BuiltCell>>[];
}

/** Write a packed ledger under `root` whose rows carry no `date` cell, the way the hand marks of
 *  the holdout are packed: one day file a day, each row holding `covers`, the day the door filed
 *  it under, and its own cells, typed by their values; then the three indexes, naming every day
 *  and no month or year. */
export async function buildRows(root: string, ledger: LedgerName, days: readonly BuiltRowsDay[]): Promise<void> {
	const ledgerRoot = path.join(root, 'compact', ...ledgerFolder(ledger).split('/'));
	const engine = await nodeEngine((specifier) => resolver.resolve(specifier), engineExtensionRepository());
	const daily: CompactEntry[] = [];
	for (const day of [...days].sort((left, right) => left.covers.localeCompare(right.covers))) {
		if (!DAY.test(day.covers)) throw new Error(`${day.covers} is not a UTC day`);
		if (day.rows.length === 0) {
			daily.push({ covers: day.covers, rows: 0, bytes: 0, state: 'empty' });
			continue;
		}
		const names = Object.keys(day.rows[0]!);
		if (names.includes('covers')) throw new Error(`a row of ${day.covers} names covers, which the builder writes`);
		const values = day.rows.map((row) => {
			if (Object.keys(row).join() !== names.join()) throw new Error(`a row of ${day.covers} names other columns`);
			return `('${day.covers}', ${names.map((name) => literal(row[name]!)).join(', ')})`;
		});
		const [year, month, date] = day.covers.split('-');
		const target = path.join(ledgerRoot, 'daily', year!, month!, `${date}.parquet`);
		mkdirSync(path.dirname(target), { recursive: true });
		const to = target.replaceAll('\\', '/').replaceAll("'", "''");
		await engine.rows(
			`COPY (SELECT * FROM (VALUES ${values.join(', ')}) AS rows(covers, ${names.map(quoted).join(', ')})) TO '${to}' (FORMAT parquet)`,
			[]
		);
		daily.push({ covers: day.covers, rows: day.rows.length, bytes: statSync(target).size });
	}
	mkdirSync(path.join(ledgerRoot, 'index'), { recursive: true });
	writeFileSync(path.join(ledgerRoot, 'index', 'daily.json'), indexText(ledger, 'daily', daily));
	writeFileSync(path.join(ledgerRoot, 'index', 'monthly.json'), indexText(ledger, 'monthly', []));
	writeFileSync(path.join(ledgerRoot, 'index', 'yearly.json'), indexText(ledger, 'yearly', []));
}

/** Stage under `to` the site's copy of a ledger built under `from`, trimmed by the site build's
 *  own rule to `windowDays` days, as the build stages `frontend/static/state/`. */
export function siteCopy(from: string, to: string, ledger: LedgerName, windowDays: number): void {
	const copy = ledgerCopy(from, [ledger], 'state', windowDays);
	if (copy.refused.length > 0 || copy.missing.length > 0) throw new Error([...copy.refused, ...copy.missing].join('\n'));
	for (const file of copy.files) {
		const target = path.join(to, ...file.split('/'));
		mkdirSync(path.dirname(target), { recursive: true });
		const index = copy.indexes[file];
		if (index === undefined) copyFileSync(path.join(from, ...file.split('/')), target);
		else writeFileSync(target, index);
	}
}

/** The file under `root` that a request for `relative`, a path under `state/`, reads, or null. */
function servedFile(root: string, relative: string): Uint8Array | null {
	const file = path.join(root, ...relative.split('/'));
	return existsSync(file) ? new Uint8Array(readFileSync(file)) : null;
}

/** A fetcher that answers from `root` as a host serves a state tree under `prefix`, and the
 *  path under `state/` of every request it was sent, in order. */
export function servedFrom(root: string, prefix: string): { fetcher: Fetcher; asked: string[] } {
	const asked: string[] = [];
	const base = `${prefix}/state/`;
	const fetcher: Fetcher = async (url) => {
		if (!url.startsWith(base)) throw new Error(`${url} is not under ${base}`);
		const relative = decodeURIComponent(new URL(url).pathname.slice(new URL(base).pathname.length));
		asked.push(relative);
		const bytes = servedFile(root, relative);
		return bytes === null ? new Response(null, { status: 404 }) : new Response(bytes.slice().buffer);
	};
	return { fetcher, asked };
}

/** Answer a page's requests to its own site for one ledger's compact files from `root`, a 404 for
 *  a file it lacks, and switch the page's writers' tier off: a built ledger has no writer's files,
 *  so the raw days the site build listed would be read from the canary. A request to the archive
 *  host is left to `serveArchiveToPage`, or to the block in `tests/support/browser.ts`. */
export async function serveToPage(context: BrowserContext, root: string, ledger: LedgerName): Promise<void> {
	const archive = ledgerArchiveBaseUrl();
	await context.addInitScript(() => Object.defineProperty(globalThis, '__RAW_LISTED_THROUGH__', { value: {}, configurable: true }));
	await context.route(
		(url) => (archive === '' || !url.href.startsWith(`${archive}/`)) && url.pathname.includes(`/state/compact/${ledger}/`),
		(route) => {
			const pathname = new URL(route.request().url()).pathname;
			const bytes = servedFile(root, pathname.slice(pathname.indexOf('/state/') + '/state/'.length));
			return bytes === null ? route.fulfill({ status: 404 }) : route.fulfill({ status: 200, body: Buffer.from(bytes) });
		}
	);
}

/** Answer a page's requests to the archive host, `ledger.archive_base_url`, from `root`, as the
 *  committed repository serves its `state/` tree to any origin, a 404 for a file it lacks. */
export async function serveArchiveToPage(context: BrowserContext, root: string): Promise<void> {
	const archive = ledgerArchiveBaseUrl();
	if (archive === '') throw new Error('ledger.archive_base_url is empty, so a page has no archive host to be served');
	const base = new URL(`${archive}/state/`).pathname;
	await context.route(`${archive}/state/**`, (route) => {
		const bytes = servedFile(root, decodeURIComponent(new URL(route.request().url()).pathname.slice(base.length)));
		const headers = { 'access-control-allow-origin': '*' };
		return bytes === null ? route.fulfill({ status: 404, headers }) : route.fulfill({ status: 200, headers, body: Buffer.from(bytes) });
	});
}
