import { error } from '@sveltejs/kit';
import { shellSeedItems } from '$lib/server/config';
import { dayShell, loadDay, publishedDates } from '$lib/server/payload';

export const prerender = true;

/** Only verticals actually present get a page, so no route leads to an empty room. */
export function entries() {
	const found: { date: string; vertical: string }[] = [];
	for (const date of publishedDates()) {
		const day = loadDay(date);
		for (const vertical of day?.verticals ?? []) {
			found.push({ date, vertical: vertical.id });
		}
	}
	return found;
}

/** The topic's own stories, split at `ui.shell_seed_items`.
 *
 * The document keeps the head and the browser fetches the rest, which is where
 * this migration's saving lands: five of the six documents a day are this
 * route, and each one used to carry the whole day so that a client-side filter
 * could throw most of it away.
 *
 * The seed is the head of the TOPIC's list, not of the day's. The published
 * order is desk-blocked rather than globally ranked, so a plain head of the day
 * is one desk and every other topic route would open on a screen holding none
 * of its own stories.
 *
 * The topic itself is one of the day's bounded facts, so the 404 below is
 * decided before a single story is looked at.
 */
export function load({ params }: { params: { date: string; vertical: string } }) {
	const shell = dayShell(params.date, shellSeedItems(), { vertical: params.vertical });
	if (!shell) error(404, `No digest was published for ${params.date}.`);
	if (!shell.facts.verticals.some((ref) => ref.id === params.vertical)) {
		error(404, `Nothing was published under ${params.vertical} on ${params.date}.`);
	}
	return {
		day: { ...shell.facts, items: shell.seed },
		date: params.date,
		vertical: params.vertical,
		// How many of this topic's stories the document does not carry. Counted
		// here rather than worked out in the browser from the topic's own count,
		// because it decides whether a reader's device makes a request at all: a
		// page that reads it low leaves stories nobody can reach.
		awaiting: shell.rest.length
	};
}
