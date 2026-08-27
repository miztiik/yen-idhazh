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
 * Two files a month, and different people pay for them. Every visitor browsing
 * the list downloads the JSON. Only a reader who searches downloads the sibling
 * `.bin`, and that reader has already accepted a 43 MB encoder.
 *
 * **Every fetch here is cached for the page's lifetime.** The list and the
 * search box read the same months, and a reader who searches twice reads them
 * again. The two maps below are that cache. Nothing in a `load` function calls
 * this module, so a prerender never fills them.
 */

import { base } from '$app/paths';
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

const indexes = new Map<string, Promise<MonthIndex | null>>();
const vectors = new Map<string, Promise<Int8Array | null>>();

/** One month, header and entries, or null when that month cannot be read.
 *
 * Null is a designed state. A month whose file is absent leaves a gap in the
 * list; it never takes the page down (`CLAUDE.md` section 1a).
 */
export function loadIndex(
	month: string,
	fetcher: typeof fetch = fetch
): Promise<MonthIndex | null> {
	const held = indexes.get(month);
	if (held) return held;
	const pending = readIndex(month, fetcher);
	indexes.set(month, pending);
	return pending;
}

async function readIndex(month: string, fetcher: typeof fetch): Promise<MonthIndex | null> {
	try {
		const response = await fetcher(`${base}/assist/index/${month}.json`);
		if (!response.ok) {
			console.warn(`[archive] the stories for ${month} are not available (${response.status})`);
			return null;
		}
		return indexOf(await response.json());
	} catch (error) {
		console.warn(`[archive] the stories for ${month} could not be read`, error);
		return null;
	}
}

/** The stories of one month, newest day first. What the browse list reads. */
export async function loadMonth(
	month: string,
	fetcher: typeof fetch = fetch
): Promise<SearchIndexEntry[] | null> {
	return (await loadIndex(month, fetcher))?.entries ?? null;
}

/** That month's vectors, end to end as raw int8, or null when they cannot be read.
 *
 * A month whose JSON is present and whose `.bin` is absent browses normally and
 * cannot be searched. That is the designed split rather than a half-failure:
 * the list needs no vector, and search cannot work without one.
 *
 * No decompression here. GitHub Pages compresses `application/octet-stream` at
 * the edge, measured against the live origin, so the file arrives compressed
 * and `arrayBuffer()` hands back the raw bytes.
 */
export function loadVectors(
	month: string,
	fetcher: typeof fetch = fetch
): Promise<Int8Array | null> {
	const held = vectors.get(month);
	if (held) return held;
	const pending = readVectors(month, fetcher);
	vectors.set(month, pending);
	return pending;
}

async function readVectors(month: string, fetcher: typeof fetch): Promise<Int8Array | null> {
	try {
		const response = await fetcher(`${base}/assist/index/${month}.bin`);
		if (!response.ok) {
			console.warn(`[archive] the vectors for ${month} are not available (${response.status})`);
			return null;
		}
		return new Int8Array(await response.arrayBuffer());
	} catch (error) {
		console.warn(`[archive] the vectors for ${month} could not be read`, error);
		return null;
	}
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
