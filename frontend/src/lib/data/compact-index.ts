/**
 * Can this build read a compact index, and what does the index say?
 *
 * `state/compact/<ledger>/index/<period>.json` is written by the gardener's
 * compaction task, one writer per ledger, and declared once, as `CompactIndex`
 * and its records in `backend/idhazh/contracts/ledger_index.py`. This module
 * is the frontend's hand copy of those shapes, the stamp this build reads,
 * and the guard that decides whether a fetched index may be acted on.
 * `backend/tests/contracts/test_frontend_index_shapes.py` holds the copy and the
 * stamp in step with the Pydantic originals.
 *
 * Only the current compact index layout is read. `entries` lists live files;
 * `coverage` records periods with no file. Range readers use both lists.
 *
 * The ledger, the period and every entry's `covers`, `rows`, `bytes`,
 * `file_sha256`, `state`, `lost_days` and `set_aside` are checked in full, because file
 * selection and the answers trust them and a `covers` becomes part of a file's
 * address.
 *
 * Imports nothing tied to one environment, so a Node test loads it as it is.
 */

import { isDay, type LedgerName } from './slice-shapes.ts';

/** The `CompactIndex` stamp this build reads: `CompactIndex.schema_version()`. */
export const COMPACT_INDEX_STAMP = '2026-11-25';

/** How much time one compact file covers. Also the directory name. */
export const COMPACT_PERIODS = ['daily', 'monthly', 'yearly'] as const;

export type Period = (typeof COMPACT_PERIODS)[number];

/** Whether a period named in an index has a file: `packed` has one, `empty` and `lost` have none. Only a day is `lost`. */
export const ENTRY_STATES = ['packed', 'empty', 'lost'] as const;

export type EntryState = (typeof ENTRY_STATES)[number];

export const COVERAGE_STATES = ['empty', 'lost'] as const;

export type CoverageState = (typeof COVERAGE_STATES)[number];

/** One period of a `CompactIndex`: what it covers, whether it has a file, its rows and size. */
export interface CompactEntry {
	covers: string;
	rows: number;
	bytes: number;
	file_sha256?: string | null;
	state?: EntryState;
	lost_days?: string[];
	set_aside?: number;
}

/** A checked period that has no file. */
export interface CompactCoverage {
	covers: string;
	state: CoverageState;
	lost_days?: string[];
	set_aside?: number;
}

/** Which compact files exist in one period of one ledger. */
export interface CompactIndex {
	version?: string;
	ledger: LedgerName;
	period: Period;
	entries: CompactEntry[];
	coverage: CompactCoverage[];
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
function brokenRecords(
	entries: unknown[], period: Period, noFile: boolean
): string | null {
	let previous = '';
	for (const [at, entry] of entries.entries()) {
		const label = `${noFile ? 'coverage record' : 'entry'} ${at}`;
		if (!isRecord(entry)) return `${label} is not an object`;
		const { covers, rows, bytes, file_sha256: fileSha256, state, lost_days: lostDays, set_aside: setAside } = entry;
		if (typeof covers !== 'string' || !COVERS[period].test(covers)) {
			return `${label} covers ${JSON.stringify(covers)}, which is not a ${period} period`;
		}
		if (covers <= previous) return `${label} (${covers}) does not come after ${previous}`;
		if (noFile) {
			if (!(COVERAGE_STATES as readonly unknown[]).includes(state)) {
				return `${label} (${covers}) has invalid state ${JSON.stringify(state)}`;
			}
			if (Object.keys(entry).some((key) => !['covers', 'state', 'lost_days', 'set_aside'].includes(key))) {
				return `${label} (${covers}) names fields other than coverage`;
			}
		} else {
			if (!isCount(rows)) return `${label} (${covers}) has rows ${JSON.stringify(rows)}`;
			if (!isCount(bytes)) return `${label} (${covers}) has bytes ${JSON.stringify(bytes)}`;
			if (fileSha256 !== undefined && fileSha256 !== null
				&& (typeof fileSha256 !== 'string' || !/^[0-9a-f]{64}$/.test(fileSha256))) {
				return `${label} (${covers}) has file_sha256 ${JSON.stringify(fileSha256)}`;
			}
			if (state !== undefined && state !== 'packed') return `${label} (${covers}) does not name a file`;
		}
		if (state === 'lost' && period !== 'daily') {
			return `${label} (${covers}) is lost, and only a day is: a ${period} entry lists the days it lost in lost_days`;
		}
		const lost = lostDays === undefined ? null : brokenLostDays(lostDays, covers, period);
		if (lost !== null) return `${label} (${covers}) ${lost}`;
		if (setAside !== undefined && !isCount(setAside)) {
			return `${label} (${covers}) has set_aside ${JSON.stringify(setAside)}`;
		}
		previous = covers;
	}
	return null;
}

/**
 * Whether a parsed index can be acted on, for the ledger and period it was
 * fetched as.
 *
 * A missing `version` defaults to the current stamp; coverage is still required.
 */
export function readIndex(value: unknown, ledger: LedgerName, period: Period): IndexReading {
	const unreadable = (detail: string): IndexReading => ({ refused: { reason: 'unreadable', detail } });
	if (!isRecord(value)) return unreadable('it is not a JSON object');
	const stamp = value.version === undefined ? COMPACT_INDEX_STAMP : value.version;
	if (typeof stamp !== 'string' || !STAMP.test(stamp)) {
		return unreadable(`its version ${JSON.stringify(stamp)} is not a stamp`);
	}
	if (stamp > COMPACT_INDEX_STAMP) return { refused: { reason: 'newer', stamp } };
	if (stamp !== COMPACT_INDEX_STAMP) return unreadable(`it uses unsupported version ${stamp}; expected ${COMPACT_INDEX_STAMP}`);
	if (value.ledger !== ledger) return unreadable(`it names the ledger ${JSON.stringify(value.ledger)}`);
	if (value.period !== period) return unreadable(`it names the period ${JSON.stringify(value.period)}`);
	if (!Array.isArray(value.entries)) return unreadable('it has no list of entries');
	const coverage = value.coverage;
	if (!Array.isArray(coverage)) return unreadable('it has no list of coverage records');
	const expired = value.expired_through ?? null;
	if (expired !== null && (period !== 'yearly' || typeof expired !== 'string' || !COVERS.yearly.test(expired))) {
		return unreadable('its expired_through is not a UTC year on a yearly index');
	}
	const broken = brokenRecords(value.entries, period, false);
	if (broken !== null) return unreadable(broken);
	const brokenCoverage = brokenRecords(coverage, period, true);
	if (brokenCoverage !== null) return unreadable(brokenCoverage);
	const files = new Set(value.entries.map((entry) => entry.covers));
	if (coverage.some((record) => files.has(record.covers))) {
		return unreadable('it lists a period in both entries and coverage');
	}
	if (typeof expired === 'string' &&
		[...value.entries, ...coverage].some((record) => record.covers <= expired)) {
		return unreadable('it lists periods at or before expired_through');
	}
	const entries = (value.entries as CompactEntry[]).map(({ covers, rows, bytes, file_sha256, state, lost_days, set_aside }) => ({
		covers,
		rows,
		bytes,
		file_sha256,
		state,
		lost_days,
		set_aside
	}));
	return {
		index: {
			version: stamp, ledger, period, entries,
			coverage: coverage as CompactCoverage[],
			expired_through: expired
		}
	};
}

/** Every checked period in order, whether it has a file or not. */
export function compactPeriods(index: CompactIndex): CompactEntry[] {
	if (!index.coverage.length) return index.entries;
	return [...index.entries, ...index.coverage.map((record) => ({ ...record, rows: 0, bytes: 0 }))]
		.sort((left, right) => left.covers.localeCompare(right.covers));
}
