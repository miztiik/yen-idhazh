/** Which feeds failed most often by UTC day when article evidence is unavailable? */
import { windowOfDays } from '../../charts/viewport';
import { failing, preserves } from '../../feed-health';
import type { FeedResult } from '../../server/payload';
import type { FeedInput } from './feeds-failed';

function failureReason(row: FeedResult): string {
	if (row.outcome === 'ok') return 'answered with no entries';
	const reason = row.outcome === 'blocked' ? 'feed access was blocked' :
		row.outcome === 'permanent' ? 'permanent error' : 'temporary error';
	return row.status === null ? reason : `${reason}, HTTP ${row.status}`;
}

export function feedFailurePreview({ read, results }: FeedInput, publishedOn: string, days: number, limit: number) {
	if (read.state !== 'read') return { state: read.state } as const;
	const through = read.through < publishedOn ? read.through : publishedOn;
	const { start, end } = windowOfDays(through, days, 'right');
	const asksByFeed = new Map<string, FeedResult[]>();
	const recordedDays = new Set<string>();
	const runs = new Set<string>();
	for (const row of results) {
		if (row.date < start || row.date > end) continue;
		recordedDays.add(row.date);
		runs.add(row.runId);
		if (preserves(row)) continue;
		const asks = asksByFeed.get(row.feedId);
		if (asks) asks.push(row);
		else asksByFeed.set(row.feedId, [row]);
	}
	const failures = [...asksByFeed].flatMap(([id, asks]) => {
		const failed = asks.filter(failing);
		if (failed.length === 0) return [];
		const failedDays = [...new Set(failed.map((row) => row.date))].sort();
		const last = failedDays[failedDays.length - 1];
		const reasons = [...new Set(failed.filter((row) => row.date === last).map(failureReason))].sort();
		return [{
			id, last, reasons, failedDays: failedDays.length, observedDays: new Set(asks.map((row) => row.date)).size,
			failedReads: failed.length, reads: asks.length
		}];
	}).sort((a, b) => b.failedDays - a.failedDays || a.id.localeCompare(b.id));
	const preview = failures.slice(0, limit);
	const more = failures.slice(limit);
	const cutoff = preview.at(-1)?.failedDays ?? null;
	const lost = read.lostDays.filter((day) => day >= start && day <= end);
	const setAside = Object.values(read.setAside).reduce((sum, count) => sum + count, 0);
	return {
		state: 'read' as const, start, end, days, publishedOn, recordedDays: recordedDays.size, lost, setAside,
		partial: end < publishedOn || recordedDays.size < days || lost.length > 0 || setAside > 0,
		checked: asksByFeed.size, runs: runs.size, failed: failures.length, preview, more, cutoff,
		tied: more.filter((row) => row.failedDays === cutoff).length,
		moreFailedReads: more.reduce((sum, row) => sum + row.failedReads, 0)
	};
}
