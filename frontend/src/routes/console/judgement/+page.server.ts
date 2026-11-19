import {
	chartConfig,
	committedFloor,
	committedWeights,
	consoleConfig,
	holdoutReachDays
} from '$lib/server/config';
import { mergeCountsOf, type MergeDay } from '$lib/console/merged-stories';
import type { ScoreWeights } from '$lib/console/holdout';
import { loadDay, publishedDates } from '$lib/server/payload';
import { holdoutReading, markReach } from '$lib/server/content-similarity-holdout';
import { windowDay } from '$lib/server/window-day';

export const prerender = true;

export type { MergeDay };

/** What Judgement reads, and what it costs.
 *
 * Two reads, both at build time, and nothing is fetched by a browser. Every span
 * the window control can draw is already in the document, so changing the
 * window costs no request.
 *
 * The first is one day file for each published day inside the widest span the
 * window control offers. The day payload is the biggest file the build reads and
 * none of it belongs in this document, so it is reduced to its four merge counts
 * here rather than handed to the browser.
 *
 * **The cover is worked out before the first file is opened** (Guardrail #12).
 * `widestDays` is the largest preset, so a day older than the widest span is
 * never opened - the read is bounded by a knob in `config/`, not by how much the
 * archive has accumulated. Raising a preset raises the cost, visibly, in the
 * config file that raised it.
 *
 * The second is the packed hand marks inside their own reach, which ends on the
 * same day as every window here, plus one published day per distinct date they
 * name. The bound is the reach and not the archive, and the days it opens sit
 * outside the window preset - so it has an entry of its own in
 * `docs/concepts/growing-reads.md`.
 */
export async function load() {
	const console = consoleConfig();
	const widestDays = Math.max(...console.window_presets);
	// Every window on this route ends on the site's newest published day.
	const day = windowDay();
	const merges: MergeDay[] = publishedDates(undefined, widestDays)
		.sort()
		.map((date) => {
			const day = loadDay(date);
			return { date, ...mergeCountsOf(day?.items ?? []) };
		});
	// The ruler the hand marks are scored under: the weight in the committed
	// config, the same one `assemble` scores a pair with.
	const committed = committedWeights();
	const weights: ScoreWeights = { cosineWeight: committed.cosine_weight };
	const reach = markReach(day, holdoutReachDays());
	const holdout = await holdoutReading(weights, reach);
	return {
		// Oldest first, the order every chart on this console draws a day axis in.
		merges,
		holdout: {
			read: holdout.read,
			reach,
			// The merge line: the floor in the committed config, which nothing fits or
			// moves. Every mark below is compared with it.
			line: committedFloor(),
			// Only the pairs marked as two different stories reach the document whole.
			// They are the load-bearing ones - the line has to stay above every one of
			// them - and inlining the rest would put two addresses and two headlines a
			// row in a prerendered page for marks that set no floor.
			marks: holdout.marks.filter((mark) => !mark.sameStory),
			skipped: holdout.skipped,
			marked: holdout.marked,
			// The pairs read as one story, as scores and nothing else. The panel
			// draws them as a range strip and counts how many sit below the line,
			// which is the other cost the line has and the one the panel used to
			// report as a bare total. 196 numbers is 1.7 KB, against 88 KB for the
			// same rows with their addresses and headlines.
			//
			// **Six places, not four.** The count is a comparison against the line,
			// so the rounding decides it: two of the 196 sit between 0.93995 and
			// 0.94, and at four places they round onto the line and the panel
			// printed 115 where the answer is 117. The extra 401 bytes buy a
			// printed number that is the number.
			agreedScores: holdout.marks
				.filter((mark) => mark.sameStory)
				.map((mark) => Number(mark.score.toFixed(6))),
			weights
		},
		// How many date labels the day axis may carry - `chart.tick_density`.
		chart: chartConfig(),
		// The day every window on this route ends on: the site's newest published day.
		windowDay: day
	};
}
