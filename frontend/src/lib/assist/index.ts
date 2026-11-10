/** The month index, fetched in the browser one month at a time.
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
 * The day view shares cached fetches through the two maps below. Archive
 * submissions use the raw readers to revalidate published files without
 * retaining every month's vectors. A prerender never fills either cache.
 *
 * The shape this returns, and the parsing that checks it, live in `month.ts`.
 * They are pure, and they stay out of this file because this file imports
 * `$app/paths` and so can only run in a browser or a SvelteKit build.
 */

import { base } from '$app/paths';
import type { SearchIndexEntry } from '$lib/payload/types';
import { indexOf, type MonthIndex } from './month';

export { entriesOf, indexOf, newestFirst, type MonthIndex } from './month';

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

/** Read without retaining a month in the page cache; archive scans release it after ranking. */
export async function readIndex(
	month: string,
	fetcher: typeof fetch = fetch,
	cache: RequestCache = 'default'
): Promise<MonthIndex | null> {
	try {
		const response = await fetcher(`${base}/index/${month}.json`, { cache });
		if (!response.ok) {
			console.warn(`[archive] the stories for ${month} are not available (${response.status})`);
			return null;
		}
		const index = indexOf(await response.json());
		if (index === null) console.warn(`[archive] the stories for ${month} have an incompatible index`);
		return index;
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

export async function readVectors(
	month: string,
	fetcher: typeof fetch = fetch,
	cache: RequestCache = 'default'
): Promise<Int8Array | null> {
	try {
		const response = await fetcher(`${base}/index/${month}.bin`, { cache });
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
