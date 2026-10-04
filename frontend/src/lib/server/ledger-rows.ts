/** Which rows of the article, score and feed records does a console route read?
 *
 * All three come from their packed files under `state/compact/`, through the
 * query door's build-time entry, `sliceFromDisk()` in `ledger-disk.ts`, so a
 * build and a browser panel asking for one span get one answer from one set of
 * files. The raw files a run appends are never read here: a day reaches these
 * routes once it is packed, so they stop at the newest packed day rather than
 * at today, and each table says which day that is.
 *
 * **The rows come back as text cells**, the way the day files used to hand them
 * over: a reading nobody took is '', a flag is 'True' or 'False' as Python
 * writes one, and a number is its decimal. Some forty panel functions read these
 * cells, and none of them had to change when the files did.
 *
 * **One row per key is the packing's job, not this reader's.** A day is packed
 * by settling its rows under the ledger's own key and preference, so a packed
 * day already holds one row per item per run, one per scored measurement, or
 * one per feed per run. A second settle here would be a second rule for one
 * question.
 *
 * They sit apart from `payload.ts`, the one payload loader, because reading a
 * committed ledger is a different question from loading a published day.
 * Imports nothing that needs a Vite alias: the browser suite loads this module
 * in plain Node.
 */

// Relative, not `$lib`, for the reason in the module docstring.
import { daysBetween, dayKey, toDay } from '../charts/viewport';
import { DRAWN_BY, NOT_A_MEASUREMENT } from '../console/eval-instruments';
import type { RecordRead } from '../console/recording';
import type { DateStamp, LedgerName, Row, SliceResult } from '../data/slice-shapes';
import { reachFromDisk, sliceFromDisk } from './ledger-disk';
import { LEDGER_WINDOW_DAYS, STATE_ROOT, type CsvTable } from './payload';

/** Every column `ItemHealthRow` declares, in the contract's own order.
 *
 * The door answers only the columns it is asked for and never offers every
 * column, so the article record's whole row is spelled here once. The console's
 * panels read nearly all of it, and a cell nobody asked for would reach a panel
 * as an empty reading rather than as an error. A backend contract test reads
 * this list and fails when the contract gains, loses or renames a column.
 */
export const ITEM_HEALTH_COLUMNS = [
	'version', 'date', 'run_id', 'item_id', 'url_key', 'canonical_url', 'vertical', 'source_id',
	'stage', 'outcome', 'code', 'http_status', 'source_chars', 'source_words', 'summary_words',
	'detail', 'fetch_ms', 'extract_ms', 'summarize_ms', 'prefill_ms', 'decode_ms', 'input_tokens',
	'output_tokens', 'cached_tokens', 'source_words_before_cap', 'machine_shard', 'machine_job',
	'span_integrity', 'elements_found', 'element_class', 'model_calls', 'label_kind',
	'label_prefill_ms', 'label_decode_ms', 'label_input_tokens', 'label_output_tokens',
	'label_cached_tokens', 'summary_kind', 'summary_prefill_ms', 'summary_decode_ms',
	'summary_input_tokens', 'summary_output_tokens', 'summary_cached_tokens',
	'truncation_cap_tokens', 'selection_score', 'authority_score', 'tier_score', 'feed_weight',
	'feed_reliability', 'lens_bonus', 'recency_bonus', 'carriage_step', 'watchlist_bonus',
	'carried_by', 'watchlist_hit', 'on_front_page', 'tier', 'source_form', 'published_at',
	'time_source', 'item_started_at', 'item_ended_at', 'item_index', 'shard_item_count',
	'queue_wait_ms', 'fetch_connect_ms', 'fetch_ttfb_ms', 'robots_ms', 'retry_count',
	'retry_total_ms', 'label_ms', 'summary_ms', 'visual_plan_ms', 'visual_plan_ms_is_estimate',
	'faithfulness_ms', 'model_wait_ms', 'item_total_ms', 'stage_gap_ms',
	'visual_plan_tokens_written', 'label_cache_pct', 'summary_cache_pct', 'slot_id',
	'kv_tokens_at_start', 'prefix_shared_with_previous', 'label_prefill_tokens_per_s',
	'label_decode_tokens_per_s', 'summary_prefill_tokens_per_s', 'summary_decode_tokens_per_s',
	'label_finish_reason', 'summary_finish_reason', 'recovered', 'cpu_model', 'cpu_busy_pct',
	'cpu_busy_max', 'cpu_busy_min', 'cpu_steal_pct', 'load_1m', 'llama_rss_bytes',
	'llama_rss_anon_bytes', 'llama_rss_peak_bytes', 'llama_major_faults', 'python_rss_bytes',
	'python_rss_anon_bytes', 'model_id', 'model_quantisation', 'n_ctx_configured', 'n_parallel',
	'n_threads', 'n_batch', 'weights_pinned', 'label_budget_tokens', 'summary_budget_tokens',
	'run_visual_decision', 'temperature', 'failed_field', 'failed_rule', 'os_mem_available_bytes',
	'os_mem_total_bytes', 'os_mem_cached_bytes', 'os_swap_free_bytes', 'os_swap_total_bytes',
	'os_mem_available_min_bytes'
] as const;

/** Every column `EvalRow` declares.
 *
 * Not a second copy: `eval-instruments.ts` already names each column once, as a
 * measurement a panel draws or as an identity no panel draws, and
 * `backend/tests/contracts/test_frontend_console_lists.py` holds those two maps
 * to the contract. The score record is read through them, so it cannot fall
 * behind the contract without that test failing first.
 */
export const SCORE_COLUMNS: readonly string[] = [
	...Object.keys(NOT_A_MEASUREMENT),
	...Object.keys(DRAWN_BY)
];

/** A packed record's newest days, as the text cells the console's panels read. */
export interface LedgerTable extends CsvTable {
	/** How the read went, so a route can say which kind of empty an empty panel is. */
	read: RecordRead;
}

/** The columns in the order a read asks for them: the day, then the run, then the rest.
 *
 * The door sorts rows by the columns in the order they were asked for, so this
 * is also the order the rows come back in - oldest day first, one run's rows
 * together - which is the order the day files handed them over.
 */
export function datedFirst(columns: readonly string[]): string[] {
	return ['date', 'run_id', ...columns.filter((name) => name !== 'date' && name !== 'run_id')];
}

/** `day` moved by `days` whole UTC days. */
function shiftDay(day: DateStamp, days: number): DateStamp {
	return dayKey(new Date(toDay(day).getTime() + days * 86_400_000));
}

function later(one: DateStamp, other: DateStamp): DateStamp {
	return one > other ? one : other;
}

/** One cell as the day files spelled it: nothing is '', a flag is 'True' or
 * 'False' as Python writes one, and a number is its decimal. */
function cellText(value: Row[string] | undefined): string {
	if (value === null || value === undefined) return '';
	if (typeof value === 'boolean') return value ? 'True' : 'False';
	return String(value);
}

function textCells(row: Row): Record<string, string> {
	return Object.fromEntries(Object.entries(row).map(([name, value]) => [name, cellText(value)]));
}

/** The newest `days` days one packed record holds, as text cells, and how the read went.
 *
 * Counted back from the newest day that holds a row, never from today, so a
 * record that stopped a week ago still answers with its last `days` days - the
 * same anchor every console window takes. That costs a second read only when the
 * newest packed days hold no row: the span is counted back from the newest
 * packed day first, and when the days at its end were packed empty, the days
 * that make up for them are read at its start. `-1` reads every packed day, and
 * a caller says beside the call why (`docs/concepts/growing-reads.md`).
 *
 * The span never starts before the record's first packed day, because a day
 * before it is a day no index names, and the door answers one as a hole.
 *
 * The read names the days in it the record's index records lost, and the files
 * its periods set aside unread, from both reads when there are two; keyed by
 * period, a month the two reads both meet counts its files once.
 *
 * `ask` makes the door call, so each reader names its own columns where the call
 * is written, which is where `chart-vocabulary.spec.ts` reads them.
 */
export async function newestRows(
	root: string,
	ledger: LedgerName,
	days: number,
	columns: readonly string[],
	ask: (from: DateStamp, to: DateStamp) => Promise<SliceResult>
): Promise<LedgerTable> {
	const empty = (read: RecordRead): LedgerTable => ({ rows: [], columns: [...columns], read });
	const reach = await reachFromDisk(root, ledger);
	// `quiet` here is an index that names no day yet: nothing has been packed.
	if (reach.state === 'missing' || reach.state === 'quiet') return empty({ state: 'not-packed' });
	if (reach.state === 'unreachable') return empty({ state: 'unreadable', at: null, fault: null });

	const every = days < 1;
	const from = every ? reach.first : later(reach.first, shiftDay(reach.through, 1 - days));
	const found = await ask(from, reach.through);
	if (found.state === 'missing') return empty({ state: 'not-packed' });
	if (found.state === 'unreachable') return empty({ state: 'unreadable', at: found.at, fault: found.fault });
	const through = found.through ?? reach.through;
	if (found.state === 'quiet') {
		return empty({ state: 'read', through, lostDays: found.lostDays, setAside: found.setAside });
	}

	let rows = found.rows;
	let { lostDays, setAside } = found;
	const newest = rows.reduce((top, row) => later(top, cellText(row.date)), '');
	const lag = daysBetween(newest, reach.through) - 1;
	if (!every && lag > 0 && from > reach.first) {
		const before = await ask(later(reach.first, shiftDay(from, -lag)), shiftDay(from, -1));
		if (before.state === 'unreachable') {
			return empty({ state: 'unreadable', at: before.at, fault: before.fault });
		}
		if (before.state === 'ok' || before.state === 'quiet') {
			lostDays = [...before.lostDays, ...lostDays];
			setAside = { ...before.setAside, ...setAside };
		}
		if (before.state === 'ok') rows = [...before.rows, ...rows];
	}
	return { rows: rows.map(textCells), columns: [...columns], read: { state: 'read', through, lostDays, setAside } };
}

/** One row per scored measurement, over the newest `days` days the score record holds.
 *
 * Read from the `summary-quality-evals` ledger, packed, and never recomputed.
 * There is no published mirror of this ledger: `frontend/public/scores/` was one
 * until 2026-09-16 and no route ever fetched it, so it went with its producer.
 */
export async function evalRows(
	days: number = LEDGER_WINDOW_DAYS,
	root: string = STATE_ROOT
): Promise<LedgerTable> {
	return newestRows(root, 'summary-quality-evals', days, SCORE_COLUMNS, (start, end) =>
		sliceFromDisk(root, 'summary-quality-evals', {
			columns: [...datedFirst(SCORE_COLUMNS)],
			from: start,
			to: end
		})
	);
}

/** One row per planned item per run, over the newest `days` days the article record holds.
 *
 * Read from `state/item-health/`, packed. The machine a row's readings were
 * taken on is `machine_job` and `machine_shard`; the ledger's own writer cells
 * are never asked for, so a panel reading a shard cannot pick up the writer's
 * by mistake.
 */
export async function itemHealthRows(
	days: number = LEDGER_WINDOW_DAYS,
	root: string = STATE_ROOT
): Promise<LedgerTable> {
	return newestRows(root, 'item-health', days, ITEM_HEALTH_COLUMNS, (start, end) =>
		sliceFromDisk(root, 'item-health', {
			columns: [...datedFirst(ITEM_HEALTH_COLUMNS)],
			from: start,
			to: end
		})
	);
}

/** The columns of `FeedHealthRow` a console route reads, in the contract's own order.
 *
 * Only these: the feed record carries the address it asked and what its robots
 * file said as well, and no console panel draws either. A backend contract test
 * fails when the contract renames or drops one of these, or when this order is
 * not the contract's.
 */
export const FEED_HEALTH_COLUMNS = [
	'run_id', 'date', 'feed_id', 'checked_at', 'outcome', 'status', 'items', 'detail'
] as const;

/** One row per feed per run, over the newest `days` days the feed record holds.
 *
 * Read from `state/compact/feed-health/`, packed, so it stops at the newest
 * packed day as the article and score records do.
 */
export async function feedHealthRows(
	days: number = LEDGER_WINDOW_DAYS,
	root: string = STATE_ROOT
): Promise<LedgerTable> {
	return newestRows(root, 'feed-health', days, FEED_HEALTH_COLUMNS, (start, end) =>
		sliceFromDisk(root, 'feed-health', {
			columns: [...datedFirst(FEED_HEALTH_COLUMNS)],
			from: start,
			to: end
		})
	);
}
