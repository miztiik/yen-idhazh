/** What does the attempt record's read say about the funnels drawn from it? */
import type { RecordRead } from '../recording';
import { noRecordSentence, setAsideSentence } from '../recording';

export type AttemptRead = 'read' | 'not-packed' | 'unreadable';

export function attemptNotes(read: RecordRead): { state: AttemptRead; notes: string[] } {
	if (read.state === 'not-packed') {
		return { state: 'not-packed', notes: ['The visual-attempt record is not packed, so the funnel is unavailable. That is not a quiet window.'] };
	}
	if (read.state === 'unreadable') {
		return { state: 'unreadable', notes: ['The visual-attempt record did not load, so the funnel is unavailable. This is a fault to fix, not a quiet day.'] };
	}
	const lost = read.lostDays.length > 0
		? noRecordSentence('visual-attempt record', read.lostDays, () => 'those days are not drawn as zero') : null;
	const aside = setAsideSentence('visual-attempt record', 'visual-design-attempts', read.setAside, 'these funnels');
	return { state: 'read', notes: [lost, aside].filter((note): note is string => note !== null) };
}
