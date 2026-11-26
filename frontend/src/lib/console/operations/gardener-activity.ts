/** Place verified compact writes by their UTC write date, not the period they cover. */
import { daysInWindow, type TimeWindow } from '../../charts/viewport';
import { COMPACT_PERIODS, type Period } from '../../data/compact-index';
import type { CompactWriteTrack } from '../../data/compact-file-writes';
import type { CompactWrite } from '../../data/compact-write-footer';
import { clockUtc, longDate, MONTHS } from '../../format';

export const PERIOD_LABEL: Record<Period, string> = { daily: 'Daily', monthly: 'Monthly', yearly: 'Yearly' };
type Tracks = Partial<Record<Period, CompactWriteTrack>>;

export function writeInstant(value: CompactWrite) { return new Date(value.writtenAt).toISOString(); }
export function utcTime(stamp: string) { return `${longDate(stamp.slice(0, 10))} ${clockUtc(stamp)}`; }
export function periodLabel(period: Period, stamp: string): string {
	if (period === 'daily') return longDate(stamp);
	if (period === 'yearly') return stamp;
	return `${MONTHS[Number(stamp.slice(5)) - 1]} ${stamp.slice(0, 4)}`;
}

export function compactActivity(tracks: Tracks, window: TimeWindow, requestedDays: number) {
	const byNewest = (a: CompactWrite, b: CompactWrite) =>
		b.writtenAt - a.writtenAt || a.ledger.localeCompare(b.ledger) || a.covers.localeCompare(b.covers);
	const calendar = daysInWindow(window);
	const writes = COMPACT_PERIODS.flatMap((period) => tracks[period]?.writes ?? [])
		.filter((write) => {
			const day = writeInstant(write).slice(0, 10);
			return day >= window.start && day <= window.end;
		}).sort(byNewest);
	const monthly = writes.find((write) => write.period === 'monthly') ?? null;
	const monthlyGroup = monthly === null ? [] : writes.filter((write) =>
		write.period === 'monthly' && write.runId === monthly.runId && write.attempt === monthly.attempt && write.covers === monthly.covers);
	const byDay = new Map<string, CompactWrite[]>();
	for (const write of writes) {
		const day = writeInstant(write).slice(0, 10);
		const onDay = byDay.get(day) ?? [];
		onDay.push(write);
		byDay.set(day, onDay);
	}
	return {
		monthly, monthlyGroup, calendar, byDay, latest: writes[0] ?? null,
		lanes: COMPACT_PERIODS.map((period) => {
			const track = tracks[period];
			const found = (day: string) => (byDay.get(day) ?? []).filter((write) => write.period === period);
			const cells = calendar.map((date) => {
				const written = found(date);
				const narrowed = period === 'daily' && track !== undefined && track.days < requestedDays;
				const uncertain = track === undefined || track.omitted || track.issues.length > 0 || narrowed;
				const state = written.length > 0 ? 'written' : uncertain ? 'unavailable' : 'checked';
				const text = written.length > 0 ? `${written.length} published ${written.length === 1 ? 'file' : 'files'}`
					: track === undefined ? 'Checking files'
					: track.omitted ? 'Not checked'
					: narrowed ? 'No write verified in the shorter read'
					: uncertain ? 'Evidence incomplete' : 'No write found in checked files';
				return { state, text, draw: period === 'daily' || written.length > 0 } as const;
			});
			return { name: PERIOD_LABEL[period], cells };
		})
	};
}
