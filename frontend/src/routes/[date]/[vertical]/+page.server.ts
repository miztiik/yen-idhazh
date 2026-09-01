import { error } from '@sveltejs/kit';
import { shellSeedItems } from '$lib/server/config';
import { dayShell, loadDay, publishedDates, wholeDay } from '$lib/server/payload';

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

/** The same seam the day route loads across, and the same day payload: a topic
 * page is a filter over the day, never a second file. The topic itself is one
 * of the day's bounded facts, so the 404 below is decided before a single story
 * is looked at.
 */
export function load({ params }: { params: { date: string; vertical: string } }) {
	const shell = dayShell(params.date, shellSeedItems());
	if (!shell) error(404, `No digest was published for ${params.date}.`);
	if (!shell.facts.verticals.some((ref) => ref.id === params.vertical)) {
		error(404, `Nothing was published under ${params.vertical} on ${params.date}.`);
	}
	return { day: wholeDay(shell), date: params.date, vertical: params.vertical };
}
