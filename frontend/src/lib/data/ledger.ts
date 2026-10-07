/**
 * What does a console panel call to read a committed ledger?
 *
 * `slice()` for rows and `ledgerReach()` for how far a ledger reaches, and
 * nothing else under `frontend/src/lib/data/`: a panel imports this module and no
 * deeper one. A panel names a ledger, the columns it draws and a closed range of
 * UTC days. This module binds the query door to this site's published tree -
 * `visuals.asset_base_url`, or SvelteKit's own prefix when that knob is empty,
 * which is the shipped default - and to the query engine, which it reaches only
 * through a dynamic `import()`, so the engine is never part of a page's first
 * load.
 *
 * **One page keeper serves the whole page** (`page-keeper.ts`). It is made on
 * first use and kept until the page is reloaded, so each index is read once a
 * page and each data file crosses the network and enters the engine once.
 *
 * A build-time reader calls `sliceFromDisk()` in
 * `frontend/src/lib/server/ledger-disk.ts` instead; a panel never does.
 */

import { base } from '$app/paths';
import { fetchedBytes } from './fetched-bytes';
import { readAsk, readAskCost, type ArchiveTier, type RawListedThrough } from './ask-reader';
import { readColumns } from './ledger-columns';
import { readReach, type LedgerReach } from './ledger-reach';
import { pageKeeper, type PageKeeper } from './page-keeper';
import { readSlice } from './slice-reader';
import type { QueryEngine } from './slice-query';
import type { AskOptions, AskResult, Column, DateStamp, LedgerName, SliceOptions, SliceResult, SpanCost } from './slice-shapes';

export type { LedgerReach } from './ledger-reach';
export type { AskFault, AskOptions, AskRefusal, AskResult, Column, DateStamp, FetchCost, LedgerFault, LedgerName, Predicate, Row, SetAsideFiles, SliceOptions, SliceResult, SpanCost, SpanGap } from './slice-shapes';

let kept: PageKeeper | null = null;
let keptArchive: PageKeeper | null = null;
let engine: Promise<QueryEngine> | null = null;

function openEngine(): Promise<QueryEngine> {
	engine ??= import('./engine').then((engineModule) => engineModule.browserEngine(__ENGINE_EXTENSION_REPOSITORY__));
	return engine;
}

/** What this page has read from the published tree. The prefix is this build's
 *  own config, never a payload's. */
function keeper(): PageKeeper {
	kept ??= pageKeeper(
		fetchedBytes(__ASSET_BASE_URL__ || base, (url, init) => fetch(url, init)),
		openEngine
	);
	return kept;
}

/** The archive's prefix: this build's `ledger.archive_base_url`. A page script that sets
 *  `__ARCHIVE_BASE_URL__` to an empty string reads the site alone, as the browser test of a
 *  site-only span does; nothing on the page can point the archive at another address. */
function archiveBaseUrl(): string {
	const runtime = (globalThis as typeof globalThis & { __ARCHIVE_BASE_URL__?: unknown }).__ARCHIVE_BASE_URL__;
	return runtime === '' ? '' : __ARCHIVE_BASE_URL__;
}

/** The archive, and how many UTC days of each ledger the site copy keeps, so the archive is
 *  asked only for days the copy may have dropped; `null` when the page reads the site alone. */
function archiveTier(): ArchiveTier | null {
	const baseUrl = archiveBaseUrl();
	if (!baseUrl) return null;
	keptArchive ??= pageKeeper(
		((source) => ({ index: source.index, data: source.data }))(fetchedBytes(baseUrl, (url, init) => fetch(url, init))),
		openEngine
	);
	return { keeper: keptArchive, siteWindowDays: __SITE_WINDOW_DAYS__ };
}

/** Ask a committed ledger for the slice a panel draws. Columns and a date range
 *  are named by the caller; nothing fetches a whole ledger. */
export function slice(ledger: LedgerName, options: SliceOptions): Promise<SliceResult> {
	return readSlice(keeper(), ledger, options);
}

/** How far a committed ledger reaches: the oldest and the newest day its
 *  indexes name. Reads nothing else and starts no engine. */
export function ledgerReach(ledger: LedgerName): Promise<LedgerReach> {
	return readReach(keeper(), ledger);
}

/** The newest raw day the site build listed for each ledger: this build's `__RAW_LISTED_THROUGH__`.
 *  A page script that sets `__RAW_LISTED_THROUGH__` to an object with no keys reads no writer's
 *  file, as the browser tests that serve a ledger they built do, because a built ledger has no
 *  writer's files; nothing on the page can name a day the build did not list. */
function rawListedThrough(): RawListedThrough {
	const runtime = (globalThis as typeof globalThis & { __RAW_LISTED_THROUGH__?: unknown }).__RAW_LISTED_THROUGH__;
	const switchedOff = runtime !== null && typeof runtime === 'object' && Object.keys(runtime).length === 0;
	return switchedOff ? {} : ((__RAW_LISTED_THROUGH__ ?? {}) as RawListedThrough);
}

/** Run one read-only statement over chosen ledgers and days. */
export function ask(options: AskOptions): Promise<AskResult> {
	return readAsk(keeper(), archiveTier(), options, rawListedThrough());
}

/** What a written question would fetch before it runs. */
export function askCost(ledgers: readonly LedgerName[], from: DateStamp, to: DateStamp): Promise<SpanCost> {
	return readAskCost(keeper(), archiveTier(), ledgers, from, to, rawListedThrough());
}

/** A chosen ledger's columns, from the files its empty view reads, whatever window is selected:
 *  it takes no window and moves none. Files over `maxFetchBytes` are not fetched. */
export function askColumns(ledger: LedgerName, maxFetchBytes: number): Promise<Column[]> {
	return readColumns(keeper(), ledger, maxFetchBytes, rawListedThrough());
}

/** Drop this page's query-door cache, so Refresh reads the registry and indexes anew. */
export async function startAfresh(): Promise<void> {
	const current = kept;
	const archive = keptArchive;
	kept = null;
	keptArchive = null;
	if (current !== null) await current.release();
	if (archive !== null) await archive.release();
}

/** Whole-file bytes the current page keeper holds in the engine. */
export function pageHeldBytes(): number {
	return (kept?.heldBytes() ?? 0) + (keptArchive?.heldBytes() ?? 0);
}
