/**
 * Can this build read a compact index, and what does the index say?
 *
 * `state/compact/<ledger>/index/<period>.json` is written by the gardener's
 * compaction task, one writer per ledger, and declared once, as `CompactIndex`
 * and `CompactEntry` in `backend/idhazh/contracts/ledger_index.py`. This module
 * is the frontend's hand copy of those two shapes, the stamp this build reads,
 * and the guard that decides whether a fetched index may be acted on.
 * `backend/tests/contracts/test_frontend_index_shapes.py` holds the copy and the
 * stamp in step with the Pydantic originals.
 *
 * **An index at this build's stamp or an older one is read; a newer one is
 * refused.** The gardener rewrites an index at its own wake, not in the commit
 * that moves the shape, so a build that demanded its own stamp exactly would
 * blank every panel from a shape change until the next wake. A newer stamp is a
 * shape this build has never seen, so it is refused rather than guessed at - the
 * rule the backend's own reader applies to a ledger file.
 *
 * **The guard checks what the door acts on, and nothing else.** An older index
 * may carry a field this build no longer declares, and that is not a reason to
 * refuse it. The ledger, the period and every entry's `covers`, `rows`, `bytes`,
 * `state`, `lost_days` and `set_aside` are checked in full, because file
 * selection and the answers trust them and a `covers` becomes part of a file's
 * address. An entry that carries no `state`, `lost_days` or `set_aside` was
 * written before entries had them, and is handed on without them: `namesFile()`
 * in `slice.ts` reads it as packed, with nothing lost or set aside, as the
 * contract does.
 *
 * Imports nothing tied to one environment, so a Node test loads it as it is.
 */

import { isDay, type LedgerName } from './slice-shapes';

/** The `CompactIndex` stamp this build reads: `CompactIndex.schema_version()`. */
export const COMPACT_INDEX_STAMP = '2026-10-07';

/** How much time one compact file covers. Also the directory name. */
export const COMPACT_PERIODS = ['daily', 'monthly', 'yearly'] as const;

export type Period = (typeof COMPACT_PERIODS)[number];

/** Whether a period named in an index has a file: `packed` has one, `empty` and `lost` have none. Only a day is `lost`. */
export const ENTRY_STATES = ['packed', 'empty', 'lost'] as const;

export type EntryState = (typeof ENTRY_STATES)[number];

/** One period of a `CompactIndex`: what it covers, whether it has a file, its rows and size. */
export interface CompactEntry {
	covers: string;
	rows: number;
	bytes: number;
	state?: EntryState;
	lost_days?: string[];
	set_aside?: number;
}

/** Which compact files exist in one period of one ledger. */
export interface CompactIndex {
	version?: string;
	ledger: LedgerName;
	period: Period;
	entries: CompactEntry[];
	expired_through?: string | null;
}

/** A stamp as the contract spells one: a UTC day, to the minute or second on a same-day revision. */
const STAMP = /^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?)?$/;

/** What `covers` looks like in each period. */
const COVERS: Record<Period, RegExp> = {
	daily: /^\d{4}-\d{2}-\d{2}$/,
	monthly: /^\d{4}-\d{2}$/,
	yearly: /^\d{4}$/
};

/** Why an index was not acted on, in words the console can print. */
export type IndexRefusal =
	| { reason: 'newer'; stamp: string }
	| { reason: 'unreadable'; detail: string };

/** The index, or why this build will not act on it. */
export type IndexReading = { index: CompactIndex } | { refused: IndexRefusal };

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isCount(value: unknown): value is number {
	return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

function isState(value: unknown): value is EntryState {
	return typeof value === 'string' && (ENTRY_STATES as readonly string[]).includes(value);
}

/** Why an entry's `lost_days` cannot be acted on, or null when it can: real UTC
 *  days of the month or year the entry covers, ascending, none twice, and none
 *  on a daily entry, where a lost day is an entry of its own. */
function brokenLostDays(days: unknown, covers: string, period: Period): string | null {
	if (!Array.isArray(days)) return `has lost_days ${JSON.stringify(days)}`;
	if (period === 'daily' && days.length > 0) return 'is a day and lists lost_days';
	let previous = '';
	for (const day of days) {
		if (!isDay(day) || !day.startsWith(`${covers}-`)) {
			return `lists ${JSON.stringify(day)} as lost, which is not a day it covers`;
		}
		if (day <= previous) return `lists the lost day ${day} after ${previous}`;
		previous = day;
	}
	return null;
}

/** The first entry that breaks the shape, named, or null when every entry holds it. */
function brokenEntry(entries: unknown[], period: Period): string | null {
	let previous = '';
	for (const [at, entry] of entries.entries()) {
		if (!isRecord(entry)) return `entry ${at} is not an object`;
		const { covers, rows, bytes, state, lost_days: lostDays, set_aside: setAside } = entry;
		if (typeof covers !== 'string' || !COVERS[period].test(covers)) {
			return `entry ${at} covers ${JSON.stringify(covers)}, which is not a ${period} period`;
		}
		if (!isCount(rows)) return `entry ${at} (${covers}) has rows ${JSON.stringify(rows)}`;
		if (!isCount(bytes)) return `entry ${at} (${covers}) has bytes ${JSON.stringify(bytes)}`;
		if (covers <= previous) return `entry ${at} (${covers}) does not come after ${previous}`;
		if (state !== undefined && !isState(state)) return `entry ${at} (${covers}) has state ${JSON.stringify(state)}`;
		if (state !== undefined && state !== 'packed' && (rows > 0 || bytes > 0)) {
			return `entry ${at} (${covers}) is ${state}, which names no file, and has rows ${rows} and bytes ${bytes}`;
		}
		if (state === 'lost' && period !== 'daily') {
			return `entry ${at} (${covers}) is lost, and only a day is: a ${period} entry lists the days it lost in lost_days`;
		}
		const lost = lostDays === undefined ? null : brokenLostDays(lostDays, covers, period);
		if (lost !== null) return `entry ${at} (${covers}) ${lost}`;
		if (setAside !== undefined && !isCount(setAside)) {
			return `entry ${at} (${covers}) has set_aside ${JSON.stringify(setAside)}`;
		}
		previous = covers;
	}
	return null;
}

/**
 * Whether a parsed index can be acted on, for the ledger and period it was
 * fetched as.
 *
 * A missing `version` reads as this build's own stamp, as the contract stamps a
 * document that omits one.
 */
export function readIndex(value: unknown, ledger: LedgerName, period: Period): IndexReading {
	const unreadable = (detail: string): IndexReading => ({ refused: { reason: 'unreadable', detail } });
	if (!isRecord(value)) return unreadable('it is not a JSON object');
	const stamp = value.version ?? COMPACT_INDEX_STAMP;
	if (typeof stamp !== 'string' || !STAMP.test(stamp)) {
		return unreadable(`its version ${JSON.stringify(stamp)} is not a stamp`);
	}
	if (stamp > COMPACT_INDEX_STAMP) return { refused: { reason: 'newer', stamp } };
	if (value.ledger !== ledger) return unreadable(`it names the ledger ${JSON.stringify(value.ledger)}`);
	if (value.period !== period) return unreadable(`it names the period ${JSON.stringify(value.period)}`);
	if (!Array.isArray(value.entries)) return unreadable('it has no list of entries');
	const expired = value.expired_through ?? null;
	if (expired !== null && (period !== 'yearly' || typeof expired !== 'string' || !COVERS.yearly.test(expired))) {
		return unreadable('its expired_through is not a UTC year on a yearly index');
	}
	const broken = brokenEntry(value.entries, period);
	if (broken !== null) return unreadable(broken);
	if (typeof expired === 'string' && value.entries.some((entry) => entry.covers <= expired)) {
		return unreadable('it lists entries at or before expired_through');
	}
	const entries = (value.entries as CompactEntry[]).map(({ covers, rows, bytes, state, lost_days, set_aside }) => ({
		covers,
		rows,
		bytes,
		state,
		lost_days,
		set_aside
	}));
	return { index: { version: stamp, ledger, period, entries, expired_through: expired } };
}
