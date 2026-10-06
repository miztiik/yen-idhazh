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
 * Each is read over the window the console's own server reads: the widest one its
 * control offers, ending on the canary's newest published day. The canary is a
 * fixture of fixed size rather than a collection a run appends to, so the read
 * costs the same on every run (`CLAUDE.md` Guardrail #12).
 *
 * Each record is read once per worker and shared by every test that asks, and
 * it is read when a test first asks rather than when a spec loads, so a canary
 * that was not built fails the tests that needed it, with the reader's own
 * message, and no other test (`CLAUDE.md` section 13).
 */

import { resolve } from 'node:path';
import { windowOfDays, type TimeWindow } from '../../src/lib/charts/viewport';
import { consoleConfig } from '../../src/lib/server/config';
import { machineRecord } from '../../src/lib/server/host-fingerprint';
import { evalRows, itemHealthRows, type LedgerTable } from '../../src/lib/server/ledger-rows';
import { windowDay } from '../../src/lib/server/window-day';

/** The canary's state tree, beside the digest `build:canary` builds the site from. */
export const CANARY_STATE = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'state');

/** Every day a console route reads over the canary: the widest window the control
 * offers, ending on the canary's newest published day, placed as the route places it. */
export function canaryWindow(): TimeWindow {
	const console = consoleConfig();
	return windowOfDays(
		windowDay(resolve(CANARY_STATE, '..', 'digest')),
		Math.max(...console.window_presets),
		console.today_anchor
	);
}

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
	articles ??= itemHealthRows(canaryWindow(), CANARY_STATE);
	return rowsOf(articles, 'article');
}

/** Every score row the canary packed: one per scored measurement. */
export function canaryScoreRows(): Promise<Record<string, string>[]> {
	scores ??= evalRows(canaryWindow(), CANARY_STATE);
	return rowsOf(scores, 'score');
}

/** Every machine row the canary packed: one per job per run. */
export function canaryMachineRows(): Promise<Record<string, string>[]> {
	machines ??= machineRecord(canaryWindow(), CANARY_STATE);
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
