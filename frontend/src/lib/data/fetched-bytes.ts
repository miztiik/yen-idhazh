/**
 * How does the query door read a published file over HTTP?
 *
 * The published tree is the committed one, copied unchanged, so a file sits at
 * `<prefix>/state/<its path under the state root>`. An index is asked for with
 * `cache: 'no-store'`, so a page's one read of it gets what the site holds now
 * rather than a copy an HTTP cache kept from an earlier visit; the page keeper
 * (`page-keeper.ts`) then keeps it for the page's life. A data file is asked for
 * with `?v=<rows>-<bytes>` from its entry: a compact file is written once, so a
 * cache may keep it for as long as that version names it.
 *
 * A 404 is an absent file; any other failure is thrown, and the reader turns it
 * into `unreachable`. The length the reader checks is the length of the bytes
 * that arrived, never `Content-Length`, because Pages compresses what it serves.
 *
 * **A file read by byte range is not fetched here, and each read of it gets an
 * address of its own**: the one a whole fetch would use, version and all, and a
 * `read` part made when the read starts that no earlier read used, on this page
 * or an earlier one. Pages ignores the query string, so every such address
 * names the same bytes. The browser keeps the parts it fetched under the whole
 * address, so a new address holds none of them, and no request names the ETag
 * the browser kept for an earlier read. Every deploy gives every file a new
 * ETag, and Pages answers a request naming an older one with the whole file.
 *
 * The prefix comes from this build's own config, never from a payload, so no
 * fetched text can move where the door asks (Guardrail #11). Imports nothing
 * tied to one environment: the caller hands it `fetch`.
 */

import type { ByteSource } from './page-keeper';

/** How the source asks for one URL: `fetch` in a browser, a recorded response in a test. */
export type Fetcher = (url: string, init: RequestInit) => Promise<Response>;

/** Random bytes in the part of an address one read alone uses: 64 bits, so no two reads share one. */
const READ_MARK_BYTES = 8;

/** The part of an address one read alone uses. Random rather than counted, because a
 *  counter restarts with each page, and the browser keeps parts across pages. */
function readMark(): string {
	const bytes = crypto.getRandomValues(new Uint8Array(READ_MARK_BYTES));
	return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

/** A byte source over HTTP, rooted at `prefix` - this site, or the knob that moves its assets. */
export function fetchedBytes(prefix: string, fetcher: Fetcher): ByteSource {
	const root = `${prefix.replace(/\/+$/, '')}/state/`;
	const dataAddress = (path: string, version: string): string => `${root}${path}?v=${encodeURIComponent(version)}`;
	async function bytesAt(url: string, init: RequestInit): Promise<Uint8Array | null> {
		const response = await fetcher(url, init);
		if (response.status === 404) return null;
		if (!response.ok) throw new Error(`${url} answered ${response.status}`);
		return new Uint8Array(await response.arrayBuffer());
	}
	return {
		index: (path) => bytesAt(`${root}${path}`, { cache: 'no-store' }),
		data: (path, version) => bytesAt(dataAddress(path, version), {}),
		address: (path, version) => `${dataAddress(path, version)}&read=${readMark()}`
	};
}
