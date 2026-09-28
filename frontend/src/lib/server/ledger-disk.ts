/**
 * How does a build-time reader ask a committed ledger for a slice?
 *
 * `sliceFromDisk()` runs the query door's own reader over the compacted files
 * under a state root on disk - `STATE_ROOT` from `payload.ts` when the site is
 * built - so a build-time page and a browser panel asking for the same span get
 * the same rows from the same files. It lives under `$lib/server/`, so SvelteKit
 * refuses to put it, or the engine's Node half it starts, into anything a
 * browser receives. A console panel calls `slice()` in `$lib/data/ledger` instead.
 */

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';
// Relative, not `$lib`: the logic suite imports this module in plain Node, where
// no Vite alias exists to resolve one.
import { nodeEngine } from '../data/engine';
import { readSlice, type ByteSource } from '../data/slice-reader';
import type { LedgerName, SliceOptions, SliceResult } from '../data/slice-shapes';
import { engineExtensionRepository } from './config';

const resolver = createRequire(import.meta.url);

/** Where a file inside an installed package sits on this disk. */
const locate = (specifier: string): string => resolver.resolve(specifier);

/** A byte source over a state root on disk. A file that is not there is absent. */
export function diskBytes(stateDir: string): ByteSource {
	async function bytesAt(path: string): Promise<Uint8Array | null> {
		try {
			return new Uint8Array(await readFile(join(stateDir, ...path.split('/'))));
		} catch (error) {
			if ((error as NodeJS.ErrnoException).code === 'ENOENT') return null;
			throw error;
		}
	}
	return { index: bytesAt, data: (path) => bytesAt(path) };
}

/** The same query as `slice()`, over the same compacted files, read from disk while the site is built. */
export function sliceFromDisk(stateDir: string, ledger: LedgerName, options: SliceOptions): Promise<SliceResult> {
	return readSlice(diskBytes(stateDir), () => nodeEngine(locate, engineExtensionRepository()), ledger, options);
}
