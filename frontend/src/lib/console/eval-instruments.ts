/** Every instrument the eval ledger writes, and the console panel that answers for it.
 *
 * The pipeline has scored a faithfulness number on every summary since the first
 * day it published, and it had never been drawn. The band was drawn, and a band
 * is a verdict: it says a summary was doubted and never says by how much, so a
 * prompt change that moved every score four points without moving a single band
 * looked like it did nothing.
 *
 * **The map below is the point of this module, not the charts.** `DRAWN_BY`
 * assigns each drawn measurement to exactly one panel, `UNDRAWN` names a
 * measurement no panel reads from this ledger, and `NOT_A_MEASUREMENT` names identities. The three
 * together must cover the contract exactly - the native frontend-list binding
 * reads `EvalRow` and fails on a column that is in neither,
 * in both, or in a map and not in the contract. So a column added to `EvalRow`
 * next month fails a test instead of quietly going undrawn for a year, which is
 * how `hhem` got here.
 *
 * **Only the agreed thresholds are drawn.** The faithfulness plot carries a rule
 * at each of the two scores the pipeline bands a summary on, because those two
 * decide what a published item says about itself - a panel that drew its own
 * line would be inventing one. Every other instrument here still sets no alarm:
 * no threshold, no red, no band tint, no polarity. Draw the numbers, and borrow
 * a threshold only where somebody already agreed it.
 *
 * Relative imports only, and no `$lib` alias, so the browser suite can import
 * this module in plain Node and re-derive every drawn figure from the ledger
 * without standing up Vite.
 */

import { BANDS } from '../bands';
import { grouped } from '../charts/series';
import type { NumberFormatConfig } from '../number-format';
import type { StackRule } from '../charts/stack-types';

/** Which panel answers for which ledger column.
 *
 * One receiver each, naming the surface that actually reads the measurement.
 */
export const DRAWN_BY: Readonly<Record<string, string>> = {
	truncation_flagged: 'daily-figures',
	hhem: 'faithfulness',
	hhem_full: 'faithfulness',
	hhem_delta: 'faithfulness',
	compression: 'summary-length',
	coherence: 'daily-figures',
	summary_words: 'summary-length',
	score_ms: 'score-cost'
};

/** Recorded measurements no panel reads from this ledger. Each says why. */
export const UNDRAWN: Readonly<Record<string, string>> = {
	band: 'The mixed historical confidence aggregate is not drawn or reinterpreted as HHEM.',
	extraction_suspect: 'The extraction class, flag and yield diagnostic is removed; the flag remains recorded.',
	source_words_before_cap: 'The article length before the cap. The article record holds the same fact and the console reads cuts from there.',
	source_words: 'The article length after the cap. The article record holds the same fact and the console reads cuts from there.'
};

/** Every remaining column, and why no panel owes it a number.
 *
 * Each of these says *which* row this is, not *how it went*. A panel drawing one
 * would draw an identifier over time, which is a chart of nothing.
 */
export const NOT_A_MEASUREMENT: Readonly<Record<string, string>> = {
	version: 'The schema stamp the row was written under.',
	date: 'Which day. It is the x axis of every panel above, never a value on one.',
	run_id: 'Which execution wrote the row.',
	item_id: 'Which slot on that day\'s page the summary was published in.',
	url_key: 'The key the ledger joins to the published item on.',
	source_url: 'The address the article was read from.',
	title: 'The headline, carried so a row can be read without a second file.',
	vertical: 'Which desk the article belongs to.',
	model_id: 'Which model wrote the summary.',
	pipeline_fingerprint:
		'A digest of the declared settings, on rows written before 2026-09-12 and blank after. It has no direction to plot. Historical setting-change markers retain this identity for days recorded before named input manifests.',
	output_digest: 'A digest of the summary, kept so a re-run can be proved identical.',
	source_digest: 'A digest of the article text, kept for the same reason.',
	scorer_version: 'Which checker ran. It says the instrument changed, not that the summaries did.',
	scored_at: 'When the check ran, which is not always the day it scored.',
	summary_attempt:
		'Which try wrote the summary. Measured 2026-09-06 over 6,966 rows: every one of them is the first try.'
};

/** The ledger rows this module reads, every cell as text. */
export type EvalInput = Readonly<Record<string, string | undefined>>;

/** An instrument the pipeline records and nothing acts on. */
export interface RecordedInstrument {
	/** The ledger column. */
	id: string;
	unit: 'percent' | 'cosine';
	/** What the daily table calls it. Absent where another panel draws the
	 * instrument in its own words. */
	label?: string;
	/** What the number is, and which way is bad, in the reader's words. Printed
	 * with `label`. */
	note?: string;
}

/** The retained recorded instruments, each with its own unit. */
export const RECORDED: readonly RecordedInstrument[] = [
	{ id: 'compression', unit: 'percent' },
	{
		id: 'coherence',
		label: 'Summary sentences that follow one another',
		unit: 'cosine',
		note: 'How close each sentence sits to the one before it, from -1 to 1. A summary that says the same thing twice scores near the top, so it is a poor thing to judge one by.'
	}
];

/** One day of the ledger, reduced to the retained measurements.
 *
 * Percents are whole numbers, and that is the whole reason the reductions happen
 * here rather than in the page: a raw score between zero and one is the checker's
 * unit, not a reader's, and it has never once told anybody what to do.
 */
export interface EvalDay {
	date: string;
	/** Summaries that day carrying a faithfulness score. */
	matched: number;
	/** Faithfulness, whole percent: lower quartile (p25), median (p50), upper quartile (p75). */
	matchLow: number | null;
	matchMid: number | null;
	matchHigh: number | null;
	/** Summaries that score differently when the whole article is used instead. */
	widerDiffers: number;
	/** The widest such gap that day, in whole percentage points. */
	widestGap: number;
	/** The middle summary's reading on each recorded instrument, in its own unit. */
	recorded: Readonly<Record<string, number | null>>;
}

/** The distinct-published counts a run settled for one day.
 *
 * A re-score or scored-then-dropped item inflates the ledger row count.
 * Publication counts its distinct set once. Keyed by date in the map
 * `modelWork` takes.
 */
export interface DayScoredCounts {
	/** Distinct published items the checker scored - replaces the row count. */
	scored: number;
}

/** A cell that is present and reads as a number, or null.
 *
 * An absent cell and a cell holding a blank are the same fact - the checker did
 * not write a reading - and both have to stay out of a median rather than enter
 * it as a zero.
 */
function measured(value: string | undefined): number | null {
	if (value === undefined || value.trim() === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

/** The value at a fraction of a sorted list, by position and never by averaging.
 *
 * Nearest-rank on purpose. An interpolated median is a number no summary
 * actually scored, and the browser oracle has to be able to re-derive this by
 * hand from a shard without reimplementing a quantile rule.
 */
function at(sorted: readonly number[], fraction: number): number {
	const index = Math.min(sorted.length - 1, Math.floor(fraction * sorted.length));
	return sorted[index];
}

/** A score between zero and one, as a whole percent. */
function pct(value: number): number {
	return Math.round(value * 100);
}

/** A cosine kept on its own scale, to two places.
 *
 * Not a percent. It runs from -1 to 1 and has no denominator, so the reader is
 * shown the number the encoder produced rather than a share of nothing.
 */
function toTwoPlaces(value: number): number {
	return Math.round(value * 100) / 100;
}

/** Every day the ledger holds, oldest first, reduced.
 *
 * Rows carrying no date are dropped rather than pooled into an empty day: a
 * ledger row with no day is a broken row, and giving it a column would draw it.
 */
export function evalDays(rows: readonly EvalInput[]): EvalDay[] {
	const byDate = new Map<string, EvalInput[]>();
	for (const row of rows) {
		const date = (row.date ?? '').trim();
		if (date === '') continue;
		const found = byDate.get(date);
		if (found) found.push(row);
		else byDate.set(date, [row]);
	}

	const days: EvalDay[] = [];
	for (const date of [...byDate.keys()].sort()) {
		const group = byDate.get(date) ?? [];
		const match: number[] = [];
		let widerDiffers = 0;
		let widestGap = 0;
		const recordedValues = new Map<string, number[]>();
		for (const instrument of RECORDED) recordedValues.set(instrument.id, []);

		for (const row of group) {
			const hhem = measured(row.hhem);
			if (hhem !== null) match.push(hhem);
			const delta = measured(row.hhem_delta);
			if (delta !== null && delta !== 0) {
				widerDiffers += 1;
				widestGap = Math.max(widestGap, Math.abs(delta));
			}
			for (const instrument of RECORDED) {
				const value = measured(row[instrument.id]);
				if (value !== null) recordedValues.get(instrument.id)?.push(value);
			}
		}

		match.sort((a, b) => a - b);
		const recorded: Record<string, number | null> = {};
		for (const instrument of RECORDED) {
			const values = (recordedValues.get(instrument.id) ?? []).sort((a, b) => a - b);
			if (values.length === 0) {
				recorded[instrument.id] = null;
				continue;
			}
			const middle = at(values, 0.5);
			recorded[instrument.id] =
				instrument.unit === 'percent' ? pct(middle) : toTwoPlaces(middle);
		}

		days.push({
			date,
			matched: match.length,
			matchLow: match.length === 0 ? null : pct(at(match, 0.25)),
			matchMid: match.length === 0 ? null : pct(at(match, 0.5)),
			matchHigh: match.length === 0 ? null : pct(at(match, 0.75)),
			widerDiffers,
			widestGap: pct(widestGap),
			recorded
		});
	}
	return days;
}

/** The two scores the pipeline bands a published summary on, as whole percents.
 *
 * Whole percents because the plot is in whole percents. The pipeline holds them
 * as scores between zero and one in `evaluation.band_high_min` and
 * `evaluation.band_medium_min`, and the page converts once, here, so the rule a
 * reader sees and the rule a run applied cannot be two different numbers.
 */
export interface MatchThresholds {
	/** At or above this a published item says it matches its source. */
	high: number;
	/** Below this a published item says it may not. */
	low: number;
}

/** How the value axis is bounded, where the data alone would mislead.
 *
 * Two knobs rather than three: the floor's lower bound is the doubt edge above,
 * because below it every summary carries the same band and there is nothing
 * left to zoom into.
 */
export interface MatchAxis {
	/** The grain the floor rounds down to, and the headroom left under the
	 * lowest drawn point. */
	step: number;
	/** The floor never rises above this, so a fixed share of the scale is always
	 * on screen and a flat fortnight cannot be magnified into a crisis. */
	floorMax: number;
}

/** The value axis floor, so the plot fills with the range the days actually hold.
 *
 * A fixed zero floor drew fifteen days of 73 to 95 percent inside the top
 * quarter of the panel, where a four-point move is two pixels. This rounds down
 * to the step below the lowest point drawn and then bounds it both ways.
 *
 * The lower bound is the doubt edge and the upper is `floorMax`. There is one
 * more rule and it outranks both: **the floor never hides a mark.** A day whose
 * lower quartile (p25) fell under the doubt edge is exactly the day an operator opened
 * the panel for, and an axis that clipped it would answer a worse question than
 * the one it was asked.
 */
export function matchFloor(
	days: readonly Pick<EvalDay, 'matchMid' | 'matchLow'>[],
	thresholds: MatchThresholds,
	axis: MatchAxis
): number {
	const values = days
		.flatMap((day) => [day.matchMid, day.matchLow])
		.filter((value): value is number => value !== null);
	if (values.length === 0) return axis.floorMax;
	const down = (value: number) => Math.floor(value / axis.step) * axis.step;
	const lowest = Math.min(...values);
	const bounded = Math.min(Math.max(down(lowest - axis.step), thresholds.low), axis.floorMax);
	return Math.min(bounded, down(lowest));
}

/** The confidence rules the operator plot can actually draw.
 *
 * The labels come from the shared confidence vocabulary. The
 * confidence ramp is lent to these two and to nothing else on the panel: it is
 * a threshold somebody agreed to, which is the only case the console lends it
 * (`docs/concepts/console-design/what-the-quality-and-source-panels-draw.md`).
 *
 * A rule under the floor is dropped rather than handed over. The floor rises to
 * fill the panel with the range the days hold, and on the committed record that
 * puts it at 65 percent - above the doubt score. The engine clips a rule outside
 * the axis, so passing it anyway draws nothing and claims a line a reader cannot
 * find. The doubt rule appears on the day it matters, because the floor drops to
 * meet a figure beneath it.
 */
export function matchRules(thresholds: MatchThresholds, floor: number): StackRule[] {
	const rules: StackRule[] = [
		{
			at: thresholds.high,
			label: `${thresholds.high}% and up: ${BANDS.high.label.toLowerCase()}`,
			side: 'above',
			token: '--band-high'
		},
		{
			at: thresholds.low,
			label: `under ${thresholds.low}%: ${BANDS.low.label.toLowerCase()}`,
			side: 'below',
			token: '--band-low'
		}
	];
	return rules.filter((rule) => rule.at >= floor);
}

/** What the whole window holds, so a sentence never re-walks the days itself. */
export interface EvalTotals {
	matched: number;
	widerDiffers: number;
	widestGap: number;
}

export function evalTotals(days: readonly EvalDay[]): EvalTotals {
	let matched = 0;
	let widerDiffers = 0;
	let widestGap = 0;
	for (const day of days) {
		matched += day.matched;
		widerDiffers += day.widerDiffers;
		widestGap = Math.max(widestGap, day.widestGap);
	}
	return { matched, widerDiffers, widestGap };
}

/** What the second faithfulness column says, in words, or null where it says nothing.
 *
 * The checker scores the summary twice - once against the text the machine was
 * given, once against the whole article - and the second column exists so a
 * summary that only looks faithful because the article was cut cannot pass. The
 * gap between them is the reading, so the panel says how often there is one. It
 * says it only where the two readings part: a sentence that reads "the same" on
 * nearly every window is one an operator learns to skip.
 */
export function widerNote(
	days: readonly EvalDay[],
	numberFormat: NumberFormatConfig
): string | null {
	const totals = evalTotals(days);
	if (totals.matched === 0 || totals.widerDiffers === 0) return null;
	return `Scored against the whole article instead of the part the machine read, ${grouped(totals.widerDiffers, numberFormat)} of these ${grouped(totals.matched, numberFormat)} summaries score differently, by up to ${totals.widestGap} points.`;
}
