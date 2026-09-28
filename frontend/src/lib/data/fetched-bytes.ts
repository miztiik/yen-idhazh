/**
 * How does the query door read a published file over HTTP?
 *
 * The published tree is the committed one, copied unchanged, so a file sits at
 * `<prefix>/state/<its path under the state root>`. An index is asked for with
 * `cache: 'no-store'`, because file selection acts on it and a stale index is a
 * wrong selection. A data file is asked for with `?v=<rows>-<bytes>` from its
 * entry: a compact file is written once, so a cache may keep it for as long as
 * that version names it.
 *
 * A 404 is an absent file; any other failure is thrown, and the reader turns it
 * into `unreachable`. The length the reader checks is the length of the bytes
 * that arrived, never `Content-Length`, because Pages compresses what it serves.
 *
 * The prefix comes from this build's own config, never from a payload, so no
 * fetched text can move where the door asks (Guardrail #11). Imports nothing
 * tied to one environment: the caller hands it `fetch`.
 */

import type { ByteSource } from './slice-reader';

/** How the source asks for one URL: `fetch` in a browser, a recorded response in a test. */
export type Fetcher = (url: string, init: RequestInit) => Promise<Response>;

/** A byte source over HTTP, rooted at `prefix` - this site, or the knob that moves its assets. */
export function fetchedBytes(prefix: string, fetcher: Fetcher): ByteSource {
	const root = `${prefix.replace(/\/+$/, '')}/state/`;
	async function bytesAt(url: string, init: RequestInit): Promise<Uint8Array | null> {
		const response = await fetcher(url, init);
		if (response.status === 404) return null;
		if (!response.ok) throw new Error(`${url} answered ${response.status}`);
		return new Uint8Array(await response.arrayBuffer());
	}
	return {
		index: (path) => bytesAt(`${root}${path}`, { cache: 'no-store' }),
		data: (path, version) => bytesAt(`${root}${path}?v=${encodeURIComponent(version)}`, {})
	};
}
