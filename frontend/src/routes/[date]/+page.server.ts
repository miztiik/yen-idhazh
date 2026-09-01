import { error } from '@sveltejs/kit';
import { shellSeedItems } from '$lib/server/config';
import { dayShell, loadDay, publishedDates } from '$lib/server/payload';

export const prerender = true;

export function entries() {
	return publishedDates().map((date) => ({ date }));
}

/** The day's own stories, split at `ui.shell_seed_items`.
 *
 * The document keeps the head and the browser fetches the rest from
 * `<base>/digest/<Y>/<M>/<D>/digest.json`. This is the route the topic pages
 * were the rehearsal for, and the one that grows: a dated document used to
 * carry every story the day published, so the site charged a reader who opens
 * one day for every day it had ever published.
 *
 * **The seed is the head UNION the day's leads.** A lead is chosen across the
 * whole day rather than off the top of the published order, and the leading
 * block is a set of anchors into the stream - so a document holding only a
 * prefix ships lead links that land on nothing until the fetch arrives, and on
 * nothing at all when it fails. The day is therefore read twice: once for the
 * leads, which decide what the document has to be able to anchor, and once for
 * the split itself. There is no way to know the first before the day has been
 * read.
 */
export function load({ params }: { params: { date: string } }) {
	const published = loadDay(params.date);
	const shell = published
		? dayShell(params.date, shellSeedItems(), {
				keep: published.leads?.map((lead) => lead.item_id)
			})
		: null;
	// A date that was never published stays a 404. Redirecting to today would
	// leave a reader unable to tell a dead link from a live one.
	if (!shell) error(404, `No digest was published for ${params.date}.`);
	return {
		day: { ...shell.facts, items: shell.seed },
		date: params.date,
		// How many of the day's stories the document does not carry. Counted here
		// rather than worked out in the browser from the day's own counts, because
		// it decides whether a reader's device makes a request at all: a page that
		// reads it low leaves stories nobody can reach.
		awaiting: shell.rest.length
	};
}
