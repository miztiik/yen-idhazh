import { REASONS, type ReasonDay } from '../doubt-reasons';
export function reasonDrawing(days: readonly ReasonDay[]) {
	return REASONS.filter((reason) => days.some((day) => day.counts[reason.id] > 0)).map((reason) => ({
		label: reason.label, token: reason.id === 'not_scored' ? '--chart-8' as const : reason.token,
		points: days.map((day) => ({ date: day.date, value: day.counts[reason.id] }))
	}));
}
