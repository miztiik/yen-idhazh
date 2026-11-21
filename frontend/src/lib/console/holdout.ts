/** The pairs a person marked apart, and how much room the merge line has left.
 *
 * The holdout marks are the floor the merge line has to stay above. Nothing in
 * the pipeline has ever scored those marks - they are a person's reading, not a
 * judged pair - so the score is derived here and this is the first derivation
 * rather than a second opinion about one the run already wrote.
 *
 * **The margin is the panel.** It is the line minus the highest score among the
 * pairs marked as two stories. Positive means the line sits clear of every
 * mark; negative means the score clears the line for a pair somebody marked
 * as two different events. This does not replay the grouping rules.
 * The line is the floor in the committed config: nothing fits or moves it.
 *
 * **A margin with no scale under it says nothing.** So this file also owns the
 * axis the margin is drawn on: the line, and a window of two configured
 * distances either side of it.
 *
 * Pure and browser safe: no config read, no disk, no `$lib` alias. The `logic`
 * group drives every function here with written-down values, so the arithmetic
 * is checked without a day off the archive (Guardrail #12).
 */
import { formatNumber, type NumberFormatConfig } from '../number-format';


/** What the score was computed under: the cosine's weight, read from the
 * committed config. */
export interface ScoreWeights {
	cosineWeight: number;
}

/** One hand-marked pair, scored. */
export interface HoldoutMark {
	leftTitle: string;
	rightTitle: string;
	/** True where a person read the two as one event. */
	sameStory: boolean;
	markedOn: string;
	note: string;
	/** The weighted score, under the weights above. */
	score: number;
}

/** A mark the day tree could not answer for, and the reason it could not. */
export interface HoldoutSkip {
	leftTitle: string;
	rightTitle: string;
	/** `no-day`, `no-item` or `no-vector`. */
	reason: string;
}

/** What the panel draws and what it says. */
export interface HoldoutMargin {
	/** The highest-scoring pair marked as two stories, or null where none is. */
	closest: HoldoutMark | null;
	/** The line minus that score. Negative means the score clears the line. */
	margin: number | null;
	/** How many marked-apart pairs score at or above the line. */
	violations: number;
	/** How many pairs are marked as two stories: what the margin is the closest of. */
	pairs: number;
}

/** Cosine between two stored int8 vectors, without decoding either of them.
 *
 * The quantisation scale cancels - dividing both vectors by it divides the dot
 * product and both norms by it too - so the angle between two stored vectors is
 * the angle between the unit vectors they decode to. `assemble.cosine_int8` is
 * the same arithmetic on the runner, and a test there asserts the two readings
 * agree rather than leaving it as a claim.
 *
 * Zero on a width mismatch. Two vectors of different widths are two encoders,
 * and a truncated dot product over them is a number that looks like a score.
 */
export function cosineInt8(left: Int8Array, right: Int8Array): number {
	if (left.length === 0 || left.length !== right.length) return 0;
	let dot = 0;
	let leftSum = 0;
	let rightSum = 0;
	for (let index = 0; index < left.length; index += 1) {
		const one = left[index]!;
		const other = right[index]!;
		dot += one * other;
		leftSum += one * one;
		rightSum += other * other;
	}
	const norms = (Math.sqrt(leftSum) || 1) * (Math.sqrt(rightSum) || 1);
	return dot / norms;
}

/** The score the merge line is applied to.
 *
 * The one term and its weight, and nothing else. The two overrides in
 * `assemble._pair_terms` - a matching reduced headline joining at 1.0, and a
 * clash of figures refusing outright - are not reproduced here, because neither
 * is a function of the line: they fire or they do not whatever the line is set
 * to, so neither can move the margin this panel measures.
 */
export function pairScore(cosine: number, weights: ScoreWeights): number {
	return weights.cosineWeight * cosine;
}

/** The margin, the pair that sets it, and how many marks sit the wrong side.
 *
 * A pair scoring exactly the line clears the score check - `assemble` refuses on
 * `score < floor_min` - so a mark AT the line is a violation. Put the
 * comparison the other way and the one pair sitting on the boundary is filed
 * as safe.
 */
export function holdoutMargin(line: number, marks: readonly HoldoutMark[]): HoldoutMargin {
	const apart = marks.filter((mark) => !mark.sameStory);
	if (apart.length === 0) return { closest: null, margin: null, violations: 0, pairs: 0 };
	let closest = apart[0]!;
	for (const mark of apart) if (mark.score > closest.score) closest = mark;
	return {
		closest,
		margin: line - closest.score,
		violations: apart.filter((mark) => mark.score >= line).length,
		pairs: apart.length
	};
}

/** The marked-apart pairs, highest first.
 *
 * The first is the closest call and the last has the most room, which is what
 * the panel labels. The rest carry a title and no label: four labels inside one
 * row of dots is four strings nobody can read.
 */
export function markedApart(marks: readonly HoldoutMark[]): HoldoutMark[] {
	return marks.filter((mark) => !mark.sameStory).sort((left, right) => right.score - left.score);
}

/** The score axis: the line, a configured distance below it and another above.
 *
 * **Not the band.** On the 0.88 to 1.00 band the margin this panel exists to
 * draw is 0.0007 of a 0.12 span, so 95 percent of the box carries no ink and
 * the dot lands on top of the rule it is measured against. This chart draws
 * how much room the line has, which is a question about a distance.
 *
 * Both ends are the line and a route knob, so the axis is the same width every
 * day and two days of this panel compare. A mark outside it is off the scale
 * and said to be, rather than widening the axis and shrinking the one part that
 * has to stay readable. The window reaches further below the line than above
 * it: a mark below the line is the clear state and wants context, a mark above
 * it is the state this panel exists for and needs room only to be read in.
 */
export function holdoutDomain(line: number, below: number, above: number): [number, number] {
	return [line - below, line + above];
}

export type HoldoutState = 'no-marks' | 'clear' | 'violation';

/** Which of the three states the panel is in.
 *
 * `no-marks` means nobody has marked a pair, so there is nothing to hold the
 * line against. `violation` means a pair marked as two stories scores at or
 * above the line. `clear` is every other day.
 */
export function holdoutState(margin: HoldoutMargin): HoldoutState {
	if (margin.closest === null) return 'no-marks';
	return margin.violations > 0 ? 'violation' : 'clear';
}

/** The hue the panel takes: what it means, never how important it looks.
 *
 * `bad` where a mark is on the wrong side of the line. A panel that looks the
 * same reporting a fault as reporting a clear day is the one thing this one may
 * not be, and the rule is the line the panel draws rather than the panel itself
 * - that rule stays neutral, because a setting is not a fault.
 */
export function holdoutTone(state: HoldoutState): 'neutral' | 'bad' {
	return state === 'violation' ? 'bad' : 'neutral';
}

/** A margin as a distance, never as a signed number.
 *
 * The margin is negative in the violation state, so the raw value renders
 * `-0.0007 BELOW`, which reads as a double negative and a typo. The absolute
 * value goes in the figure and the word carries the direction.
 */
export function marginDistance(margin: number, numberFormat: NumberFormatConfig): string {
	return formatNumber(Math.abs(margin), numberFormat, { si: false });
}

/** The sentence under the panel, one per state.
 *
 * It counts the pairs a person marked as two stories because the margin is the
 * closest of them: a distance with no population beside it says how little room
 * there is and not how many marks that room is measured against.
 */
export function holdoutNote(
	margin: HoldoutMargin,
	state: HoldoutState,
	line: number,
	numberFormat: NumberFormatConfig
): string {
	const distance = marginDistance(margin.margin ?? 0, numberFormat);
	const among = margin.pairs === 1 ? 'the one pair' : `the highest-scoring of the ${margin.pairs} pairs`;
	switch (state) {
		case 'no-marks':
			return 'No scored pair marked as two stories was returned, so there is no measured margin.';
		case 'violation': {
			const count = margin.violations;
			return (
				`The line is ${distance} BELOW ${among} a person marked as two stories.` +
				(margin.pairs === 1
					? ' Its score clears the line.'
					: ` ${count} of the ${margin.pairs} ${count === 1 ? 'scores' : 'score'} at or above it.`)
			);
		}
		default:
			return (
				`The line sits ${distance} above ${among} a person marked as two stories` +
				(margin.pairs === 1 ? '.' : `, so none of the ${margin.pairs} is on the wrong side of it.`) +
				// The line is in the sentence because the margin alone says how much
				// room there is and not where the room starts.
				` The line is at ${formatNumber(line, numberFormat, { si: false })}.`
			);
	}
}

/** What the score was computed under, in one sentence.
 *
 * Printed beside the margin because a reader who changes the weight has to see
 * that the margin moved because the ruler moved. A score with no weight beside
 * it is a number that rots quietly.
 */
export function weightsNote(weights: ScoreWeights): string {
	return `Scored at ${weights.cosineWeight} on the cosine, the weight in the committed config.`;
}

/** The lowest, middle and highest of a set of scores. */
export interface MarkRange {
	min: number;
	median: number;
	max: number;
}

/** The range a population of scores covers, or null where it holds nothing.
 *
 * The lower median on an even count, so the middle is always a score somebody
 * marked rather than the mean of two.
 */
export function scoreRange(scores: readonly number[]): MarkRange | null {
	if (scores.length === 0) return null;
	const sorted = [...scores].sort((left, right) => left - right);
	return {
		min: sorted[0]!,
		median: sorted[Math.floor((sorted.length - 1) / 2)]!,
		max: sorted[sorted.length - 1]!
	};
}

/** How many of a population sit below the line.
 *
 * A pair read as ONE story scoring below the line does not qualify by score.
 * It is the mirror of a violation,
 * and it is the reason the one-story marks are worth drawing at all: without
 * them the panel reports one of the two costs the line has.
 */
export function belowLine(scores: readonly number[], line: number): number {
	return scores.filter((score) => score < line).length;
}

/** The pairs read as one story, in one sentence. */
export function agreedNote(
	scores: readonly number[],
	line: number,
	numberFormat: NumberFormatConfig
): string {
	const at = scoreRange(scores);
	if (at === null) {
		return 'No scored pair marked as one story was returned, so there is no second population to draw.';
	}
	const below = belowLine(scores, line);
	return (
		`${scores.length} ${scores.length === 1 ? 'pair was' : 'pairs were'} read as one story, ` +
		`running ${formatNumber(at.min, numberFormat, { si: false })} to ${formatNumber(at.max, numberFormat, { si: false })}. ${below} of them ` +
		`${below === 1 ? 'scores' : 'score'} below the line.`
	);
}

/** What the day tree could not answer, in one sentence, or null where it
 * answered everything.
 *
 * A blank dot would say the margin is fine. A counted skip says the mark could
 * not be checked, which is a different fact and the one an operator can act on.
 */
export function skipNote(skipped: readonly HoldoutSkip[]): string | null {
	if (skipped.length === 0) return null;
	const reasons = new Set(skipped.map((skip) => skip.reason));
	return (
		`${skipped.length} marked ${skipped.length === 1 ? 'pair' : 'pairs'} could not be ` +
		`checked against the day tree: ${[...reasons].sort().join(', ')}. ` +
		'A mark whose article is no longer published is not a mark that passed.'
	);
}
