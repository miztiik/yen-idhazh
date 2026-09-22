/** What each work shard's machine did, per shard and per run, read at build time.
 *
 * Two ledgers meet here and neither is derived from the other.
 * `state/host-fingerprint/<Y>/<M>/<D>.csv` carries what the model server itself
 * counted reading prompts, what the job's clock said, and which processor the
 * host drew. `state/item-health/<Y>/<M>/<D>.csv` carries what every item cost,
 * which folded by shard gives the cache, the written tokens, the longest
 * sequence, the memory high-water mark, the time no named stage claimed and
 * the time an item waited before its worker started it. The run's planned
 * shard count comes from its own manifest and from nowhere else.
 *
 * **The read rate is the server's and the write rate is the ledger's, on
 * purpose.** Reading is the one quantity two instruments measure, so the two
 * are kept apart: the shard's `readTokensPerSecond` is `server_prompt_tokens`
 * over `server_prompt_seconds`, and the item ledger's own answer is pooled
 * beside it. A shard whose read rate was folded from the same item rows the
 * ledger side pools would make both halves of the clock check one expression
 * over one set of rows, and a check that cannot disagree has never run.
 *
 * **The planned shard count is never counted off the rows that reported.** A
 * denominator taken from the same rows as its numerator is always equal to it,
 * so "three shards of four reported this" could never be said. A run whose
 * manifest predates the cell carries `shards: null`, which is unknown and is
 * drawn as unknown - it is not zero and it is not the count that answered.
 *
 * Nothing here is published. It sits under `$lib/server/` so SvelteKit refuses
 * to bundle it for a browser, the same place and for the same reason as
 * `model-work.ts`, and it adds no published telemetry column: `state/` is not
 * served and no cell of it crosses to a reader.
 *
 * **An empty cell is unknown and never zero.** A server that never answered and
 * a server that read no tokens are different facts, and one of them is a broken
 * scrape. Every derived figure therefore leaves here as a `Reading`, carrying
 * the shards it was made from and the shards the run planned - so a page can
 * tell never measured from measured on three of sixteen without guessing.
 *
 * Imports nothing at runtime beyond the shared CSV readers: the browser suite
 * loads this module in plain Node, where no Vite alias resolves.
 */

import { join } from 'node:path';
// Relative, not `$lib`, for the reason in the module docstring.
import { itemRead } from '../charts/machine';
import { inferenceConfig, runConfig } from './config';
import {
	DIGEST_ROOT,
	itemHealthRows,
	LEDGER_WINDOW_DAYS,
	loadManifests,
	readDayShards,
	STATE_ROOT
} from './payload';

/** How far the two clocks may sit apart before one of them is wrong, in percent.
 *
 * The same bound `backend/utilities/reconcile_prefill.py` gates its exit code
 * on, restated rather than re-decided: two numbers for one tolerance is how a
 * page starts disagreeing with the audit that is supposed to check it. Five
 * percent is far above millisecond rounding over about 150 rows and far below
 * the failure it exists to catch, which was counting cached tokens as read -
 * 11.09 tokens a second against 19.96 on run `2026-08-25-1`, an 80 percent
 * error.
 *
 * Not a `config/` knob. Tuning it is how a failing check is made to pass.
 */
export const CLOCKS_AGREE_WITHIN_PCT = 5;

/** A figure, and how much of the run it was made from.
 *
 * `from` of zero means nothing measured it - and that is a different fact from
 * a measurement of zero, which arrives as `value: 0` with `from` above zero. A
 * page that prints the value without the pair prints a run figure derived from
 * three shards of sixteen as if it covered the run.
 */
export interface Reading<T> {
	/** Null where no shard reported every cell the figure needs. */
	value: T | null;
	/** Shards that reported those cells. */
	from: number;
	/** Shards the run planned, from its manifest. Null where it recorded none. */
	outOf: number | null;
}

/** The two ceilings a counter is read against, from `config/idhazh.json`.
 *
 * A counter without its ceiling is not a measurement: 4,925 says nothing until
 * 8,192 sits beside it. Both arrive as arguments rather than being read inside
 * a derivation, so a test drives them and Guardrail #6 keeps them out of the code.
 */
export interface MachineLimits {
	/** `--ctx-size` on the summarize entry - what the longest sequence is a share of. */
	contextWindow: number | null;
	/** `run.shard_timeout_minutes` as seconds - what `job_seconds` is a share of. */
	jobTimeoutSeconds: number | null;
}

/** One work shard: one llama-server, started at job start and kept to the end.
 *
 * Both server counters are cumulative for that process, so the one scrape at
 * job end is the whole shard and there is nothing to subtract.
 */
export interface ShardCounters {
	shard: number;
	/** Item rows this shard committed with both of a model call's token cells. */
	items: number;
	/** Seconds the server itself counted reading prompts. */
	readSeconds: number | null;
	/** Seconds the item ledger charged to decode, added over the shard's items. */
	writeSeconds: number | null;
	/** Reading as a share of the two together, whole percent. */
	readPct: number | null;
	/** Prompt tokens the server counted reading, cached ones excluded. */
	promptTokens: number | null;
	/** Prompt tokens the items reused from the cache instead of reading. */
	cachedTokens: number | null;
	/** Cached as a share of every prompt token the shard needed, whole percent. */
	cachedPct: number | null;
	/** Tokens the shard's model calls wrote. */
	writtenTokens: number | null;
	/** The server's own read rate. The half of the clock check the ledger cannot make. */
	readTokensPerSecond: number | null;
	writeTokensPerSecond: number | null;
	/** The longest sequence any of the shard's items reached, prompt plus answer. */
	longestSequence: number | null;
	/** That sequence as a share of the context window, whole percent. */
	contextUsedPct: number | null;
	/** The shard job's own clock. A floor, never a ceiling. */
	jobSeconds: number | null;
	/** That clock as a share of `run.shard_timeout_minutes`, whole percent. */
	jobUsedPct: number | null;
	/** The processor the host drew, as the text /proc/cpuinfo printed. */
	cpuModel: string | null;
	/** The least busy the processor was over any one item's model window. */
	cpuBusyPct: number | null;
	/** Cores the host let this job see. What `loadMax` is read against: a queue
	 * is load past the cores, and 6.1 is a queue on four and not on eight. */
	cores: number | null;
	/** The middle item's mean CPU busy. A typical item, not the worst one. */
	cpuBusyMedianPct: number | null;
	/** The busiest any one item's model window got. */
	cpuBusyMaxPct: number | null;
	/** The middle item's share of its interval that the host gave to another
	 * tenant's machine while ours was ready to run. */
	cpuStolenMedianPct: number | null;
	/** The worst any one item lost that way. What a slow shard is checked
	 * against: a long clock at a normal busy share and a high stolen share is a
	 * shared box rather than our own work. */
	cpuStolenMaxPct: number | null;
	/** Items of the shard that recorded the stolen share at all. Zero where the
	 * shard ran before the ledger split it out of the busy share, which is a
	 * different fact from a host that took nothing. */
	cpuStolenItems: number;
	/** llama-server's own memory high-water mark over the shard's items. */
	peakRssBytes: number | null;
	/** The middle item's high-water mark. Paired with `peakRssBytes` it is a
	 * range: a median near the peak is a shard that ran hot throughout. */
	rssMedianBytes: number | null;
	/** The highest one-minute load any of the shard's items ended under. */
	loadMax: number | null;
	/** The least swap left at the end of any of the shard's items. */
	swapFreeMinBytes: number | null;
	/** Swap the host has. Zero is a box with no swap, which is a different fact
	 * from swap consumed - and only the second is an emergency. */
	swapTotalBytes: number | null;
	/** What the shard paid opening the weights before its first item. */
	modelLoadMs: number | null;
	/** Seconds of the shard's items that no named stage claimed - `stage_gap_ms`
	 * added over them, and never a difference worked out here.
	 *
	 * **Signed, and added as it is stored.** Below zero means the named stages
	 * claim more time than the items took, which is two clocks disagreeing.
	 * Taking the absolute value would throw away the one finding this figure
	 * exists for. Each item's gap is a slice of that item's own clock and the
	 * items run one after another, so adding them is the shard's own total.
	 */
	unclaimedSeconds: number | null;
	/** Items of this shard whose unclaimed time is below zero.
	 *
	 * Carried beside the sum because a sum can cancel: one item at plus two
	 * seconds and one at minus two add to nothing, and the disagreement the pair
	 * records would disappear.
	 */
	clocksDisagreed: number;
	/** Item rows of this shard that carried an unclaimed figure at all. The
	 * denominator `clocksDisagreed` is read against, and not `items` - a row with
	 * no model call still has a stage clock, so the two counts differ. */
	clockedItems: number;
	/** The middle item's wait before its worker started it, in seconds. */
	queueMedianSeconds: number | null;
	/** The longest any one item waited, in seconds.
	 *
	 * **Never a sum.** The stage fetches every item and then works them in a
	 * different order, so each item's wait covers the queue ahead of it and
	 * adding them counts that queue once per item - measured 2026-09-14 at 2,786
	 * seconds against a shard's true 2,196. A typical item and the worst one are
	 * two figures that stay true however many items the shard ran.
	 */
	queueMaxSeconds: number | null;
}

/** Tokens and the seconds they took, summed. Never a mean of per-part rates.
 *
 * A rate is a ratio, and averaging ratios weighs a shard that did 20 items the
 * same as one that did 40 (`docs/reference/pipeline-cost.md`). The same shape
 * `reconcile_prefill.Pooled` carries, so one definition serves the audit and
 * the page.
 */
export interface Pooled {
	tokens: number;
	seconds: number;
	/** Shards on the server side, items on the ledger side. */
	parts: number;
	/** Tokens a second. Null where nothing was pooled or no time was spent. */
	rate: number | null;
}

/** The item ledger's own reading of a run, against the server's.
 *
 * Both sides count prompt tokens read - `input_tokens` minus `cached_tokens` on
 * the ledger, `server_prompt_tokens` on the machine record - so a disagreement
 * is one of the two instruments being wrong rather than the two measuring
 * different things. Arithmetic over the item ledger cannot check the item
 * ledger, which is why the server half comes off a different file.
 */
export interface ClockCheck {
	ledger: Pooled;
	server: Pooled;
	/** How far the ledger sits from the server, as a percent of the server.
	 * Null where either side pooled nothing, which is not a disagreement. */
	gapPct: number | null;
	/** Null where nothing was compared. Never `false` by default. */
	agrees: boolean | null;
}

/** One run, made of the shards the two ledgers recorded. */
export interface MachineRun {
	runId: string;
	date: string;
	/** Shards the run planned, from `RunManifest.shards`. Null where the
	 * manifest predates the cell, which is unknown and never a count. */
	shards: number | null;
	/** One entry per distinct shard index either ledger holds, ascending.
	 *
	 * Shorter than `shards` whenever a shard's job died before it recorded
	 * anything. That difference is the whole reason the denominator is the
	 * plan's rather than a count of these.
	 */
	reported: ShardCounters[];
	readSeconds: Reading<number>;
	writeSeconds: Reading<number>;
	readPct: Reading<number>;
	promptTokens: Reading<number>;
	cachedTokens: Reading<number>;
	cachedPct: Reading<number>;
	readTokensPerSecond: Reading<number>;
	writeTokensPerSecond: Reading<number>;
	/** The fastest shard's read rate over the slowest.
	 *
	 * The figure this route exists for. Measured 2026-09-01 over the 18 runs the
	 * counters ledger could then be read for, it ran 1.007x to 4.345x, and a
	 * per-run average reports neither end of it.
	 */
	readSpread: Reading<number>;
	/** The longest sequence any shard saw. A maximum, not a sum. */
	longestSequence: Reading<number>;
	contextUsedPct: Reading<number>;
	/** The slowest shard's clock. The run's wall clock is its slowest shard. */
	slowestJobSeconds: Reading<number>;
	jobUsedPct: Reading<number>;
	/** Every distinct processor the run drew, sorted. A run draws up to eight. */
	cpuModels: Reading<string[]>;
	/** The least busy shard. The reading sits near 100 and a DROP is the signal:
	 * it says that shard spent its job waiting rather than computing. */
	lowestCpuBusyPct: Reading<number>;
	/** The highest any shard reached. What decides whether a model can be served
	 * on the runner's 16 GB with headroom left. A maximum and never a sum: shards
	 * are separate jobs on separate hosts, so adding four of them would report a
	 * machine that never existed. */
	peakRssBytes: Reading<number>;
	/** The slowest shard's load. Read against the same wall clock the job clock
	 * is read against, so the two are the same shard's worst case. */
	slowestModelLoadMs: Reading<number>;
	clocks: ClockCheck;
}

/** A run whose rows cannot be made into one run, and what stopped it.
 *
 * Never dropped silently. The machine record writes its row in two halves at
 * one key, so a half that disagrees with its partner about a cell is two
 * servers answering for one shard - which cannot be added and cannot be picked
 * between.
 */
export interface RefusedRun {
	runId: string;
	date: string;
	/** Rows the two ledgers hold for the run. */
	rows: number;
	/** Plain words: what could not be reconciled. */
	why: string;
}

/** Every run the two ledgers describe, and every run they could not. */
export interface MachineCounters {
	/** Newest first, by run id. */
	runs: MachineRun[];
	/** Newest first. A page that prints a run count prints this one beside it. */
	refused: RefusedRun[];
}

/** An empty cell is an absent value, never a zero. */
function measured(value: string | undefined): number | null {
	if (value === undefined || value === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

function text(value: string | undefined): string | null {
	return value === undefined || value === '' ? null : value;
}

/** A share as whole percent, or null where either side is unknown.
 *
 * A zero denominator returns null rather than infinity: nothing was measured to
 * take a share of.
 */
function sharePct(part: number | null, whole: number | null): number | null {
	if (part === null || whole === null || whole <= 0) return null;
	return Math.round((part / whole) * 100);
}

/** Tokens over seconds. Null where either is unknown or no time was spent. */
function rate(tokens: number | null, seconds: number | null): number | null {
	if (tokens === null || seconds === null || seconds <= 0) return null;
	return tokens / seconds;
}

/** Milliseconds as seconds, keeping absence absent and keeping the sign. */
function msToSeconds(value: number | null): number | null {
	return value === null ? null : value / 1000;
}

const sum = (values: number[]): number => values.reduce((total, value) => total + value, 0);
const highest = (values: number[]): number => Math.max(...values);
const lowest = (values: number[]): number => Math.min(...values);

/** Every cell of the machine record this route reads.
 *
 * A job files its row in two halves at one key - the probe before the work, the
 * clock and the server's counters after it - so two rows for one shard are one
 * record when no cell disagrees. A cell filled differently twice is two servers
 * answering for one shard, and the run is refused.
 */
const HOST_CELLS = [
	'cpu_model',
	'cores',
	'job_seconds',
	'model_load_ms',
	'server_prompt_tokens',
	'server_prompt_seconds'
] as const;

/** One shard's machine cells, merged from however many halves the record holds. */
interface HostCells {
	cpuModel: string | null;
	cores: number | null;
	jobSeconds: number | null;
	modelLoadMs: number | null;
	serverPromptTokens: number | null;
	serverPromptSeconds: number | null;
}

/** The item cells of one shard, added up. */
interface ItemFold {
	items: number;
	cachedTokens: number | null;
	writtenTokens: number | null;
	writeSeconds: number | null;
	longestSequence: number | null;
	cpuBusyPct: number | null;
	peakRssBytes: number | null;
	/** Every item's own reading, kept only long enough to take the middle one.
	 * A median cannot be folded the way a sum or a maximum can. Bounded by the
	 * items one shard ran, and dropped before a `ShardCounters` leaves here. */
	busy: number[];
	rss: number[];
	cpuBusyMaxPct: number | null;
	/** Every item's own stolen share, on the same terms as `busy`. */
	stolen: number[];
	cpuStolenMaxPct: number | null;
	loadMax: number | null;
	swapFreeMinBytes: number | null;
	swapTotalBytes: number | null;
	/** The processor, where the item ledger recorded one. Read only when the
	 * machine record missed the shard, so a shard the record never reached still
	 * names its machine instead of drawing as unrecorded. */
	cpuModel: string | null;
	/** `stage_gap_ms` added over the shard's items, signed. */
	unclaimedMs: number | null;
	/** How many of those items carried a gap below zero. */
	clocksDisagreed: number;
	/** How many item rows carried a gap at all. */
	clockedItems: number;
	/** Every item's own wait, kept only long enough to take the middle one and
	 * the worst. Bounded by the items one shard ran, and dropped before a
	 * `ShardCounters` leaves here - the same handling `busy` and `rss` get. */
	queueWaits: number[];
}

function emptyFold(): ItemFold {
	return {
		items: 0,
		cachedTokens: null,
		writtenTokens: null,
		writeSeconds: null,
		longestSequence: null,
		cpuBusyPct: null,
		peakRssBytes: null,
		busy: [],
		rss: [],
		cpuBusyMaxPct: null,
		stolen: [],
		cpuStolenMaxPct: null,
		loadMax: null,
		swapFreeMinBytes: null,
		swapTotalBytes: null,
		cpuModel: null,
		unclaimedMs: null,
		clocksDisagreed: 0,
		clockedItems: 0,
		queueWaits: []
	};
}

/** The middle reading of a set, interpolated between the two nearest ranks.
 *
 * The same rule the route's percentiles use, so a median printed beside a p50
 * cannot be a second answer to one question.
 */
function median(values: readonly number[]): number | null {
	if (values.length === 0) return null;
	const sorted = [...values].sort((left, right) => left - right);
	const position = (sorted.length - 1) / 2;
	const low = Math.floor(position);
	const high = Math.ceil(position);
	return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

/** One item row folded into a shard's totals. A missing cell adds nothing.
 *
 * Not a zero: a row that predates token capture is evidence in neither
 * direction, and counting it as an item that wrote nothing would drag every
 * total on the row down by however many such rows the day holds.
 */
function foldItem(carry: ItemFold, row: Record<string, string>): void {
	const input = measured(row.input_tokens);
	const cached = measured(row.cached_tokens);
	const written = measured(row.output_tokens);
	if (input !== null && cached !== null) {
		carry.items += 1;
		carry.cachedTokens = (carry.cachedTokens ?? 0) + cached;
		if (written !== null) {
			carry.longestSequence = Math.max(carry.longestSequence ?? 0, input + written);
		}
	}
	if (written !== null) carry.writtenTokens = (carry.writtenTokens ?? 0) + written;
	const decode = measured(row.decode_ms);
	if (decode !== null) carry.writeSeconds = (carry.writeSeconds ?? 0) + decode / 1000;
	const busy = measured(row.cpu_busy_pct);
	if (busy !== null) {
		carry.cpuBusyPct = Math.min(carry.cpuBusyPct ?? busy, busy);
		carry.busy.push(busy);
	}
	const busyMax = measured(row.cpu_busy_max);
	if (busyMax !== null) carry.cpuBusyMaxPct = Math.max(carry.cpuBusyMaxPct ?? busyMax, busyMax);
	// A row written before 2026-09-20 carries no stolen share, and the absence is
	// kept as an absence: a zero here would say the host took nothing from a run
	// whose busy figure was holding both halves at the time.
	const stolen = measured(row.cpu_steal_pct);
	if (stolen !== null) {
		carry.stolen.push(stolen);
		carry.cpuStolenMaxPct = Math.max(carry.cpuStolenMaxPct ?? stolen, stolen);
	}
	const peak = measured(row.llama_rss_peak_bytes);
	if (peak !== null) {
		carry.peakRssBytes = Math.max(carry.peakRssBytes ?? 0, peak);
		carry.rss.push(peak);
	}
	const load = measured(row.load_1m);
	if (load !== null) carry.loadMax = Math.max(carry.loadMax ?? load, load);
	const swapFree = measured(row.os_swap_free_bytes);
	if (swapFree !== null)
		carry.swapFreeMinBytes = Math.min(carry.swapFreeMinBytes ?? swapFree, swapFree);
	const swapTotal = measured(row.os_swap_total_bytes);
	if (swapTotal !== null) carry.swapTotalBytes = swapTotal;
	carry.cpuModel = carry.cpuModel ?? text(row.cpu_model);
	// Added as stored, sign and all. A row below zero is the finding, so it is
	// counted as well as added: a sum alone lets two items cancel each other out.
	const unclaimed = measured(row.stage_gap_ms);
	if (unclaimed !== null) {
		carry.unclaimedMs = (carry.unclaimedMs ?? 0) + unclaimed;
		carry.clockedItems += 1;
		if (unclaimed < 0) carry.clocksDisagreed += 1;
	}
	const queued = measured(row.queue_wait_ms);
	if (queued !== null) carry.queueWaits.push(queued);
}

/** The machine record's halves for one shard, merged. Null where they disagree. */
function mergeHost(rows: Record<string, string>[]): HostCells | null {
	const held = new Map<string, string>();
	for (const row of rows) {
		for (const cell of HOST_CELLS) {
			const value = (row[cell] ?? '').trim();
			if (value === '') continue;
			const carried = held.get(cell);
			if (carried !== undefined && carried !== value) return null;
			held.set(cell, value);
		}
	}
	return {
		cpuModel: text(held.get('cpu_model')),
		cores: measured(held.get('cores')),
		jobSeconds: measured(held.get('job_seconds')),
		modelLoadMs: measured(held.get('model_load_ms')),
		serverPromptTokens: measured(held.get('server_prompt_tokens')),
		serverPromptSeconds: measured(held.get('server_prompt_seconds'))
	};
}

/** One shard's two sources read into figures, with the two ceilings applied. */
function shardCounters(
	shard: number,
	host: HostCells,
	fold: ItemFold,
	limits: MachineLimits
): ShardCounters {
	const readSeconds = host.serverPromptSeconds;
	const promptTokens = host.serverPromptTokens;
	const writeSeconds = fold.writeSeconds;
	return {
		shard,
		items: fold.items,
		readSeconds,
		writeSeconds,
		// The server's read clock against the ledger's write clock. Reading is the
		// only side two instruments measure, and the panel below says whether they
		// agree - so the split is read with that answer beside it.
		readPct:
			readSeconds === null || writeSeconds === null
				? null
				: sharePct(readSeconds, readSeconds + writeSeconds),
		promptTokens,
		cachedTokens: fold.cachedTokens,
		// The denominator is every prompt token the shard needed, read or reused,
		// so the share answers "would a bigger cache have saved wall clock".
		cachedPct:
			promptTokens === null || fold.cachedTokens === null
				? null
				: sharePct(fold.cachedTokens, promptTokens + fold.cachedTokens),
		writtenTokens: fold.writtenTokens,
		readTokensPerSecond: rate(promptTokens, readSeconds),
		writeTokensPerSecond: rate(fold.writtenTokens, writeSeconds),
		longestSequence: fold.longestSequence,
		contextUsedPct: sharePct(fold.longestSequence, limits.contextWindow),
		jobSeconds: host.jobSeconds,
		jobUsedPct: sharePct(host.jobSeconds, limits.jobTimeoutSeconds),
		// The machine record first, because it is the instrument for this cell. The
		// item ledger's copy is the fallback for a shard the record never reached,
		// which would otherwise draw as a machine nobody can name.
		cpuModel: host.cpuModel ?? fold.cpuModel,
		cpuBusyPct: fold.cpuBusyPct,
		cores: host.cores,
		cpuBusyMedianPct: median(fold.busy),
		cpuBusyMaxPct: fold.cpuBusyMaxPct,
		cpuStolenMedianPct: median(fold.stolen),
		cpuStolenMaxPct: fold.cpuStolenMaxPct,
		cpuStolenItems: fold.stolen.length,
		peakRssBytes: fold.peakRssBytes,
		rssMedianBytes: median(fold.rss),
		loadMax: fold.loadMax,
		swapFreeMinBytes: fold.swapFreeMinBytes,
		swapTotalBytes: fold.swapTotalBytes,
		modelLoadMs: host.modelLoadMs,
		unclaimedSeconds: msToSeconds(fold.unclaimedMs),
		clocksDisagreed: fold.clocksDisagreed,
		clockedItems: fold.clockedItems,
		queueMedianSeconds: msToSeconds(median(fold.queueWaits)),
		queueMaxSeconds:
			fold.queueWaits.length === 0 ? null : Math.max(...fold.queueWaits) / 1000
	};
}

/** A `Reading` over the shards that answered a question, and only those.
 *
 * `pick` returns null for a shard that cannot answer, so the denominator on the
 * way out is the run's planned shard count and the numerator is who spoke.
 */
function reading<T, V>(
	shards: ShardCounters[],
	outOf: number | null,
	pick: (shard: ShardCounters) => V | null,
	fold: (values: V[]) => T
): Reading<T> {
	const values = shards.map(pick).filter((value): value is V => value !== null);
	return {
		value: values.length === 0 ? null : fold(values),
		from: values.length,
		outOf
	};
}

/** A pooled rate over the shards that reported both of its cells.
 *
 * Sum over sum, which is the only correct composition. A shard missing either
 * cell is left out of both sums rather than contributing a zero to one of them,
 * which would report a rate the machine never ran at.
 */
function pooledRate(
	shards: ShardCounters[],
	outOf: number | null,
	tokensOf: (shard: ShardCounters) => number | null,
	secondsOf: (shard: ShardCounters) => number | null
): Reading<number> {
	const pairs = shards
		.map((shard) => ({ tokens: tokensOf(shard), seconds: secondsOf(shard) }))
		.filter(
			(pair): pair is { tokens: number; seconds: number } =>
				pair.tokens !== null && pair.seconds !== null
		);
	const seconds = sum(pairs.map((pair) => pair.seconds));
	return {
		value:
			pairs.length === 0 || seconds <= 0
				? null
				: sum(pairs.map((pair) => pair.tokens)) / seconds,
		from: pairs.length,
		outOf
	};
}

/** One run's item-health rows, pooled the way `reconcile_prefill.pool_ledger` pools them.
 *
 * `input_tokens - cached_tokens` is the definition and `itemRead` in
 * `$lib/charts/machine.ts` owns it, so the run figure here and the per-shard
 * figure the machine page draws can never disagree about what a prompt token
 * is. A row missing either required cell predates token capture and is evidence
 * in neither direction, so it is skipped rather than counted as an item that
 * read nothing.
 */
function poolLedger(health: Record<string, string>[]): Pooled {
	let tokens = 0;
	let milliseconds = 0;
	let parts = 0;
	for (const row of health) {
		const read = itemRead(row);
		if (read === null) continue;
		tokens += read.tokens;
		milliseconds += read.ms;
		parts += 1;
	}
	const seconds = milliseconds / 1000;
	return { tokens, seconds, parts, rate: rate(tokens, seconds) };
}

function poolServer(shards: ShardCounters[]): Pooled {
	const counted = shards.filter(
		(shard) => shard.promptTokens !== null && shard.readSeconds !== null
	);
	const tokens = sum(counted.map((shard) => shard.promptTokens ?? 0));
	const seconds = sum(counted.map((shard) => shard.readSeconds ?? 0));
	return { tokens, seconds, parts: counted.length, rate: rate(tokens, seconds) };
}

function clockCheck(shards: ShardCounters[], health: Record<string, string>[]): ClockCheck {
	const ledger = poolLedger(health);
	const server = poolServer(shards);
	if (ledger.rate === null || server.rate === null) {
		return { ledger, server, gapPct: null, agrees: null };
	}
	const gapPct = (Math.abs(ledger.rate - server.rate) / server.rate) * 100;
	return { ledger, server, gapPct, agrees: gapPct <= CLOCKS_AGREE_WITHIN_PCT };
}

/** The two ledgers' rows for one run, as one run - or the reason they are not.
 *
 * `health` and `hosts` are this run's own rows, already picked out by the
 * caller. `planned` is what its manifest said, which may be nothing.
 */
function oneRun(
	runId: string,
	hosts: Record<string, string>[],
	health: Record<string, string>[],
	planned: number | null,
	limits: MachineLimits
): MachineRun | RefusedRun {
	const rows = hosts.length + health.length;
	const date = hosts[0]?.date ?? health[0]?.date ?? '';
	const refuse = (why: string): RefusedRun => ({ runId, date, rows, why });

	const days = new Set([...hosts, ...health].map((row) => row.date ?? ''));
	if (days.size > 1) {
		return refuse('its rows disagree about which day the run belongs to');
	}

	const hostsByShard = new Map<number, Record<string, string>[]>();
	for (const row of hosts) {
		const shard = measured(row.shard ?? '');
		// A row that does not say which shard it is cannot be merged against any
		// other row, and reading it as shard zero would fold it into a real
		// shard's record.
		if (shard === null) return refuse('a machine record does not say which shard it came from');
		const held = hostsByShard.get(shard);
		if (held === undefined) hostsByShard.set(shard, [row]);
		else held.push(row);
	}

	const folds = new Map<number, ItemFold>();
	for (const row of health) {
		const shard = measured(row.shard ?? '');
		if (shard === null) continue;
		let carry = folds.get(shard);
		if (carry === undefined) {
			carry = emptyFold();
			folds.set(shard, carry);
		}
		foldItem(carry, row);
	}

	const reported: ShardCounters[] = [];
	for (const shard of [...new Set([...hostsByShard.keys(), ...folds.keys()])].sort(
		(a, b) => a - b
	)) {
		const host = mergeHost(hostsByShard.get(shard) ?? []);
		if (host === null) {
			return refuse(
				`shard ${shard} filed two machine records that disagree, so two servers ` +
					'answered for one shard and neither can be read over the other'
			);
		}
		reported.push(shardCounters(shard, host, folds.get(shard) ?? emptyFold(), limits));
	}
	if (reported.length === 0) return refuse('neither ledger holds a shard for this run');

	// The plan's own count. Never the count of who answered: those are the same
	// rows the numerator comes from, so the difference this denominator exists to
	// show could never appear.
	if (planned !== null && reported.length > planned) {
		return refuse(
			`${reported.length} shards filed a row for a run the plan split into ${planned}`
		);
	}
	if (planned !== null && reported.some((shard) => shard.shard >= planned)) {
		return refuse(`a shard index sits at or above the run's planned shard count of ${planned}`);
	}

	const over = <T>(pick: (shard: ShardCounters) => number | null, fold: (values: number[]) => T) =>
		reading(reported, planned, pick, fold);
	const readRates = reported
		.map((shard) => shard.readTokensPerSecond)
		.filter((value): value is number => value !== null);

	return {
		runId,
		date,
		shards: planned,
		reported,
		readSeconds: over((shard) => shard.readSeconds, sum),
		writeSeconds: over((shard) => shard.writeSeconds, sum),
		// Both halves or neither: a share of the two clocks needs a shard to have
		// reported both of them, and pairing a summed read against a summed write
		// over two different shard sets is not a share of anything.
		readPct: reading(
			reported,
			planned,
			(shard) =>
				shard.readSeconds === null || shard.writeSeconds === null
					? null
					: { read: shard.readSeconds, write: shard.writeSeconds },
			(pairs) =>
				Math.round(
					(sum(pairs.map((pair) => pair.read)) /
						sum(pairs.map((pair) => pair.read + pair.write))) *
						100
				)
		),
		promptTokens: over((shard) => shard.promptTokens, sum),
		cachedTokens: over((shard) => shard.cachedTokens, sum),
		cachedPct: reading(
			reported,
			planned,
			(shard) =>
				shard.promptTokens === null || shard.cachedTokens === null
					? null
					: { read: shard.promptTokens, cached: shard.cachedTokens },
			(pairs) =>
				Math.round(
					(sum(pairs.map((pair) => pair.cached)) /
						sum(pairs.map((pair) => pair.read + pair.cached))) *
						100
				)
		),
		readTokensPerSecond: pooledRate(
			reported,
			planned,
			(shard) => shard.promptTokens,
			(shard) => shard.readSeconds
		),
		writeTokensPerSecond: pooledRate(
			reported,
			planned,
			(shard) => shard.writtenTokens,
			(shard) => shard.writeSeconds
		),
		// One shard cannot spread against itself, so a run of one reports nothing
		// rather than 1.00x, which would read as "the hosts agreed".
		readSpread: {
			value: readRates.length < 2 ? null : highest(readRates) / lowest(readRates),
			from: readRates.length,
			outOf: planned
		},
		longestSequence: over((shard) => shard.longestSequence, highest),
		contextUsedPct: over((shard) => shard.contextUsedPct, highest),
		slowestJobSeconds: over((shard) => shard.jobSeconds, highest),
		jobUsedPct: over((shard) => shard.jobUsedPct, highest),
		cpuModels: reading(
			reported,
			planned,
			(shard) => shard.cpuModel,
			(models) => [...new Set(models)].sort()
		),
		lowestCpuBusyPct: over((shard) => shard.cpuBusyPct, lowest),
		peakRssBytes: over((shard) => shard.peakRssBytes, highest),
		slowestModelLoadMs: over((shard) => shard.modelLoadMs, highest),
		clocks: clockCheck(reported, health)
	};
}

/** Only the work job files the rows this route reads.
 *
 * Every job records the machine it drew, and they are not this slice: the plan
 * and assemble jobs run one shard each and serve different weights, so pooling
 * them into a shard board would answer about a matrix nobody dispatched. A row
 * whose cell is empty is the work job, which is what the contract defaults it
 * to. The same rule `machine.PUBLISHED_JOB` states for the published series.
 */
export const READ_JOB = 'work';

/** Every run the two ledgers describe, newest first.
 *
 * Pure: it takes rows, the planned shard counts and the two ceilings, so a test
 * drives a fixture without touching the disk and `loadMachineCounters` is the
 * only thing that knows where the files are.
 *
 * Both ledgers are grouped by run in one pass each, and each run is then handed
 * its own rows - one check a row whatever the run count is (Guardrail #12).
 */
export function machineCounters(
	hosts: Record<string, string>[],
	health: Record<string, string>[],
	planned: ReadonlyMap<string, number>,
	limits: MachineLimits
): MachineCounters {
	const byRun = new Map<string, Record<string, string>[]>();
	for (const row of hosts) {
		const runId = row.run_id ?? '';
		if (!runId) continue;
		if ((row.job ?? '') !== '' && row.job !== READ_JOB) continue;
		const held = byRun.get(runId);
		if (held === undefined) byRun.set(runId, [row]);
		else held.push(row);
	}
	const itemsByRun = new Map<string, Record<string, string>[]>();
	for (const row of health) {
		const runId = row.run_id ?? '';
		if (!runId) continue;
		const held = itemsByRun.get(runId);
		if (held === undefined) itemsByRun.set(runId, [row]);
		else held.push(row);
	}
	const runs: MachineRun[] = [];
	const refused: RefusedRun[] = [];
	// Run ids are `<date>-<n>`, so a plain string sort orders a day's runs
	// correctly and orders the days too - up to run ten of one day, which this
	// pipeline has never reached and which `run.max_parallel` of 4 bounds.
	const ids = [...new Set([...byRun.keys(), ...itemsByRun.keys()])].sort().reverse();
	for (const runId of ids) {
		const result = oneRun(
			runId,
			byRun.get(runId) ?? [],
			itemsByRun.get(runId) ?? [],
			planned.get(runId) ?? null,
			limits
		);
		if ('why' in result) refused.push(result);
		else runs.push(result);
	}
	return { runs, refused };
}

/** One row per job per run of the machine record, read from the committed ledger.
 *
 * Through `STATE_ROOT` like every other ledger read, so a test can point the
 * whole tree at a fixture and a canary build cannot reach the real one.
 */
export function hostRows(days: number = LEDGER_WINDOW_DAYS): Record<string, string>[] {
	return readDayShards(join(STATE_ROOT, 'host-fingerprint'), days).rows;
}

/** What each run's plan decided its shard count was, by run id.
 *
 * The manifest and nothing else. The plan settled this before any work job
 * existed, so it is the one reading that can disagree with how many of them
 * answered - and a run whose manifest predates the cell is absent here, which
 * is unknown rather than zero.
 */
export function plannedShards(
	days: number = LEDGER_WINDOW_DAYS,
	root: string = DIGEST_ROOT
): Map<string, number> {
	const found = new Map<string, number>();
	for (const day of loadManifests(root, days)) {
		for (const run of day.records) {
			if (run.shards !== null) found.set(run.runId, run.shards);
		}
	}
	return found;
}

/** The two ceilings, read from `config/idhazh.json` through the one config reader.
 *
 * the summarize entry's `--ctx-size` and `run.shard_timeout_minutes` (Guardrail #6). Both have
 * a default there, so a fresh clone with no config file still draws a ceiling
 * rather than none.
 */
export function machineLimits(): MachineLimits {
	return {
		contextWindow: inferenceConfig().n_ctx,
		jobTimeoutSeconds: runConfig().shard_timeout_minutes * 60
	};
}

/** Everything the machine route needs, off the committed ledgers.
 *
 * The one caller a route needs. Reading happens here and nowhere else, so
 * `machineCounters` stays drivable from a fixture.
 *
 * `days` covers all three reads - both day-sharded ledgers and the manifests -
 * so they can never answer over different days.
 */
export function loadMachineCounters(days: number = LEDGER_WINDOW_DAYS): MachineCounters {
	return machineCounters(
		hostRows(days),
		itemHealthRows(days).rows,
		plannedShards(days),
		machineLimits()
	);
}
