/** How many stories a day folded into another, counted off the day's own payload.
 *
 * This is the one figure on Judgement that involves no model. `same_story_as`
 * is written by the grouping pass and published with the day: null on the story
 * that is kept and on a story nothing grouped with, set to the kept story's id
 * on one that was folded behind it. So the count is a read of what shipped,
 * not a re-derivation of it - the scores and the vectors that decided the
 * grouping are dropped from the published payload, and a page that recomputed
 * them would be a second opinion about a decision already taken.
 *
 * Pure and browser safe on purpose: no config read, no disk, no `$lib` alias.
 * The `logic` test group drives it with a written-down array and no build, so
 * the arithmetic is checked without a day off the archive (Guardrail #12).
 */

import { grouped } from '../charts/series';
import { dayMonth } from '../format';

/** The two fields the count reads. A published item carries far more; taking
 * only these two keeps a test fixture to two keys a row. */
export interface MergeItem {
	item_id: string;
	same_story_as?: string | null;
}

export interface MergeCounts {
	/** Stories in the day's payload, folded ones included. They are published,
	 * addressable and in the archive - they are not drawn on the day page. */
	published: number;
	/** Stories folded behind another. */
	merges: number;
	/** Distinct stories that gained at least one other behind them. */
	groups: number;
	/** The biggest group, counting the story that was kept. 0 where nothing was
	 * folded: there is no group, and a 1 here would name one that does not exist. */
	largest: number;
}

export interface MergeDay extends MergeCounts {
	date: string;
}

/** What the whole window folded, and where its biggest group sits. */
export interface MergeTotals {
	/** Days with a published payload in the window. 0 is state E1. */
	days: number;
	published: number;
	merges: number;
	largest: number;
	/** The day the biggest group is on, or '' where nothing was folded. */
	largestOn: string;
}

export type MergeState = 'no-days' | 'no-merges' | 'merged';

/** The four numbers, in one pass over the day's items.
 *
 * A story naming itself is not a merge. The grouping pass has never written
 * one and the schema does not allow it, which is exactly why the guard is here
 * rather than trusted: an anchor pointing at its own row would otherwise count
 * a story as folded behind itself and inflate both the merge count and the
 * group it is in.
 */
export function mergeCountsOf(items: readonly MergeItem[]): MergeCounts {
	const members = new Map<string, number>();
	let merges = 0;
	for (const item of items) {
		const anchor = item.same_story_as;
		if (!anchor || anchor === item.item_id) continue;
		merges += 1;
		members.set(anchor, (members.get(anchor) ?? 0) + 1);
	}
	let biggest = 0;
	for (const count of members.values()) biggest = Math.max(biggest, count);
	return {
		published: items.length,
		merges,
		groups: members.size,
		// The kept story is in its own group, so the size is the members plus one.
		largest: biggest === 0 ? 0 : biggest + 1
	};
}

/** Add up the days a window drew, and find the biggest group in it.
 *
 * Ties go to the newest day, because a reader reading "on 4 Sep" wants the
 * occasion he can still act on rather than the first one on the calendar.
 */
export function mergeTotals(days: readonly MergeDay[]): MergeTotals {
	let published = 0;
	let merges = 0;
	let largest = 0;
	let largestOn = '';
	for (const day of days) {
		published += day.published;
		merges += day.merges;
		if (day.largest > 0 && day.largest >= largest) {
			largest = day.largest;
			largestOn = day.date;
		}
	}
	return { days: days.length, published, merges, largest, largestOn };
}

/** Which of the three states the window is in.
 *
 * `no-days` and `no-merges` are different answers and the panel says so in
 * different words. The first means the day tree cannot answer; the second means
 * it answered no. Reading the first as the second is reading a null as a zero.
 */
export function mergeState(totals: MergeTotals): MergeState {
	if (totals.days === 0) return 'no-days';
	return totals.merges === 0 ? 'no-merges' : 'merged';
}

/** The span the control is holding, written the way a person says it.
 *
 * `1` is one of the presets, and `these 1 days` is what a plain template prints
 * for it. */
function span(windowDays: number): string {
	return windowDays === 1 ? 'this one day' : `these ${windowDays} days`;
}

/** The sentence under the chart, one per state. */
export function mergeNote(totals: MergeTotals, windowDays: number): string {
	switch (mergeState(totals)) {
		case 'no-days':
			return 'No published day is in this window, so nothing here can be counted.';
		case 'no-merges':
			return `No story in ${span(windowDays)} was grouped with another. Every one ran on its own.`;
		default: {
			// Singular is spelled out rather than templated over: one day with one
			// fold would otherwise read "1 stories were folded".
			const folded =
				totals.merges === 1
					? '1 story was folded into another'
					: `${grouped(totals.merges)} stories were folded into another`;
			return `${folded} over ${span(windowDays)}. The biggest group held ${totals.largest} stories, on ${dayMonth(totals.largestOn)}.`;
		}
	}
}

/** The share, in type, with the denominator it is a share of.
 *
 * There is no rate line on the chart. A day publishes a few hundred stories and
 * folds a handful, so the share runs at a few percent: on a 0 to 100 axis that
 * is a flat line two pixels off the floor, and on an axis fitted to it the
 * noise becomes drama. A real measurement that rounds away prints `<1`, never
 * `0` - a zero here would say nothing was folded, and something was.
 *
 * Null where there is no share to state: no days, or no fold.
 */
export function mergeRate(totals: MergeTotals, windowDays: number): string | null {
	if (totals.days === 0 || totals.merges === 0 || totals.published === 0) return null;
	const share = (totals.merges / totals.published) * 100;
	const printed = share < 0.5 ? '<1' : String(Math.round(share));
	return `That is ${printed}% of the ${grouped(totals.published)} stories ${span(windowDays)} published.`;
}
