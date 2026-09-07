/** The telemetry a console session holds, as revision-owned month shards.
 *
 * The page opens on a seed the server inlined - one window of rows - and grows
 * it by fetching a month file when the operator widens or pans past what the
 * seed covers. This is where those rows live between fetches.
 *
 * Three things it does that the old inline map did not:
 *
 * **A month is one shard, and a fetch replaces the shard whole.** A correction
 * that removed a row reaches the page, because the new shard owns the month and
 * the row that is gone from it is gone from the hold (Fowler). The old merge
 * only ever added, so a retracted row lived on for the session.
 *
 * **An observation is a run, an item AND a stage.** A run carries an item
 * through fetch, extract, summarize and publish, so run+item names four rows,
 * not one. Keying on run+item collapsed them to the last stage seen, which the
 * failure-by-stage panels read as three missing stages (Andre).
 *
 * **Only fetched months grow, so only fetched months are bounded.** The seed is
 * a fixed one or two months and the page's fallback; what accumulates over a
 * long session of panning is the fetched shards, and the ceiling is the count
 * of months the widest window can touch - so the window in force is always in
 * hand and memory does not climb with the session (Carmack, Rule #12).
 */

import type { TelemetryRow } from './series';
import { monthsInWindow, type TimeWindow } from './viewport';

/** The month a dated row belongs to, e.g. `2026-08-20` -> `2026-08`. */
function monthOf(date: string): string {
	return date.slice(0, 7);
}

/** The first day of a month, e.g. `2026-08` -> `2026-08-01`. */
function monthStart(month: string): string {
	return `${month}-01`;
}

/** One observation's identity inside its month.
 *
 * The stage is part of it on purpose: two rows that share a run and an item but
 * not a stage are two legitimate observations, and a later fetch of the same
 * month must keep both. The NUL byte cannot occur in a run id, an item id or a
 * stage, so no two identities collide by running together at a separator.
 */
function identity(row: TelemetryRow): string {
	return `${row.run_id}\u0000${row.item_id}\u0000${row.stage}`;
}

export interface TelemetryHold {
	/** Rows by month, each month owning the observations dated in it, keyed by
	 * identity. Iteration is insertion order, which is touch order: a fetched
	 * month moves to the end, and eviction drops from the front. */
	shards: Map<string, Map<string, TelemetryRow>>;
	/** Months whose whole CSV shard is in hand - a complete, retractable set. A
	 * seed month is not here: the seed is a slice of a month, not a month. */
	loaded: Set<string>;
	/** The months the seed provided. Kept out of eviction, because the seed is
	 * the SSR fallback and a fixed size, not the thing that grows. */
	seeded: Set<string>;
	/** The oldest day the seed covers, or null for an empty seed. The seed
	 * carries every row on or after this day, so a window that reaches no
	 * further back needs no fetch - even into a month the seed only partly fills.
	 */
	seedStart: string | null;
}

/** Build a hold from the rows the server inlined, and the day they reach back
 * to.
 *
 * `seedStart` is the seed window's start, not the oldest row in it: the seed is
 * complete for the whole span it covers, so a month with no rows in that span
 * is still covered there and costs no fetch. Pass the window the page opens on.
 */
export function seedHold(rows: readonly TelemetryRow[], seedStart: string | null): TelemetryHold {
	const shards = new Map<string, Map<string, TelemetryRow>>();
	const seeded = new Set<string>();
	for (const row of rows) {
		const month = monthOf(row.date);
		let shard = shards.get(month);
		if (shard === undefined) {
			shard = new Map();
			shards.set(month, shard);
		}
		shard.set(identity(row), row);
		seeded.add(month);
	}
	return { shards, loaded: new Set(), seeded, seedStart };
}

/** Every held row, oldest day first. What the page hands its charts.
 *
 * Bounded by the ceiling, not by the archive: at most the widest window's
 * months of rows are ever held, so this sort is over a fixed input however long
 * the pipeline runs (Rule #12).
 */
export function holdRows(hold: TelemetryHold): TelemetryRow[] {
	const rows: TelemetryRow[] = [];
	for (const shard of hold.shards.values()) rows.push(...shard.values());
	return rows.sort((a, b) => a.date.localeCompare(b.date));
}

/** The months in view this hold still has to fetch.
 *
 * A month is fetched when the window reaches into it, the pipeline published
 * it, and the hold does not already cover that reach. It is covered when it is
 * fully loaded, or when the part of it the window reaches is no older than the
 * seed. The one case that used to be missed is the older part of a month the
 * seed only partly fills: the seed marked the whole month loaded, so the older
 * days never fetched and the gap never healed.
 *
 * A month the pipeline never published is never returned: asking for it would
 * only produce a 404 and a gap the charts already draw.
 */
export function monthsToLoad(
	hold: TelemetryHold,
	window: TimeWindow,
	available: readonly string[]
): string[] {
	const published = new Set(available);
	const wanted: string[] = [];
	for (const month of monthsInWindow(window)) {
		if (!published.has(month)) continue;
		if (hold.loaded.has(month)) continue;
		const reach = window.start > monthStart(month) ? window.start : monthStart(month);
		if (hold.seedStart !== null && reach >= hold.seedStart) continue;
		wanted.push(month);
	}
	return wanted;
}

/** Replace a month's owned rows with a freshly fetched shard.
 *
 * The whole month is replaced, not merged, so a row a correction removed is
 * gone from the hold. The month is marked loaded here and only here - on a
 * shard that arrived - so a fetch that failed leaves the month unloaded for a
 * later attempt to fill. A row not dated in this month is ignored: a shard owns
 * its own month and nothing else.
 */
export function applyShard(
	hold: TelemetryHold,
	month: string,
	rows: readonly TelemetryRow[],
	ceiling: number
): TelemetryHold {
	const shard = new Map<string, TelemetryRow>();
	for (const row of rows) {
		if (monthOf(row.date) !== month) continue;
		shard.set(identity(row), row);
	}
	const shards = new Map(hold.shards);
	// Delete then set, so the month lands at the end - the newest touch, and the
	// last a bound would evict.
	shards.delete(month);
	shards.set(month, shard);
	const loaded = new Set(hold.loaded);
	loaded.add(month);
	const next: TelemetryHold = { shards, loaded, seeded: hold.seeded, seedStart: hold.seedStart };
	evict(next, ceiling);
	return next;
}

/** Drop fetched months past the ceiling, oldest touch first.
 *
 * Seed months are never dropped: they are the page's fallback and a fixed size,
 * so bounding them would trade a constant for a fetch. What the ceiling bounds
 * is the fetched shards, which are what a session of panning accumulates.
 */
function evict(hold: TelemetryHold, ceiling: number): void {
	const fetched = [...hold.shards.keys()].filter((month) => !hold.seeded.has(month));
	let over = fetched.length - ceiling;
	if (over <= 0) return;
	for (const month of fetched) {
		if (over <= 0) break;
		hold.shards.delete(month);
		hold.loaded.delete(month);
		over -= 1;
	}
}

/** How many fetched months to hold at most: the months the widest window can
 * touch.
 *
 * A window of `maxWindowDays` days touches one partial start month, then whole
 * months, then one partial end month, so `floor((days - 2) / 28) + 2` never
 * undercounts (28 is the shortest month). One or two months generous costs a
 * spare shard and never evicts a month the open window still needs, which is
 * the one failure this ceiling may not have.
 */
export function monthCeiling(maxWindowDays: number): number {
	return Math.floor((Math.max(1, maxWindowDays) - 2) / 28) + 2;
}

/** The months held right now, sorted. For a test or a readout, never a fetch. */
export function heldMonths(hold: TelemetryHold): string[] {
	return [...hold.shards.keys()].sort();
}
