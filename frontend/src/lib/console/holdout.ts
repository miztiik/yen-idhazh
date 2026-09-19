/** The pairs a person marked apart, and how much room the merge line has left.
 *
 * The holdout file is the floor every fitted line has to stay above. Nothing in
 * the pipeline has ever scored those marks - they are a person's reading, not a
 * judged pair - so the score is derived here and this is the first derivation
 * rather than a second opinion about one the run already wrote.
 *
 * **The margin is the panel.** It is the applied line minus the highest score
 * among the pairs marked as two stories. Positive means the line sits clear of
 * every mark; negative means the line would merge a pair somebody read as two
 * different events, and that is the one thing this file exists to say out loud.
 *
 * **A margin with no scale under it says nothing.** So this file also owns the
 * axis the margin is drawn on, the zone one day's legal fall opens below the
 * line, and how many marks that fall reaches. A distance is only a number until
 * something says how fast it can be spent.
 *
 * Pure and browser safe: no config read, no disk, no `$lib` alias. The `logic`
 * group drives every function here with written-down values, so the arithmetic
 * is checked without a day off the archive (Guardrail #12).
 */

/** What the score was computed under. Both terms come from the newest fitted
 * row where one exists, and from `config/idhazh.json` where none does. */
export interface ScoreWeights {
	cosineWeight: number;
	keyPointWeight: number;
	/** The date of the fitted row these weights came off, or null for the
	 * committed config. A weight with no date beside it is a number that rots. */
	fittedOn: string | null;
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
	/** Applied minus that score. Negative means the line would merge it. */
	margin: number | null;
	/** How many marked-apart pairs score at or above the line. */
	violations: number;
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

/** A block of text as the set of words the score counts, lower-cased.
 *
 * Mirrors `assemble._reduce`: compatibility-normalise, fold case, turn anything
 * that is not a letter, a digit or an underscore into a space. Two spellings of
 * one rule, in two languages, because no contract can be generated for a string
 * function - so the copy was measured against its source rather than asserted
 * (`docs/architecture/publishing/same-story.md`).
 *
 * **A combining mark is a separator here, as it is there.** Python's `\w` is
 * alphanumeric plus the underscore and a matra is neither, so a Devanagari word
 * splits at every matra. Keeping marks instead read like the kinder choice and
 * disagreed with the run on 3 of the 10,328 committed key-point blocks.
 */
export function reduceWords(text: string): string[] {
	const folded = text.normalize('NFKC').toLowerCase();
	const words = folded.replace(/[^\p{L}\p{N}_]+/gu, ' ').trim();
	return words === '' ? [] : words.split(' ');
}

/** What share of their key-point words two items have between them, 0 to 1.
 *
 * Shared words over the words they have between them - the same Jaccard share
 * `assemble.key_point_overlap` takes. Zero where either side reduces to
 * nothing, which is the honest answer for a term: no evidence rather than a
 * match, because the line is what decides and a term may not decide alone.
 */
export function keyPointOverlap(left: readonly string[], right: readonly string[]): number {
	const one = new Set(left);
	const other = new Set(right);
	if (one.size === 0 || other.size === 0) return 0;
	let shared = 0;
	for (const word of one) if (other.has(word)) shared += 1;
	return shared / (one.size + other.size - shared);
}

/** The weighted sum the merge line is applied to.
 *
 * The two terms and their two weights, and nothing else. The two overrides in
 * `assemble._pair_terms` - a matching reduced headline joining at 1.0, and a
 * clash of figures refusing outright - are not reproduced here, because neither
 * is a function of the line: they fire or they do not whatever the line is set
 * to, so neither can move the margin this panel measures.
 */
export function pairScore(cosine: number, keyPoints: number, weights: ScoreWeights): number {
	return weights.cosineWeight * cosine + weights.keyPointWeight * keyPoints;
}

/** The margin, the pair that sets it, and how many marks sit the wrong side.
 *
 * A pair scoring exactly the line merges - `assemble` refuses on
 * `score < floor_min` - so a mark AT the line is a violation. Put the
 * comparison the other way and the one pair sitting on the boundary is filed
 * as safe.
 */
export function holdoutMargin(applied: number, marks: readonly HoldoutMark[]): HoldoutMargin {
	const apart = marks.filter((mark) => !mark.sameStory);
	if (apart.length === 0) return { closest: null, margin: null, violations: 0 };
	let closest = apart[0]!;
	for (const mark of apart) if (mark.score > closest.score) closest = mark;
	return {
		closest,
		margin: applied - closest.score,
		violations: apart.filter((mark) => mark.score >= applied).length
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

/** How far below the line the score axis reaches, in days of legal fall.
 *
 * Two, because the sentence under the figure counts two: a mark inside one
 * day's fall is inside tomorrow's reach, and one inside two days is inside the
 * day after. An axis stopping at one day would print a count of marks it had
 * not drawn.
 */
export const DAYS_BELOW = 2;

/** And above the line, one day's fall.
 *
 * A mark above the line is the state this panel exists for, so it needs room to
 * be read in. One day's fall is the unit everything else here is measured in,
 * so the room above the line is that unit rather than a number picked to look
 * right.
 */
export const DAYS_ABOVE = 1;

/** The score axis: the line, two days' legal fall below it and one above.
 *
 * **Not the band.** On the 0.88 to 1.00 band the margin this panel exists to
 * draw is 0.0007 of a 0.12 span, so 95 percent of the box carries no ink and
 * the dot lands on top of the rule it is measured against. The band is already
 * the axis of `MergeLinePlot` further up the route, where it is the right
 * answer - that chart draws where the line has been, and this one draws how
 * much room it has left.
 *
 * Both ends are the line and a config knob, so the axis is the same width every
 * day and two days of this panel compare. A mark outside it is off the scale
 * and said to be, rather than widening the axis and shrinking the one part that
 * has to stay readable.
 */
export function holdoutDomain(applied: number, maxDownStep: number): [number, number] {
	return [applied - DAYS_BELOW * maxDownStep, applied + DAYS_ABOVE * maxDownStep];
}

/** The zone a mark inside is a pair tomorrow could fold: one day's fall, down.
 *
 * **Down only.** The clamp caps both directions, but only a fall folds a pair
 * the line refuses today - a rise folds fewer. A corridor drawn either side of
 * the line would tint scores tomorrow cannot reach.
 */
export function reachZone(applied: number, maxDownStep: number): [number, number] {
	return [applied - maxDownStep, applied];
}

/** How many marked-apart pairs sit on the wrong side of the line: as it stands,
 * after one day of legal fall, and after two. */
export interface HoldoutReach {
	today: number;
	tomorrow: number;
	dayAfter: number;
}

export function holdoutReach(
	applied: number,
	maxDownStep: number,
	marks: readonly HoldoutMark[]
): HoldoutReach {
	const apart = markedApart(marks);
	const wrongSide = (line: number): number =>
		apart.filter((mark) => mark.score >= line).length;
	return {
		today: wrongSide(applied),
		tomorrow: wrongSide(applied - maxDownStep),
		dayAfter: wrongSide(applied - DAYS_BELOW * maxDownStep)
	};
}

export type HoldoutState = 'no-marks' | 'no-fit' | 'clear' | 'violation';

/** Which of the four states the panel is in.
 *
 * `no-marks` means nobody has marked a pair, so there is nothing to hold the
 * line against. `no-fit` means marks exist and the rule is the line the newest
 * day was built with rather than one a fit chose.
 *
 * **A violation outranks the provenance note.** A marked-apart pair above the
 * line would be merged whether or not a fit has ever run, so a panel that said
 * "no day has fitted a line yet" and stopped there would hide the one state it
 * exists for. Where both are true the violation is the sentence and
 * `weightsNote` still says no day has fitted a line.
 */
export function holdoutState(margin: HoldoutMargin, fitted: boolean): HoldoutState {
	if (margin.closest === null) return 'no-marks';
	if (margin.violations > 0) return 'violation';
	return fitted ? 'clear' : 'no-fit';
}

/** The hue the panel takes: what it means, never how important it looks.
 *
 * `bad` where a mark is already on the wrong side. `warn` where none is yet and
 * one day's legal fall would put one there. A panel that looks the same
 * reporting a fault as reporting a clear day is the one thing this one may not
 * be, and the rule is the line the panel draws rather than the panel itself -
 * that rule stays neutral, because a setting is not a fault.
 */
export function holdoutTone(
	state: HoldoutState,
	reach: HoldoutReach
): 'neutral' | 'warn' | 'bad' {
	if (state === 'violation') return 'bad';
	return reach.tomorrow > reach.today ? 'warn' : 'neutral';
}

/** A margin as a distance, never as a signed number.
 *
 * The margin is negative in the violation state, so the raw value renders
 * `-0.0007 BELOW`, which reads as a double negative and a typo. The absolute
 * value goes in the figure and the word carries the direction.
 */
export function marginDistance(margin: number): string {
	return Math.abs(margin).toFixed(4);
}

/** The sentence under the panel, one per state. */
export function holdoutNote(
	margin: HoldoutMargin,
	state: HoldoutState,
	marked: number,
	applied: number
): string {
	switch (state) {
		case 'no-marks':
			return 'No pair has been marked by hand yet, so there is nothing to hold the line against.';
		case 'no-fit':
			return (
				`${marked} ${marked === 1 ? 'pair is' : 'pairs are'} marked by hand. No day has ` +
				'fitted a line yet, so the rule below is the line the newest day was built with.'
			);
		case 'violation': {
			const count = margin.violations;
			return (
				`The line is ${marginDistance(margin.margin ?? 0)} BELOW a pair a person marked ` +
				`as two stories, so it would merge them. ${count} hand-marked ` +
				`${count === 1 ? 'pair is' : 'pairs are'} on the wrong side of it.`
			);
		}
		default:
			return (
				`The line sits ${marginDistance(margin.margin ?? 0)} above the closest pair a ` +
				'person marked as two stories. No hand-marked pair is on the wrong side of it.' +
				// The line is in the sentence because the margin alone says how much
				// room there is and not where the room starts.
				` The line is at ${applied.toFixed(4)}.`
			);
	}
}

/** What the score was computed under, in one sentence.
 *
 * Printed beside the margin because a reader who changes a weight has to see
 * that the margin moved because the ruler moved. A score with no weights beside
 * it is a number that rots quietly.
 */
export function weightsNote(weights: ScoreWeights): string {
	const under =
		`Scored at ${weights.cosineWeight} on the cosine and ${weights.keyPointWeight} on the ` +
		'key points';
	return weights.fittedOn === null
		? `${under}, the weights in the committed config. No day has fitted a line yet.`
		: `${under}, the weights on the newest fitted day, ${weights.fittedOn}.`;
}

/** What one more day of legal fall would do, in one sentence.
 *
 * The figure on its own says how much room there is. It does not say how fast
 * that room can go, and it can go in one night - which is the whole reason the
 * margin is worth printing rather than the margin itself.
 */
export function reachNote(reach: HoldoutReach, maxDownStep: number, apart: number): string {
	const fall = `One day's legal fall is up to ${maxDownStep.toFixed(3)}`;
	const more = reach.tomorrow - reach.today;
	if (more === 0 && reach.dayAfter === reach.today) {
		return `${fall}, and no further mark is inside the next two days' reach.`;
	}
	return (
		`${fall}, so ${more} more ${more === 1 ? 'mark is' : 'marks are'} inside tomorrow's ` +
		`reach and ${reach.dayAfter} of ${apart} would be on the wrong side the day after.`
	);
}

/** The lowest, middle and highest of a set of scores. */
export interface MarkRange {
	min: number;
	median: number;
	max: number;
}

/** The range a population of scores covers, or null where it holds nothing.
 *
 * The lower median on an even count, which is the convention `populationRange`
 * takes on the verdict record - two strips on one route may not report a middle
 * two different ways.
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
 * A pair read as ONE story scoring below the line is a pair the run will not
 * fold, so the reader sees that story twice. It is the mirror of a violation,
 * and it is the reason the one-story marks are worth drawing at all: without
 * them the panel reports one of the two costs the line has.
 */
export function belowLine(scores: readonly number[], applied: number): number {
	return scores.filter((score) => score < applied).length;
}

/** The pairs read as one story, in one sentence. */
export function agreedNote(scores: readonly number[], applied: number): string {
	const at = scoreRange(scores);
	if (at === null) {
		return 'No pair has been read as one story yet, so there is no second population to draw.';
	}
	const below = belowLine(scores, applied);
	return (
		`${scores.length} ${scores.length === 1 ? 'pair was' : 'pairs were'} read as one story, ` +
		`running ${at.min.toFixed(4)} to ${at.max.toFixed(4)}. ${below} of them ` +
		`${below === 1 ? 'scores' : 'score'} below the line, so the reader would see those ` +
		'stories twice.'
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
