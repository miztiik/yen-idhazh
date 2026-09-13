import { consoleConfig } from '$lib/server/config';
import { sourceHealthView, type SourceHealthView } from '$lib/server/payload';
import { percentOf } from '$lib/charts/rank';
import { targetGeometry, type TargetMarks } from '$lib/charts/targetbar';

export const prerender = true;

/** The bar for a share that is already bounded at 1.0.
 *
 * `targetMarks` sizes its own track to `max(value, target) * 1.15`, which is
 * right for a measure with no ceiling - a failure count has no natural full -
 * and wrong here. This factor cannot exceed 1.0, so the track IS 1.0: a full
 * bar means a feed the ranker did not discount, and two feeds' bars can be read
 * against each other because they are drawn to the same scale. An auto-sized
 * track would give a feed at 1.0 and a feed at 0.5 the same 87 percent fill.
 *
 * The band and the sense come from `targetGeometry` rather than from a second
 * rule written here, so the colour a bar takes and the colour a delta on the
 * same figure takes cannot disagree.
 */
function shareMarks(factor: number, floor: number): TargetMarks {
	const geometry = targetGeometry(factor, floor, 'higher-is-better');
	return {
		...geometry,
		track: 1,
		valueFraction: factor,
		markerFraction: floor,
		valuePercent: percentOf(factor),
		markerPercent: percentOf(floor)
	};
}

/** One feed's standing with the ranker, as the page draws it.
 *
 * `factor` is what the run applied and `reads` is what it was reduced over.
 * They travel together because a factor with no denominator is not a
 * measurement: a feed nobody asked scores the same 1.0 as a feed that never
 * missed, and the page has to be able to tell those apart.
 *
 * `marks` is computed here rather than in the browser, so the bar is on the
 * page before any script runs - the same trade the feed-failure bars take.
 */
export interface FeedStanding {
	sourceId: string;
	title: string;
	vertical: string;
	/** The multiplier, in the range the floor and 1.0 bound. */
	factor: number;
	/** Evidence-bearing reads behind it. Zero means the factor is a default. */
	reads: number;
	/** True when the ranker has taken this feed as far down as it goes. */
	onTheFloor: boolean;
	/** Null where `reads` is zero - there is no bar to draw over no evidence. */
	marks: TargetMarks | null;
}

/** What the ranking did about the record, ready to draw. */
export interface Standing {
	headline: string;
	floor: number;
	windowDays: number;
	/** Worst first, then by id, so two builds over one view draw one order. */
	feeds: FeedStanding[];
	/** Feeds the row cap left out, and how many of those are on the floor. */
	hidden: number;
	hiddenOnTheFloor: number;
	/** Feeds with no evidence behind their factor, over how many were counted. */
	unmeasured: number;
	counted: number;
	generatedAt: string;
	runId: string;
}

/** The ranking factor per feed, from the view the pipeline published.
 *
 * Read and never re-derived. `ledger.feed_reliability` reduced these rows when
 * the run happened; reducing them again in a page would be a second answer to
 * one question, and the day the two disagreed neither would be worth drawing
 * (`docs/architecture/sources/health.md`).
 *
 * Retired addresses are left out. Their factor is whatever the window still
 * holds from before we stopped asking, so drawing it would put a bar on a feed
 * no run will ever ask again.
 */
export function standing(view: SourceHealthView | null, rows: number): Standing | null {
	if (view === null) return null;
	const live = view.sources.filter((row) => !row.retired);
	const ranked = live
		.map((row) => ({
			sourceId: row.source_id,
			title: row.title,
			vertical: row.vertical,
			factor: row.reliability,
			reads: row.reliability_reads,
			onTheFloor: row.reliability_reads > 0 && row.reliability <= view.reliability_floor,
			// Higher is better here, so the fill runs from nothing up to 1.0 and the
			// mark sits on the floor the ranker will not discount past.
			marks: row.reliability_reads > 0 ? shareMarks(row.reliability, view.reliability_floor) : null
		}))
		.sort(
			(a, b) =>
				a.factor - b.factor || b.reads - a.reads || a.sourceId.localeCompare(b.sourceId)
		);
	const drawn = ranked.slice(0, rows);
	const hidden = ranked.slice(drawn.length);
	return {
		headline: view.headline_sentence,
		floor: view.reliability_floor,
		windowDays: view.reliability_window_days,
		feeds: drawn,
		hidden: hidden.length,
		hiddenOnTheFloor: hidden.filter((feed) => feed.onTheFloor).length,
		unmeasured: ranked.filter((feed) => feed.reads === 0).length,
		counted: ranked.length,
		generatedAt: view.generated_at,
		runId: view.run_id
	};
}

/** The Voices route reads one published projection and nothing else.
 *
 * No ledger walk and no window control: every figure here was reduced over
 * `collect.reliability_window_days` when the run happened, so the page cannot
 * offer a span the numbers were not taken over (`CLAUDE.md` Guardrail #12).
 */
export async function load() {
	const console = consoleConfig();
	return {
		// Null when no run has written the view or it cannot be read, which the
		// page draws as a named absence rather than as a section that is missing.
		standing: standing(sourceHealthView(), console.source_rows),
		console
	};
}
