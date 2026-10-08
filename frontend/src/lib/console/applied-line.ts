/** Which merge line a build used on a given day: a line a fit applied, or the committed floor.
 *
 * The console's one copy of the rule a build follows, `applied_line()` in
 * `backend/idhazh/similarity/applied.py`. With the switch on, a build groups at
 * the newest line a fit applied on its own day or in the `applied_lookback_days`
 * days before it. A held day is skipped: its line was inherited from the day
 * before, and no fit chose it. With the switch off, or with no such line, the
 * build groups at the committed floor. Judgement's merge line asks about its
 * window's last day, and its verdict split and holdout margin about the newest
 * published day, so the three panels read one rule.
 *
 * Pure and browser safe: no config read, no disk, no `$lib` alias. The `logic`
 * test group drives it with rows the test writes down and no build.
 */

import { windowOfDays } from '../charts/viewport';

/** The three fields of a fitted row the rule reads. */
export interface FittedLine {
	date: string;
	applied: number;
	/** `none` where a fit ran that day. */
	heldReason: string;
}

/** The line a build on `day` grouped stories at.
 *
 * `rows` are oldest first, one a date: its newest run, the run the console
 * draws. A build reads its own day and the `applied_lookback_days` before it,
 * both ends included, so a lookback of 7 reads 8 days.
 */
export function findAppliedLine(
	day: string,
	rows: readonly FittedLine[],
	knobs: { enabled: boolean; applied_lookback_days: number },
	floor: number
): number {
	if (!knobs.enabled) return floor;
	const read = windowOfDays(day, knobs.applied_lookback_days + 1, 'right');
	const fitted = rows.findLast(
		(row) => row.heldReason === 'none' && row.date >= read.start && row.date <= read.end
	);
	return fitted?.applied ?? floor;
}
