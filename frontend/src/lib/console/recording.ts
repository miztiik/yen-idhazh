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
 * The strings are fixed - the owner wrote the first of them on 2026-08-30 - and
 * only the dates, counts and names inside them are computed. **A date that is
 * not true is worse than no date**, so every one of them is derived from the
 * ledger that is missing rather than typed here.
 *
 * Pure and dependency-free apart from the date formatter, so the browser suite
 * drives every state without a page. The names of a ledger's missing-file faults
 * are types from the query door, and nothing of the door runs here.
 */

import type { LedgerFault, LedgerName, SetAsideFiles } from '../data/ledger';
import { dayMonth, shortDate } from '../format';

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
	/** Days the instrument's own record has no record for, because its packing
	 * recorded them lost. Unlike `lost`, nothing else is joined to know it: the
	 * record's index says so. The route's record notes name them. */
	daysWithNoRecord?: readonly string[];
	/** What the days before the first recorded one have none of. */
	figures?: string;
}

export function recordingNotes(facts: RecordingFacts): RecordingNotes {
	const recorded = [...facts.recorded].sort();
	const last = recorded.at(-1) ?? null;
	const lost = (facts.lost ?? []).filter((day) => !recorded.includes(day.date));
	// The instrument started on the first day it is known to have run: a day it
	// recorded, or a day whose record did not survive, destroyed or recorded lost.
	// Dated from the recorded days alone, a loss before them would date the
	// instrument's start to the day after the loss and count the loss as a day
	// before it, which is the lie these states exist to stop.
	const ran = [...recorded, ...lost.map((day) => day.date), ...(facts.daysWithNoRecord ?? [])].sort();
	const first = ran[0] ?? null;
	const before = first === null ? 0 : facts.window.filter((date) => date < first).length;
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
 * day at all - a fresh clone, or a packing step not yet run - and is the query
 * door's fault of that name. `unreadable` is a packed day, or the list of them,
 * that did not load; `at` is the first day that failed, or null when the list
 * itself did not load, and `fault` names the missing file behind it as the door
 * does, or is null for another cause. `read` carries the newest packed day,
 * which is where every panel built on the record stops; `lostDays`, the days in
 * the read the record's index records lost, ascending; and `setAside`, the files
 * the packing of the read's periods set aside unread.
 */
export type RecordRead =
	| { state: 'read'; through: string; lostDays: string[]; setAside: SetAsideFiles }
	| { state: Extract<LedgerFault, 'not-packed'> }
	| { state: 'unreadable'; at: string | null; fault: Exclude<LedgerFault, 'not-packed'> | null };

/** The three records the console reads at build time, as its notes name them. */
export type RecordName = 'article' | 'score' | 'machine';

/** The ledger each record is read from, so a note can send a person to its files. */
const RECORD_LEDGERS: Readonly<Record<RecordName, LedgerName>> = {
	article: 'item-health',
	score: 'summary-quality-evals',
	machine: 'host-fingerprint'
};

/** One sentence about one or more records. `unreadable` is a fault; the others are not. */
export interface RecordNote {
	kind: 'not-packed' | 'unreadable' | 'behind' | 'lost' | 'set-aside';
	records: RecordName[];
	text: string;
}

/** `a`, `a and b`, `a, b and c`. */
function englishList(items: readonly string[]): string {
	if (items.length < 2) return items.join('');
	return `${items.slice(0, -1).join(', ')} and ${items.at(-1)}`;
}

function recordNoun(records: readonly RecordName[]): string {
	return `${englishList(records)} ${records.length === 1 ? 'record' : 'records'}`;
}

/** UTC days as English, consecutive days joined into one run the way a span is
 * written: `19 Aug 2026`, `14 Aug to 16 Aug 2026`, `14 Aug to 16 Aug and 19 Aug
 * 2026`. The year is printed once when every day shares it. */
function namedDays(days: readonly string[]): string {
	const runs: [string, string][] = [];
	for (const day of [...new Set(days)].sort()) {
		const run = runs.at(-1);
		if (run !== undefined && daysAfter(run[1], day) === 1) run[1] = day;
		else runs.push([day, day]);
	}
	const oneYear = new Set(days.map((day) => day.slice(0, 4))).size === 1;
	const newest = runs.at(-1)?.[1];
	const named = (day: string): string => (oneYear && day !== newest ? dayMonth(day) : shortDate(day));
	return englishList(runs.map(([first, end]) => (first === end ? named(first) : `${named(first)} to ${named(end)}`)));
}

/** Days a record has no record for, because its packing recorded them lost.
 *
 * Not a quiet day and not a fault to fix: what was written that day could not
 * be recovered, so the packing wrote the day down as lost and carried on. The
 * sentence says it could not be recovered, so an operator does not read it as
 * one more fault to fix. `subject` names the record the way the surface does -
 * `machine record` on a route, `host-fingerprint record` in the explorer - and
 * `missingFrom` says what the reader of that surface does not get, for
 * `that day` or `those days`.
 */
export function noRecordSentence(
	subject: string,
	days: readonly string[],
	missingFrom: (them: 'that day' | 'those days') => string
): string {
	const them = new Set(days).size === 1 ? 'that day' : 'those days';
	return (
		`There is no ${subject} for ${namedDays(days)}, so ${missingFrom(them)}. ` +
		`The record for ${them} was lost and could not be recovered; ` +
		`${them === 'that day' ? 'it was not a quiet day' : 'they were not quiet days'}.`
	);
}

/** Where a person reads the files a ledger's packing set aside: the packing
 * moves a file it cannot read there and never deletes it, and no step reads it. */
function setAsideFolder(ledger: LedgerName): string {
	return `state/raw/${ledger}/set-aside/`;
}

/** Files a ledger's packing set aside unread, and where a person reads them; null when none were.
 *
 * The count belongs to the packed periods, never to days: a month counts every
 * file it set aside, so the sentence says "this data" rather than naming days.
 * The folder is the reader's next step, so it is printed whole, and never last
 * in a sentence, where the full stop would read as part of it. `subject` and
 * `missingFrom` name the record and what may be short, as in `noRecordSentence`.
 */
export function setAsideSentence(
	subject: string,
	ledger: LedgerName,
	setAside: SetAsideFiles,
	missingFrom: string
): string | null {
	const files = Object.values(setAside).reduce((total, count) => total + count, 0);
	if (files === 0) return null;
	const one = files === 1;
	return (
		`${files} ${subject} ${one ? 'file was' : 'files were'} set aside unread when this data was packed, ` +
		`so ${missingFrom} may be missing ${one ? 'its' : 'their'} rows. ` +
		`${one ? 'It waits' : 'They wait'} in ${setAsideFolder(ledger)} for a person to read.`
	);
}

/** The sentence for a record that did not load. A missing file and a missing
 * day send an operator to different fixes, so each has its own words; every
 * other cause of a day that failed shares one. */
function unreadableText(record: RecordName, read: Extract<RecordRead, { state: 'unreadable' }>): string {
	const after = 'has anything to show. This is a fault to fix, not a quiet day.';
	if (read.at === null) {
		return `The ${record} record's list of packed days did not load, so nothing below that uses it ${after}`;
	}
	const day = shortDate(read.at);
	if (read.fault === 'file-missing') {
		return `The ${record} record lists a packed file for ${day} that is not there, so nothing below that uses this record ${after}`;
	}
	if (read.fault === 'day-missing') {
		return `The ${record} record is missing ${day}, a day between packed days, so nothing below that uses this record ${after}`;
	}
	return `The ${record} record's day for ${day} did not load, so nothing below that uses this record ${after}`;
}

/** What a route says about the records it read, before any panel draws from them.
 *
 * One sentence a record and a state, never one a panel and never a banner: the
 * record is what is late, broken or short, and every panel built on it is empty,
 * stops early or misses the same rows for the same reason. `newestDay` is the
 * newest day the site published. A record packed as far as the day before it is
 * as current as packing can be - a day is packed only once it has ended - so it
 * earns no sentence. Further behind than that, the panels stop early for a
 * reason a reader cannot see, so the sentence says where they stop and how many
 * days are not shown yet. A record read in full can still be short: a day its
 * packing recorded lost has no record, and a file it set aside unread holds rows
 * no panel draws, so each says so, one record at a time and lost days first.
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
				`so nothing below that uses ${notPacked.length === 1 ? 'it' : 'them'} has anything to show. ` +
				'That is a step not yet run, not a quiet pipeline.'
		});
	}
	for (const { record, read } of reads) {
		if (read.state !== 'unreadable') continue;
		notes.push({ kind: 'unreadable', records: [record], text: unreadableText(record, read) });
	}
	if (newestDay !== null) notes.push(...behindNotes(reads, newestDay));
	for (const { record, read } of reads) {
		if (read.state !== 'read') continue;
		const subject = `${record} record`;
		if (read.lostDays.length > 0) {
			notes.push({
				kind: 'lost',
				records: [record],
				text: noRecordSentence(subject, read.lostDays, (them) => `nothing below that uses this record shows ${them}`)
			});
		}
		const setAside = setAsideSentence(subject, RECORD_LEDGERS[record], read.setAside, 'anything below that uses this record');
		if (setAside !== null) notes.push({ kind: 'set-aside', records: [record], text: setAside });
	}
	return notes;
}

/** The records packed short of the day before `newestDay`, one sentence for each day they stop on. */
function behindNotes(reads: readonly { record: RecordName; read: RecordRead }[], newestDay: string): RecordNote[] {
	const behind = new Map<string, RecordName[]>();
	for (const { record, read } of reads) {
		if (read.state !== 'read') continue;
		// Two days short of the newest published day is the first that is late:
		// the day before it may not have ended when the packing step last ran.
		if (daysAfter(read.through, newestDay) < 2) continue;
		behind.set(read.through, [...(behind.get(read.through) ?? []), record]);
	}
	return [...behind]
		.sort(([left], [right]) => left.localeCompare(right))
		.map(([through, records]): RecordNote => {
			const after = daysAfter(through, newestDay);
			return {
				kind: 'behind',
				records,
				text:
					`The ${recordNoun(records)} ${records.length === 1 ? 'is' : 'are'} packed as far as ` +
					`${shortDate(through)}, so the ${after} ${after === 1 ? 'day' : 'days'} after it ` +
					`${after === 1 ? 'is' : 'are'} not shown yet.`
			};
		});
}

/** Whole UTC days from `from` to `to`, negative when `to` is earlier. */
function daysAfter(from: string, to: string): number {
	return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000);
}
