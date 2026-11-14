/** Which daily first-check counts are known for each recorded refusal reason? */
import type { SeriesInput } from '../../charts/d3/dateSeries';
import { readoutOf, type Readout } from '../../charts/readout';
import { grouped } from '../../charts/series';
import { daysInWindow, type TimeWindow } from '../../charts/viewport';
import { coveredDays } from '../../data/slice';
import { shortDate } from '../../format';
import type { NumberFormatConfig } from '../../number-format';
import type { RecordRead } from '../recording';
import type { VisualAttemptDay } from './visual-attempts';

export interface RefusalLine {
	reason: string | null;
	label: string;
	series: SeriesInput;
	readout: Readout;
}

export function refusalLines(
	days: readonly VisualAttemptDay[],
	read: RecordRead,
	window: TimeWindow,
	numberFormat: NumberFormatConfig
): RefusalLine[] {
	if (read.state !== 'read') return [];
	const start = window.start > read.first ? window.start : read.first;
	const end = window.end < read.through ? window.end : read.through;
	if (start > end) return [];
	const dates = daysInWindow({ start, end });
	const inside = days.filter((day) => day.date >= window.start && day.date <= window.end);
	if (inside.length === 0) return [];
	const recorded = new Map(inside.map((day) => [day.date, day]));
	const aside = Object.entries(read.setAside).filter(([, count]) => count > 0).map(([date]) =>
		coveredDays(date.length === 4 ? 'yearly' : date.length === 7 ? 'monthly' : 'daily', date));
	const status = dates.map((date) => {
		if (date < read.first || date > read.through) return 'Outside the packed record coverage; no complete count is measured.';
		if (read.lostDays.includes(date)) return 'The record for this UTC day was lost; any surviving counts are incomplete.';
		if (aside.some((span) => span.first <= date && date <= span.last)) return 'Some input files were unreadable; any surviving counts are incomplete.';
		return recorded.has(date) ? null : 'No visual attempt is recorded on this UTC day; no failed-check count is measured.';
	});
	const totals = new Map<string, number>();
	for (const day of inside) for (const refusal of day.refusals) {
		totals.set(refusal.reason, (totals.get(refusal.reason) ?? 0) + refusal.count);
	}
	const reasons: (string | null)[] = totals.size === 0 ? [null] :
		[...totals].sort(([a, n], [b, m]) => m - n || a.localeCompare(b)).map(([reason]) => reason);
	const countText = (value: number) => `${grouped(value, numberFormat)} ${value === 1 ? 'attempt' : 'attempts'}`;
	return reasons.map((reason) => {
		const label = reason === null ? 'First failed plan checks' : `Failed check: ${reason.replaceAll('_', ' ')}`;
		const points = dates.map((date, index) => {
			const day = recorded.get(date);
			const observed = day?.refusals.find((refusal) => refusal.reason === reason)?.count;
			return { date, value: observed ?? (day !== undefined && status[index] === null ? 0 : null) };
		});
		return {
			reason, label, series: { label, token: '--chart-1', points },
			readout: readoutOf({
				type: 'dateSeries', columns: dates.map((date) => `${shortDate(date)} UTC`),
				series: [
					{ label: 'Failed checks', swatch: 'var(--chart-1)', values: points.map((point) => point.value), format: countText },
					{ label: 'Recorded attempts', swatch: null, values: dates.map((date) => recorded.get(date)?.attempts ?? null), format: countText }
				],
				events: { lines: status.map((note, index) => note === null || !recorded.has(dates[index])
					? [] : [{ label: 'Record', value: note, swatch: null }]) },
				notMeasured: 'No complete failed-check count is recorded.',
				notMeasuredAt: status, resting: 'newest'
			})
		};
	});
}
