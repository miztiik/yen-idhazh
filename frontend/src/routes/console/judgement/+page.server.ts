import {
	chartConfig,
	committedFloor,
	committedWeights,
	consoleConfig,
	holdoutReachDays,
	similarityConfig
} from '$lib/server/config';
import { daysInWindow, windowOfDays } from '$lib/charts/viewport';
import { mergeCountsOf, type JudgeDay, type LineDay, type MergeDay } from '$lib/console/merge-line';
import type { ScoreWeights } from '$lib/console/holdout';
import { loadDay, publishedDates } from '$lib/server/payload';
import { fittedLines, scoreRecord } from '$lib/server/similarity-ledger';
import { holdoutReading, markReach, mergeLineHoldoutScore } from '$lib/server/similarity-holdout';
import { windowDay } from '$lib/server/window-day';

export const prerender = true;

export type { JudgeDay, LineDay, MergeDay };

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
export async function load() {
	const console = consoleConfig();
	const widestDays = Math.max(...console.window_presets);
	// Every window on this route ends on the site's newest published day.
	const day = windowDay();
	// The widest span the window control offers, as a window: the fitted lines and
	// the holdout score are read inside it, and the squares strip draws every day
	// of it.
	const readSpan = windowOfDays(day, widestDays, console.today_anchor);
	const merges: MergeDay[] = publishedDates(undefined, widestDays)
		.sort()
		.map((date) => {
			const day = loadDay(date);
			return { date, ...mergeCountsOf(day?.items ?? []) };
		});
	// One read, three panels. The fitted row carries the line, both judge rates
	// and all three gate counts, so asking the ledger twice would be two reads
	// that could disagree about which run of a date they took. It also holds the
	// days the merge line's rule looks back over while `applied_lookback_days` is
	// under the widest preset, because no row is dated after the newest published
	// day. The rows come from the packed record, read inside the widest span, so a
	// fitted day reaches the page once the gardener has packed it.
	const rows = await fittedLines(readSpan);
	// The record is cumulative and the counts are per day, so the newest row is
	// what both the split and the figures strip are about.
	const newest = rows.length === 0 ? null : rows[rows.length - 1];
	// The ruler the holdout marks are scored under. The newest fitted row wins,
	// because the margin has to be read under the weights the line was set with;
	// the committed config answers on a day no fit has ever run, and on a row
	// written before the two columns existed.
	const committed = committedWeights();
	const weights: ScoreWeights = {
		cosineWeight: newest?.cosineWeight ?? committed.cosine_weight,
		fittedOn: newest === null ? null : newest.date
	};
	// The packed hand marks inside their own reach, which ends on the same day as
	// every window here, plus one published day per distinct date they name. The
	// bound is the reach and not the archive, and the days it opens sit outside
	// the window preset - so it has an entry of its own in
	// `docs/concepts/growing-reads.md`.
	const holdout = await holdoutReading(weights, markReach(day, holdoutReachDays()));
	// How the line stood against the marks, off the committed row rather than
	// counted again here. Null where nobody has run the verb that writes it, where
	// its day is not packed yet, or where the newest row is older than the widest
	// preset reaches - and the panel says the line has not been scored rather
	// than showing four zeros.
	const scored = await mergeLineHoldoutScore(readSpan);
	return {
		// Oldest first, the order every chart on this console draws a day axis in.
		merges,
		// Eight numbers and two words a day at the widest preset, so the window
		// control filters an array that is already here and no preset costs a fetch.
		lines: rows.map(
			(row): LineDay => ({
				date: row.date,
				previous: row.previous,
				proposed: row.proposed,
				applied: row.applied,
				clampKind: row.clampKind,
				heldReason: row.heldReason,
				maxDownStep: row.maxDownStep,
				maxUpStep: row.maxUpStep
			})
		),
		// The judge's own health and the record's fill, off the same rows.
		judge: rows.map(
			(row): JudgeDay => ({
				date: row.date,
				disagreementRate: row.disagreementRate,
				unclearRate: row.unclearRate,
				pairsJudged: row.pairsJudged ?? 0,
				pairsUsable: row.pairsUsable ?? 0,
				negativesOnRecord: row.negativesOnRecord,
				aboveLineOnRecord: row.aboveLineOnRecord,
				daysOnRecord: row.daysOnRecord,
				heldReason: row.heldReason
			})
		),
		// Every date the widest preset spans, so the squares strip draws the days
		// nothing recorded. A strip built from the rows would draw a shorter,
		// tidier picture of a record that had stopped filling. Date arithmetic rather
		// than a directory walk, so the cost is the span the config names and never
		// what the archive holds (Guardrail #12).
		span: daysInWindow(readSpan),
		// The band and the daily step the chart draws against, read off config so
		// the axis is the range a line MAY take rather than the range it has taken.
		// The switch and the lookback come with them, so a window with no fitted
		// day draws its rule at the line a build used.
		similarity: similarityConfig(),
		// 120 slots, a fixed size whatever the archive grows to, so this read costs
		// the same on the thousandth day as on the third. The page draws no 120-slot
		// chart, so only the four counts, the two ranges and the 24 rebinned rows
		// reach the document.
		record: scoreRecord(),
		// The day's three counts, off the newest fitted row. A dash where the ledger
		// holds no answer, never a zero.
		figures: {
			inBand: newest?.pairsInBand ?? null,
			judged: newest?.pairsJudged ?? null,
			usable: newest?.pairsUsable ?? null
		},
		// The committed floor: what a build groups at while the switch is off, or
		// when no fit applied a line in its lookback.
		configuredLine: committedFloor(),
		// Only the pairs marked as two different stories reach the document whole.
		// They are the load-bearing ones - the line has to stay above every one of
		// them - and inlining the rest would put two addresses and two headlines a
		// row in a prerendered page for marks that set no floor.
		holdout: {
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
			weights,
			// The committed reading, or null. Ten numbers, so the panel can print what
			// the line did to every mark on the day somebody scored it -
			// which is the part a rebuild of this page cannot reconstruct.
			scored
		},
		console,
		// How many date labels the day axis may carry - `chart.tick_density`.
		chart: chartConfig(),
		// The day every window on this route ends on: the site's newest published day.
		windowDay: day
	};
}
