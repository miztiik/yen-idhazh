/**
 * What does the canary's packed article, score and machine record hold, read the way the console's own server reads it?
 *
 * The browser suite is built from the canary tree, and the three records a
 * console route reads at build time come from their packed files only. So an
 * oracle that recomputes a panel reads them through the same readers the page's
 * server calls - `itemHealthRows`, `evalRows` and `machineRecord` - and a change
 * in how the records are filed cannot leave it comparing the page against an
 * empty set, which is what a walk of the old day files would now do.
 *
 * `-1` reads every packed day. The canary is a fixture of fixed size rather than
 * a collection a run appends to, so the read costs the same on every run
 * (`CLAUDE.md` Guardrail #12).
 *
 * Each record is read once per worker and shared by every test that asks, and
 * it is read when a test first asks rather than when a spec loads, so a canary
 * that was not built fails the tests that needed it, with the reader's own
 * message, and no other test (`CLAUDE.md` section 13).
 */

import { resolve } from 'node:path';
import { machineRecord } from '../../src/lib/server/host-fingerprint';
import { evalRows, itemHealthRows, type LedgerTable } from '../../src/lib/server/ledger-rows';

/** The canary's state tree, beside the digest `build:canary` builds the site from. */
export const CANARY_STATE = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'state');

let articles: Promise<LedgerTable> | null = null;
let scores: Promise<LedgerTable> | null = null;
let machines: Promise<LedgerTable> | null = null;

/** Every row a packed canary record holds, or a failure naming what was not read. */
async function rowsOf(table: Promise<LedgerTable>, record: string): Promise<Record<string, string>[]> {
	const { rows, read } = await table;
	if (read.state !== 'read') {
		throw new Error(
			`the canary's ${record} record was not read (${JSON.stringify(read)}). ` +
				'Build it with `npm run build:canary`, which packs every fixture day.'
		);
	}
	return rows;
}

/** Every article row the canary packed: one per planned item per run. */
export function canaryArticleRows(): Promise<Record<string, string>[]> {
	articles ??= itemHealthRows(-1, CANARY_STATE);
	return rowsOf(articles, 'article');
}

/** Every score row the canary packed: one per scored measurement. */
export function canaryScoreRows(): Promise<Record<string, string>[]> {
	scores ??= evalRows(-1, CANARY_STATE);
	return rowsOf(scores, 'score');
}

/** Every machine row the canary packed: one per job per run. */
export function canaryMachineRows(): Promise<Record<string, string>[]> {
	machines ??= machineRecord(-1, CANARY_STATE);
	return rowsOf(machines, 'machine');
}

/** One record's rows, read in a hook and handed to a spec's synchronous helpers.
 *
 * For a spec whose oracles call one another several levels deep, where making
 * every level wait would rewrite the spec rather than its reads. `load` goes in
 * `test.beforeAll`; it never throws, so a canary that was not built fails only
 * the tests that call `rows`, each with the reader's own message, rather than
 * every test in the file.
 */
export function heldRows(read: () => Promise<Record<string, string>[]>): {
	load: () => Promise<void>;
	rows: () => Record<string, string>[];
} {
	let held: Record<string, string>[] | Error | null = null;
	return {
		async load() {
			try {
				held = await read();
			} catch (error) {
				held = error instanceof Error ? error : new Error(String(error));
			}
		},
		rows() {
			if (held === null) throw new Error('the canary rows were asked for before the hook that reads them ran');
			if (held instanceof Error) throw held;
			return held;
		}
	};
}
