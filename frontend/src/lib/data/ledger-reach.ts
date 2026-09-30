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
 * - `ok`: `through` is the newest day `daily.json` names - the day a slice
 *   returns as its own `through`. `first` is the oldest day any index names, a
 *   month counting from its first day and a year from its 1 January.
 * - `quiet`: `daily.json` names no day yet.
 * - `missing`: there is no `daily.json`, so the ledger is not published.
 * - `unreachable`: `daily.json` is one this build will not act on, or could not
 *   be read, and the console says why. It carries no day, because the reach asks
 *   for none.
 *
 * `monthly.json` and `yearly.json` only move `first` back. When one is not there
 * the ledger has no such files yet. When this build will not act on one, the
 * reach is what the other indexes name, and the console says why.
 *
 * Each index is read the way a slice reads it, by `readIndexFrom()` in
 * `slice-reader.ts`, so a slice and a reach never disagree about what an index
 * says. Imports nothing tied to one environment, so a Node test loads it as it is.
 */

import type { IndexReading, Period } from './compact-index';
import type { PageKeeper } from './page-keeper';
import { explainRefusal, LOG_PREFIX, readIndexFrom } from './slice-reader';
import { LEDGER_NAMES, SliceRequestError, type DateStamp, type LedgerName } from './slice-shapes';

/** How far a ledger reaches, or which of three nothings it is. */
export type LedgerReach =
	| { state: 'ok'; first: DateStamp; through: DateStamp }
	| { state: 'quiet' }
	| { state: 'missing' }
	| { state: 'unreachable' };

/** The first day of what one coarser entry covers: a month's 1st, a year's 1 January. */
const FIRST_DAY: Record<Exclude<Period, 'daily'>, (covers: string) => DateStamp> = {
	monthly: (covers) => `${covers}-01`,
	yearly: (covers) => `${covers}-01-01`
};

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
	if (daily === null) return { state: 'missing' };
	if ('refused' in daily) {
		console.warn(`${LOG_PREFIX} ${ledger}: ${explainRefusal('daily', daily.refused)}, so how far it reaches is not known`);
		return { state: 'unreachable' };
	}
	const days = daily.index.entries;
	if (days.length === 0) return { state: 'quiet' };
	const through = days[days.length - 1].covers;
	let first = days[0].covers;
	const refusals: string[] = [];
	const coarser: [Exclude<Period, 'daily'>, IndexReading | null][] = [
		['monthly', monthly],
		['yearly', yearly]
	];
	for (const [period, reading] of coarser) {
		if (reading === null) continue;
		if ('refused' in reading) {
			refusals.push(explainRefusal(period, reading.refused));
		} else if (reading.index.entries.length > 0) {
			const oldest = FIRST_DAY[period](reading.index.entries[0].covers);
			if (oldest < first) first = oldest;
		}
	}
	for (const why of refusals) {
		console.warn(`${LOG_PREFIX} ${ledger}: ${why}, so it reaches back only to ${first}, the oldest day the other indexes name`);
	}
	return { state: 'ok', first, through };
}
