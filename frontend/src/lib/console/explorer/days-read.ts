/** What a Data explorer answer says about the UTC days it read: how many, from which day to which,
 *  and, for each ledger whose earlier days were cut from the window, the day that ledger starts on.
 *
 * The answer says the usual case once and names each exception by its ledger, so a question over
 * five ledgers that all began years ago prints one sentence, not five. Every date carries its year,
 * because a window can cross one (Reader, 2026-10-07).
 */

// Relative, not `$lib`: the logic suite imports this module in plain Node.
import { shortDate } from '../../format';
import { daysBetween } from '../../data/slice';
import type { CutDays, DateStamp } from '../../data/slice-shapes';

/** The line that says which days an answer read: from `from`, the first day any selected ledger's
 *  answer read, to `to`, the last day any of them read, both counted. An answer with rows read at
 *  least one day, so `from` is never after `to`. */
export function describeDaysRead(from: DateStamp, to: DateStamp): string {
	const days = daysBetween(from, to).length;
	return days === 1 ? `Read from 1 UTC day, ${shortDate(to)}.` : `Read from ${days} UTC days, ${shortDate(from)} to ${shortDate(to)}.`;
}

/** The sentence that names a ledger whose days before `before` were cut from the window. "Not on
 *  this site" stays true whether the ledger began on that day, that day is the 1st of its first
 *  month, packed whole, or this page reads the site alone. When `before` is after `lastDay`, the
 *  window's last day, the ledger gave the answer nothing, and the sentence says so, because an
 *  operator should not have to work that out from two dates. */
export function describeCutDays({ ledger, before }: CutDays, lastDay: DateStamp): string {
	const sentence = `Days of the ${ledger} record before ${shortDate(before)} are not on this site`;
	return before > lastDay ? `${sentence}, so nothing from that record is in this answer.` : `${sentence}.`;
}
