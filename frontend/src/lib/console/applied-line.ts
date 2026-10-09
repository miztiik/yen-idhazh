/** Which merge line a build used on a given day: the line its run record names, or the line the rule works out.
 *
 * Every build writes down the line it grouped the day at, and that record is
 * the answer wherever it holds one. Where it holds none - a day built before the
 * record carried the line, or a record that cannot be read - the line is worked
 * out with the console's one copy of the rule a build follows, `applied_line()`
 * in `backend/idhazh/similarity/applied.py`. With the switch on, a build groups
 * at the newest line a fit applied on its own day or in the
 * `applied_lookback_days` days before it. A held day is skipped: its line was
 * inherited from the day before, and no fit chose it. With the switch off, or
 * with no such line, the build groups at the committed floor.
 *
 * The record comes first because the rule can name a line no build used: the
 * nightly fit files its row after most of that day's builds ran, so a site built
 * again before the next build would name that row's line for a day whose builds
 * could not read it. The Judgement route asks once, for the newest published
 * day, and its merge line, verdict split and holdout margin draw that answer.
 *
 * Pure and browser safe: no config read, no disk, no `$lib` alias. The `logic`
 * test group drives it with records and rows the test writes down and no build.
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

/** The line the build on `day` grouped stories at: the line `day`'s run record
 * names, where it holds one, and otherwise the line the rule above works out.
 *
 * `recorded` is what the record of `day` itself holds, from
 * `readRecordedLine` in `$lib/server/recorded-line`, or null.
 */
export function findBuiltLine(
	day: string,
	recorded: number | null,
	rows: readonly FittedLine[],
	knobs: { enabled: boolean; applied_lookback_days: number },
	floor: number
): number {
	return recorded ?? findAppliedLine(day, rows, knobs, floor);
}
