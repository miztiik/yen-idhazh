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
import { readAsk, readAskCost, type RawListedThrough } from './ask-reader';
import { readReach, type LedgerReach } from './ledger-reach';
import { pageKeeper, type PageKeeper } from './page-keeper';
import { readSlice } from './slice-reader';
import type { AskOptions, AskResult, DateStamp, LedgerName, SliceOptions, SliceResult, SpanCost } from './slice-shapes';

export type { LedgerReach } from './ledger-reach';
export type { AskFault, AskOptions, AskRefusal, AskResult, Column, DateStamp, FetchCost, LedgerFault, LedgerName, Predicate, Row, SliceOptions, SliceResult, SpanCost } from './slice-shapes';

let kept: PageKeeper | null = null;

/** What this page has read from the published tree. The prefix is this build's
 *  own config, never a payload's. */
function keeper(): PageKeeper {
	kept ??= pageKeeper(
		fetchedBytes(__ASSET_BASE_URL__ || base, (url, init) => fetch(url, init)),
		() => import('./engine').then((engine) => engine.browserEngine(__ENGINE_EXTENSION_REPOSITORY__))
	);
	return kept;
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

const rawListedThrough = (__RAW_LISTED_THROUGH__ ?? {}) as RawListedThrough;

/** Run one read-only statement over chosen ledgers and days. */
export function ask(options: AskOptions): Promise<AskResult> {
	return readAsk(keeper(), options, rawListedThrough);
}

/** What a written question would fetch before it runs. */
export function askCost(ledgers: readonly LedgerName[], from: DateStamp, to: DateStamp): Promise<SpanCost> {
	return readAskCost(keeper(), ledgers, from, to, rawListedThrough);
}
