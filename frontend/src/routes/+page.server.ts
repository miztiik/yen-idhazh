import { shellSeedItems } from '$lib/server/config';
import { dayShell, latestDate, loadDay, publishedDates, wholeDay } from '$lib/server/payload';

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
	const recent = publishedDates()
		.slice(0, 7)
		.map((date) => ({ date, items: loadDay(date)?.items.length ?? 0 }));
	return { day, today: day?.date ?? latest, recent };
}
