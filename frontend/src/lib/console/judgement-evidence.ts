/** What the existing packed reads let the Judgement panels establish. */
import type { TimeWindow } from '../charts/viewport';
import { shortDate } from '../format';
import { coveredDays } from '../data/slice';
import { noRecordSentence, setAsideSentence, type RecordRead } from './recording';

const SOURCES = {
	judge: { subject: 'judge record', ledger: 'fitted-thresholds' },
	marks: { subject: 'hand-mark record', ledger: 'holdout-pairs' },
	scores: { subject: 'holdout-score record', ledger: 'merge-line-holdout-scores' }
} as const;

export function judgementEvidence(
	read: RecordRead,
	shown: TimeWindow,
	loaded: TimeWindow,
	source: keyof typeof SOURCES
): string[] {
	const { subject, ledger } = SOURCES[source];
	if (read.state === 'not-packed') return [`The ${subject} has not been packed yet. Its readings are unavailable.`];
	if (read.state === 'unreadable') return [`The ${subject} could not be read. Its readings are unavailable.`];
	const notes: string[] = [];
	if (read.first > shown.start) notes.push(`The ${subject} starts on ${shortDate(read.first)}.`);
	if (read.through < shown.end) {
		notes.push(`The ${subject} is packed through ${shortDate(read.through)}. Later days have no packed reading here.`);
	}
	const rowsPeriod = read.lastRows === null ? null : coveredDays(read.lastRows.period, read.lastRows.covers);
	if (rowsPeriod !== null && rowsPeriod.last < shown.end) {
		notes.push(`The last packed period with rows in the ${subject} is ${shortDate(rowsPeriod.first)} to ${shortDate(rowsPeriod.last)}. This is a period, not the date of the last run.`);
	}
	const lost = read.lostDays.filter((day) => day >= shown.start && day <= shown.end);
	if (lost.length > 0) notes.push(noRecordSentence(subject, lost, (days) => `its readings for ${days} are unavailable`));
	const aside = setAsideSentence(subject, ledger, read.setAside, 'the loaded readings');
	if (aside !== null) {
		notes.push(aside);
		notes.push(`The set-aside count covers the loaded input from ${shortDate(loaded.start)} to ${shortDate(loaded.end)}, not only the selected window.`);
	}
	return notes;
}
