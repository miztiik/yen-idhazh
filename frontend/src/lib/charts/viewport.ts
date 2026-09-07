export type TodayAnchor = 'right' | 'centre';

export interface ViewportConfig {
	default_window_days: number;
	window_presets: number[];
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
	// By month, not by day. Walking every day and testing `includes` per day
	// costs the window's width times the month count for an answer that is pure
	// calendar arithmetic: step the year and month from the first to the last.
	const last = window.end.slice(0, 7);
	let year = Number(window.start.slice(0, 4));
	let month = Number(window.start.slice(5, 7));
	const months: string[] = [];
	for (let cursor = window.start.slice(0, 7); cursor <= last; ) {
		months.push(cursor);
		month += 1;
		if (month > 12) {
			month = 1;
			year += 1;
		}
		cursor = `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}`;
	}
	return months;
}

/** A window of exactly `days` days, anchored where the config asks.
 *
 * Exactly, even when the ledger holds fewer days than that. The window used to
 * shrink to fit the rows it found, which was invisible while nothing on the page
 * named the span - and a lie the moment a control does. A page whose control
 * reads 90 while the charts draw 2 cannot be trusted about anything else, and
 * empty calendar space is the honest answer to "there is nothing there".
 */
export function windowOfDays(
	dates: string[],
	today: string,
	days: number,
	anchor: TodayAnchor
): TimeWindow {
	const newest = [...dates].sort().at(-1) ?? today;
	const end = anchor === 'right' ? newest : shift(newest, Math.floor((days - 1) / 2));
	return { start: shift(end, -(days - 1)), end };
}

export function defaultWindow(dates: string[], today: string, config: ViewportConfig): TimeWindow {
	return windowOfDays(dates, today, config.default_window_days, config.today_anchor);
}

/** The next preset wider (`1`) or narrower (`-1`) than the span in force.
 *
 * At either end it answers with the end it is already at, so a key held down
 * stops rather than wrapping round to the opposite window.
 */
export function stepPreset(days: number, presets: readonly number[], direction: 1 | -1): number {
	const ordered = [...presets].sort((a, b) => a - b);
	if (ordered.length === 0) return days;
	if (direction === 1) return ordered.find((preset) => preset > days) ?? (ordered.at(-1) as number);
	return [...ordered].reverse().find((preset) => preset < days) ?? ordered[0];
}

/** The month files a window needs that are on the server and not yet in hand.
 *
 * This is the price of widening, and the control prints its length before the
 * operator pays it. A month that was never published is not a cost: asking for
 * it would only produce a 404 and a gap the charts already draw.
 */
export function monthsToFetch(
	window: TimeWindow,
	available: readonly string[],
	loaded: readonly string[]
): string[] {
	const published = new Set(available);
	const held = new Set(loaded);
	return monthsInWindow(window).filter((month) => published.has(month) && !held.has(month));
}

export function panWindow(window: TimeWindow, days: number): TimeWindow {
	return { start: shift(window.start, days), end: shift(window.end, days) };
}

