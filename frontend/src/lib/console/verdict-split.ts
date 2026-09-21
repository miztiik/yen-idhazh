/** What the judge said about the line, split at the line itself.
 *
 * Pure and browser safe on purpose: no config read, no disk, no `$lib` alias.
 * The `logic` group drives it with a written-down record and no build, so the
 * arithmetic is checked without a day off the archive (Guardrail #12).
 *
 * Separate from `merge-line.ts` because it answers a different question. That
 * file asks what a day did; this one asks what the whole record says about the
 * number the days were built with.
 */

/** One slot of the record, as the page reads it. */
export interface RecordSlot {
	binLow: number;
	same: number;
	different: number;
	unclear: number;
}

/** The record, reduced to what a page can draw. */
export interface ScoreRecord {
	bandLow: number;
	bandHigh: number;
	binWidth: number;
	slots: RecordSlot[];
	daysCounted: number;
}

/** The four cells of the 2x2, split at the line the day was built with. */
export interface VerdictSplit {
	/** At or above the line, and the judge said one story. */
	eligibleAgreed: number;
	/** At or above the line, and the judge said two. The expensive cell. */
	eligibleDisagreed: number;
	/** Below the line, and the judge said two. */
	refusedAgreed: number;
	/** Below the line, and the judge said one. */
	refusedDisagreed: number;
}

/** Split the record at the applied line and sum both verdicts on each side.
 *
 * **The cells say ELIGIBLE and never MERGED, because the record cannot tell the
 * difference and the words must not claim it can.** It holds counts in slots
 * rather than pairs, so splitting it says which side of the line a verdict fell
 * on and nothing more. Whether the day actually merged a pair depends on two
 * things the record never saw: a group is refused unless every pair inside it
 * clears the line, and two items on different published days never fold at all.
 * A cell labelled MERGED would overstate what happened, which is the exact class
 * of defect this page exists to catch.
 *
 * A pair scoring exactly the line merges, so the slot whose lower edge IS the
 * line sits on the eligible side.
 */
export function splitAtLine(record: ScoreRecord, applied: number): VerdictSplit {
	const split: VerdictSplit = {
		eligibleAgreed: 0,
		eligibleDisagreed: 0,
		refusedAgreed: 0,
		refusedDisagreed: 0
	};
	for (const slot of record.slots) {
		if (slot.binLow >= applied) {
			split.eligibleAgreed += slot.same;
			split.eligibleDisagreed += slot.different;
		} else {
			split.refusedDisagreed += slot.same;
			split.refusedAgreed += slot.different;
		}
	}
	return split;
}

/** What share of the pairs above the line the judge called two stories.
 *
 * The one number on this panel that moves in both directions. The other three
 * cells only ever rise, because the record only accumulates - four rising lines
 * would say the record got bigger, which is what the date axis already says.
 *
 * Null where nothing sits above the line. A share of nothing is not a zero.
 */
export function precisionMiss(split: VerdictSplit): number | null {
	const above = split.eligibleAgreed + split.eligibleDisagreed;
	if (above === 0) return null;
	return split.eligibleDisagreed / above;
}

/** The precision axis: zero to the discard share times the console's multiple.
 *
 * The fit places the line so that the discard share of judged two-story pairs
 * stays above it, so one percent is where this line should hover. Ten times that
 * shows the target and a tenfold overshoot on one fixed scale.
 */
export function precisionCorridor(discardShare: number, multiple: number): [number, number] {
	return [0, discardShare * multiple];
}

/** The lowest, middle and highest slot holding a verdict of one kind.
 *
 * Null where that verdict has never been recorded. Two ranges on one score axis
 * answer the question a reader actually brings - do the two populations still
 * separate? - where a 120-slot chart answered it with 240 marks in a 190 px
 * plot, changing by single counts a day.
 */
export function populationRange(
	record: ScoreRecord,
	verdict: 'same' | 'different'
): { min: number; median: number; max: number } | null {
	const held = record.slots.filter((slot) => slot[verdict] > 0);
	if (held.length === 0) return null;
	const total = held.reduce((count, slot) => count + slot[verdict], 0);
	let seen = 0;
	let median = held[0].binLow;
	for (const slot of held) {
		seen += slot[verdict];
		if (seen >= total / 2) {
			median = slot.binLow;
			break;
		}
	}
	return { min: held[0].binLow, median, max: held[held.length - 1].binLow };
}

/** One row of the rebinned table. */
export interface RebinnedRow {
	from: number;
	to: number;
	same: number;
	different: number;
	unclear: number;
}

/** The record rebinned to a width a person can read off a table.
 *
 * 120 slots at 0.001 becomes 24 rows at 0.005 - a fifth of the numbers, and the
 * resolution a reader can actually compare. Rows holding nothing are dropped: a
 * table where twenty of twenty-four rows are zero is a table nobody reads to the
 * end.
 */
export function rebin(record: ScoreRecord, width: number): RebinnedRow[] {
	const rows = new Map<number, { same: number; different: number; unclear: number }>();
	for (const slot of record.slots) {
		// The same tolerance `slot_index` carries, and for the same reason: an exact
		// edge divides a hair short in binary floating point and would file one
		// bucket low.
		const bucket = Math.floor((slot.binLow - record.bandLow) / width + 1e-9);
		const held = rows.get(bucket) ?? { same: 0, different: 0, unclear: 0 };
		rows.set(bucket, {
			same: held.same + slot.same,
			different: held.different + slot.different,
			unclear: held.unclear + slot.unclear
		});
	}
	return [...rows.entries()]
		.filter(([, counts]) => counts.same + counts.different + counts.unclear > 0)
		.sort(([left], [right]) => left - right)
		.map(([bucket, counts]) => ({
			from: record.bandLow + bucket * width,
			to: record.bandLow + (bucket + 1) * width,
			...counts
		}));
}
