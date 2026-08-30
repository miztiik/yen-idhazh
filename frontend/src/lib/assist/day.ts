/** A day payload, fetched from the published site rather than inlined.
 *
 * The archive used to carry every committed day whole so a search result could
 * be rendered from one. That cost every visitor 1.7 MB gzipped to browse a
 * list. A result now names a day, and the day is fetched only when a result
 * from it is on screen.
 *
 * **Fetched once per page.** Ten results spanning ten days cost ten requests at
 * worst; ten results from one day cost one. A day already in hand is never
 * fetched again, and a day that failed is not retried - a second attempt at a
 * file the host does not have costs a reader a request and tells them nothing.
 *
 * **Null is the designed state.** A result whose day cannot be read still
 * renders: it keeps the title, the date and the topic the index carried, and
 * loses the summary. The page never waits on this and never breaks on it.
 */

import { base } from '$app/paths';
import type { DigestDay, DigestItem } from '$lib/payload/types';

const days = new Map<string, Promise<DigestDay | null>>();

/** The day published on that date, or null when it cannot be read. */
export function loadDay(date: string, fetcher: typeof fetch = fetch): Promise<DigestDay | null> {
	const held = days.get(date);
	if (held) return held;
	const pending = readDay(date, fetcher);
	days.set(date, pending);
	return pending;
}

async function readDay(date: string, fetcher: typeof fetch): Promise<DigestDay | null> {
	const [year, month, day] = date.split('-');
	if (!year || !month || !day) return null;
	try {
		const response = await fetcher(`${base}/digest/${year}/${month}/${day}/digest.json`);
		if (!response.ok) {
			console.warn(`[archive] the stories of ${date} are not available (${response.status})`);
			return null;
		}
		const payload = (await response.json()) as DigestDay;
		return Array.isArray(payload?.items) ? payload : null;
	} catch (error) {
		console.warn(`[archive] the stories of ${date} could not be read`, error);
		return null;
	}
}

/** One item out of a day already in hand, or null. */
export function itemOf(day: DigestDay | null, itemId: string): DigestItem | null {
	return day?.items.find((item) => item.item_id === itemId) ?? null;
}
