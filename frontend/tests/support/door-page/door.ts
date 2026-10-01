/** What does a browser spec's page call to ask the query door for a slice?
 *
 * The door as a console panel reaches it - a page keeper over this site's byte
 * source and this tab's engine, made the way `ledger.ts` makes one - built into a
 * page of its own, because no route on the site calls `slice()` yet and a route
 * that exists only to host a test would ship to a reader. `ledger.ts` itself is
 * not imported: it takes its prefix from `$app/paths`, which only a SvelteKit
 * build provides, so each call names the data root it reads. Each root keeps one
 * keeper a page, as `ledger.ts` keeps one, so a second slice on a page acts on
 * what the first kept; the engine starts once a page, as `ledger.ts` starts it,
 * and fetches its add-on from this host, so the page reaches no other.
 */

import { browserEngine } from '../../../src/lib/data/engine';
import { fetchedBytes } from '../../../src/lib/data/fetched-bytes';
import { pageKeeper, type PageKeeper } from '../../../src/lib/data/page-keeper';
import { readSlice } from '../../../src/lib/data/slice-reader';
import type { LedgerName, SliceOptions, SliceResult } from '../../../src/lib/data/slice-shapes';

/** Which files the engine reads by byte range: the ones the door picks, every one, or none. */
export type RangeChoice = 'door' | 'every-file' | 'no-file';

/** One answer, the milliseconds from the call to its rows, and what the door printed. */
export interface TimedSlice {
	result: SliceResult;
	ms: number;
	warned: string[];
}

/** A timed answer reduced to what a measurement compares, so ten thousand rows
 *  never cross back to the spec: the state, the row count and a digest of the rows. */
export interface MeasuredSlice {
	state: SliceResult['state'];
	rows: number;
	digest: string;
	ms: number;
	warned: string[];
}

const REPOSITORY = new URL('/ext', location.href).href;

const keepers = new Map<string, PageKeeper>();

function keeperFor(root: string, choice: RangeChoice): PageKeeper {
	const key = `${root} ${choice}`;
	const held = keepers.get(key);
	if (held !== undefined) return held;
	const made = pageKeeper(
		fetchedBytes(`/${root}`, (url, init) => fetch(url, init)),
		() => browserEngine(REPOSITORY)
	);
	const byRange = choice === 'every-file';
	const kept: PageKeeper =
		choice === 'door' ? made : { ...made, hold: (files) => made.hold(files.map((file) => ({ ...file, byRange }))) };
	keepers.set(key, kept);
	return kept;
}

/** One slice of a ledger under the data root `root`, timed from the call to its rows. */
async function slice(root: string, ledger: LedgerName, options: SliceOptions, choice: RangeChoice): Promise<TimedSlice> {
	const warned: string[] = [];
	const original = console.warn;
	console.warn = (...parts: unknown[]) => {
		warned.push(parts.map(String).join(' '));
		original(...parts);
	};
	try {
		const started = performance.now();
		const result = await readSlice(keeperFor(root, choice), ledger, options);
		return { result, ms: performance.now() - started, warned };
	} finally {
		console.warn = original;
	}
}

/** The same slice, reduced after the clock stops. The digest is 32-bit FNV-1a over the rows as JSON. */
async function measure(root: string, ledger: LedgerName, options: SliceOptions, choice: RangeChoice): Promise<MeasuredSlice> {
	const { result, ms, warned } = await slice(root, ledger, options, choice);
	let hash = 0x811c9dc5;
	for (const unit of JSON.stringify(result.rows)) {
		hash = Math.imul(hash ^ unit.charCodeAt(0), 0x01000193) >>> 0;
	}
	return { state: result.state, rows: result.rows.length, digest: hash.toString(16), ms, warned };
}

/** The name of every file this page's engine holds now, in order. */
async function held(): Promise<string[]> {
	const engine = await browserEngine(REPOSITORY);
	return (await engine.rows(`SELECT file FROM glob('door/*') ORDER BY file`, [])).map((row) => String(row.file));
}

declare global {
	interface Window {
		door: { slice: typeof slice; measure: typeof measure; held: typeof held };
	}
}

window.door = { slice, measure, held };
