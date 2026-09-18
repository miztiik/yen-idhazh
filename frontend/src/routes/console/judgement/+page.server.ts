import { chartConfig, consoleConfig } from '$lib/server/config';
import { mergeCountsOf, type MergeDay } from '$lib/console/merge-line';
import { loadDay, publishedDates } from '$lib/server/payload';

export const prerender = true;

export type { MergeDay };

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
	return {
		// Oldest first, the order every chart on this console draws a day axis in.
		merges,
		console,
		// How many date labels the day axis may carry - `chart.tick_density`.
		chart: chartConfig(),
		today: new Date().toISOString().slice(0, 10)
	};
}
