/** Which refusals and successfully written types do the attempt rows record on each UTC day? */
import type { Row } from '../../data/ledger';

export interface RefusalCount { reason: string; count: number }
export interface WrittenTypeCount { planned: string; rendered: string; count: number }
export interface VisualAttemptDay {
	date: string;
	attempts: number;
	refusals: RefusalCount[];
	written: WrittenTypeCount[];
	untypedWritten: number;
}

const cell = (row: Row, name: string): string => row[name] === null || row[name] === undefined ? '' : String(row[name]);

function addWritten(pairs: WrittenTypeCount[], planned: string, rendered: string, count: number) {
	const held = pairs.find((pair) => pair.planned === planned && pair.rendered === rendered);
	if (held === undefined) pairs.push({ planned, rendered, count });
	else held.count += count;
}

const rankWritten = (pairs: WrittenTypeCount[]): WrittenTypeCount[] =>
	pairs.sort((a, b) => b.count - a.count || a.planned.localeCompare(b.planned) || a.rendered.localeCompare(b.rendered));

export function visualAttemptDays(rows: readonly Row[]): VisualAttemptDay[] {
	const days = new Map<string, VisualAttemptDay>();
	for (const row of rows) {
		const date = cell(row, 'date');
		let day = days.get(date);
		if (day === undefined) {
			day = { date, attempts: 0, refusals: [], written: [], untypedWritten: 0 };
			days.set(date, day);
		}
		day.attempts += 1;
		const reason = cell(row, 'rejection_reason');
		if (reason !== '') {
			const held = day.refusals.find((refusal) => refusal.reason === reason);
			if (held === undefined) day.refusals.push({ reason, count: 1 });
			else held.count += 1;
		}
		const rendered = cell(row, 'rendered_type');
		if (rendered !== '') addWritten(day.written, cell(row, 'planned_type'), rendered, 1);
		else if (cell(row, 'state') === 'rendered') day.untypedWritten += 1;
	}
	return [...days.values()].sort((a, b) => a.date.localeCompare(b.date)).map((day) => ({
		...day,
		refusals: day.refusals.sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason)),
		written: rankWritten(day.written)
	}));
}

/** Combine only the selected days; an absent type is never inferred from the planned type. */
export function writtenTypeCounts(days: readonly VisualAttemptDay[]): WrittenTypeCount[] {
	const pairs: WrittenTypeCount[] = [];
	for (const day of days) for (const pair of day.written) addWritten(pairs, pair.planned, pair.rendered, pair.count);
	return rankWritten(pairs);
}
