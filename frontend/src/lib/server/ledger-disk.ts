/**
 * How does a build-time reader ask a committed ledger for a slice, or for how far it reaches?
 *
 * `sliceFromDisk()` runs the query door's own reader over the compacted files
 * under a state root on disk - `STATE_ROOT` from `payload.ts` when the site is
 * built - so a build-time page and a browser panel asking for the same span get
 * the same rows from the same files. `reachFromDisk()` is the disk twin of
 * `ledgerReach()`, so a build-time reader learns how far a ledger is packed and
 * where its rows stop without reading a data file. Both live under `$lib/server/`, so
 * SvelteKit refuses to put them, or the engine's Node half they start, into
 * anything a browser receives. A console panel calls `slice()` in
 * `$lib/data/ledger` instead.
 *
 * **Each call keeps what it read for itself alone.** It makes a fresh page
 * keeper, so it reads the indexes as the disk holds them now, and when it ends
 * it drops every file it handed the engine. A build reads many ledgers and days
 * in one process, and a development server reads `state/` again as it changes,
 * so a keeper that outlived the call would hold every file for the life of the
 * process and answer from indexes the disk no longer holds. So a missing file's
 * fault, named as a browser panel's answer names it, is printed once a call.
 */

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';
// Relative, not `$lib`: the logic suite imports this module in plain Node, where
// no Vite alias exists to resolve one.
import { nodeEngine } from '../data/engine';
import { readReach, type LedgerReach } from '../data/ledger-reach';
import { pageKeeper, type ByteSource } from '../data/page-keeper';
import { readSlice } from '../data/slice-reader';
import type { LedgerName, SliceOptions, SliceResult } from '../data/slice-shapes';
import { engineExtensionRepository } from './config';

const resolver = createRequire(import.meta.url);

/** Where a file inside an installed package sits on this disk. */
const locate = (specifier: string): string => resolver.resolve(specifier);

/** A fresh page keeper over a state root, for one call and no longer. */
function diskKeeper(stateDir: string) {
	return pageKeeper(diskBytes(stateDir), () => nodeEngine(locate, engineExtensionRepository()));
}

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
export async function sliceFromDisk(stateDir: string, ledger: LedgerName, options: SliceOptions): Promise<SliceResult> {
	const keeper = diskKeeper(stateDir);
	try {
		return await readSlice(keeper, ledger, options);
	} finally {
		await keeper.release();
	}
}

/** The same answer as `ledgerReach()`, from the indexes on disk. Reads no data file and starts no engine. */
export async function reachFromDisk(stateDir: string, ledger: LedgerName): Promise<LedgerReach> {
	const keeper = diskKeeper(stateDir);
	try {
		return await readReach(keeper, ledger);
	} finally {
		await keeper.release();
	}
}
