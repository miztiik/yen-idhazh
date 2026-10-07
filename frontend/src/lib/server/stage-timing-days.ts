/** How long did each day's items take at the three stages they wait on, and how many did each stage time?
 *
 * The three stages an item waits on are fetch, extract and summarize. `score_ms`
 * was a fourth entry here until 2026-08-31: the scorer runs after the summary is
 * written, so nothing waits on it, and a fourth line on a critical-path chart
 * read as a fourth thing the run is held up by. It is on the Model route now,
 * beside the cost of writing the summary it checks.
 *
 * Imports nothing at runtime: the browser suite loads this module in plain Node,
 * where no Vite alias resolves. The import below is a type, which the compiler
 * erases, and it is written relative for the same reason.
 */

import type { StageTiming, StageTimingDay } from '../charts/series';

/** Null when nothing was timed. Zero is a measurement - a cheap stage really
 * does finish inside a millisecond clock's own resolution - so it can never
 * stand in for the absence of one.
 *
 * It takes a `Sample` rather than an array so that a hand-built list of
 * numbers, and any zero invented to fill an empty cell, has nowhere to land. */
function median(of: Sample): number | null {
	if (of.values.length === 0) return null;
	const sorted = [...of.values].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function measured(row: Record<string, string>, name: string): number | null {
	const raw = row[name];
	if (raw === undefined || raw === '') return null;
	const value = Number(raw);
	return Number.isFinite(value) ? value : null;
}

/** One column of one group of rows, and how many rows could have filled it.
 *
 * `timed` against `total` is the fact a bare array cannot carry: eight items
 * timed out of ten and ten out of ten arrive as the same list of numbers.
 */
interface Sample {
	values: number[];
	timed: number;
	total: number;
}

function sample(rows: Record<string, string>[], name: string): Sample {
	const values = rows
		.map((row) => measured(row, name))
		.filter((value): value is number => value !== null);
	return { values, timed: values.length, total: rows.length };
}

/** A sample reduced to what the chart draws: one median, and the two counts
 * that say whether the day was timed in full, in part, or not at all. */
function timing(of: Sample): StageTiming {
	return { ms: median(of), timed: of.timed, total: of.total };
}

function byDate(rows: Record<string, string>[]): Map<string, Record<string, string>[]> {
	const grouped = new Map<string, Record<string, string>[]>();
	for (const row of rows) {
		const date = row.date ?? '';
		if (!date) continue;
		grouped.set(date, [...(grouped.get(date) ?? []), row]);
	}
	return grouped;
}

/** One entry a day, newest first, for every day of `rows` on which a stage timed something.
 *
 * A day is kept when something on it was timed. Judging it by its medians
 * would drop a day whose only measurement was a zero, which is the same
 * mistake one level up.
 */
export function stageTimingDays(rows: Record<string, string>[]): StageTimingDay[] {
	return [...byDate(rows).entries()]
		.map(([date, group]) => ({
			date,
			items: group.length,
			fetch: timing(sample(group, 'fetch_ms')),
			extract: timing(sample(group, 'extract_ms')),
			summarize: timing(sample(group, 'summarize_ms'))
		}))
		.filter((day) => [day.fetch, day.extract, day.summarize].some((stage) => stage.timed > 0))
		.sort((a, b) => b.date.localeCompare(a.date));
}
