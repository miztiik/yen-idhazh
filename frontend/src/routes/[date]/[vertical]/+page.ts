/** A topic page: the day, filtered to one desk, rendered in the browser.
 *
 * The same move the dated day route makes, and the larger half of it: 96 of the
 * 116 documents this row deletes were this route. A topic is one desk of one
 * day, so it was always a filter over a file the browser can fetch for itself -
 * the build was writing five documents a day to run that filter early.
 *
 * `ssr = false` and no `prerender`. See [../+page.ts](../+page.ts) for why the
 * fetch does not happen here.
 */
export const ssr = false;

export function load({ params }: { params: { date: string; vertical: string } }) {
	return { date: params.date, vertical: params.vertical };
}
