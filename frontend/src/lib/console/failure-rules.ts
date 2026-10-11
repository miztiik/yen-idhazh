/** How many recorded failures name each rule, without inventing item or source identities? */
import type { Row } from '../data/ledger';
import { isDay } from '../data/slice-shapes';
import { daysInWindow, type TimeWindow } from '../charts/viewport';

export interface FailureRuleRow {
	readonly date: string;
	readonly stage: string;
	readonly outcome: string;
	readonly code: string;
	readonly failed_rule: string | null;
}

export function failureRuleRows(rows: readonly Row[]): FailureRuleRow[] {
	return rows.map((row) => {
		const { date, stage, outcome, code, failed_rule } = row;
		if (typeof date !== 'string' || !isDay(date)) throw new Error('A failure rule row needs a UTC date.');
		if (typeof stage !== 'string' || typeof outcome !== 'string' || typeof code !== 'string') {
			throw new Error('A failure rule row needs stage, outcome and code strings.');
		}
		if (failed_rule !== null && typeof failed_rule !== 'string') {
			throw new Error('A failure rule row needs a failed_rule string or null.');
		}
		return { date, stage, outcome, code, failed_rule };
	});
}

export function failureRules(rows: readonly FailureRuleRow[], window: TimeWindow, stage: string) {
	const dates = daysInWindow(window);
	const slot = new Map(dates.map((date, index) => [date, index]));
	const own = rows.filter((row) => row.stage === stage && slot.has(row.date));
	const failed = own.filter((row) => row.outcome === 'failed');
	const held = new Map<string, { count: number; daily: number[]; last: string }>();
	let unknown = 0;
	for (const row of failed) {
		if (row.failed_rule === null || row.failed_rule.trim() === '') {
			unknown += 1;
			continue;
		}
		const rule = held.get(row.failed_rule) ?? { count: 0, daily: dates.map(() => 0), last: row.date };
		rule.count += 1;
		rule.daily[slot.get(row.date)!] += 1;
		if (row.date > rule.last) rule.last = row.date;
		held.set(row.failed_rule, rule);
	}
	return {
		dates, rows: own.length, failed: failed.length, unknown,
		rules: [...held].map(([label, rule]) => ({ label, ...rule }))
	};
}
