/**
 * What does a page keep of what the query door fetched?
 *
 * Each index it read, and the name the engine holds each data file under, so
 * nothing crosses the network or enters the engine twice.
 *
 * A keeper lives as long as whoever made it. In a browser, `ledger.ts` makes one
 * on first use and keeps it until the page is reloaded, so every panel the page
 * draws asks through it. At build time `sliceFromDisk()` makes one for each call
 * and releases it when the call ends.
 *
 * **An index is fetched once and kept.** What the fetch returned - the bytes, or
 * `null` for a file that is not there - answers every later ask, and two asks at
 * the same moment share one fetch. So every slice and every reach on one page
 * acts on the same index, and a page shows the data it opened with until it is
 * reloaded. A fetch that threw is not kept, so the next ask tries again.
 *
 * **A data file enters the engine once, and the keeper holds its name, never its
 * bytes.** A file is known by its path and the version its index entry names. It
 * is fetched once, checked against the length its entry gives, and handed to the
 * engine, which mints the name every later ask gets. A browser's engine takes
 * the buffer it is handed and leaves the page's copy empty, so bytes kept here
 * would read as an empty file the second time. A file that is not there is kept
 * as absent. A fetch that threw, or bytes of the wrong length, is neither
 * registered nor kept, so the next ask tries again.
 *
 * **The engine starts only when every file a call needs has arrived whole**, so
 * a call that cannot be answered never loads it.
 *
 * Imports nothing tied to one environment, so a Node test loads it as it is.
 */

import type { QueryEngine } from './slice-query';

/** Where the door's bytes come from, given a path under the state root.
 *  `null` means there is no such file; anything else that goes wrong is thrown. */
export interface ByteSource {
	/** An index, asked for fresh rather than from a cache. A keeper asks once and keeps the answer. */
	index(path: string): Promise<Uint8Array | null>;
	/** A data file, and the version its index entry names, which a cache may key on. */
	data(path: string, version: string): Promise<Uint8Array | null>;
}

/** Starts the engine, or hands back the one already started. */
export type EngineOpener = () => Promise<QueryEngine>;

/** One data file a call needs: where it sits, the version its entry names, and
 *  the length in bytes its entry gives. */
export interface WantedFile {
	path: string;
	version: string;
	bytes: number;
}

/** Why a wanted file could not be had. */
export type FileShortfall =
	| { reason: 'absent' }
	| { reason: 'length'; arrived: number }
	| { reason: 'fetch'; error: unknown };

/** Every wanted file as the engine holds it, by name in the order asked; or the
 *  first one that could not be had, and why. */
export type Holding = { engine: QueryEngine; names: string[] } | { failed: number; shortfall: FileShortfall };

/** What one page keeps, and the three things a caller asks of it. */
export interface PageKeeper {
	/** An index: its bytes, or `null` when there is no such file. Rejects when the fetch threw. */
	index(path: string): Promise<Uint8Array | null>;
	/** Has the engine hold every file in `files`, fetching and registering only
	 *  what this keeper does not hold yet. Rejects when the engine cannot start or
	 *  cannot take a file. */
	hold(files: readonly WantedFile[]): Promise<Holding>;
	/** Drops every file this keeper registered. A build-time call does this when it ends; a page never does. */
	release(): Promise<void>;
}

type Arrival = { bytes: Uint8Array } | FileShortfall;

/** Drops `key` only while `held` still maps it to `value`, so a newer ask for the same key is left alone. */
function forget<T>(held: Map<string, T>, key: string, value: T): void {
	if (held.get(key) === value) held.delete(key);
}

/** A keeper that reads through `source` and registers with the engine `openEngine` starts. */
export function pageKeeper(source: ByteSource, openEngine: EngineOpener): PageKeeper {
	const indexes = new Map<string, Promise<Uint8Array | null>>();
	/** Data files in flight, files that were not there, and bytes waiting for the engine. */
	const arrivals = new Map<string, Promise<Arrival>>();
	/** The name the engine holds each registered file under. */
	const names = new Map<string, Promise<string>>();
	let registeredWith: QueryEngine | null = null;

	function index(path: string): Promise<Uint8Array | null> {
		const kept = indexes.get(path);
		if (kept !== undefined) return kept;
		const asked = source.index(path);
		indexes.set(path, asked);
		asked.catch(() => forget(indexes, path, asked));
		return asked;
	}

	function arrive(file: WantedFile, key: string): Promise<Arrival> {
		const kept = arrivals.get(key);
		if (kept !== undefined) return kept;
		const arriving = source.data(file.path, file.version).then(
			(bytes): Arrival => {
				if (bytes === null) return { reason: 'absent' };
				if (bytes.byteLength !== file.bytes) return { reason: 'length', arrived: bytes.byteLength };
				return { bytes };
			},
			(error: unknown): Arrival => ({ reason: 'fetch', error })
		);
		arrivals.set(key, arriving);
		void arriving.then((arrival) => {
			if ('reason' in arrival && arrival.reason !== 'absent') forget(arrivals, key, arriving);
		});
		return arriving;
	}

	function nameFor(engine: QueryEngine, key: string, arrival: Arrival | null): Promise<string> {
		const named = names.get(key);
		if (named !== undefined) return named;
		if (arrival === null || !('bytes' in arrival)) {
			return Promise.reject(new Error(`${key} was being registered by another call, and that registration failed`));
		}
		const registering = engine.register(arrival.bytes);
		names.set(key, registering);
		registering.catch(() => forget(names, key, registering));
		return registering;
	}

	async function hold(files: readonly WantedFile[]): Promise<Holding> {
		const keys = files.map((file) => `${file.path}?v=${file.version}`);
		const arriving = files.map((file, at) => (names.has(keys[at]) ? null : arrive(file, keys[at])));
		let arrived: (Arrival | null)[] = [];
		try {
			arrived = await Promise.all(arriving);
			const failed = arrived.findIndex((one) => one !== null && 'reason' in one);
			if (failed !== -1) return { failed, shortfall: arrived[failed] as FileShortfall };
			const engine = await openEngine();
			registeredWith = engine;
			return { engine, names: await Promise.all(keys.map((key, at) => nameFor(engine, key, arrived[at]))) };
		} finally {
			// Bytes wait here only until the engine has them, and never past the call that fetched them.
			arriving.forEach((one, at) => {
				const arrival = arrived[at];
				if (one !== null && arrival !== undefined && arrival !== null && 'bytes' in arrival) {
					forget(arrivals, keys[at], one);
				}
			});
		}
	}

	async function release(): Promise<void> {
		const settled = await Promise.allSettled([...names.values()]);
		names.clear();
		const held = settled.flatMap((one) => (one.status === 'fulfilled' ? [one.value] : []));
		if (registeredWith !== null && held.length > 0) await registeredWith.drop(held);
	}

	return { index, hold, release };
}
