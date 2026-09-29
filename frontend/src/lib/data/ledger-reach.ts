/**
 * How far does a ledger reach, read from its two indexes and nothing else?
 *
 * A console route anchors its span on the data rather than on the clock, so it
 * needs the oldest and the newest day a ledger holds before it asks for a slice.
 * `ledgerReach()` in `ledger.ts` answers with this module. It reads `daily.json`
 * and `monthly.json` at the same time, through the page keeper, so a slice asked
 * afterwards fetches neither again; and it starts no engine, because an index is
 * JSON.
 *
 * - `ok`: `through` is the newest day `daily.json` names - the day a slice
 *   returns as its own `through`. `first` is the oldest day either index names,
 *   a month counting from its first day.
 * - `quiet`: `daily.json` names no day yet.
 * - `missing`: there is no `daily.json`, so the ledger is not published.
 * - `unreachable`: `daily.json` is one this build will not act on, or could not
 *   be read, and the console says why. It carries no day, because the reach asks
 *   for none.
 *
 * `monthly.json` only moves `first` back. When it is not there the ledger has no
 * months yet. When this build will not act on it, the reach is the days
 * `daily.json` names, and the console says why.
 *
 * Each index is read the way a slice reads it, by `readIndexFrom()` in
 * `slice-reader.ts`, so a slice and a reach never disagree about what an index
 * says. Imports nothing tied to one environment, so a Node test loads it as it is.
 */

import type { PageKeeper } from './page-keeper';
import { explainRefusal, LOG_PREFIX, readIndexFrom } from './slice-reader';
import { LEDGER_NAMES, SliceRequestError, type DateStamp, type LedgerName } from './slice-shapes';

/** How far a ledger reaches, or which of three nothings it is. */
export type LedgerReach =
	| { state: 'ok'; first: DateStamp; through: DateStamp }
	| { state: 'quiet' }
	| { state: 'missing' }
	| { state: 'unreachable' };

/** The oldest and the newest day `ledger` holds, from its two indexes as the page keeps them. */
export async function readReach(keeper: PageKeeper, ledger: LedgerName): Promise<LedgerReach> {
	if (!(LEDGER_NAMES as readonly string[]).includes(ledger)) {
		throw new SliceRequestError(`${JSON.stringify(ledger)} is not a ledger the console may query`);
	}
	const [daily, monthly] = await Promise.all([
		readIndexFrom(keeper, ledger, 'daily'),
		readIndexFrom(keeper, ledger, 'monthly')
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
	if (monthly !== null && 'refused' in monthly) {
		console.warn(
			`${LOG_PREFIX} ${ledger}: ${explainRefusal('monthly', monthly.refused)}, ` +
				`so it reaches back only to ${first}, the oldest day daily.json names`
		);
	} else if (monthly !== null && monthly.index.entries.length > 0) {
		const oldestMonth = `${monthly.index.entries[0].covers}-01`;
		if (oldestMonth < first) first = oldestMonth;
	}
	return { state: 'ok', first, through };
}
