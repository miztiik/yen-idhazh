/** The month index's shape, and how to read one safely.
 *
 * Pure. It knows nothing about fetching, which is what lets a test drive it in
 * Node and what keeps the guard over the committed shards out of a browser.
 * `index.ts` is the half that fetches, and it imports `$app/paths`.
 */

import type { SearchIndex, SearchIndexEntry } from '$lib/payload/types';

/** One month's index, header and all.
 *
 * The header is not decoration. `model_id` says which encoder wrote the
 * vectors, and a shard from another encoder decodes perfectly into a different
 * space, so every score it makes still looks like a score. `scale` says what a
 * stored byte is worth, so a later encoder can re-quantise without breaking
 * this file.
 */
export type MonthIndex = Omit<SearchIndex, 'version'>;

/** The index a payload actually carries, entries newest day first.
 *
 * The shape is checked rather than trusted. This file is ours, but a half-
 * written or truncated one has to leave a gap in the list instead of throwing
 * inside a render. The header is checked as strictly as the entries, because a
 * shard with no `scale` would decode into nonsense that still ranks.
 */
export function indexOf(payload: unknown): MonthIndex | null {
	if (typeof payload !== 'object' || payload === null) return null;
	const record = payload as Record<string, unknown>;
	if (!Array.isArray(record.entries)) return null;
	if (typeof record.model_id !== 'string') return null;
	if (typeof record.dimensions !== 'number' || record.dimensions < 1) return null;
	if (record.dtype !== 'int8') return null;
	if (typeof record.scale !== 'number' || !(record.scale > 0)) return null;
	return {
		month: typeof record.month === 'string' ? record.month : '',
		model_id: record.model_id,
		dimensions: record.dimensions,
		dtype: 'int8',
		scale: record.scale,
		entries: newestFirst(record.entries.filter(isEntry))
	};
}

/** The entries a payload actually carries, newest day first. */
export function entriesOf(payload: unknown): SearchIndexEntry[] | null {
	return indexOf(payload)?.entries ?? null;
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
 *
 * Reordering costs search nothing, because `vector` is a byte offset into the
 * `.bin` rather than a position in this list.
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

/** The oldest day a window of `days` still reaches back to, as `YYYY-MM-DD`.
 *
 * Measured back from `anchor`, the newest published day, not from today. A
 * corpus that stopped last month opens on its own last stories rather than on
 * an empty page - the search scope anchors the same way, for the same reason.
 * A one-day window is the anchor itself, so the span is `days - 1` before it.
 */
export function windowStart(anchor: string, days: number): string {
	const start = new Date(`${anchor}T00:00:00Z`);
	start.setUTCDate(start.getUTCDate() - (days - 1));
	return start.toISOString().slice(0, 10);
}

/** The months a window reaches into, newest first - and no month it cannot.
 *
 * The archive browses a window, not the whole corpus, so the list fetches only
 * the month files that window could hold a story from. A month is one of them
 * when it lies between the window's start month and the anchor's, inclusive;
 * every month older than that is out of reach and is never fetched, which is
 * what keeps the walk bounded by the window rather than by the archive
 * (`CLAUDE.md` Rule #12).
 *
 * `months` is the set that exists on disk (`indexMonths()`, newest first), so a
 * month the window reaches but nobody published is simply absent from the
 * result and costs no request. The return is a newest-first prefix of that
 * set, which is what lets the browse loop fetch it one month at a time.
 *
 * Pure, so a test drives it in Node the way the search scope is - the canary
 * publishes a single month and a rule about several cannot show up in it.
 */
export function monthsInWindow(months: string[], anchor: string, days: number): string[] {
	const startMonth = windowStart(anchor, days).slice(0, 7);
	const anchorMonth = anchor.slice(0, 7);
	return months.filter((month) => month >= startMonth && month <= anchorMonth);
}
