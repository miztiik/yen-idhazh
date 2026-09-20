/** How a chart whose columns are RUNS, rather than days, reads its own dates.
 *
 * Both run-by-run charts on the Hardware route - context headroom and the
 * latency multiples - draw one mark a run, so a day with three runs is three
 * columns carrying one date. Every question that follows from that is answered
 * here once rather than in each panel: which column keeps the date, which tick
 * keeps its label, and which columns a model-change rule falls on.
 *
 * The rows themselves are carried once and bounded to the widest preset, so a
 * span only ever decides which of them to keep - which is what `inSpan` does,
 * on the same pair of dates the server filtered on.
 */
import { dayTicks } from '$lib/charts/frame';

/** How much room the oldest and newest marks need inside the plot. */
export const MARK_PAD = 6;

/** The rows a span keeps. The server filters the same pair of dates the same
 * way, so the chart it drew and the chart a browser redraws are built from one
 * set. */
export function inSpan<T extends { date: string }>(
	rows: readonly T[],
	start: string,
	end: string
): T[] {
	return rows.filter((row) => row.date >= start && row.date <= end);
}

/** One date a run, with a repeat blanked.
 *
 * `modelRules` draws a rule where a drawn column's date is a boundary. A day
 * with three runs is three columns carrying one date, and drawing three rules
 * for one change would say the pipeline changed three times. The first run of
 * the day keeps the date, so the rule falls on the leading edge of the day -
 * which is where the shared helper puts it on a calendar axis too.
 */
export function firstOfDay(rows: readonly { date: string }[]): string[] {
	return rows.map((row, index) => (rows[index - 1]?.date === row.date ? '' : row.date));
}

/** A date axis whose columns are runs: a repeated day is labelled once.
 *
 * `dayTicks` owns the measured thinning and the anchoring. What it cannot
 * know is that two neighbouring columns can be the same day, and two identical
 * dates side by side read as a chart that lost its order. Read backwards, so
 * the NEWER of two runs on one day keeps the label: it is the end of the axis
 * and the column an operator reads first. The tick mark stays either way - a
 * reader counting columns needs the grid.
 */
export function runTicks(
	dates: readonly string[],
	columns: readonly number[],
	density: number
): ReturnType<typeof dayTicks> {
	const ticks = dayTicks(dates, { density, columns });
	let carried = '';
	for (let at = ticks.length - 1; at >= 0; at -= 1) {
		if (ticks[at].text === '') continue;
		if (ticks[at].text === carried) ticks[at] = { ...ticks[at], text: '' };
		else carried = ticks[at].text;
	}
	return ticks;
}

/** The days a model-change rule falls on, as a set for O(1) membership.
 *
 * `modelRules` draws a rule where a drawn column's date is a boundary, and a
 * strip below asks the same question once a column. Asked as a scan of the
 * rule list it was O(runs x rules) rebuilt on every resize; asked as a set it
 * is built once a span. It mirrors `modelRules` exactly: the first drawn
 * column draws no rule, so index 0 is skipped, and `firstOfDay` has blanked a
 * repeated day, so a `changes` list that never holds `''` cannot admit one.
 */
export function boundaryDates(changes: readonly string[], dates: readonly string[]): Set<string> {
	const changed = new Set(changes);
	const on = new Set<string>();
	for (let index = 1; index < dates.length; index += 1) {
		if (changed.has(dates[index])) on.add(dates[index]);
	}
	return on;
}
