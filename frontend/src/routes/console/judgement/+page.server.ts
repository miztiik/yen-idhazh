import {
	chartConfig,
	committedFloor,
	consoleConfig,
	similarityConfig
} from '$lib/server/config';
import { mergeCountsOf, type JudgeDay, type LineDay, type MergeDay } from '$lib/console/merge-line';
import { loadDay, publishedDates } from '$lib/server/payload';
import { fittedLines } from '$lib/server/similarity-ledger';

export const prerender = true;

export type { JudgeDay, LineDay, MergeDay };

/** Every date the widest preset spans, oldest first, whether or not anything
 * happened on it.
 *
 * Date arithmetic rather than a directory walk, so the cost is the span the
 * config names and never what the archive holds (Guardrail #12).
 */
function spanOfDays(days: number): string[] {
	const end = new Date();
	const dates: string[] = [];
	for (let back = days; back >= 0; back -= 1) {
		const day = new Date(end);
		day.setUTCDate(day.getUTCDate() - back);
		dates.push(day.toISOString().slice(0, 10));
	}
	return dates;
}

/** What Judgement reads, and what it costs.
 *
 * One day file a published day inside the widest span the window control
 * offers, and nothing else. The route fetches nothing at read time: every span
 * the control can draw is already in the document, so changing the window costs
 * no request.
 *
 * **The cover is worked out before the first file is opened** (Guardrail #12).
 * `widestDays` is the largest preset, so a day older than the widest span is
 * never opened - the read is bounded by a knob in `config/`, not by how much the
 * archive has accumulated. Raising a preset raises the cost, visibly, in the
 * config file that raised it.
 *
 * Four numbers survive per day. The day payload is the biggest file the build
 * reads and none of it belongs in this document, so it is reduced to its counts
 * here rather than handed to the browser.
 */
export function load() {
	const console = consoleConfig();
	const widestDays = Math.max(...console.window_presets);
	const merges: MergeDay[] = publishedDates(undefined, widestDays)
		.sort()
		.map((date) => {
			const day = loadDay(date);
			return { date, ...mergeCountsOf(day?.items ?? []) };
		});
	// One read, three panels. The fitted row carries the line, both judge rates
	// and all three gate counts, so asking the ledger twice would be two reads of
	// one file that could disagree about which run of a date they took.
	const rows = fittedLines(widestDays);
	return {
		// Oldest first, the order every chart on this console draws a day axis in.
		merges,
		// Seven numbers and two words a day at the widest preset, so the window
		// control filters an array that is already here and no preset costs a fetch.
		lines: rows.map(
			(row): LineDay => ({
				date: row.date,
				previous: row.previous,
				proposed: row.proposed,
				applied: row.applied,
				clampKind: row.clampKind,
				heldReason: row.heldReason,
				maxDownStep: row.maxDownStep
			})
		),
		// The judge's own health and the record's fill, off the same rows.
		judge: rows.map(
			(row): JudgeDay => ({
				date: row.date,
				disagreementRate: row.disagreementRate,
				unclearRate: row.unclearRate,
				pairsJudged: row.pairsJudged,
				negativesOnRecord: row.negativesOnRecord,
				aboveLineOnRecord: row.aboveLineOnRecord,
				daysOnRecord: row.daysOnRecord,
				heldReason: row.heldReason
			})
		),
		// Every date the widest preset spans, so the squares strip draws the days
		// nothing recorded. A strip built from the rows would draw a shorter,
		// tidier picture of a record that had stopped filling.
		span: spanOfDays(widestDays),
		// The band and the daily step the chart draws against, read off config so
		// the axis is the range a line MAY take rather than the range it has taken.
		similarity: similarityConfig(),
		// What the newest day was built with when no fit has ever run.
		configuredLine: committedFloor(),
		console,
		// How many date labels the day axis may carry - `chart.tick_density`.
		chart: chartConfig(),
		today: new Date().toISOString().slice(0, 10)
	};
}
