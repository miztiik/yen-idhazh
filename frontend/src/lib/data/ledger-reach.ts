/**
 * How far does a ledger reach, read from its indexes and nothing else?
 *
 * A console route anchors its span on the data rather than on the clock, so it
 * needs the oldest and the newest day a ledger holds before it asks for a slice.
 * `ledgerReach()` in `ledger.ts` answers with this module. It reads `daily.json`,
 * `monthly.json` and `yearly.json` at the same time, through the page keeper, so
 * a slice asked afterwards fetches none of them again; and it starts no engine,
 * because an index is JSON.
 *
 * - `ok`: `through` is how far the ledger is packed, the newest day any index
 *   names - the day a slice returns as its own `through`. `first` is the oldest
 *   day any index names, a month counting from its first day and a year from its
 *   1 January. `fault` is `index-missing` when there is no `monthly.json` or no
 *   `yearly.json`: `first` and `through` are then what the indexes that are
 *   there name, so a route anchored on them still draws every day the door can
 *   read.
 * - `quiet`: no index names a day yet.
 * - `missing`: there is no `daily.json`, so the ledger is not published. Its
 *   fault is `not-packed`.
 * - `unreachable`: `daily.json` is one this build will not act on, or could not
 *   be read, and the console says why. It carries no day, because the reach asks
 *   for none, and no fault, because it reads no file an index names.
 *
 * `monthly.json` and `yearly.json` move `first` back. The packing moves a closed
 * month's days out of `daily.json`, so they give `through` only when `daily.json`
 * names no day. An empty one says no month, or no year, is packed yet. When this
 * build will not act on one, the reach is what the other indexes name, and the
 * console says why.
 *
 * Each index is read the way a slice reads it, by `readIndexFrom()` in
 * `slice-reader.ts`, a fault's console line is the slice's own `faultLine()`,
 * and `first` and `through` are `firstNamed()` and `newestNamed()` in `slice.ts`,
 * so a slice and a reach never disagree about what an index says or print one
 * fault twice. Imports nothing tied to one environment, so a Node test loads it
 * as it is.
 */

import type { CompactEntry, IndexReading, Period } from './compact-index';
import type { PageKeeper } from './page-keeper';
import { firstNamed, newestNamed } from './slice';
import { explainRefusal, faultLine, LOG_PREFIX, readIndexFrom } from './slice-reader';
import { LEDGER_NAMES, SliceRequestError, type DateStamp, type LedgerFault, type LedgerName } from './slice-shapes';

/** How far a ledger reaches, or which of three nothings it is. */
export type LedgerReach =
	| { state: 'ok'; first: DateStamp; through: DateStamp; fault: Extract<LedgerFault, 'index-missing'> | null }
	| { state: 'quiet' }
	| { state: 'missing'; fault: Extract<LedgerFault, 'not-packed'> }
	| { state: 'unreachable' };

/** The entries of an index this build acts on, and none for one it will not or that is not there. */
function entriesOf(reading: IndexReading | null): CompactEntry[] {
	return reading === null || 'refused' in reading ? [] : reading.index.entries;
}

/** The oldest and the newest day `ledger` holds, from its three indexes as the page keeps them. */
export async function readReach(keeper: PageKeeper, ledger: LedgerName): Promise<LedgerReach> {
	if (!(LEDGER_NAMES as readonly string[]).includes(ledger)) {
		throw new SliceRequestError(`${JSON.stringify(ledger)} is not a ledger the console may query`);
	}
	const [daily, monthly, yearly] = await Promise.all([
		readIndexFrom(keeper, ledger, 'daily'),
		readIndexFrom(keeper, ledger, 'monthly'),
		readIndexFrom(keeper, ledger, 'yearly')
	]);
	if (daily === null) {
		keeper.warn(faultLine(ledger, { fault: 'not-packed' }));
		return { state: 'missing', fault: 'not-packed' };
	}
	if ('refused' in daily) {
		keeper.warn(`${LOG_PREFIX} ${ledger}: ${explainRefusal('daily', daily.refused)}, so how far it reaches is not known`);
		return { state: 'unreachable' };
	}
	const coarser: [Exclude<Period, 'daily'>, IndexReading | null][] = [
		['monthly', monthly],
		['yearly', yearly]
	];
	let fault: Extract<LedgerFault, 'index-missing'> | null = null;
	for (const [period, reading] of coarser) {
		if (reading !== null) continue;
		keeper.warn(faultLine(ledger, { fault: 'index-missing', period }));
		fault = 'index-missing';
	}
	const days = daily.index.entries;
	const months = entriesOf(monthly);
	const years = entriesOf(yearly);
	const through = newestNamed(days, months, years);
	if (through === null) return { state: 'quiet' };
	const first = firstNamed(days, months, years);
	for (const [period, reading] of coarser) {
		if (reading === null || !('refused' in reading)) continue;
		keeper.warn(
			`${LOG_PREFIX} ${ledger}: ${explainRefusal(period, reading.refused)}, ` +
				`so it reaches back only to ${first}, the oldest day the other indexes name`
		);
	}
	return { state: 'ok', first, through, fault };
}
