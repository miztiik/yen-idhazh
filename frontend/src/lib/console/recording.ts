/** What the recording itself was doing, said in words.
 *
 * Every figure on this console is read off a ledger, and a ledger has states
 * that are not "a number". Measurement can be switched off; it can be sampled;
 * it can have started after the window opened; and two instruments that answer
 * about the same day can disagree about whether that day exists at all. None of
 * those is a zero, and printing them as one is how a figure nobody checks gets
 * onto an operator's page.
 *
 * **The empty state is the panel, not a replacement for it.** Nothing here
 * removes a heading or the sentence under it. Each function returns the one
 * line that goes where the figure would have been, so an operator learns the
 * measurement exists and learns why it has no answer today.
 *
 * The strings are fixed - the owner wrote them, on 2026-08-30 - and only the
 * dates and counts inside them are computed. **A date that is not true is worse
 * than no date**, so every one of them is derived from the ledger that is
 * missing rather than typed here.
 *
 * Pure and dependency-free apart from the date formatter, so the browser suite
 * drives every state without a page.
 */

import { shortDate } from '../format';

/** A measurement that was switched off, and when it last recorded anything.
 *
 * It names `config/idhazh.json` and never the knob inside it: a term from a
 * subsystem is not a term for a user (CLAUDE.md section 0b), and an operator
 * looking for `runtime_counters_scrape` does not know that is what he wants.
 */
export function measurementOff(lastRecorded: string | null): string {
	const since =
		lastRecorded === null
			? 'Nothing has been recorded at all'
			: `Nothing has been recorded since ${shortDate(lastRecorded)}, so the figures below stop on that day`;
	return `Measurement is off. ${since}. Turn it back on in config/idhazh.json.`;
}

/** A rate below 1.0, as one run in N.
 *
 * Null at 1.0, because a figure that measured everything owes no caveat and a
 * caveat printed on every panel is one nobody reads. The sentence refuses to
 * scale the figures up, which is the whole point: a sampled count is a count of
 * what we measured, and multiplying it by four would publish an estimate as a
 * measurement (CLAUDE.md Rule #10).
 */
export function sampledAt(rate: number): string | null {
	if (!Number.isFinite(rate) || rate >= 1 || rate <= 0) return null;
	const oneIn = 1 / rate;
	// A clean fraction reads as one run in four; anything else reads as a
	// percentage, because "1 run in 2.7" is not a thing that happened.
	const measured =
		Math.abs(oneIn - Math.round(oneIn)) < 1e-9
			? `Measured on 1 run in ${Math.round(oneIn)}`
			: `Measured on ${Math.round(rate * 100)}% of runs`;
	return `${measured}. These figures count the runs we measured and are not scaled up to stand for the rest.`;
}

/** The day the machine was timed and nothing scored what it wrote. */
export function countersWithoutScores(): string {
	return 'The machine ran and we timed it. Nothing scored the summaries, so this day has no quality figure.';
}

/** The day the summaries were scored and the server wrote no counters.
 *
 * The state most committed days are in, and the reason the sentence names where
 * the speed figures come from instead: the summariser's own clock and the
 * server's own clock are two instruments, and a page that let a reader think it
 * had the second one would be quoting the wrong denominator.
 */
export function scoresWithoutCounters(): string {
	return "The summaries were scored, but the server's own counters were not written down for this day. The speed figures here come from the summariser, not the server.";
}

/** Recording that began after the window opened.
 *
 * A gap at the left of a chart reads as quiet days. It is not: it is days the
 * instrument did not exist for, and the difference decides whether an operator
 * goes looking for a broken pipeline.
 */
export function recordingStarted(firstRecorded: string | null, daysBefore: number): string | null {
	if (firstRecorded === null || daysBefore <= 0) return null;
	const days = daysBefore === 1 ? 'The 1 day before it has' : `The ${daysBefore} days before it have`;
	return `Recording started on ${shortDate(firstRecorded)}. ${days} no server figures, and the gap in the chart is a gap in the recording, not a quiet day.`;
}

/** Every state a panel governed by one instrument can be in.
 *
 * Null where the state does not apply, so a panel renders whichever of them is
 * not null and prints nothing where the recording behaved. Three panels can be
 * in three different states on one day, which is why this is per instrument and
 * never one banner across the page.
 */
export interface RecordingNotes {
	off: string | null;
	sampled: string | null;
	startedMidWindow: string | null;
	scoresOnly: string | null;
}

export interface RecordingFacts {
	/** The toggle in `config/idhazh.json` that governs this instrument. */
	enabled: boolean;
	/** Its sample rate, 1.0 where it measures everything. */
	rate: number;
	/** The days this instrument recorded, ascending. */
	recorded: readonly string[];
	/** The days the window covers, ascending. Anything before the first recorded
	 * day is a gap in the recording rather than a quiet day. */
	window: readonly string[];
	/** Days another instrument answered for that this one did not. */
	coveredElsewhere?: readonly string[];
}

export function recordingNotes(facts: RecordingFacts): RecordingNotes {
	const recorded = [...facts.recorded].sort();
	const first = recorded[0] ?? null;
	const last = recorded.at(-1) ?? null;
	const before = first === null ? 0 : facts.window.filter((date) => date < first).length;
	const elsewhere = (facts.coveredElsewhere ?? []).filter((date) => !recorded.includes(date));
	return {
		off: facts.enabled ? null : measurementOff(last),
		sampled: facts.enabled ? sampledAt(facts.rate) : null,
		startedMidWindow: recordingStarted(first, before),
		scoresOnly: elsewhere.length === 0 ? null : scoresWithoutCounters()
	};
}
