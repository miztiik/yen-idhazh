/** Which attempt and refusal counts do the rows record on each UTC day? */
import type { Row } from '../../data/ledger';

export interface RefusalCount { reason: string; count: number }
export interface VisualAttemptDay {
	date: string;
	attempts: number;
	refusals: RefusalCount[];
}

const cell = (row: Row, name: string): string => row[name] === null || row[name] === undefined ? '' : String(row[name]);

export function visualAttemptDays(rows: readonly Row[]): VisualAttemptDay[] {
	const days = new Map<string, VisualAttemptDay>();
	for (const row of rows) {
		const date = cell(row, 'date');
		let day = days.get(date);
		if (day === undefined) {
			day = { date, attempts: 0, refusals: [] };
			days.set(date, day);
		}
		day.attempts += 1;
		const reason = cell(row, 'rejection_reason');
		if (reason !== '') {
			const held = day.refusals.find((refusal) => refusal.reason === reason);
			if (held === undefined) day.refusals.push({ reason, count: 1 });
			else held.count += 1;
		}
	}
	return [...days.values()].sort((a, b) => a.date.localeCompare(b.date)).map((day) => ({
		...day,
		refusals: day.refusals.sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason))
	}));
}
