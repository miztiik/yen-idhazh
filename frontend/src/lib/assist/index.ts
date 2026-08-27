/** The month index, read in the browser one month at a time.
 *
 * **Fetched at runtime, not inlined at prerender.** Every other committed
 * payload this site renders is read from the filesystem at build time and
 * baked into the HTML, and for a day page that is right - the day is bounded
 * and the reader came to read it. The archive is the whole corpus, so inlining
 * it would put every story ever published into one document and grow it by
 * about 50 gzipped bytes an item forever. The console already solved this
 * shape: a bounded seed in the HTML, and older months fetched from `static/`
 * as the reader asks for them. This is the same mechanism.
 *
 * Nothing here reads the sibling vector file. The list browses; searching over
 * the index is a later change, and keeping them apart is what lets either one
 * be undone on its own.
 */

import { base } from '$app/paths';
import type { SearchIndexEntry } from '$lib/payload/types';

/** One month of stories, or null when that month cannot be read.
 *
 * Null is a designed state. A month whose file is absent leaves a gap in the
 * list; it never takes the page down (`CLAUDE.md` section 1a).
 */
export async function loadMonth(
	month: string,
	fetcher: typeof fetch = fetch
): Promise<SearchIndexEntry[] | null> {
	try {
		const response = await fetcher(`${base}/index/${month}.json`);
		if (!response.ok) {
			console.warn(`[archive] the stories for ${month} are not available (${response.status})`);
			return null;
		}
		return entriesOf(await response.json());
	} catch (error) {
		console.warn(`[archive] the stories for ${month} could not be read`, error);
		return null;
	}
}

/** The entries a payload actually carries, newest day first.
 *
 * The shape is checked rather than trusted. This file is ours, but a half-
 * written or truncated one has to leave a gap in the list instead of throwing
 * inside a render.
 */
export function entriesOf(payload: unknown): SearchIndexEntry[] | null {
	if (typeof payload !== 'object' || payload === null) return null;
	const entries = (payload as { entries?: unknown }).entries;
	if (!Array.isArray(entries)) return null;
	return newestFirst(entries.filter(isEntry));
}

function isEntry(value: unknown): value is SearchIndexEntry {
	if (typeof value !== 'object' || value === null) return false;
	const entry = value as Record<string, unknown>;
	return (
		typeof entry.date === 'string' &&
		typeof entry.item_id === 'string' &&
		typeof entry.title === 'string' &&
		typeof entry.vertical === 'string'
	);
}

/** Published order, newest day first.
 *
 * A month lists its days in published order, so its dates only ever go
 * forward. A reader opens the archive to see what is new, so the days come
 * back the other way round - but the order **inside** a day is left exactly as
 * published. That is what makes the first story here the first story on that
 * day's own page. No reader can change either order (`layout.md`).
 */
export function newestFirst(entries: SearchIndexEntry[]): SearchIndexEntry[] {
	const byDate = new Map<string, SearchIndexEntry[]>();
	for (const entry of entries) {
		const found = byDate.get(entry.date);
		if (found) found.push(entry);
		else byDate.set(entry.date, [entry]);
	}
	return [...byDate.keys()]
		.sort()
		.reverse()
		.flatMap((date) => byDate.get(date) ?? []);
}
