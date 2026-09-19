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

// --- Where the merge line sits -------------------------------------------------

/** One day's fitted row, reduced to what the chart draws. */
export interface LineDay {
	date: string;
	previous: number;
	proposed: number | null;
	applied: number;
	clampKind: string;
	heldReason: string;
	maxDownStep: number;
	maxUpStep: number;
}

/** The score axis: the whole range a fitted line may take, and never the data.
 *
 * Fixed by two config knobs on purpose. After the first fortnight the line moves
 * under 0.002 a day - auto-scaled, that fills the panel top to bottom and a
 * normal day reads as an incident. On a 0-to-1 axis the same move is a fifth of
 * a pixel and the chart is a flat line whether or not anything is happening. The
 * corridor is the answer to both: a normal day looks flat, and the reader can
 * see it is flat against a scale that would have shown a real move.
 */
export function corridorOf(knobs: { band_low: number; band_high: number }): [number, number] {
	return [knobs.band_low, knobs.band_high];
}

/** The envelope a day's move was allowed to land in, per day.
 *
 * Drawn behind the applied line, because without it the dotted proposal leaving
 * the band is a dotted line going somewhere and a reader cannot see which side
 * of the limit it is on. `low` is `previous - max_down_step` and `high` is
 * `previous + max_up_step`: both directions are capped, and the fall cap is the
 * wider of the two, so the envelope is taller below the line than above it.
 */
export function clampEnvelope(days: readonly LineDay[]): { low: number; high: number }[] {
	return days.map((day) => ({
		low: day.previous - day.maxDownStep,
		high: day.previous + day.maxUpStep
	}));
}

/** How the clamp behaved over the window, in one sentence.
 *
 * The clamp gets no panel of its own: a panel titled "the clamp" would draw a
 * bar chart of a word. The dotted line outside the band IS the clamp firing, in
 * the one place a reader is already looking. What the reader would lose is the
 * count, so the count is here.
 */
export function clampNote(days: readonly LineDay[], windowDays: number): string {
	const held = days.filter((day) => day.clampKind !== 'none').length;
	if (held === 0) {
		return `The clamp has not held the line back on any of the last ${windowDays} days.`;
	}
	return `The clamp held the line back on ${held} of the last ${windowDays} days.`;
}

/** How many days in the window fitted nothing, in one sentence, or null.
 *
 * A held day breaks the proposed series rather than joining across it: a line
 * drawn through a day nothing was fitted on claims a measurement nobody took.
 * The applied line does continue, because the line really was applied.
 */
export function heldNote(days: readonly LineDay[], windowDays: number): string | null {
	const held = days.filter((day) => day.heldReason !== 'none').length;
	if (held === 0) return null;
	return `Nothing was fitted on ${held} of these ${windowDays} days.`;
}

// --- Whether the judge agrees with itself, and what the record still needs ------

/** One day's judge health and one day's record fill, off the same fitted row. */
export interface JudgeDay {
	date: string;
	/** What share of the judged pairs the two readings disagreed about. */
	disagreementRate: number;
	/** What share of the agreed readings were UNCLEAR. */
	unclearRate: number;
	/** How many pairs a judging leg actually read. The denominator both rates
	 * are a share of, so a panel can print it in the same sentence. */
	pairsJudged: number;
	negativesOnRecord: number;
	aboveLineOnRecord: number;
	daysOnRecord: number;
	heldReason: string;
}

/** The two limits that hold a run, as the chart draws them. */
export interface AgreementLimits {
	disagreementMax: number;
	unclearMax: number;
}

/** The three gates, as the count they hold and the count they need. */
export interface GateNeed {
	label: string;
	value: number;
	target: number;
	/** The phrase under the marker. Words, never the knob's own name. */
	targetText: string;
}

/** The agreement axis: zero to the looser of the two limits, never the data.
 *
 * Both rates are bounded by the two knobs that hold the run, and the looser of
 * the two carries both series and both markers. Not 0 to 1: neither rate can
 * reach 1 without the run holding first, so half the plot would be a region the
 * data cannot enter. Not fitted to the data either - a rate of 0.02 drawn full
 * height says the judge is in trouble when it is not.
 */
export function agreementCorridor(limits: AgreementLimits): [number, number] {
	return [0, Math.max(limits.disagreementMax, limits.unclearMax)];
}

/** The three bars, in the order the record fills them.
 *
 * The negatives first, because it is the one that takes longest. The days next,
 * because it is the one a reader can predict. The pairs above the line last,
 * because it is the one that moves when the line moves.
 */
export function gateNeeds(
	newest: JudgeDay | null,
	gates: { minimumNegatives: number; minimumDays: number; minimumAboveLine: number }
): GateNeed[] {
	return [
		{
			label: 'Readings the record holds',
			value: newest?.negativesOnRecord ?? 0,
			target: gates.minimumNegatives,
			targetText: `${gates.minimumNegatives} needed before a line may be fitted`
		},
		{
			label: 'Days the record has folded',
			value: newest?.daysOnRecord ?? 0,
			target: gates.minimumDays,
			targetText: `${gates.minimumDays} needed, so one fortnight of one kind of news cannot set the line`
		},
		{
			label: 'Pairs judged at or above the line',
			value: newest?.aboveLineOnRecord ?? 0,
			target: gates.minimumAboveLine,
			targetText: `${gates.minimumAboveLine} needed - these are the whole precision reading`
		}
	];
}

/** What one square on the strip says about one date. */
export type FoldState = 'fitted' | 'filling' | 'held' | 'silent';

export interface FoldSquare {
	date: string;
	state: FoldState;
	/** The sentence the square carries, so colour is never the only signal. */
	title: string;
}

/** One square a date across the window, including the dates nothing recorded.
 *
 * Every date is present whether or not a run wrote a row, because a gap is the
 * fact the strip exists to show - a strip built from the rows would draw a
 * shorter, tidier picture of a record that had stopped filling.
 *
 * **A held day while the gates are still unfilled is not a warning.** It is the
 * design working. Painting it amber would put ten amber squares on the panel's
 * first fortnight and burn the colour before it ever meant anything, so the
 * warning fill arrives only once the gates are met and a hold stops being
 * expected.
 */
export function foldDays(
	dates: readonly string[],
	rows: readonly JudgeDay[],
	gatesMet: boolean
): FoldSquare[] {
	const byDate = new Map(rows.map((row) => [row.date, row]));
	return dates.map((date) => {
		const row = byDate.get(date);
		if (row === undefined) {
			return { date, state: 'silent', title: `${date}: no run recorded anything.` };
		}
		if (row.heldReason === 'none') {
			return { date, state: 'fitted', title: `${date}: a line was fitted.` };
		}
		if (!gatesMet) {
			return { date, state: 'filling', title: `${date}: the record was still filling.` };
		}
		return {
			date,
			state: 'held',
			title: `${date}: nothing was fitted. ${heldInWords(row.heldReason)}.`
		};
	});
}

/** A hold reason as a reader reads it. The ledger's own word never reaches a page. */
export function heldInWords(reason: string): string {
	switch (reason) {
		case 'sheet_too_small':
			return 'The record did not hold enough to fit on';
		case 'inputs_changed':
			return 'The encoder or the ask moved, so the record was started again';
		case 'judge_unstable':
			return 'The two readings disagreed too often to trust';
		case 'judge_uncertain':
			return 'Too many readings could not tell';
		case 'legs_missing':
			return 'One of the judging legs did not report';
		default:
			return 'The run held the line';
	}
}

/** How many days at the newest end of the strip recorded nothing at all. */
export function silentTail(squares: readonly FoldSquare[]): number {
	let count = 0;
	for (let index = squares.length - 1; index >= 0; index -= 1) {
		if (squares[index].state !== 'silent') break;
		count += 1;
	}
	return count;
}

/** A share as a whole percent with the denominator it is a share of.
 *
 * Null under `min_attempts_for_rate`: a share over four pairs is not a
 * measurement, and printing one invites a decision the evidence cannot carry.
 * The counts still print - that is the rule `FailurePanels` already runs on.
 */
export function rateWithDenominator(
	numerator: number,
	denominator: number,
	floor: number
): string | null {
	if (denominator < floor) return null;
	return `${Math.round((numerator / denominator) * 100)}% of ${denominator} pairs`;
}
