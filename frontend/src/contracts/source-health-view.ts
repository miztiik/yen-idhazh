// Generated from `backend/idhazh/contracts/source_health_view.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * One source, one complete day: what it offered and what it read.
 *
 * The strip on `/console/voices/` needs a time axis and the totals beside it
 * cannot supply one - fourteen days into a countdown and a dip yesterday land
 * in the same number. So the shares are published a day at a time and the page
 * draws a square each.
 *
 * The two counts rather than the share, because a share with no denominator
 * cannot tell a bad day from a quiet one. 0 of 0 is a day the source offered
 * nothing, which the page draws as no record rather than as a failure.
 */
export interface DayYield {
	date: string;

	/** Distinct addresses this source had planned on this date. */
	opportunities: number;

	/** Those that reached publish on any attempt of this date. */
	publications: number;

	/** Those lost to a failure this source owns, on this date. */
	source_failures: number;
}

/**
 * Whether the address is answering now, by the rule the run rests on.
 *
 * Derived from `discover.streak` and `discover.resting` over the settled
 * ledger, which is the same loop the quarantine uses. Two reducers would be
 * two answers, and a page that disagrees with the run that produced it is
 * worse than a page with no answer.
 */
export const SOURCE_AVAILABILITY = ['answering', 'failing', 'resting', 'never_asked'] as const;

export type SourceAvailability = (typeof SOURCE_AVAILABILITY)[number];

/**
 * One configured address, as a page is allowed to read it.
 *
 * A nested shape rather than a contract of its own: nothing writes a row on
 * its own and nothing reads one out of context, so it travels inside the view
 * and is inlined under that schema's `$defs`.
 */
export interface SourceHealthRow {
	source_id: string;

	title: string;

	vertical: string;

	permission: SourcePermission;

	availability: SourceAvailability;

	/** Has a run stopped asking this address for good? True only when the retirement ledger holds its endpoint. The console renders this decision and never re-derives it. */
	retired: boolean;

	/** The day the retirement was filed. Absent unless `retired`. */
	retired_on?: string | null;

	/** Distinct addresses this source had planned on a complete date, inside the window. One address on one date counts once however many runs of that date attempted it. */
	opportunities: number;

	/** Those addresses that reached publish on any attempt of their date. Never more than `opportunities`, which is enforced rather than assumed. */
	publications: number;

	/** Opportunities lost to a failure this source owns - a refusal, a bad status, no text, a paywall. Reported beside the ratio and never subtracted from it, so one lost article is counted once. */
	source_failures: number;

	/** The multiplier the ranker applied to this feed's authority on this run, from `ledger.feed_reliability` over the trailing `collect.reliability_window_days`. Published rather than recomputed by a page: a console figure that is a second derivation of a ranking factor is two verdicts, and the day they disagree neither is trustworthy. */
	reliability: number;

	/** Evidence-bearing reads the factor was reduced over - every read that did not preserve the streak, so a rest and a robots answer are set aside. Zero means the factor is the 1.0 a feed with no evidence scores and not a record of perfect answering, which is the difference a page draws as a dash rather than a full bar. */
	reliability_reads: number;

	/** This source's share a day at a time over the dwell window, oldest first, on the view's own `dwell_dates` axis. Every date on that axis is present even where the source offered nothing, so every row's strip has the same squares in the same places and one date axis serves the whole list. Empty where the record holds no complete date yet. */
	recent_days?: DayYield[];

	/** The UNBROKEN run of days at the newest end of `recent_days` whose share was under `collect.source_yield_alarm_point`. This is the dwell, and the run is what `collect.source_quality_dwell_days` is counted against: one day back at or above the mark resets it to zero, so a source that recovered keeps its place. Computed here rather than in the page - a countdown a console re-derives is a second verdict, and the day the two disagree neither is trustworthy. */
	days_under_the_mark?: number;

	/** The day the dwell completes if the source stays under the mark, derived from the newest date on the axis and NEVER from a wall clock - a page re-opened at midnight must not move a date the run decided. Absent when no dwell is running, when the source is already retired, or when the evidence floors are not met. */
	retires_on?: string | null;
}

/**
 * What the site's own `robots.txt` said about this address.
 *
 * Four members where the ledger's `RobotsOutcome` has three, and the fourth is
 * the one that matters: a row written before the column existed carries an
 * empty cell, and that is not the same fact as `allowed`. Reading absence as a
 * refusal would take every desk under its feed floor on the day the column
 * landed; reading it as permission would claim a check nobody ran.
 */
export const SOURCE_PERMISSION = ['allowed', 'denied', 'unreachable', 'unrecorded'] as const;

export type SourcePermission = (typeof SOURCE_PERMISSION)[number];

/** Every address the run may ask, and what the committed record says about it. */
export interface SourceHealthView {
	version?: string;

	generated_at: string;

	run_id: string;

	/** The one line the page opens with: the worst figure on it against that figure's own bound, or a count of the figures the record cannot compute yet, or a sentence saying nothing here is outside its bound. Computed here rather than in the page, so the sentence and the table below it are reduced from the same rows. Never absent and never empty - a page whose summary line can vanish teaches an operator to scroll past it. */
	headline_sentence: string;

	/** `collect.reliability_floor` - the furthest down the ranker will discount a feed, and the mark a page puts on the bar it draws each factor in. Carried because the bound and the figure must come from one run: a page holding a published factor to a floor it read somewhere else is drawing two runs on one bar. */
	reliability_floor: number;

	/** `collect.reliability_window_days` - how far back the factor was reduced. Published so the page can say what the number covers; a bare share with no period is not a measurement. */
	reliability_window_days: number;

	/** `collect.source_yield_min_complete_days`. It is both how far back the publishing record reads and how much of that record is enough to read as a rate, because there is one question here - how many complete days does a yield judgement need - and a second number would be a second answer to it. */
	min_complete_days: number;

	/** Complete UTC dates the census actually covered, capped at `min_complete_days`. Today is never one of them: a run is still going, so its date has opportunities nobody has attempted yet. */
	complete_dates: number;

	/** Is the record deep enough to read as a rate? Carried rather than left to the page, so the page and this file cannot answer it differently. */
	yield_readable: boolean;

	/** Oldest complete date in the census. Absent when there is none. */
	first_date?: string | null;

	/** Newest complete date in the census. Absent when there is none. */
	last_date?: string | null;

	/** `collect.source_yield_alarm_point` - the share a source has to stay at or above. Carried for the reason `reliability_floor` is: the bound and the figure must come from one run, or the page holds a published share to a mark it read somewhere else. */
	yield_alarm_point?: number;

	/** `collect.source_yield_alarm_min_decisions` - decisions a source needs before its share may be judged at all. The page prints it beside a source that has not reached it, so a dash says what is missing rather than only that something is. */
	yield_alarm_min_decisions?: number;

	/** `collect.source_quality_dwell_days` - running days under the mark that complete a retirement. It is also how many dates `dwell_dates` carries. */
	dwell_days?: number;

	/** `collect.source_quality_auto_retire`. False means a completed dwell files nothing and this view is watching only, which the page says in words - a countdown that retires nothing and does not admit it is a lie told in colour. */
	auto_retire?: boolean;

	/** The dates every row's `recent_days` runs over, oldest first: the newest `dwell_days` complete dates the census read. One axis for the whole list, so a square in the same column on two rows is the same day - which is the only thing that makes a stack of strips readable. */
	dwell_dates?: string[];

	/** One row per address a curator left active, ordered by source id. Every row carries exactly one permission state, so the states sum to the number of addresses by construction rather than by a page adding them up. */
	sources: SourceHealthRow[];
}
