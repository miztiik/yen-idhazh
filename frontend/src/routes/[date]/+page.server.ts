import { error } from '@sveltejs/kit';
import { shellSeedItems } from '$lib/server/config';
import { dayShell, publishedDates, wholeDay } from '$lib/server/payload';

export const prerender = true;

export function entries() {
	return publishedDates().map((date) => ({ date }));
}

/** The day arrives in two halves - its bounded facts, and its stories split at
 * `ui.shell_seed_items` - and is put straight back together here. Both halves
 * are still read at build time, so the prerendered document does not move. What
 * the split buys is a seam the rows after it fetch the remainder across.
 */
export function load({ params }: { params: { date: string } }) {
	const shell = dayShell(params.date, shellSeedItems());
	// A date that was never published stays a 404. Redirecting to today would
	// leave a reader unable to tell a dead link from a live one.
	if (!shell) error(404, `No digest was published for ${params.date}.`);
	return { day: wholeDay(shell), date: params.date };
}
