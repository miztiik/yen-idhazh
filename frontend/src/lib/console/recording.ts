/** What the recording itself was doing, said in words.
 *
 * Every figure on this console is read off a ledger, and a ledger has states
 * that are not "a number". Measurement can be switched off; it can be sampled;
 * it can have started after the window opened, or held its last rows before it;
 * it can have run on a day and lost what it wrote; and two instruments that
 * answer about the same day can disagree about whether that day exists at all.
 * None of those is a zero, and printing them as one is how a figure nobody
 * checks gets onto an operator's page.
 *
 * **The empty state is the panel, not a replacement for it.** Nothing here
 * removes a heading or the sentence under it. Each function returns the one
 * line that goes where the figure would have been, so an operator learns the
 * measurement exists and learns why it has no answer today.
 *
 * The strings are fixed - Susan chose the first of them on 2026-08-30, Reader
 * and Jony chose the words of the "Measurement is off" line on 2026-10-07, and
 * Reader those of the "Recording started" line the same day - and only the
 * dates, counts and names inside them are computed.
 * **A date that is not true is worse than no date**, so every one of them is
 * derived from the ledger that is missing rather than typed here.
 *
 * Pure and dependency-free apart from the date formatter and the door's own
 * calendar of what an index entry covers, so the browser suite drives every
 * state without a page. The names of a ledger's missing-file faults are types
 * from the query door, and no read of the door runs here.
 */

import type { LedgerFault, LedgerName, SetAsideFiles } from '../data/ledger';
import { coveredDays, type HeldPeriod } from '../data/slice';
import { dayMonth, MONTHS, shortDate } from '../format';

/** What the "Measurement is off" line is worked out from, for one window. */
export interface MeasurementFacts {
	/** The toggle in `config/idhazh.json` that governs this instrument. */
	enabled: boolean;
	/** The days this instrument recorded, ascending. Only those inside `open` can be named. */
	recorded: readonly string[];
	/** How the read of the record behind this instrument went. Its index says
	 * whether the record ever held a row, and where its rows stop. */
	read: RecordRead;
	/** The window the line is printed over. */
	open: OfferedWindow;
	/** Every window the control offers, so the line can name one that reaches back
	 * to the last recorded day. */
	offered: readonly OfferedWindow[];
}

/** A measurement that was switched off, and what the open window holds of it;
 * null while it is on.
 *
 * It names `config/idhazh.json` and never the knob inside it: a term from a
 * subsystem is not a term for a user (CLAUDE.md section 0b), and an operator
 * looking for `host_fingerprint` does not know that is what he wants.
 *
 * It names a day only inside the open window. A window that holds no recorded
 * day says so, and names the narrowest window the control offers that reaches
 * back to the last recorded day, because the day itself is off screen. "At all"
 * is said only of a record whose index names no row, in every window, because
 * that is a fact about the whole record. A record that is not packed or did not
 * load, a window that holds no packed day, and a window that holds no day this
 * instrument recorded but overlaps the period of the record's newest rows get the
 * switch and the fix and no claim about what was recorded: the page has not read
 * what would make one true.
 */
export function measurementOff(facts: MeasurementFacts): string | null {
	if (facts.enabled) return null;
	const { read, open } = facts;
	const fix = 'Turn it on in config/idhazh.json.';
	const newest = facts.recorded.filter((day) => day >= open.start && day <= open.end).sort().at(-1);
	if (newest !== undefined) return `Measurement is off. Nothing has been recorded since ${shortDate(newest)}. ${fix}`;
	if (read.state !== 'read') return `Measurement is off. ${fix}`;
	if (read.lastRows === null) return `Measurement is off. Nothing has been recorded at all. ${fix}`;
	const rowsInWindow = coveredDays(read.lastRows.period, read.lastRows.covers).last >= open.start;
	if (read.through < open.start || rowsInWindow) return `Measurement is off. ${fix}`;
	const wider = narrowestReaching(facts.offered, read.lastRows);
	const reach =
		wider === undefined
			? 'No window here reaches back to the last recorded day.'
			: `The ${wider.days}-day window reaches back to the last recorded day.`;
	return `Measurement is off. Nothing was recorded ${windowPhrase(open)}. ${fix} ${reach}`;
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
 * goes looking for a broken pipeline. `daysBefore` counts only the days of the
 * window that had a run, so the sentence says that rather than claiming every
 * day before the start.
 *
 * `figures` names what those days have none of, because each instrument on a
 * route answers a different question: "server figures" is true of the server's
 * own counters and of nothing else.
 */
export function recordingStarted(
	firstRecorded: string | null,
	daysBefore: number,
	figures: string = 'server figures'
): string | null {
	if (firstRecorded === null || daysBefore <= 0) return null;
	const days = daysBefore === 1 ? '1 day' : `${daysBefore} days`;
	return `Recording started on ${shortDate(firstRecorded)}. Earlier in this window, ${days} had a run but no ${figures}.`;
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

/** Every state a panel governed by one instrument can be in, apart from its
 * switch: `measurementOff` words that for each window the control offers.
 *
 * Null where the state does not apply, so a panel renders whichever of them is
 * not null and prints nothing where the recording behaved. Three panels can be
 * in three different states on one day, which is why this is per instrument and
 * never one banner across the page.
 */
export interface RecordingNotes {
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
	/** The days this instrument recorded, ascending. Only those inside `open` count. */
	recorded: readonly string[];
	/** The days the route has a run on, ascending. Only those inside `open` count,
	 * and those before the first day this instrument ran had a run and none of
	 * its figures. */
	window: readonly string[];
	/** How the read of this instrument's record went. Its indexes say where the
	 * record begins and which of its days were lost, and a lost day is a day the
	 * instrument ran. */
	read: RecordRead;
	/** The window the notes are for. */
	open: OfferedWindow;
	/** Days another instrument answered for that this one did not. */
	coveredElsewhere?: readonly string[];
	/** Days that published articles and that this instrument kept no row of. */
	lost?: readonly LostDay[];
	/** What the days before the first recorded one have none of. */
	figures?: string;
}

/** What the recording was doing over the open window, from what the route read.
 *
 * Every fact is kept only where the open window shows it, as `measurementOff`
 * keeps its days, so a note never names a day off screen. **A start is dated only
 * for a record that began inside the window.** A record whose indexes name a day
 * before the window began before anything the window shows, so its first day in
 * the window is not when recording started, and no line is better than a false
 * one. The day a record began is the oldest day its indexes name; nothing before
 * the window is read to know it.
 */
export function recordingNotes(facts: RecordingFacts): RecordingNotes {
	const { read, open } = facts;
	const shown = (day: string): boolean => day >= open.start && day <= open.end;
	const recorded = facts.recorded.filter(shown).sort();
	const lost = (facts.lost ?? []).filter((day) => shown(day.date) && !recorded.includes(day.date));
	// The instrument started on the first day it is known to have run: a day it
	// recorded, or a day whose record did not survive, destroyed or recorded lost.
	// Dated from the recorded days alone, a loss before them would date the
	// instrument's start to the day after the loss and count the loss as a day
	// before it, which is the lie these states exist to stop.
	const noRecord = read.state === 'read' ? read.lostDays.filter(shown) : [];
	const ran = [...recorded, ...lost.map((day) => day.date), ...noRecord].sort();
	const began = read.state === 'read' && read.first >= open.start;
	const first = began ? (ran[0] ?? null) : null;
	const before = first === null ? 0 : facts.window.filter((date) => shown(date) && date < first).length;
	const elsewhere = (facts.coveredElsewhere ?? []).filter((date) => shown(date) && !recorded.includes(date));
	return {
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
 * `through`, after which no panel built on the record has rows to draw; `first`,
 * the oldest day the record's indexes name, a month counting from its 1st and a
 * year from its 1 January, so a note can tell a record that began inside a
 * window from one that began before it without reading a day before the window;
 * `lastRows`, the newest period the record's index says holds rows, or null when
 * none does, so a window that starts after it can say where the rows stop
 * without reading a day before the window; `lostDays`, the days in the read the
 * record's index records lost, ascending; and `setAside`, the files the packing
 * of the read's periods set aside unread.
 */
export type RecordRead =
	| {
			state: 'read';
			through: string;
			first: string;
			lastRows: HeldPeriod | null;
			lostDays: string[];
			setAside: SetAsideFiles;
	  }
	| { state: Extract<LedgerFault, 'not-packed'> }
	| { state: 'unreadable'; at: string | null; fault: Exclude<LedgerFault, 'not-packed'> | null };

/** The three records the console reads at build time, as its notes name them. */
export type RecordName = 'article' | 'score' | 'machine';

/** One record a route read, as its notes take it. */
export interface RouteRecord {
	record: RecordName;
	read: RecordRead;
	/** True where the route prints this record's "Measurement is off" line, which
	 * already says why its panels are empty, so no second note says it again. */
	switchedOff?: boolean;
}

/** The ledger each record is read from, so a note can send a person to its files. */
const RECORD_LEDGERS: Readonly<Record<RecordName, LedgerName>> = {
	article: 'item-health',
	score: 'summary-quality-evals',
	machine: 'host-fingerprint'
};

/** One sentence about one or more records. `unreadable` is a fault; the others are not.
 *
 * `emptiesWindow` is true when the state the note names leaves every panel built
 * on its records empty for the whole window, so a sentence that reads an empty
 * page as one with nothing to show would be false beside it. */
export interface RecordNote {
	kind: 'not-packed' | 'unreadable' | 'behind' | 'rows-end' | 'lost' | 'set-aside' | 'on-time';
	records: RecordName[];
	text: string;
	emptiesWindow: boolean;
}

/** One window the control offers, as a note reads it: how many days, and which. */
export interface OfferedWindow {
	days: number;
	start: string;
	end: string;
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
 * newest day the site published, and every window ends on it. A day is packed
 * only once it has ended, so a record packed as far as the day before it is as
 * current as packing can be, and that day still shows nothing in every window:
 * the quietest line on the page says so, last, and that it is normal. Further
 * behind than that, the panels stop early for a reason a reader cannot see, so
 * the sentence says where they stop and how many days are not shown yet.
 * `open` is the window the notes are for, and `offered` every window the control
 * offers: a record whose packed days in the open window hold no row, and whose
 * newest packed rows are before it, leaves every panel built on it empty for the
 * whole window, so the sentence says where its rows stop, and names the
 * narrowest offered window that reaches back to them, when one does. A record
 * read in full can still be short: a day its packing recorded lost has no
 * record, and a file it set aside unread holds rows no panel draws, so each says
 * so, one record at a time and lost days first.
 *
 * The words are fixed, like the other notes in this file; only the names, the
 * dates and the counts inside them are computed. Reader and Jony chose the
 * words for a record whose rows stop before the window, and Susan and Jony the
 * line for the day packing has not reached yet, on 2026-10-06.
 */
export function recordNotes(
	reads: readonly RouteRecord[],
	newestDay: string | null,
	open: OfferedWindow,
	offered: readonly OfferedWindow[]
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
				'That is a step not yet run, not a quiet pipeline.',
			emptiesWindow: true
		});
	}
	for (const { record, read } of reads) {
		if (read.state !== 'unreadable') continue;
		notes.push({ kind: 'unreadable', records: [record], text: unreadableText(record, read), emptiesWindow: true });
	}
	if (newestDay !== null) notes.push(...behindNotes(reads, newestDay, open));
	const ended = rowsEndNotes(reads, open, offered);
	notes.push(...ended);
	for (const { record, read } of reads) {
		if (read.state !== 'read') continue;
		const subject = `${record} record`;
		if (read.lostDays.length > 0) {
			notes.push({
				kind: 'lost',
				records: [record],
				text: noRecordSentence(subject, read.lostDays, (them) => `nothing below that uses this record shows ${them}`),
				emptiesWindow: false
			});
		}
		const setAside = setAsideSentence(subject, RECORD_LEDGERS[record], read.setAside, 'anything below that uses this record');
		if (setAside !== null) notes.push({ kind: 'set-aside', records: [record], text: setAside, emptiesWindow: false });
	}
	if (newestDay !== null) {
		const said = new Set(ended.flatMap((note) => note.records));
		notes.push(...onTimeNotes(reads.filter((entry) => !said.has(entry.record)), newestDay, open));
	}
	return notes;
}

/** The records packed short of the day before `newestDay`, one sentence for each day they stop on. */
function behindNotes(reads: readonly RouteRecord[], newestDay: string, open: OfferedWindow): RecordNote[] {
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
					`${after === 1 ? 'is' : 'are'} not shown yet.`,
				emptiesWindow: through < open.start
			};
		});
}

/** The records packed as far as the day before `newestDay`, in one sentence.
 *
 * As current as packing can be, and still the newest day in every window shows
 * nothing from them, which reads as a quiet day unless the page says otherwise.
 * It prints in normal running, every day, so it is the quietest note and the
 * last one (`RecordNotes.svelte`), and it says that this is normal, so the late
 * note above it still reads as news. */
function onTimeNotes(reads: readonly RouteRecord[], newestDay: string, open: OfferedWindow): RecordNote[] {
	const current = reads.filter(({ read }) => read.state === 'read' && daysAfter(read.through, newestDay) === 1);
	const first = current[0]?.read;
	if (first === undefined || first.state !== 'read') return [];
	const records = current.map((entry) => entry.record);
	const one = records.length === 1;
	return [
		{
			kind: 'on-time',
			records,
			text:
				`The ${recordNoun(records)} ${one ? 'is' : 'are'} packed as far as ${shortDate(first.through)}, ` +
				`so nothing below that uses ${one ? 'it' : 'them'} shows ${shortDate(newestDay)} yet. ` +
				'That is normal: a day is packed only after it ends.',
			emptiesWindow: first.through < open.start
		}
	];
}

/** Whole UTC days from `from` to `to`, negative when `to` is earlier. */
function daysAfter(from: string, to: string): number {
	return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000);
}

/** A period as a sentence names it: `6 May 2030`, a month in full as `May 2030`, or `2029`. */
function namedPeriod(held: HeldPeriod): string {
	if (held.period === 'daily') return shortDate(held.covers);
	if (held.period === 'yearly') return held.covers;
	const [year, month] = held.covers.split('-').map(Number);
	return `${MONTHS[(month ?? 1) - 1]} ${year}`;
}

/** The open window as a sentence ends on it: `on 6 Oct 2026` for one day, `in these 14 days` for more. */
function windowPhrase(open: OfferedWindow): string {
	return open.days === 1 ? `on ${shortDate(open.start)}` : `in these ${open.days} days`;
}

/** The narrowest window the control offers that holds the whole of `held`, or undefined when none does. */
function narrowestReaching(offered: readonly OfferedWindow[], held: HeldPeriod): OfferedWindow | undefined {
	const covered = coveredDays(held.period, held.covers);
	return [...offered]
		.sort((left, right) => left.days - right.days)
		.find((window) => window.start <= covered.first && window.end >= covered.last);
}

/** The records whose rows stop before the open window, one sentence for each period they stop in.
 *
 * Only where the open window holds a packed day: a window packing has not
 * reached yet is the behind note's to name, and saying it holds no rows would
 * claim days nothing has read. The period comes from the index, never from the
 * rows, because the read covers only the window and the rows stop before it;
 * and only packed rows count, because on the day a writer starts again its rows
 * exist and are not packed yet. The sentence names no cause: a writer that
 * stopped, one that paused and a quiet stretch are filed alike. It names the
 * narrowest window the control offers that reaches back to the whole period,
 * where one does, because an instruction that does not work costs a click, and
 * on Pipelines a download. A record whose route already says its measurement is
 * off gets no second explanation.
 */
function rowsEndNotes(reads: readonly RouteRecord[], open: OfferedWindow, offered: readonly OfferedWindow[]): RecordNote[] {
	const ended = new Map<string, { held: HeldPeriod; records: RecordName[] }>();
	for (const { record, read, switchedOff } of reads) {
		if (switchedOff === true || read.state !== 'read' || read.lastRows === null || read.through < open.start) continue;
		if (coveredDays(read.lastRows.period, read.lastRows.covers).last >= open.start) continue;
		const key = `${read.lastRows.period} ${read.lastRows.covers}`;
		const held = ended.get(key) ?? { held: read.lastRows, records: [] };
		held.records.push(record);
		ended.set(key, held);
	}
	const span = windowPhrase(open);
	return [...ended.values()]
		.map(({ held, records }) => ({ held, records, covered: coveredDays(held.period, held.covers) }))
		.sort((left, right) => left.covered.last.localeCompare(right.covered.last))
		.map(({ held, records }): RecordNote => {
			const wider = narrowestReaching(offered, held);
			return {
				kind: 'rows-end',
				records,
				text:
					`The newest packed rows in the ${recordNoun(records)} are from ${namedPeriod(held)}. ` +
					`The packed days since then hold no rows, so nothing below that uses ` +
					`${records.length === 1 ? 'this record' : 'them'} has anything to show ${span}. ` +
					'This page cannot tell if that is a quiet stretch or a fault.' +
					(wider === undefined ? '' : ` The ${wider.days}-day window reaches back to ${namedPeriod(held)}.`),
				emptiesWindow: true
			};
		});
}

/** The notes for every window the control offers, keyed by its day count, so a
 *  page picks the open window's and recomputes nothing. */
export function recordNotesByWindow(
	reads: readonly RouteRecord[],
	newestDay: string | null,
	offered: readonly OfferedWindow[]
): Record<string, RecordNote[]> {
	return Object.fromEntries(offered.map((open) => [String(open.days), recordNotes(reads, newestDay, open, offered)]));
}
