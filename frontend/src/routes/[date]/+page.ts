/** A dated day page, rendered in the browser.
 *
 * **`ssr = false` and no `prerender`, and both are the row.** Until 2026-09-09
 * this route wrote one document per published day - 20 of them, beside 96 topic
 * documents, each with a `__data.json` twin, all rebuilt on every run. One shell
 * answers every dated URL now: `adapter-static`'s fallback is `404.html`, the
 * client router resolves this route from the address, and this load fetches the
 * day the same served file a search result and a topic page already read.
 *
 * **A universal load may not import `$lib/server/`**, which is the framework's
 * own guarantee that nothing under it can reach a browser. So there is no
 * `loadDay` off disk, no `dayShell` split and no seed: the page has the whole
 * day or it has none of it, and which of those it is arrives as a status.
 *
 * **The fetch is not awaited here, and that is a reader decision rather than a
 * style.** A cold load of a dated URL already waits for the fallback and the
 * bundle before anything can paint; awaiting the day as well would hold a blank
 * page for a payload that is 1.1 MB at the median over the committed days. The
 * page renders its chrome and its date first and says one sentence if the wait
 * runs long, which is what `PayloadState` has always been for.
 */
export const ssr = false;

export function load({ params }: { params: { date: string } }) {
	return { date: params.date };
}
