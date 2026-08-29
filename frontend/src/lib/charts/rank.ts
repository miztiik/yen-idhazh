/** The arithmetic behind a ranked list, and the sentence that covers its tail.
 *
 * Five of the console's six tables sorted by date, so the row that cost the
 * digest the most articles sat wherever it happened to fall. This module is the
 * one place that ordering is decided: by magnitude, descending, always.
 *
 * It also owns the percentage a bar is drawn at. A bar is only readable for
 * absolute size if the divisor is on the page, so `max` comes out of here and
 * the list prints it. A component that picked its own divisor could disagree
 * with the number beside it, and nothing on screen would look wrong.
 *
 * The percentage leaves here as a finished CSS length rather than a number.
 * That is what keeps every display component free of a runtime import, so one
 * rounding rule serves the plain bar and the target bar, and a component can be
 * rendered on its own by a test.
 */

/** What every ranked row prints, whatever the section is about. */
export interface RankedDisplay {
	/** What the row is about. An entity, never a ledger column name. */
	label: string;
	/** The magnitude, already formatted with its unit. The list does no
	 * arithmetic on a number it is about to print. */
	value: string;
	/** A word beside the label - `rested`, `past the cap`. Colour is one signal
	 * and never the only one, so a row that means something says it. */
	status?: string | null;
	/** One short string: a denominator, the last outcome, the newest date. */
	context?: string | null;
}

export interface Rankable<T extends RankedDisplay> {
	/** Stable across a re-render, and what `onSelect` hands back. */
	key: string;
	/** The magnitude to rank by. A distance, a count, a share of a threshold -
	 * whatever the section's own question measures. Callers pass a magnitude,
	 * so a signed measure is made absolute before it gets here. */
	value: number;
	/** Broken ties are ranked by this, then by key. Without it two equal
	 * magnitudes could swap places between builds, and the prerendered page
	 * would move for no reason. */
	tiebreak?: number;
	row: T;
}

export interface RankedRow<T extends RankedDisplay> {
	key: string;
	value: number;
	/** `value / max` of the rendered set, 0 to 1. */
	fraction: number;
	/** The same fraction as a CSS length, for the bar's inline size. */
	percent: string;
	row: T;
}

export interface Ranked<T extends RankedDisplay> {
	rows: RankedRow<T>[];
	/** The divisor every fraction was taken against, and the number the list
	 * prints beside itself. Zero where nothing had a magnitude. */
	max: number;
	/** Entries the cap left off. */
	hidden: number;
	/** Their magnitudes summed, for the tail sentence. */
	hiddenValue: number;
	/** No entry carried a magnitude this list could rank. */
	empty: boolean;
}

/** A fraction as a CSS length.
 *
 * Clamped, because a track cannot draw a negative length and a bar cannot run
 * past its own end. Four decimals so a 1000px track lands on the same tenth of
 * a pixel every build - a percentage that drifts moves the prerendered page and
 * the byte gate reads it as a regression.
 */
export function percentOf(fraction: number): string {
	if (!Number.isFinite(fraction)) return '0%';
	const clamped = Math.min(1, Math.max(0, fraction));
	return `${(clamped * 100).toFixed(4)}%`;
}

/** Rank by magnitude and cap the list.
 *
 * An entry whose value is not a finite number is dropped rather than ranked: it
 * has no magnitude, so it has no place in an order and no share of a sum the
 * tail sentence would report.
 */
export function rank<T extends RankedDisplay>(
	entries: readonly Rankable<T>[],
	cap: number
): Ranked<T> {
	const measured = entries.filter((e) => Number.isFinite(e.value));
	const ordered = [...measured].sort(
		(a, b) =>
			b.value - a.value || (b.tiebreak ?? 0) - (a.tiebreak ?? 0) || a.key.localeCompare(b.key)
	);

	const kept = cap > 0 ? ordered.slice(0, cap) : ordered;
	const dropped = ordered.slice(kept.length);
	const max = kept.reduce((high, e) => Math.max(high, e.value), 0);

	return {
		rows: kept.map((e) => {
			const fraction = max > 0 ? e.value / max : 0;
			return { key: e.key, value: e.value, fraction, percent: percentOf(fraction), row: e.row };
		}),
		max,
		hidden: dropped.length,
		hiddenValue: dropped.reduce((sum, e) => sum + e.value, 0),
		empty: kept.length === 0
	};
}

/** The words the tail sentence needs. A sum of the hidden magnitudes is
 * reported only where adding them up means something: counts add, distances do
 * not. Leave the units out and the sentence says how many rows are missing and
 * nothing else. */
export interface TailNouns {
	/** `source` / `sources` - the thing the list ranks. */
	one: string;
	many: string;
	/** `cut` / `cuts` - what the magnitudes count. */
	unitOne?: string | null;
	unitMany?: string | null;
}

/** What the cap left out, in one sentence. Null where it left out nothing -
 * a sentence saying zero rows are hidden is a line the operator reads and
 * learns nothing from. */
export function tailSentence<T extends RankedDisplay>(
	ranked: Ranked<T>,
	nouns: TailNouns
): string | null {
	if (ranked.hidden <= 0) return null;
	const noun = ranked.hidden === 1 ? nouns.one : nouns.many;
	const head = `${ranked.hidden} more ${noun}`;

	if (!nouns.unitOne || !nouns.unitMany) {
		return ranked.hidden === 1 ? `${head} is not shown.` : `${head} are not shown.`;
	}

	const total = ranked.hiddenValue;
	const unit = total === 1 ? nouns.unitOne : nouns.unitMany;
	return ranked.hidden === 1
		? `${head} had ${total} ${unit}.`
		: `${head} had ${total} ${unit} between them.`;
}
