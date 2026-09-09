import { base } from '$app/paths';
import { BAND_UNREAD, readBand } from '$lib/console/band';

export const prerender = true;

/** The band, the strip and the months list, fetched once for all three routes.
 *
 * **It is a universal load and that is the whole design.** At build time it runs
 * in Node and SvelteKit resolves the fetch against the staged payload, so the
 * band is real markup in each of the three documents and an operator on a dead
 * connection still reads the verdict. In a browser the same code runs again on a
 * client-side move between routes, so the strip follows him without a second
 * document.
 *
 * Until 2026-09-09 this derived the band itself, from the committed ledger under
 * `state/`, which made the console a thing only a finished build could produce.
 * The pipeline writes `console/band.json` now. What crosses here is 2 KB of
 * settled facts rather than the ledger they were settled from.
 *
 * The months list rides on the same payload rather than arriving on its own: a
 * page cannot ask for a month until it knows which months exist, so a second
 * file would be one more wait before the first row of data (Carmack,
 * 2026-09-08).
 */
export async function load({ fetch }) {
	try {
		const response = await fetch(`${base}/console/band.json`);
		if (!response.ok) {
			console.warn(`[console] band unavailable (${response.status}); drawing the absence`);
			return BAND_UNREAD;
		}
		return readBand(await response.json());
	} catch (cause) {
		console.warn(`[console] band could not be read; drawing the absence - ${String(cause)}`);
		return BAND_UNREAD;
	}
}
