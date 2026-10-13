/** The live payload reader's month walk agrees with an independent UTC day walk. */
import { expect, test } from '@playwright/test';
import { daysInWindow, monthsInWindow, type TimeWindow } from '../src/lib/charts/viewport';

function monthsByDay(window: TimeWindow): string[] {
	const months: string[] = [];
	for (const day of daysInWindow(window)) {
		const month = day.slice(0, 7);
		if (!months.includes(month)) months.push(month);
	}
	return months;
}

test('monthsInWindow matches the day walk across month, year and leap-day boundaries', () => {
	const windows: TimeWindow[] = [
		{ start: '2026-08-20', end: '2026-08-20' },
		{ start: '2026-07-31', end: '2026-08-01' },
		{ start: '2026-05-23', end: '2026-08-20' },
		{ start: '2026-12-15', end: '2027-01-14' },
		{ start: '2025-12-31', end: '2026-12-31' },
		{ start: '2024-01-01', end: '2025-03-15' },
		{ start: '2024-02-28', end: '2024-03-01' }
	];
	for (const window of windows) {
		expect(monthsInWindow(window), `${window.start}..${window.end}`).toEqual(monthsByDay(window));
	}
	expect(monthsInWindow({ start: '2026-12-15', end: '2027-01-14' })).toEqual(['2026-12', '2027-01']);
	expect(monthsInWindow({ start: '2025-12-31', end: '2026-12-31' })).toHaveLength(13);
});
