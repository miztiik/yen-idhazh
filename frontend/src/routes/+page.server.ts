import { shellSeedItems } from '$lib/server/config';
import { homeShell, latestDate, loadDay, publishedDates } from '$lib/server/payload';

/** The flag is here rather than on the root layout, and it has to be.
 *
 * Until 2026-09-09 one `prerender = true` on `+layout.server.ts` cascaded to
 * every route on the site. The layout is a universal load now and page options
 * went with it, so each route that ships a document declares its own. Without
 * this line the site root emits no `index.html` at all and GitHub Pages answers
 * `/` with the fallback, at HTTP 404.
 */
export const prerender = true;

/** The home page reads the day it renders, and carries a seed of it.
 *
 * **It inlined the whole day until 2026-09-10**, which ruling D2 of the
 * shell-and-fetch plan says it may not - shell plus fetch "admits no special
 * case, on the home page and the console alike". The case made for the
 * exception was that `/` stayed readable with no script at all. It did not.
 * Measured that day on a clean production build with the scripts stripped, on a
 * 72-story day: the document is 176,622 bytes raw, 63.9 percent of them script,
 * and what a script-free reader can read is **17 stories under a header saying
 * 72, above a button offering 55 more that does nothing**. On a mature day the
 * header says 360 or 627 and the seed is still about 17.
 *
 * So the exception charged a script-free reader for a day they could not reach
 * and left them a control that lies. The seed is what the document carries now,
 * and the browser fetches the rest from the served file a dated URL and a search
 * result already read.
 *
 * **The seed keeps the day's leads whatever their position**, which is what
 * `dayShell`'s `keep` was written for and had no caller for. `homeShell` makes
 * that decision, so a fixture can drive it: the canary's biggest day holds 8
 * stories against a 15-story seed and no leads, so nothing built from it can see
 * this route's behaviour at all.
 */
export function load() {
	const latest = latestDate();
	const shell = latest ? homeShell(latest, shellSeedItems()) : null;
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
	return { day: shell ? { ...shell.facts, items: shell.seed } : null, today: latest, recent };
}
