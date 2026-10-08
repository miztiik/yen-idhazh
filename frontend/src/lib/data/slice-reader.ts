/**
 * How is one slice answered from what the page keeps?
 *
 * The door reads `daily.json`; `monthly.json` only when the span starts before
 * the oldest day `daily.json` names, or when it names no day; and `yearly.json`
 * only when it starts before the oldest day those two name, or when `daily.json`
 * names no day. It takes the coarsest file for each day
 * (`slice.ts`), has the page keeper hold the files that hold rows
 * (`page-keeper.ts`), asks the engine one query over them (`slice-query.ts`),
 * and returns one of four states:
 *
 * - `missing`: there is no `daily.json`. A panel reads only published ledgers,
 *   and a build-time read finds every ledger the state tree holds, so this is a
 *   ledger with no compact folder: one that is not packed yet, never one left
 *   unpublished. Its fault is `not-packed`.
 * - `quiet`: every day asked for is covered and no row matched, or the span lies
 *   wholly after the newest day compacted, or wholly before the ledger began. A
 *   file whose entry says `rows: 0` is never fetched, and neither is a period
 *   whose entry is `empty` or `lost`, which has no file, so a span of quiet days
 *   loads no engine at all.
 * - `unreachable`: `at` is the first day that could not be answered, and the
 *   console says why. Its fault is `index-missing` for a span that reaches back
 *   past the days `daily.json` names when there is no `monthly.json`, or past
 *   the days those two name when there is no `yearly.json`; `day-missing` for a
 *   day between the first and the newest packed day that no index names; and
 *   `file-missing` for a named file that is not there. It is `null` for an index
 *   this build will not act on, a file that did not arrive whole, or an engine
 *   that could not answer.
 * - `ok`: the rows, exactly as the files hold them. The door never merges rows:
 *   the compaction already wrote one row per record.
 *
 * `ok` and `quiet` carry `first`, the first day the answer covers. A span that
 * starts before the oldest day any index names starts before the ledger began,
 * and those days are outside the ledger rather than missing from it, so the
 * door cuts them, answers from the ledger's first day, and names that day.
 * The span's end stays where it was asked to end.
 *
 * `ok` and `quiet` carry `lostDays`, the days in the span an index records lost.
 * Such a day has no file to read and no record to draw, so it is named rather
 * than counted as a day with no rows, and the other days are read as usual.
 * They also carry `setAside`, the periods the span is read from whose packing
 * set files aside unread, so a panel can say its rows may be short.
 *
 * `through` is how far the ledger is packed: the newest day any index names. The
 * packing moves a closed month's days out of `daily.json`, so while it names a
 * day, its newest day is that one, and a short span reads one index. A day after
 * `through` has not been compacted yet, so it is clamped away rather than drawn
 * as a zero.
 *
 * **A day in a packed year is read from its year file, by byte range.** In a
 * browser the engine opens the year file at an address no earlier read used and
 * asks the host for its footer and the row groups of the months a query touches
 * - one row group a month - so a month out of a year costs about what the
 * month's own file would. The page keeper checks the length the engine opened
 * against the entry, and the engine drops the file when the read ends, so the
 * next read opens it again where the browser holds no part fetched before a
 * deploy. A day or month file is fetched whole, and at build time every file is.
 *
 * **The address is composed here and nowhere else**, from the closed ledger
 * name, the period and a `covers` the index guard has already checked, so no
 * caller and no fetched text can name a path. **So is the reading of an index**,
 * `readIndexFrom()`, which `ledger-reach.ts` calls too, so a slice and a reach
 * never disagree about what an index says. **And so is the one line a fault
 * prints**, `faultLine()`: the slice and the reach both meet `not-packed` and
 * `index-missing`, and the page keeper prints a line once only if both spell it
 * the same way.
 *
 * Imports nothing tied to one environment. `ledger.ts` binds it to the published
 * site for a browser; `frontend/src/lib/server/ledger-disk.ts` binds it to the
 * state root on disk for a build-time reader.
 */

import { COMPACT_INDEX_STAMP, readIndex, type CompactEntry, type IndexReading, type IndexRefusal, type Period } from './compact-index';
import type { FileShortfall, PageKeeper, WantedFile } from './page-keeper';
import { filesFor, firstNamed, newestNamed, type ChosenFile } from './slice';
import { rowsFor } from './slice-query';
import {
	checkedRequest,
	LEDGER_FOLDERS,
	LEDGER_NAMES,
	SliceRequestError,
	type DateStamp,
	type LedgerFault,
	type LedgerName,
	type Row,
	type SliceOptions,
	type SliceResult
} from './slice-shapes';

/** The folder a ledger's files sit in under `raw/` and `compact/`: its family's
 *  folder and its own where `LEDGER_FOLDERS` names one, else its own name. */
export function ledgerFolder(ledger: LedgerName): string {
	const folders: Partial<Record<LedgerName, string>> = LEDGER_FOLDERS;
	return folders[ledger] ?? ledger;
}

/** Where one ledger's index for one period sits under the state root. */
export function indexPath(ledger: LedgerName, period: Period): string {
	return `compact/${ledgerFolder(ledger)}/index/${period}.json`;
}

/** Where one raw day listing sits under the state root. */
export function rawIndexPath(ledger: LedgerName, day: DateStamp): string {
	return `raw/${ledgerFolder(ledger)}/index/${day}.json`;
}

/** Where one raw writer file sits under the state root. */
export function rawDataPath(ledger: LedgerName, day: DateStamp, name: string): string {
	const [year, month, date] = day.split('-');
	return `raw/${ledgerFolder(ledger)}/${year}/${month}/${date}/${name}`;
}

/** Where one compact file sits under the state root, named for what it covers. */
export function dataPath(ledger: LedgerName, period: Period, covers: string): string {
	const [year, month, day] = covers.split('-');
	const named: Record<Period, string> = {
		daily: `daily/${year}/${month}/${day}`,
		monthly: `monthly/${year}/${month}`,
		yearly: `yearly/${year}/${year}`
	};
	return `compact/${ledgerFolder(ledger)}/${named[period]}.parquet`;
}

/** The version a data file is asked for under. A file is written once, so its
 *  entry's rows and bytes change only when the file does. */
export function dataVersion(entry: CompactEntry): string {
	return `${entry.rows}-${entry.bytes}`;
}

/** The periods an engine that reads a host may read by byte range rather than
 *  whole. A year file holds one row group a month, so one month of it is one run
 *  of bytes; a day or month file is what the span asked for, whole. */
export const RANGED_PERIODS: ReadonlySet<Period> = new Set<Period>(['yearly']);

/** What every line the door prints to the console starts with. */
export const LOG_PREFIX = '[ledger]';

/** What a line calls the stretch of time one period's file covers. */
const UNIT: Record<Period, string> = { daily: 'day', monthly: 'month', yearly: 'year' };

/** One fault as the door met it, with what its line names. */
export type FaultMet =
	| { fault: Extract<LedgerFault, 'not-packed'> }
	| { fault: Extract<LedgerFault, 'index-missing'>; period: Exclude<Period, 'daily'> }
	| { fault: Extract<LedgerFault, 'file-missing'>; period: Period; covers: string }
	| { fault: Extract<LedgerFault, 'day-missing'>; day: DateStamp };

/** The one console line a fault gets: `[ledger] <fault> <ledger> <path>: <what is
 *  wrong>. <what fixes it>.` The path is the committed one, so an operator can
 *  open it, and the line names no span, so every panel that meets one fault on
 *  a page prints the same line. */
export function faultLine(ledger: LedgerName, met: FaultMet): string {
	const line = (path: string, words: string): string => `${LOG_PREFIX} ${met.fault} ${ledger} state/${path}: ${words}`;
	if (met.fault === 'not-packed') {
		return line(
			indexPath(ledger, 'daily'),
			'it is not there: this record is not packed, or not published. Turn on whichever is off, or wait for the next upkeep run.'
		);
	}
	if (met.fault === 'index-missing') {
		return line(
			indexPath(ledger, met.period),
			`it is not there, though daily.json is. Run the upkeep again to write it; it lists nothing until a ${UNIT[met.period]} is packed.`
		);
	}
	if (met.fault === 'file-missing') {
		return line(
			dataPath(ledger, met.period, met.covers),
			`${met.period}.json names it; it is not there. Reload; if it stays, re-pack that ${UNIT[met.period]}.`
		);
	}
	return line(
		indexPath(ledger, 'daily'),
		`no index names ${met.day}, a day between packed days. ` +
			'Re-pack that day from raw files; if they are gone, try git history.'
	);
}

function reason(error: unknown): string {
	return error instanceof Error ? error.message : String(error);
}

/** What one of a ledger's indexes says, as the page keeps it: the index, why this
 *  build will not act on it, or `null` when there is no such file. */
export async function readIndexFrom(keeper: PageKeeper, ledger: LedgerName, period: Period): Promise<IndexReading | null> {
	let bytes: Uint8Array | null;
	try {
		bytes = await keeper.index(indexPath(ledger, period));
	} catch (error) {
		return { refused: { reason: 'unreadable', detail: `it could not be fetched (${reason(error)})` } };
	}
	if (bytes === null) return null;
	let parsed: unknown;
	try {
		parsed = JSON.parse(new TextDecoder().decode(bytes));
	} catch {
		return { refused: { reason: 'unreadable', detail: 'it is not JSON' } };
	}
	return readIndex(parsed, ledger, period);
}

/** Why an index is not acted on, as the console says it. */
export function explainRefusal(period: Period, refused: IndexRefusal): string {
	return refused.reason === 'newer'
		? `${period}.json is stamped ${refused.stamp} and this build reads ${COMPACT_INDEX_STAMP} or older`
		: `${period}.json cannot be read: ${refused.detail}`;
}

/** Why a file a slice or a written question needs arrived but could not be used, as the console says it. */
export function explainShortfall(
	wanted: WantedFile,
	shortfall: Exclude<FileShortfall, { reason: 'absent' }>
): string {
	if (shortfall.reason === 'length') {
		return `${wanted.path} arrived as ${shortfall.arrived} bytes and its entry says ${wanted.bytes}`;
	}
	if (shortfall.reason === 'opened') {
		return `${wanted.path} opened at ${shortfall.length} bytes to be read by range, and its entry says ${wanted.bytes}`;
	}
	return `${wanted.path} could not be fetched (${reason(shortfall.error)})`;
}

/** Answer one request: the four states above, or a `SliceRequestError` for a
 *  request the door refuses before it fetches anything. */
export async function readSlice(keeper: PageKeeper, ledger: LedgerName, options: SliceOptions): Promise<SliceResult> {
	if (!(LEDGER_NAMES as readonly string[]).includes(ledger)) {
		throw new SliceRequestError(`${JSON.stringify(ledger)} is not a ledger the console may query`);
	}
	const request = checkedRequest(options);
	const unreachable = (at: DateStamp, why: string): SliceResult => {
		keeper.warn(`${LOG_PREFIX} ${ledger} ${request.from} to ${request.to}: ${why}, so nothing is drawn from ${at}`);
		return { state: 'unreachable', rows: [], at, fault: null };
	};
	const faulted = (at: DateStamp, met: Exclude<FaultMet, { fault: 'not-packed' }>): SliceResult => {
		keeper.warn(faultLine(ledger, met));
		return { state: 'unreachable', rows: [], at, fault: met.fault };
	};

	const daily = await readIndexFrom(keeper, ledger, 'daily');
	if (daily === null) {
		keeper.warn(faultLine(ledger, { fault: 'not-packed' }));
		return { state: 'missing', rows: [], fault: 'not-packed' };
	}
	if ('refused' in daily) return unreachable(request.from, explainRefusal('daily', daily.refused));
	const days = daily.index.entries;

	let months: CompactEntry[] = [];
	let years: CompactEntry[] = [];
	if (days.length === 0 || request.from < days[0].covers) {
		const monthly = await readIndexFrom(keeper, ledger, 'monthly');
		if (monthly === null) return faulted(request.from, { fault: 'index-missing', period: 'monthly' });
		if ('refused' in monthly) return unreachable(request.from, explainRefusal('monthly', monthly.refused));
		months = monthly.index.entries;
		if (days.length === 0 || request.from < firstNamed(days, months, [])) {
			const yearly = await readIndexFrom(keeper, ledger, 'yearly');
			if (yearly === null) return faulted(request.from, { fault: 'index-missing', period: 'yearly' });
			if ('refused' in yearly) return unreachable(request.from, explainRefusal('yearly', yearly.refused));
			years = yearly.index.entries;
		}
	}

	const through = newestNamed(days, months, years);
	if (through === null || request.from > through) {
		return { state: 'quiet', rows: [], first: request.from, through, lostDays: [], setAside: {} };
	}
	const began = firstNamed(days, months, years);
	const first = request.from < began ? began : request.from;
	const until = request.to < through ? request.to : through;
	if (first > until) return { state: 'quiet', rows: [], first, through, lostDays: [], setAside: {} };

	const selection = filesFor(first, until, days, months, years);
	if ('hole' in selection) return faulted(selection.hole, { fault: 'day-missing', day: selection.hole });
	const { lostDays, setAside } = selection;
	const holding = selection.files.filter((file) => file.entry.rows > 0);
	if (holding.length === 0) return { state: 'quiet', rows: [], first, through, lostDays, setAside };

	const wanted: WantedFile[] = holding.map((file) => ({
		path: dataPath(ledger, file.period, file.entry.covers),
		version: dataVersion(file.entry),
		bytes: file.entry.bytes,
		byRange: RANGED_PERIODS.has(file.period)
	}));
	let rows: Row[];
	try {
		const held = await keeper.hold(wanted);
		if ('failed' in held) {
			const file: ChosenFile = holding[held.failed];
			if (held.shortfall.reason === 'absent') {
				return faulted(file.firstDay, { fault: 'file-missing', period: file.period, covers: file.entry.covers });
			}
			return unreachable(file.firstDay, explainShortfall(wanted[held.failed], held.shortfall));
		}
		try {
			rows = await rowsFor(held.engine, held.names, { ...request, from: first }, until, (message) =>
				keeper.warn(`${LOG_PREFIX} ${ledger}: ${message}`)
			);
		} finally {
			await held.done();
		}
	} catch (error) {
		return unreachable(first, `the query engine could not answer (${reason(error)})`);
	}
	return rows.length === 0
		? { state: 'quiet', rows: [], first, through, lostDays, setAside }
		: { state: 'ok', rows, first, through, lostDays, setAside };
}
