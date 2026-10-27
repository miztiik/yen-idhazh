/** Which configured lens ids have a reader-facing name? */
import taxonomy from '../../../../config/taxonomy.json' with { type: 'json' };

export const LENS_NAMES: Readonly<Record<string, string>> = Object.fromEntries(
	taxonomy.lenses.map((lens) => [lens.id, lens.display_name] as const)
);

/** How many chips one item may show.
 *
 * Three of "Trade and tariffs" length wrap the eyebrow on a 390px screen. The
 * reader loses the third word on a rare three-lens story and keeps a one-line
 * eyebrow on every item on every phone.
 */
export const MAX_LENS_CHIPS = 2;

/** The lenses an item shows: named ones in taxonomy order, then the rest, capped.
 *
 * An id this file cannot name is kept rather than dropped, and that is the
 * whole of the change made on 2026-09-12 when lens ids became open slugs. A
 * filter on known-ness reads as tidiness and is really a silent edit of a day:
 * it is how 18 items carrying a retired `ai-roi` came to render one chip fewer
 * than their own payload held, with nothing failing anywhere. Deleting an entry
 * from `config/taxonomy.json` - rather than retiring it - is what takes a name
 * away, and the drift test above is what makes that a deliberate act.
 *
 * Named first so the cap spends its two slots on words a reader can read. The
 * order inside the named group is the taxonomy's, not the payload's, so a
 * re-run cannot reorder a day.
 */
export function shownLenses(lenses: readonly string[] | undefined): string[] {
	if (!lenses?.length) return [];
	const named = Object.keys(LENS_NAMES).filter((id) => lenses.includes(id));
	const unnamed = lenses.filter((id) => !(id in LENS_NAMES));
	return [...named, ...unnamed].slice(0, MAX_LENS_CHIPS);
}

/** What a chip says: the committed display name, or the raw id when there is none.
 *
 * The raw id is deliberately ugly. It is only reachable once somebody deletes a
 * word from `config/taxonomy.json` that a published day still carries, and the
 * honest thing to show then is the word the day recorded - the alternative is a
 * day quietly saying less than it said, which is the defect this replaced.
 */
export function lensLabel(id: string): string {
	return LENS_NAMES[id] ?? id;
}
