/** What does the attempt record's read say about the views drawn from it? */
import type { RecordRead } from '../recording';
import type { TimeWindow } from '../../charts/viewport';
import { coveredDays } from '../../data/slice';
import { noRecordSentence, setAsideSentence } from '../recording';

export type AttemptRead = 'read' | 'not-packed' | 'unreadable';

export function attemptNotes(read: RecordRead, window?: TimeWindow): { state: AttemptRead; notes: string[] } {
	if (read.state === 'not-packed') {
		return { state: 'not-packed', notes: ['The visual-attempt record is not packed, so these views are unavailable. That is not a quiet window.'] };
	}
	if (read.state === 'unreadable') {
		return { state: 'unreadable', notes: ['The visual-attempt record did not load, so these views are unavailable. This is a fault to fix, not a quiet day.'] };
	}
	const lostDays = read.lostDays.filter((date) => window === undefined || (date >= window.start && date <= window.end));
	const lost = lostDays.length > 0
		? noRecordSentence('visual-attempt record', lostDays, () => 'those days are not drawn as zero') : null;
	const setAside = Object.fromEntries(Object.entries(read.setAside).filter(([date]) => {
		if (window === undefined) return true;
		const period = date.length === 4 ? 'yearly' : date.length === 7 ? 'monthly' : 'daily';
		const span = coveredDays(period, date);
		return span.first <= window.end && span.last >= window.start;
	}));
	const aside = setAsideSentence('visual-attempt record', 'visual-design-attempts', setAside, 'these views');
	const limited = window !== undefined && (read.first > window.start || read.through < window.end)
		? `The visual-attempt record covers ${read.first} through ${read.through} UTC, not the whole selected window. These views are incomplete; unrecorded days are not drawn as zero.`
		: null;
	return { state: 'read', notes: [limited, lost, aside].filter((note): note is string => note !== null) };
}
