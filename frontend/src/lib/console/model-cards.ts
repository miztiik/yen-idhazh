import { shortDate } from '../format';
import {
	sparklineMarks,
	type SparkPoint,
	type SparklineMarks,
	type SparklineRule
} from '../charts/sparkline';

/** A model change, as a card's line and the table's divider both read it. */
export interface CardSwap {
	date: string;
	model: string;
}

/** One card's drawn points and the swap rules that land on them. */
export interface CardTrend {
	marks: SparklineMarks;
	rules: SparklineRule[];
}

/** Every card's line and its swap rules, built in one pass over the open window.
 *
 * The cards, the table under them and the reason panel all read one selected
 * view. A card that re-walked the window on its own is how a marker on a card
 * and the divider in the table below it come to name a different day for the
 * same swap. So the window is walked once here and every column is filled
 * together, rather than once per card.
 *
 * Each column keeps its own dates, because a day the ledger left null for one
 * column is a point that column never drew - so a swap can land on a different
 * point from one card to the next, and that is the reading, not a rounding.
 * `read` returns a day's value for a column, or null where the ledger has no
 * answer, and the nulls are dropped the way the printed cells drop them. The
 * window is oldest first, so a line reads left to right in time and a swap's
 * point is the first drawn day at or after its date; a swap that lands on the
 * first drawn day draws no rule, because a rule across the left edge says the
 * ground moved before the line began.
 */
export function buildCardTrends<Day extends { date: string }>(
	keys: readonly string[],
	window: readonly Day[],
	read: (day: Day, key: string) => number | null,
	swaps: readonly CardSwap[]
): Map<string, CardTrend> {
	const readings: Record<string, SparkPoint[]> = {};
	for (const key of keys) readings[key] = [];
	for (const day of window) {
		for (const key of keys) readings[key].push({ date: day.date, value: read(day, key) });
	}
	const trends = new Map<string, CardTrend>();
	for (const key of keys) {
		const marks = sparklineMarks(readings[key]);
		if (marks.empty) {
			trends.set(key, { marks, rules: [] });
			continue;
		}
		const rules = swaps.flatMap((swap) => {
			const point = marks.dates.findIndex((date) => date >= swap.date);
			if (point < 1) return [];
			return [
				{ point, label: `The model changed to ${swap.model} on ${shortDate(swap.date)}.` }
			];
		});
		trends.set(key, { marks, rules });
	}
	return trends;
}
