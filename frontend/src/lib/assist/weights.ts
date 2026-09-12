/**
 * The encoder's failover leg: a second origin, and the manifest that makes it safe.
 *
 * **Our own origin is primary and nothing here changes that.** The weights are
 * committed under `frontend/static/assist/models/` and every reader gets them
 * from this site. This module runs only after that has already failed a reader -
 * a dead cache, a partial deploy, a network that answers this site and not that
 * file - and it exists so the answer to "the download did not work" is a second
 * try rather than a page with no search on it.
 *
 * **The URL is the convenience. The manifest is the point.** A second origin
 * without one would be a permission for another party to put bytes into a
 * reader's tab, and no amount of care about WHERE the bytes came from would
 * bound WHAT they are. So every file is hashed as it arrives and compared with
 * a SHA-256 committed in `config/idhazh.json`, before a single byte reaches
 * transformers.js. On any miss - a non-200, a truncation, a timeout or a wrong
 * digest - the WHOLE set is discarded and the reader is told the download did
 * not finish. Provenance is never mixed across files: five verified files or
 * none, never four of ours and one of theirs.
 *
 * **The manifest is baked into the bundle, not fetched.** A manifest a page
 * fetched could be answered by whoever answered the fetch, which is the thing
 * it exists to guard against. `vite.config.ts` reads it from `config/` at build
 * time, so it is exactly as trustworthy as the bundle carrying it.
 *
 * Nothing here reads a payload field, a model output or any fetched text
 * (Guardrail #11). The URL is built from two committed config values and a path that
 * is a key of the committed manifest, so a file this module does not already
 * hold a digest for cannot be asked for at all.
 */

/** Where the encoder may be fetched from, and what it must hash to. */
export interface EncoderSource {
	/** The repository prefix, or `''` when there is no second origin. */
	baseUrl: string;
	/** Origins `baseUrl` redirects a large file to. In `connect-src`, not in a URL. */
	cdnOrigins: string[];
	/** The upstream commit, 40 hex characters. */
	revision: string;
	/** Path under the model directory -> SHA-256, lower-case hex. */
	digests: Record<string, string>;
	/** How long the whole set may take, in milliseconds. */
	deadlineMs: number;
}

/** No second origin. Every failure answers this, and it turns the leg off. */
export const NO_SECOND_ORIGIN: EncoderSource = {
	baseUrl: '',
	cdnOrigins: [],
	revision: '',
	digests: {},
	deadlineMs: 0
};

/** Why a set was discarded. Every one of these means the reader gets no encoder. */
export type WeightsRefusal =
	/** No second origin is configured, so there was nothing to try. */
	| 'off'
	/** The fetch threw - no network, a refused connection, a blocked origin. */
	| 'unreachable'
	/** The origin answered, and not with the file. */
	| 'refused'
	/** The bytes arrived and are not the bytes we committed. */
	| 'mismatch'
	/** The set did not finish inside `deadlineMs`. */
	| 'timeout';

/** Five verified files, or the reason there are none. */
export type WeightsOutcome =
	| { ok: true; files: Map<string, ArrayBuffer> }
	| { ok: false; reason: WeightsRefusal; path?: string };

/** What `vite.config.ts` injected, or nothing at all outside a browser build.
 *
 * A bare read rather than a `typeof` guard: the build replaces the identifier
 * textually, and a Node test that imports this module for its pure functions
 * has no such identifier at all. Both cases answer without throwing.
 */
export function injectedSource(): EncoderSource {
	try {
		return __ENCODER_SOURCE__;
	} catch {
		return NO_SECOND_ORIGIN;
	}
}

/**
 * The address one encoder file is fetched from.
 *
 * Pinned to a 40-hex commit rather than a branch, so the bytes this asks for
 * are the bytes the manifest describes. A branch hands back whatever was
 * uploaded last, which would make every digest in the manifest a coin flip.
 */
export function remoteUrl(source: EncoderSource, path: string): string {
	return `${source.baseUrl}/resolve/${source.revision}/${path}`;
}

/** SHA-256 of what arrived, as lower-case hex. */
export async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
	const digest = await crypto.subtle.digest('SHA-256', bytes);
	return Array.from(new Uint8Array(digest))
		.map((byte) => byte.toString(16).padStart(2, '0'))
		.join('');
}

/** The files a set is made of: every path the committed manifest names. */
export function manifestPaths(source: EncoderSource): string[] {
	return Object.keys(source.digests).sort();
}

/**
 * Fetch every file the manifest names and verify all of them, or hand back none.
 *
 * One deadline covers the whole set rather than each file, because a reader is
 * waiting on the set and a per-file deadline lets four slow files add up to a
 * wait nobody bounded.
 *
 * The verification is not a formality and the order matters: a file is hashed
 * the moment its bytes are complete, and a mismatch abandons the set right
 * there. Nothing is handed back until the last digest has matched, so a caller
 * cannot accidentally read a partially checked set.
 */
export async function fetchVerifiedWeights(
	source: EncoderSource,
	options: {
		fetch?: typeof globalThis.fetch;
		signal?: AbortSignal;
		onBytes?: (loaded: number) => void;
	} = {}
): Promise<WeightsOutcome> {
	const paths = manifestPaths(source);
	if (!source.baseUrl || !source.revision || paths.length === 0 || source.deadlineMs <= 0) {
		return { ok: false, reason: 'off' };
	}

	const get = options.fetch ?? globalThis.fetch;
	const clock = new AbortController();
	const expired = setTimeout(() => clock.abort(), source.deadlineMs);
	const stop = () => clock.abort();
	options.signal?.addEventListener('abort', stop);

	const files = new Map<string, ArrayBuffer>();
	let loaded = 0;
	try {
		for (const path of paths) {
			let response: Response;
			try {
				response = await get(remoteUrl(source, path), { signal: clock.signal });
			} catch {
				return { ok: false, reason: clock.signal.aborted ? 'timeout' : 'unreachable', path };
			}
			if (!response.ok) return { ok: false, reason: 'refused', path };

			let bytes: ArrayBuffer;
			try {
				bytes = await response.arrayBuffer();
			} catch {
				// A body that stops early lands here, and it is a truncation rather
				// than a bad digest. Both discard the set; only the sentence differs.
				return { ok: false, reason: clock.signal.aborted ? 'timeout' : 'refused', path };
			}
			if ((await sha256Hex(bytes)) !== source.digests[path]) {
				return { ok: false, reason: 'mismatch', path };
			}
			files.set(path, bytes);
			loaded += bytes.byteLength;
			options.onBytes?.(loaded);
		}
		return { ok: true, files };
	} finally {
		clearTimeout(expired);
		options.signal?.removeEventListener('abort', stop);
	}
}
