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

/** Inclusive UTC dates; an empty bound leaves that end of the range open. */
export interface ArchiveRange {
	from: string;
	to: string;
}

export function dateInRange(date: string, range: ArchiveRange): boolean {
	return (range.from === '' || date >= range.from) && (range.to === '' || date <= range.to);
}

/** Select registered month names before any file is requested. */
export function monthsInRange(months: string[], range: ArchiveRange): string[] {
	return months.filter(
		(month) =>
			(range.from === '' || month >= range.from.slice(0, 7)) &&
			(range.to === '' || month <= range.to.slice(0, 7))
	);
}

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

/** The month a day sits in and the `back` months before it, newest first.
 *
 * **The archive is handed the months that exist; a reading page has to derive
 * them.** A dated route is one shell with a universal load, so it may not reach
 * `$lib/server/` and there is no build-time list of published months on it. The
 * alternative was baking that list into the reading bundle, which grows as the
 * archive grows (Guardrail #12) and rewrites the bundle the day a month starts.
 * A date does neither: it is in the address the reader typed.
 *
 * A name with no file is the designed gap `loadIndex` already returns null for,
 * so a reader on the oldest published month spends one refused request and gets
 * a narrower scope, which the sentence under the field then states in days. It
 * never takes the page down (`CLAUDE.md` section 1a).
 *
 * `back` is `assist.search_months`, so the list is exactly as long as
 * `readScope` can read plus the one extra it takes when the newest shard is
 * thin. Pure, and driven in Node.
 */
export function monthsBackFrom(date: string, back: number): string[] {
	const parts = /^(\d{4})-(\d{2})/.exec(date);
	if (parts === null) return [];
	const year = Number(parts[1]);
	const month = Number(parts[2]);
	const names: string[] = [];
	for (let step = 0; step <= Math.max(back, 0); step += 1) {
		const at = new Date(Date.UTC(year, month - 1 - step, 1));
		names.push(at.toISOString().slice(0, 7));
	}
	return names;
}
