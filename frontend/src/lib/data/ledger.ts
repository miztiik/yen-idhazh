/**
 * What does a console panel call to read a committed ledger?
 *
 * `slice()`, and nothing else under `frontend/src/lib/data/`: a panel imports
 * this module and no deeper one. A panel names a ledger, the columns it draws
 * and a closed range of UTC days. This module binds the query door to this
 * site's published tree - `visuals.asset_base_url`, or SvelteKit's own prefix
 * when that knob is empty, which is the shipped default - and to the query
 * engine, which it reaches only through a dynamic `import()`, so the engine is
 * never part of a page's first load.
 *
 * A build-time reader calls `sliceFromDisk()` in
 * `frontend/src/lib/server/ledger-disk.ts` instead; a panel never does.
 */

import { base } from '$app/paths';
import { fetchedBytes } from './fetched-bytes';
import { readSlice } from './slice-reader';
import type { LedgerName, SliceOptions, SliceResult } from './slice-shapes';

export type { DateStamp, LedgerName, Predicate, Row, SliceOptions, SliceResult } from './slice-shapes';

/** The published tree. The prefix is this build's own config, never a payload's. */
const published = fetchedBytes(__ASSET_BASE_URL__ || base, (url, init) => fetch(url, init));

/** Ask a committed ledger for the slice a panel draws. Columns and a date range
 *  are named by the caller; nothing fetches a whole ledger. */
export function slice(ledger: LedgerName, options: SliceOptions): Promise<SliceResult> {
	return readSlice(
		published,
		() => import('./engine').then((engine) => engine.browserEngine(__ENGINE_EXTENSION_REPOSITORY__)),
		ledger,
		options
	);
}
