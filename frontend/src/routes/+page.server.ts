import { shellSeedItems } from '$lib/server/config';
import { dayShell, latestDate, loadDay, publishedDates, wholeDay } from '$lib/server/payload';

/** The flag is here rather than on the root layout, and it has to be.
 *
 * Until 2026-09-09 one `prerender = true` on `+layout.server.ts` cascaded to
 * every route on the site. The layout is a universal load now and page options
 * went with it, so each route that ships a document declares its own. Without
 * this line the site root emits no `index.html` at all and GitHub Pages answers
 * `/` with the fallback, at HTTP 404.
 */
export const prerender = true;

/** The home page reads the day it renders.
 *
 * It used to read one the root layout returned, which is why every other page
 * carried that day too - the console, the archive, an old dated page.
 *
 * It loads across the same seam the dated routes do - the day's bounded facts,
 * its stories split at `ui.shell_seed_items`, and both halves put straight back
 * together. Nothing fetches yet, so the prerendered document does not move.
 */
export function load() {
	const latest = latestDate();
	const shell = latest ? dayShell(latest, shellSeedItems()) : null;
	const day = shell ? wholeDay(shell) : null;
	// A handful of recent days, so "what did I miss on Tuesday" is answered in
	// place. Dates and counts only: the stories stay where they are, and this
	// list grows per day rather than per story.
	//
	// Seven is a count and the read's cover is a span, so this takes the default
	// cover and slices seven from the front of it. The two only disagree where
	// the pipeline published fewer than seven days in the last ninety, and then
	// there are fewer than seven recent days to show.
	const recent = publishedDates()
		.slice(0, 7)
		.map((date) => ({ date, items: loadDay(date)?.items.length ?? 0 }));
	return { day, today: day?.date ?? latest, recent };
}
