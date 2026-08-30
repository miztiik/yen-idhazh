/** The lens display names, mirrored from `config/taxonomy.json`.
 *
 * Held here rather than passed through `data`: the six names would otherwise be
 * repeated inside every prerendered day page, and a day page is the heaviest
 * thing we publish. As a module they are bundled into the shared chunk once.
 *
 * Retired lenses are absent on purpose. An id that does not resolve renders
 * nothing, so a tombstone can never return to the page.
 *
 * `test_contracts.py::test_the_frontend_names_every_live_lens_and_no_retired_one`
 * reads the config and fails on any drift, in either direction.
 */
export const LENS_NAMES: Readonly<Record<string, string>> = {
	chips: 'Chips',
	china: 'China',
	cyber: 'Cyber',
	markets: 'Markets',
	trade: 'Trade and tariffs',
	war: 'War'
};

/** How many chips one item may show.
 *
 * Three of "Trade and tariffs" length wrap the eyebrow on a 390px screen. The
 * reader loses the third word on a rare three-lens story and keeps a one-line
 * eyebrow on every item on every phone.
 */
export const MAX_LENS_CHIPS = 2;

/** The lenses an item shows: known, in configured order, capped. */
export function shownLenses(lenses: readonly string[] | undefined): string[] {
	const known = Object.keys(LENS_NAMES);
	return known.filter((id) => lenses?.includes(id)).slice(0, MAX_LENS_CHIPS);
}
