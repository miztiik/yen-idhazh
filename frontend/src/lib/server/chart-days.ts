/** What did each published day's chart drawing cost, and what did it produce?
 *
 * Imports nothing at runtime: the browser suite loads this module in plain Node,
 * where no Vite alias resolves. The import below is a type, which the compiler
 * erases, and it is written relative for the same reason.
 */

import type { DayVisuals, RunRecord, RunSummary } from './payload';

/** What one day's chart drawing cost and what it produced.
 *
 * Four counts and one division. Two gaps carry the whole story: reached against
 * asked is the check that runs before the model, drafted against published is
 * the pair of checks that run after it.
 *
 * `plannerMinutes` and `minutesPerChart` are null rather than zero wherever the
 * number does not exist - a day whose visuals job never ran measured no time, and
 * a day with no chart has no per-chart cost. Zero would read as free.
 */
export interface ChartDay {
	date: string;
	reached: number;
	asked: number;
	drafted: number;
	published: number;
	/** Items the day published, chart or no chart. Chart drawing's second threshold is
	 * a share of this, and a share needs its denominator on the page. */
	items: number;
	plannerMinutes: number | null;
	minutesPerChart: number | null;
}

/** One row per published day, from the day's own manifest and payload.
 *
 * Nothing here is stored as a rate. The manifest carries counts and one
 * millisecond total; the division happens at read time, so a ratio can never
 * disagree with the counts printed beside it.
 */
export function chartDays(days: RunSummary[], charts: Map<string, DayVisuals>): ChartDay[] {
	return days.map((day) => {
		const sum = (of: (run: RunRecord) => number) =>
			day.records.reduce((total, run) => total + of(run), 0);
		const timed = day.records.map((run) => run.decisionMs).filter((ms): ms is number => ms !== null);
		const plannerMinutes = timed.length === 0 ? null : timed.reduce((a, b) => a + b, 0) / 60_000;
		const seen = charts.get(day.date);
		const published = seen?.charts ?? 0;
		return {
			date: day.date,
			reached: sum((run) => run.decided + run.prefiltered),
			asked: sum((run) => run.decided),
			drafted: sum((run) => run.chartsDrafted),
			published,
			items: seen?.items ?? 0,
			plannerMinutes,
			minutesPerChart: plannerMinutes === null || published === 0 ? null : plannerMinutes / published
		};
	});
}
