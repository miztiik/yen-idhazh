/** Which sources are counting down to retiring themselves, and what does each row of the countdown draw?
 *
 * `/console/voices/` reads it once, at build time, from the source census the run
 * published. It is kept apart from the route so a test can hand it a census it
 * wrote and read every figure a row carries.
 */

import { percentOf } from '../charts/rank';
import { shareMarks, type TargetMarks } from '../charts/targetbar';
import { shortDate } from '../format';
import type { DayYield, SourceHealthView } from './payload';

/** What one square on a reliability strip says. Colour is never the only signal:
 * each of these has a sentence on the square's own label. */
export type YieldDay = 'at-or-above' | 'under' | 'nothing';

/** One day of one source's share, as a square. */
export interface YieldSquare {
	date: string;
	state: YieldDay;
	label: string;
}

/** One source counting down to retiring itself, as the panel draws it. */
export interface Countdown {
	sourceId: string;
	title: string;
	/** The trailing share, or null where the source decided nothing at all. */
	share: number | null;
	publications: number;
	decisions: number;
	opportunities: number;
	/** The bar. Sized here rather than in the browser, so it is on the page
	 * before any script runs - the same trade the feed-failure bars take. */
	marks: TargetMarks;
	daysUnder: number;
	retiresOn: string | null;
	/** Days left on a live dwell, or null where none is running. Derived from the
	 * run's own count and never from a clock. */
	daysLeft: number | null;
	retired: boolean;
	/** True while the source has not met both evidence floors. It is still drawn,
	 * in a block below the ranked rows: hiding it would hide the shape. */
	unjudged: boolean;
	squares: YieldSquare[];
}

/** The reliability strip, as `/console/voices/` reads it. */
export interface Retiring {
	alarmPoint: number;
	minDecisions: number;
	minCompleteDays: number;
	completeDates: number;
	dwellDays: number;
	autoRetire: boolean;
	dates: string[];
	/** Ranked nearest-to-retirement first, then by how far under the mark. */
	rows: Countdown[];
	/** Under one or both evidence floors, so no countdown may be drawn. Capped the
	 * same way the ranked rows are: the block exists so an operator can see the
	 * shape of a source nobody may judge yet, and on a shallow record that is
	 * every source we have - 156 of them on this checkout, which is a wall rather
	 * than a panel. Closest to clearing its floors first, because a source with no
	 * decisions at all has no shape to look at: its strip is empty by definition,
	 * so ten of those would be ten rows saying nothing. */
	unjudged: Countdown[];
	/** Unjudged rows the cap dropped. */
	unjudgedHidden: number;
	/** How many judged sources are at or above the mark today. */
	clear: number;
	/** Rows the cap dropped. A ranking is read from the top and its tail is a
	 * number, never another page of rows. */
	hidden: number;
	generatedAt: string;
	runId: string;
}

/** The share a source turned into a story, or null where it decided nothing.
 *
 * `null` rather than 0 for a source nobody has asked: 0 of 0 is not zero, and a
 * page that prints 0 percent for it makes an accusation the record cannot
 * support. The same rule `SourceHealthRow.source_yield` applies in Python.
 */
function shareOf(publications: number, decisions: number): number | null {
	return decisions > 0 ? publications / decisions : null;
}

/** One day's square, with the sentence that says what it means without colour. */
function squareFor(day: DayYield, alarmPoint: number): YieldSquare {
	const decisions = day.publications + day.source_failures;
	const share = shareOf(day.publications, decisions);
	if (share === null) {
		return {
			date: day.date,
			state: 'nothing',
			label: `${shortDate(day.date)}: it decided nothing, so there is no share.`
		};
	}
	const state: YieldDay = share >= alarmPoint ? 'at-or-above' : 'under';
	const wording = state === 'under' ? 'under the mark' : 'at or above the mark';
	return {
		date: day.date,
		state,
		label: `${shortDate(day.date)}: ${day.publications} of ${decisions} read, ${percentOf(
			share
		)} - ${wording}.`
	};
}

/** Every source's countdown, ranked nearest to retiring first.
 *
 * **Nothing here re-derives the dwell.** The run counted the unbroken run of
 * under-the-mark days and named the day it completes, over the same evidence
 * this strip draws, so a person watching `retires in 2 days` sees the number
 * that will fire rather than a second opinion about it.
 *
 * The bar's track is the full 0 to 100 percent share and the marker sits at the
 * alarm point on every row. A per-row maximum would put the marker at a
 * different x on each row, and the whole reason to stack these is that a column
 * means the same thing all the way down.
 */
export function retiring(view: SourceHealthView | null, rows: number): Retiring | null {
	if (view === null) return null;
	const alarmPoint = view.yield_alarm_point ?? 0.5;
	const minDecisions = view.yield_alarm_min_decisions ?? 30;
	const dwellDays = view.dwell_days ?? 14;
	const dates = view.dwell_dates ?? [];
	const deepEnough = view.complete_dates >= view.min_complete_days;

	const drawn = view.sources
		.filter((row) => !row.retired || row.retired_on !== null)
		.map((row): Countdown => {
			const decisions = row.publications + row.source_failures;
			const share = shareOf(row.publications, decisions);
			const daysUnder = row.days_under_the_mark ?? 0;
			const retiresOn = row.retires_on ?? null;
			return {
				sourceId: row.source_id,
				title: row.title,
				share,
				publications: row.publications,
				decisions,
				opportunities: row.opportunities,
				marks: shareMarks(share ?? 0, alarmPoint),
				daysUnder,
				retiresOn,
				daysLeft: retiresOn === null ? null : Math.max(dwellDays - daysUnder, 0),
				retired: row.retired,
				unjudged: !deepEnough || decisions < minDecisions,
				squares: (row.recent_days ?? []).map((day) => squareFor(day, alarmPoint))
			};
		});

	const judged = drawn.filter((row) => !row.unjudged);
	const under = judged
		.filter((row) => row.daysUnder > 0 || row.retired)
		.sort(
			(a, b) =>
				(a.daysLeft ?? 0) - (b.daysLeft ?? 0) ||
				(a.share ?? 1) - (b.share ?? 1) ||
				a.sourceId.localeCompare(b.sourceId)
		);
	const waiting = drawn
		.filter((row) => row.unjudged)
		.sort((a, b) => b.decisions - a.decisions || a.sourceId.localeCompare(b.sourceId));
	return {
		alarmPoint,
		minDecisions,
		minCompleteDays: view.min_complete_days,
		completeDates: view.complete_dates,
		dwellDays,
		autoRetire: view.auto_retire ?? false,
		dates,
		rows: under.slice(0, rows),
		unjudged: waiting.slice(0, rows),
		unjudgedHidden: Math.max(waiting.length - rows, 0),
		clear: judged.length - under.length,
		hidden: Math.max(under.length - rows, 0),
		generatedAt: view.generated_at,
		runId: view.run_id
	};
}
