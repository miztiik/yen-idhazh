export type TodayAnchor = 'right' | 'centre';

export interface ViewportConfig {
	default_window_days: number;
	today_anchor: TodayAnchor;
	pan_days: number;
	zoom_factor: number;
	min_window_days: number;
	max_window_days: number;
}

export interface TimeWindow {
	start: string;
	end: string;
}

const DAY_MS = 86_400_000;

export function toDay(value: string): Date {
	return new Date(`${value}T00:00:00Z`);
}

export function dayKey(value: Date): string {
	return value.toISOString().slice(0, 10);
}

function shift(day: string, days: number): string {
	return dayKey(new Date(toDay(day).getTime() + days * DAY_MS));
}

export function daysBetween(start: string, end: string): number {
	return Math.max(1, Math.round((toDay(end).getTime() - toDay(start).getTime()) / DAY_MS) + 1);
}

export function daysInWindow(window: TimeWindow): string[] {
	const total = daysBetween(window.start, window.end);
	return Array.from({ length: total }, (_, index) => shift(window.start, index));
}

export function monthsInWindow(window: TimeWindow): string[] {
	const months: string[] = [];
	for (const day of daysInWindow(window)) {
		const month = day.slice(0, 7);
		if (!months.includes(month)) months.push(month);
	}
	return months;
}

export function defaultWindow(dates: string[], today: string, config: ViewportConfig): TimeWindow {
	const sorted = [...new Set(dates)].sort();
	if (sorted.length > 0) {
		const first = sorted[0];
		const last = sorted.at(-1) as string;
		if (daysBetween(first, last) <= config.default_window_days) return { start: first, end: last };
		const end =
			config.today_anchor === 'right'
				? last
				: shift(last, Math.floor((config.default_window_days - 1) / 2));
		return { start: shift(end, -(config.default_window_days - 1)), end };
	}
	return { start: shift(today, -(config.default_window_days - 1)), end: today };
}

export function panWindow(window: TimeWindow, days: number): TimeWindow {
	return { start: shift(window.start, days), end: shift(window.end, days) };
}

export function zoomWindow(window: TimeWindow, factor: number, config: ViewportConfig): TimeWindow {
	const span = daysBetween(window.start, window.end);
	const next = Math.max(
		config.min_window_days,
		Math.min(config.max_window_days, Math.round(span * factor))
	);
	const centre = toDay(window.start).getTime() + ((span - 1) * DAY_MS) / 2;
	const start = new Date(centre - ((next - 1) * DAY_MS) / 2);
	return { start: dayKey(start), end: shift(dayKey(start), next - 1) };
}

