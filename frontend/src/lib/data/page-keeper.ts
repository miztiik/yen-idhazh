/**
 * What does a page keep of what the query door fetched, and of what it told the console?
 *
 * Each index it read, the name the engine holds each file it fetched whole under,
 * and each line it printed, so no index or whole file crosses the network or
 * enters the engine twice, and no line reaches the console twice.
 *
 * A keeper lives as long as whoever made it. In a browser, `ledger.ts` makes one
 * on first use and keeps it until the page is reloaded, except the Data explorer page
 * calls `startAfresh()` on Refresh; every panel the page draws asks through it. At build time `sliceFromDisk()` makes one for each call
 * and releases it when the call ends.
 *
 * **An index is fetched once and kept.** What the fetch returned - the bytes, or
 * `null` for a file that is not there - answers every later ask, and two asks at
 * the same moment share one fetch. So every slice and every reach on one page
 * acts on the same index, and a page shows the data it opened with until it is
 * reloaded. A fetch that threw is not kept, so the next ask tries again.
 *
 * **A data file fetched whole enters the engine once, and the keeper holds its
 * name, never its bytes.** A file is known by its path and the version its index
 * entry names. It is fetched once, checked against the length its entry gives,
 * and handed to the engine, which mints the name every later ask gets. A
 * browser's engine takes the buffer it is handed and leaves the page's copy
 * empty, so bytes kept here would read as an empty file the second time. A file
 * that is not there is kept as absent. A fetch that threw, or bytes of the wrong
 * length, is neither registered nor kept, so the next ask tries again.
 *
 * **A file the door reads by byte range is never fetched here, and never kept.**
 * When a wanted file asks for that, the source has an address for it and the
 * engine reads a host, the engine opens the file at an address the source made
 * for this one call, and asks the host only for the parts the call's query
 * needs. The length it opened is checked against the entry, as a fetched file's
 * is, and a file of another length is dropped. The caller drops the rest when its
 * query ends (`done`), so the next call opens the file again at a new address,
 * where the browser holds no part fetched before a deploy changed the file's
 * ETag. A source with no address, or an engine that reads no host, gets the file
 * fetched whole instead, and kept like any other.
 *
 * **The engine starts beside the selected data fetches.** The reader has already
 * validated the indexes and selected non-empty files before calling `hold`, so
 * a quiet span or missing index starts no engine. A failed data fetch can still
 * overlap startup, without registering its bytes or hiding its fault.
 *
 * **A console line is printed once for the keeper's life.** A missing file is
 * met by every panel that reads it, and fifteen panels on one page would print
 * fifteen copies of one fault; the line names the fault and the path, so its
 * first copy says everything the others would.
 *
 * Imports nothing tied to one environment, so a Node test loads it as it is.
 */

import type { OpenedAddress, QueryEngine } from './slice-query';

/** Where the door's bytes come from, given a path under the state root.
 *  `null` means there is no such file; anything else that goes wrong is thrown. */
export interface ByteSource {
	/** An index, asked for fresh rather than from a cache. A keeper asks once and keeps the answer. */
	index(path: string): Promise<Uint8Array | null>;
	/** A data file, and the version its index entry names, which a cache may key on. */
	data(path: string, version: string): Promise<Uint8Array | null>;
	/** Where an engine that reads a host itself finds a data file, by the path and
	 *  version `data` takes, for one read: each call answers an address no earlier
	 *  call answered. Absent from a source with no host, such as a disk. */
	address?(path: string, version: string): string;
}

/** Starts the engine, or hands back the one already started. */
export type EngineOpener = () => Promise<QueryEngine>;

/** One data file a call needs: where it sits, the version its entry names, the
 *  length in bytes its entry gives, and whether the engine may read it by byte
 *  range rather than whole. */
export interface WantedFile {
	path: string;
	version: string;
	bytes: number;
	byRange: boolean;
}

/** Why a wanted file could not be had. `opened` is the length the engine found
 *  at a file's address, where it reads the file by byte range. */
export type FileShortfall =
	| { reason: 'absent' }
	| { reason: 'length'; arrived: number }
	| { reason: 'opened'; length: number }
	| { reason: 'fetch'; error: unknown };

/** Every wanted file as the engine holds it, by name in the order asked, and
 *  `done`, which drops the files opened at an address for this call alone and is
 *  called once the call's query has ended, answered or not; or the first file
 *  that could not be had, and why, with nothing of this call's left open. */
export type Holding =
	| { engine: QueryEngine; names: string[]; fetched: boolean[]; done(): Promise<void> }
	| { failed: number; shortfall: FileShortfall };

/** What one page keeps, and the three things a caller asks of it. */
export interface PageKeeper {
	/** An index: its bytes, or `null` when there is no such file. Rejects when the fetch threw. */
	index(path: string): Promise<Uint8Array | null>;
	/** Has the engine hold every file in `files`, fetching and registering only
	 *  what this keeper does not hold yet, and opening a file it reads by byte
	 *  range for this call alone. Rejects when the engine cannot start or cannot
	 *  take a file. */
	hold(files: readonly WantedFile[]): Promise<Holding>;
	/** Drops every file this keeper keeps registered. A build-time call does this when it ends; the Data explorer page also does it when Refresh starts afresh. */
	release(): Promise<void>;
	/** Whole-file bytes this keeper currently holds in the engine. Byte-range files are not kept. */
	heldBytes(): number;
	/** Prints `line` as a console warning the first time this keeper meets it, and never again. */
	warn(line: string): void;
}

type Arrival = { bytes: Uint8Array } | FileShortfall;

/** What registering one file came to: the name the engine reads it under, or why it cannot be had. */
type Registration = { name: string } | FileShortfall;

/** Drops `key` only while `held` still maps it to `value`, so a newer ask for the same key is left alone. */
function forget<T>(held: Map<string, T>, key: string, value: T): void {
	if (held.get(key) === value) held.delete(key);
}

/** A keeper that reads through `source` and registers with the engine `openEngine` starts. */
export function pageKeeper(source: ByteSource, openEngine: EngineOpener): PageKeeper {
	const indexes = new Map<string, Promise<Uint8Array | null>>();
	/** Data files in flight, files that were not there, and bytes waiting for the engine. */
	const arrivals = new Map<string, Promise<Arrival>>();
	/** The name the engine holds each registered file under, and each registration in flight. */
	const names = new Map<string, Promise<Registration>>();
	/** Whole files the engine keeps for this page, by key. */
	const heldLengths = new Map<string, number>();
	/** Every line this keeper has printed. */
	const told = new Set<string>();
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

	/** Keeps a registration while it is in flight or has a name. One that came to a
	 *  shortfall, or threw, is not kept, so the next ask registers the file again. */
	function keep(key: string, registering: Promise<Registration>): Promise<Registration> {
		names.set(key, registering);
		registering.then(
			(one) => {
				if ('reason' in one) forget(names, key, registering);
			},
			() => forget(names, key, registering)
		);
		return registering;
	}

	/** Hands fetched bytes to the engine, unless another call already has. */
	function handOver(engine: QueryEngine, key: string, bytes: Uint8Array): Promise<Registration> {
		heldLengths.set(key, bytes.byteLength);
		return names.get(key) ?? keep(key, engine.register(bytes).then((name) => ({ name })));
	}

	/** Has the engine open a file at its address, and refuses a length its entry does not give. */
	async function openAt(engine: QueryEngine, file: WantedFile, address: string): Promise<Registration> {
		let opened: OpenedAddress;
		try {
			opened = await engine.registerAddress!(address);
		} catch (error) {
			return { reason: 'fetch', error };
		}
		if (opened.bytes === file.bytes) return { name: opened.name };
		await engine.drop([opened.name]);
		return { reason: 'opened', length: opened.bytes };
	}

	/** A file with an address the engine cannot read, fetched whole now instead. */
	async function fetchedLate(engine: QueryEngine, file: WantedFile, key: string): Promise<Registration> {
		const arriving = arrive(file, key);
		const late = await arriving;
		if (!('bytes' in late)) return late;
		forget(arrivals, key, arriving);
		return handOver(engine, key, late.bytes);
	}

	/** The engine's name for one file this keeper keeps, registering it unless it already holds it. */
	function registration(
		engine: QueryEngine,
		file: WantedFile,
		key: string,
		address: string | null,
		arrival: Arrival | null
	): { registration: Promise<Registration>; fetched: boolean } {
		const named = names.get(key);
		if (named !== undefined) return { registration: named, fetched: false };
		if (address !== null) return { registration: fetchedLate(engine, file, key), fetched: true };
		if (arrival === null || !('bytes' in arrival)) {
			return {
				registration: Promise.reject(new Error(`${key} was being registered by another call, and that registration failed`)),
				fetched: false
			};
		}
		return { registration: handOver(engine, key, arrival.bytes), fetched: true };
	}

	async function hold(files: readonly WantedFile[]): Promise<Holding> {
		const keys = files.map((file) => `${file.path}?v=${file.version}`);
		const addresses = files.map((file) =>
			file.byRange && source.address !== undefined ? source.address(file.path, file.version) : null
		);
		const starting = openEngine();
		void starting.catch(() => undefined);
		const arriving = files.map((file, at) =>
			names.has(keys[at]) || addresses[at] !== null ? null : arrive(file, keys[at])
		);
		let arrived: (Arrival | null)[] = [];
		try {
			arrived = await Promise.all(arriving);
			const failed = arrived.findIndex((one) => one !== null && 'reason' in one);
			if (failed !== -1) return { failed, shortfall: arrived[failed] as FileShortfall };
			const engine = await starting;
			registeredWith = engine;
			// A file the engine opens at an address is this call's alone: never kept, and dropped by `done`.
			const opening = files.map((file, at) => {
				const address = addresses[at];
				return address !== null && engine.registerAddress !== undefined && !names.has(keys[at])
					? openAt(engine, file, address)
					: null;
			});
			const done = async (): Promise<void> => {
				const settled = await Promise.allSettled(opening.filter((one): one is Promise<Registration> => one !== null));
				const opened = settled.flatMap((one) => (one.status === 'fulfilled' && 'name' in one.value ? [one.value.name] : []));
				if (opened.length > 0) await engine.drop(opened);
			};
			let held: Registration[];
			const fetched: boolean[] = [];
			try {
				const registrations = files.map((file, at) => {
					if (opening[at] !== null) {
						fetched[at] = true;
						return opening[at]!;
					}
					const one = registration(engine, file, keys[at], addresses[at], arrived[at]);
					fetched[at] = one.fetched;
					return one.registration;
				});
				held = await Promise.all(registrations);
			} catch (error) {
				await done();
				throw error;
			}
			const named: string[] = [];
			for (const [at, one] of held.entries()) {
				if ('reason' in one) {
					await done();
					return { failed: at, shortfall: one };
				}
				named.push(one.name);
			}
			return { engine, names: named, fetched, done };
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
		heldLengths.clear();
		const held = settled.flatMap((one) => (one.status === 'fulfilled' && 'name' in one.value ? [one.value.name] : []));
		if (registeredWith !== null && held.length > 0) await registeredWith.drop(held);
	}

	function heldBytes(): number {
		let total = 0;
		for (const bytes of heldLengths.values()) total += bytes;
		return total;
	}

	function warn(line: string): void {
		if (told.has(line)) return;
		told.add(line);
		console.warn(line);
	}

	return { index, hold, release, heldBytes, warn };
}
