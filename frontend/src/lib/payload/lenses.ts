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

/** Keep configured names first in taxonomy order, then unknown ids, within the chip limit. */
export function shownLenses(lenses: readonly string[] | undefined): string[] {
	if (!lenses?.length) return [];
	const named = Object.keys(LENS_NAMES).filter((id) => lenses.includes(id));
	const unnamed = lenses.filter((id) => !(id in LENS_NAMES));
	return [...named, ...unnamed].slice(0, MAX_LENS_CHIPS);
}

/** Retain an unknown id so an older article does not silently lose its label. */
export function lensLabel(id: string): string {
	return LENS_NAMES[id] ?? id;
}
