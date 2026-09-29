/**
 * How is one slice answered from what the page keeps?
 *
 * The door reads `daily.json`, and `monthly.json` only when the span starts
 * before the oldest day `daily.json` names. It takes the coarsest file for each
 * day (`slice.ts`), has the page keeper hold the files that hold rows
 * (`page-keeper.ts`), asks the engine one query over them (`slice-query.ts`),
 * and returns one of four states:
 *
 * - `missing`: there is no `daily.json`, so the ledger is not published.
 * - `quiet`: every day asked for is covered and no row matched, or the span lies
 *   wholly after the newest day compacted. A file whose entry says `rows: 0` is
 *   never fetched, so a span of quiet days loads no engine at all.
 * - `unreachable`: a day at or before the newest compacted day that neither index
 *   names, a named file that did not arrive whole, an index this build will not
 *   act on, or an engine that could not answer. `at` is the first day that could
 *   not be answered, and the console says why.
 * - `ok`: the rows, exactly as the files hold them. The door never merges rows:
 *   the compaction already wrote one row per record.
 *
 * `through` is the newest day `daily.json` names. A day after it has not been
 * compacted yet, so it is clamped away rather than drawn as a zero.
 *
 * **The address is composed here and nowhere else**, from the closed ledger
 * name, the period and a `covers` the index guard has already checked, so no
 * caller and no fetched text can name a path. **So is the reading of an index**,
 * `readIndexFrom()`, which `ledger-reach.ts` calls too, so a slice and a reach
 * never disagree about what an index says.
 *
 * Imports nothing tied to one environment. `ledger.ts` binds it to the published
 * site for a browser; `frontend/src/lib/server/ledger-disk.ts` binds it to the
 * state root on disk for a build-time reader.
 */

import { COMPACT_INDEX_STAMP, readIndex, type CompactEntry, type IndexReading, type IndexRefusal, type Period } from './compact-index';
import type { FileShortfall, PageKeeper, WantedFile } from './page-keeper';
import { filesFor, type ChosenFile } from './slice';
import { rowsFor } from './slice-query';
import {
	checkedRequest,
	LEDGER_NAMES,
	SliceRequestError,
	type DateStamp,
	type LedgerName,
	type Row,
	type SliceOptions,
	type SliceResult
} from './slice-shapes';

/** Where one ledger's index for one period sits under the state root. */
export function indexPath(ledger: LedgerName, period: Period): string {
	return `compact/${ledger}/index/${period}.json`;
}

/** Where one compact file sits under the state root, named for what it covers. */
export function dataPath(ledger: LedgerName, period: Period, covers: string): string {
	const [year, month, day] = covers.split('-');
	return period === 'daily'
		? `compact/${ledger}/daily/${year}/${month}/${day}.parquet`
		: `compact/${ledger}/monthly/${year}/${month}.parquet`;
}

/** The version a data file is asked for under. A file is written once, so its
 *  entry's rows and bytes change only when the file does. */
export function dataVersion(entry: CompactEntry): string {
	return `${entry.rows}-${entry.bytes}`;
}

/** What every line the door prints to the console starts with. */
export const LOG_PREFIX = '[ledger]';

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

/** Why a file a slice needs could not be had, as the console says it. */
function explainShortfall(wanted: WantedFile, file: ChosenFile, shortfall: FileShortfall): string {
	if (shortfall.reason === 'absent') return `${wanted.path} is named in ${file.period}.json and is not there`;
	if (shortfall.reason === 'length') {
		return `${wanted.path} arrived as ${shortfall.arrived} bytes and its entry says ${wanted.bytes}`;
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
		console.warn(`${LOG_PREFIX} ${ledger} ${request.from} to ${request.to}: ${why}, so nothing is drawn from ${at}`);
		return { state: 'unreachable', rows: [], at };
	};

	const daily = await readIndexFrom(keeper, ledger, 'daily');
	if (daily === null) return { state: 'missing', rows: [] };
	if ('refused' in daily) return unreachable(request.from, explainRefusal('daily', daily.refused));
	const days = daily.index.entries;
	const through = days.at(-1)?.covers ?? null;
	if (through === null || request.from > through) return { state: 'quiet', rows: [], through };
	const until = request.to < through ? request.to : through;

	let months: CompactEntry[] = [];
	if (request.from < days[0].covers) {
		const monthly = await readIndexFrom(keeper, ledger, 'monthly');
		if (monthly !== null && 'refused' in monthly) {
			return unreachable(request.from, explainRefusal('monthly', monthly.refused));
		}
		if (monthly !== null) months = monthly.index.entries;
	}

	const selection = filesFor(request.from, until, days, months);
	if ('hole' in selection) return unreachable(selection.hole, `${selection.hole} is named by neither index`);
	const holding = selection.files.filter((file) => file.entry.rows > 0);
	if (holding.length === 0) return { state: 'quiet', rows: [], through };

	const wanted: WantedFile[] = holding.map((file) => ({
		path: dataPath(ledger, file.period, file.entry.covers),
		version: dataVersion(file.entry),
		bytes: file.entry.bytes
	}));
	let rows: Row[];
	try {
		const held = await keeper.hold(wanted);
		if ('failed' in held) {
			const at = held.failed;
			return unreachable(holding[at].firstDay, explainShortfall(wanted[at], holding[at], held.shortfall));
		}
		rows = await rowsFor(held.engine, held.names, request, until, (message) =>
			console.warn(`${LOG_PREFIX} ${ledger}: ${message}`)
		);
	} catch (error) {
		return unreachable(request.from, `the query engine could not answer (${reason(error)})`);
	}
	return rows.length === 0 ? { state: 'quiet', rows: [], through } : { state: 'ok', rows, through };
}
