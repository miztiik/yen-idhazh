/** What the recording itself was doing, said in words.
 *
 * Every figure on this console is read off a ledger, and a ledger has states
 * that are not "a number". Measurement can be switched off; it can be sampled;
 * it can have started after the window opened; it can have run on a day and
 * lost what it wrote; and two instruments that answer about the same day can
 * disagree about whether that day exists at all. None of those is a zero, and
 * printing them as one is how a figure nobody checks gets onto an operator's
 * page.
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
 * looking for `host_fingerprint` does not know that is what he wants.
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
 * measurement (CLAUDE.md Guardrail #10).
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
 *
 * `figures` names what the days before it have none of, because two instruments
 * answer this route and "no server figures" is true of only one of them.
 */
export function recordingStarted(
	firstRecorded: string | null,
	daysBefore: number,
	figures: string = 'server figures'
): string | null {
	if (firstRecorded === null || daysBefore <= 0) return null;
	const days = daysBefore === 1 ? 'The 1 day before it has' : `The ${daysBefore} days before it have`;
	return `Recording started on ${shortDate(firstRecorded)}. ${days} no ${figures}, and the gap in the chart is a gap in the recording, not a quiet day.`;
}

/** A day that published articles and whose instrument kept no row of it. */
export interface LostDay {
	date: string;
	/** Articles the digest for that date carries. Never zero - a day that
	 * published nothing is a quiet day, and a quiet day is not a loss. */
	articles: number;
}

/** Days that ran, published, and whose measurement did not survive.
 *
 * The third state, and the one the console could not say until 2026-09-17.
 * "This day has no rows" is the sentence a quiet day gets, and it was also the
 * sentence 2026-09-16 got - a day that published articles and lost 303 measured
 * rows to a merge collision. The two readings send an operator to opposite
 * places, so they may not share a sentence.
 *
 * The derivation is one join and it carries no judgement: the digest for that
 * date carries articles, so a run worked, and the instrument's own day file
 * holds nothing, so what it measured is gone. A day the instrument never opened
 * a file for is not here - that is a record that had not begun.
 */
export function recordDestroyed(lost: readonly LostDay[]): string | null {
	if (lost.length === 0) return null;
	const articles = lost.reduce((total, day) => total + day.articles, 0);
	const counted = `${articles} ${articles === 1 ? 'article' : 'articles'}`;
	return lost.length === 1
		? `This day published ${counted} and its machine record is missing. The run worked; what it measured about the machine did not survive.`
		: `${lost.length} days published ${counted} between them and their machine record is missing. The runs worked; what they measured about the machine did not survive.`;
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
	recordDestroyed: string | null;
}

export interface RecordingFacts {
	/** The toggle in `config/idhazh.json` that governs this instrument. */
	enabled: boolean;
	/** Its sample rate, 1.0 where it measures everything. Omitted by an
	 * instrument that has no sampling knob, which owes no caveat either way. */
	rate?: number;
	/** The days this instrument recorded, ascending. */
	recorded: readonly string[];
	/** The days the window covers, ascending. Anything before the first recorded
	 * day is a gap in the recording rather than a quiet day. */
	window: readonly string[];
	/** Days another instrument answered for that this one did not. */
	coveredElsewhere?: readonly string[];
	/** Days that published articles and that this instrument kept no row of. */
	lost?: readonly LostDay[];
	/** What the days before the first recorded one have none of. */
	figures?: string;
}

export function recordingNotes(facts: RecordingFacts): RecordingNotes {
	const recorded = [...facts.recorded].sort();
	const first = recorded[0] ?? null;
	const last = recorded.at(-1) ?? null;
	const lost = (facts.lost ?? []).filter((day) => !recorded.includes(day.date));
	const destroyed = new Set(lost.map((day) => day.date));
	// A day whose rows were destroyed is not a day before the recording started.
	// Counted in the gap it would date the instrument's own start to the day after
	// the loss and hand that back as the reason for it, which is the lie this
	// third state exists to stop.
	const before =
		first === null ? 0 : facts.window.filter((date) => date < first && !destroyed.has(date)).length;
	const elsewhere = (facts.coveredElsewhere ?? []).filter((date) => !recorded.includes(date));
	return {
		off: facts.enabled ? null : measurementOff(last),
		sampled: facts.enabled ? sampledAt(facts.rate ?? 1) : null,
		startedMidWindow: recordingStarted(first, before, facts.figures),
		scoresOnly: elsewhere.length === 0 ? null : scoresWithoutCounters(),
		recordDestroyed: recordDestroyed(lost)
	};
}

/** How a build-time read of one packed record went.
 *
 * A console route reads three records from their packed files only, so a record
 * has two states a day file never had. `not-packed` is a record with no packed
 * day at all - a fresh clone, or a packing step not yet run. `unreadable` is a
 * packed day, or the list of them, that did not load; `at` is the first day that
 * failed, or null when the list itself did not load. `read` carries the newest
 * packed day, which is where every panel built on the record stops.
 */
export type RecordRead =
	| { state: 'read'; through: string }
	| { state: 'not-packed' }
	| { state: 'unreadable'; at: string | null };

/** The three records the console reads at build time, as its notes name them. */
export type RecordName = 'article' | 'score' | 'machine';

/** One sentence about one or more records. `unreadable` is a fault; the others are not. */
export interface RecordNote {
	kind: 'not-packed' | 'unreadable' | 'behind';
	records: RecordName[];
	text: string;
}

/** `article`, `article and score`, `article, score and machine`. */
function recordsNamed(records: readonly RecordName[]): string {
	if (records.length < 2) return records.join('');
	return `${records.slice(0, -1).join(', ')} and ${records.at(-1)}`;
}

function recordNoun(records: readonly RecordName[]): string {
	return `${recordsNamed(records)} ${records.length === 1 ? 'record' : 'records'}`;
}

/** What a route says about the records it read, before any panel draws from them.
 *
 * One sentence a record and a state, never one a panel and never a banner: the
 * record is what is late or broken, and every panel built on it is empty for the
 * same reason. `newestDay` is the newest day the site published. A record packed
 * as far as the day before it is as current as packing can be - a day is packed
 * only once it has ended - so it earns no sentence. Further behind than that,
 * the panels stop early for a reason a reader cannot see, so the sentence says
 * where they stop and how many days are not shown yet.
 *
 * The words are fixed, like the other notes in this file; only the names, the
 * dates and the counts inside them are computed.
 */
export function recordNotes(
	reads: readonly { record: RecordName; read: RecordRead }[],
	newestDay: string | null
): RecordNote[] {
	const notes: RecordNote[] = [];
	const notPacked = reads.filter((entry) => entry.read.state === 'not-packed').map((entry) => entry.record);
	if (notPacked.length > 0) {
		notes.push({
			kind: 'not-packed',
			records: notPacked,
			text:
				`The ${recordNoun(notPacked)} ${notPacked.length === 1 ? 'has' : 'have'} not been packed yet, ` +
				`so the panels below that use ${notPacked.length === 1 ? 'it' : 'them'} are empty. ` +
				'That is a step not yet run, not a quiet pipeline.'
		});
	}
	for (const { record, read } of reads) {
		if (read.state !== 'unreadable') continue;
		const what =
			read.at === null
				? `The ${record} record's list of packed days did not load`
				: `The ${record} record's day for ${shortDate(read.at)} did not load`;
		notes.push({
			kind: 'unreadable',
			records: [record],
			text: `${what}, so the panels below that use it are empty. This is a fault to fix, not a quiet day.`
		});
	}
	if (newestDay === null) return notes;
	const behind = new Map<string, RecordName[]>();
	for (const { record, read } of reads) {
		if (read.state !== 'read') continue;
		// Two days short of the newest published day is the first that is late:
		// the day before it may not have ended when the packing step last ran.
		if (daysAfter(read.through, newestDay) < 2) continue;
		behind.set(read.through, [...(behind.get(read.through) ?? []), record]);
	}
	for (const [through, records] of [...behind].sort(([left], [right]) => left.localeCompare(right))) {
		const after = daysAfter(through, newestDay);
		notes.push({
			kind: 'behind',
			records,
			text:
				`The ${recordNoun(records)} ${records.length === 1 ? 'is' : 'are'} packed as far as ` +
				`${shortDate(through)}, so the ${after} ${after === 1 ? 'day' : 'days'} after it ` +
				`${after === 1 ? 'is' : 'are'} not shown yet.`
		});
	}
	return notes;
}

/** Whole UTC days from `from` to `to`, negative when `to` is earlier. */
function daysAfter(from: string, to: string): number {
	return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000);
}
