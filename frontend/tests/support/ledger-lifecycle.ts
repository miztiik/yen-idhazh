/**
 * How does a test build a ledger in a lifecycle state, with no committed fixture?
 *
 * A test names a ledger, pins a UTC day, and lists the ledger's days counted back from it,
 * each packed with a number of rows, empty or lost. `buildLedger` writes what the gardener's
 * compaction leaves for those days: the three compact indexes, and one real Parquet file for
 * each packed day and each closed month, written by the door's own query engine with
 * `COPY ... TO`. A
 * day the list leaves out is a hole. Each file holds `covers`, the UTC day a row was filed
 * under, as every packed file does, and `n`, the row's number within its day, from 1.
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
import type { DateStamp, LedgerName } from '../../src/lib/data/slice-shapes';
import { engineExtensionRepository } from '../../src/lib/server/config';

/** One day of a built ledger, `ago` days before the pinned day: a packed day holds `rows` rows,
 *  an `empty` day held none, and a `lost` day lost its rows. */
export type BuiltDay = { ago: number; rows: number } | { ago: number; state: 'empty' | 'lost' };

export interface BuiltLedger {
	ledger: LedgerName;
	/** The UTC day every `ago` counts back from. */
	pinned: DateStamp;
	/** Every day the ledger's indexes name; a day left out is a hole. */
	days: readonly BuiltDay[];
	/** Months the compaction has closed, `YYYY-MM`: each is one month entry, and its packed days one file. */
	closedMonths?: readonly string[];
}

const DAY_MS = 86_400_000;
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const MONTH = /^\d{4}-\d{2}$/;
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

/** Write `rows` rows for each day into one Parquet file at `target`, through this process's own
 *  query engine, and return the file's size. */
async function writeParquet(target: string, days: readonly [DateStamp, number][]): Promise<number> {
	for (const [day] of days) if (!DAY.test(day)) throw new Error(`${day} is not a UTC day`);
	mkdirSync(path.dirname(target), { recursive: true });
	const values = days.map(([day, rows]) => `('${day}', ${rows})`).join(', ');
	const to = target.replaceAll('\\', '/').replaceAll("'", "''");
	const engine = await nodeEngine((specifier) => resolver.resolve(specifier), engineExtensionRepository());
	await engine.rows(
		`COPY (SELECT covers, CAST(unnest(generate_series(1, rows)) AS BIGINT) AS n FROM (VALUES ${values}) AS days(covers, rows) ORDER BY covers, n) TO '${to}' (FORMAT parquet)`,
		[]
	);
	return statSync(target).size;
}

function indexText(ledger: LedgerName, period: Period, entries: CompactEntry[]): string {
	return `${JSON.stringify({ entries, ledger, period, version: COMPACT_INDEX_STAMP }, null, 2)}\n`;
}

/** Write a built ledger under `root` as `state/` holds one: three indexes and the files they name. */
export async function buildLedger(root: string, built: BuiltLedger): Promise<void> {
	const closed = new Set(built.closedMonths ?? []);
	for (const month of closed) if (!MONTH.test(month)) throw new Error(`${month} is not a UTC month`);
	const named = new Map<DateStamp, BuiltDay>();
	for (const day of built.days) {
		const covers = daysBefore(built.pinned, day.ago);
		if (named.has(covers)) throw new Error(`${built.ledger} names ${covers} twice`);
		if ('rows' in day && !(Number.isInteger(day.rows) && day.rows > 0)) throw new Error(`${covers} is packed with ${day.rows} rows`);
		named.set(covers, day);
	}
	const ascending = [...named.keys()].sort();
	const ledgerRoot = path.join(root, 'compact', built.ledger);
	const daily: CompactEntry[] = [];
	const monthly: CompactEntry[] = [];
	for (const covers of ascending) {
		if (closed.has(covers.slice(0, 7))) continue;
		const day = named.get(covers)!;
		if ('state' in day) {
			daily.push({ covers, rows: 0, bytes: 0, state: day.state });
			continue;
		}
		const [year, month, date] = covers.split('-');
		const bytes = await writeParquet(path.join(ledgerRoot, 'daily', year!, month!, `${date}.parquet`), [[covers, day.rows]]);
		daily.push({ covers, rows: day.rows, bytes });
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
		if (packed.length === 0) {
			monthly.push({ covers: month, rows: 0, bytes: 0, state: 'empty', ...lostDays });
			continue;
		}
		const [year, number] = month.split('-');
		const bytes = await writeParquet(path.join(ledgerRoot, 'monthly', year!, `${number}.parquet`), packed);
		monthly.push({ covers: month, rows: packed.reduce((sum, [, rows]) => sum + rows, 0), bytes, ...lostDays });
	}
	mkdirSync(path.join(ledgerRoot, 'index'), { recursive: true });
	writeFileSync(path.join(ledgerRoot, 'index', 'daily.json'), indexText(built.ledger, 'daily', daily));
	writeFileSync(path.join(ledgerRoot, 'index', 'monthly.json'), indexText(built.ledger, 'monthly', monthly));
	writeFileSync(path.join(ledgerRoot, 'index', 'yearly.json'), indexText(built.ledger, 'yearly', []));
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

/** Answer a page's requests for one ledger's compact files from `root`, a 404 for a file it lacks. */
export async function serveToPage(context: BrowserContext, root: string, ledger: LedgerName): Promise<void> {
	await context.route(`**/state/compact/${ledger}/**`, (route) => {
		const pathname = new URL(route.request().url()).pathname;
		const bytes = servedFile(root, pathname.slice(pathname.indexOf('/state/') + '/state/'.length));
		return bytes === null ? route.fulfill({ status: 404 }) : route.fulfill({ status: 200, body: Buffer.from(bytes) });
	});
}
