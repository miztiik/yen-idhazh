/** What a data-explorer answer says about the days and files its ledgers are missing.
 *
 * One line a ledger and a state, in the order the ledgers were chosen, lost days
 * first: a day a ledger's packing recorded lost has no record, so nothing from
 * it is in the answer, and a file the packing set aside unread may hold rows the
 * answer lacks. The sentences are the ones a console route prints about its
 * records (`recording.ts`), with the answer as the thing that is short.
 */

// Relative, not `$lib`: the logic suite imports this module in plain Node.
import type { LedgerName, SpanGap } from '../../data/slice-shapes';
import { noRecordSentence, setAsideSentence } from '../recording';

/** One paragraph under an answer: which ledger, which state, and the sentence. */
export type GapLine = { kind: 'lost' | 'set-aside'; ledger: LedgerName; text: string };

export function gapLines(gaps: readonly SpanGap[]): GapLine[] {
	return gaps.flatMap((gap) => {
		const lines: GapLine[] = [];
		if (gap.lostDays.length > 0) {
			lines.push({
				kind: 'lost',
				ledger: gap.ledger,
				text: noRecordSentence(`${gap.ledger} record`, gap.lostDays, (them) => `nothing from ${them} is in this answer`)
			});
		}
		const setAside = setAsideSentence(gap.ledger, gap.ledger, gap.setAside, 'this answer');
		if (setAside !== null) lines.push({ kind: 'set-aside', ledger: gap.ledger, text: setAside });
		return lines;
	});
}
