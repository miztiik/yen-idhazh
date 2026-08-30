/** What llama-server itself counted, per shard and per run, read at build time.
 *
 * `state/runtime-counters.csv` has been committed since 2026-08-27 and until
 * this module nothing read a cell of it. Over that time every throughput figure
 * this project quoted came off one instrument - the timings the summarize stage
 * copied out of each model reply - and the second instrument that could check
 * them sat unread. Measured 2026-08-30 by this module over the 10 committed runs
 * it can read: the read rate inside a single run varies 1.01x to 4.35x, and the
 * worst run ran one shard at 9.80 prompt tokens a second against another at
 * 42.58. A per-run average hides all of that, which is why the shard is the unit
 * here and the run figure always carries how many shards it was made from.
 *
 * Nothing here is published. It sits under `$lib/server/` so SvelteKit refuses
 * to bundle it for a browser, the same place and for the same reason as
 * `model-work.ts`, and it adds no published telemetry column: `state/` is not
 * served and no cell of it crosses to a reader.
 *
 * **An empty cell is unknown and never zero.** `RuntimeCountersRow.csv_row`
 * says it in the writer: "A server that never answered and a server that read
 * no tokens are different facts, and one of them is a broken scrape." Three of
 * the columns landed on 2026-08-29 and three more on 2026-08-30, so most
 * committed rows are blank in most of them. Every derived figure therefore
 * leaves here as a `Reading`, carrying the shards it was made from and the
 * shards the run had - so a page can tell never measured from measured on three
 * of sixteen without guessing.
 *
 * Imports nothing at runtime beyond the shared CSV reader: the browser suite
 * loads this module in plain Node, where no Vite alias resolves.
 */

import { join } from 'node:path';
// Relative, not `$lib`, for the reason in the module docstring.
import { inferenceConfig, runConfig } from './config';
import { itemHealthRows, readCsv, STATE_ROOT, type CsvTable } from './payload';

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
	/** Shards the run split into. The denominator. */
	outOf: number;
}

/** The two ceilings a counter is read against, from `config/idhazh.json`.
 *
 * A counter without its ceiling is not a measurement: 4,925 says nothing until
 * 8,192 sits beside it. Both arrive as arguments rather than being read inside
 * a derivation, so a test drives them and Rule #6 keeps them out of the code.
 */
export interface MachineLimits {
	/** `models.inference.n_ctx` - what `n_tokens_max` is a share of. */
	contextWindow: number | null;
	/** `run.shard_timeout_minutes` as seconds - what `job_seconds` is a share of. */
	jobTimeoutSeconds: number | null;
}

/** One work shard: one llama-server, started at job start and kept to the end.
 *
 * Both `llamacpp:` counters are cumulative for that process, so the one scrape
 * at job end is the whole shard and there is nothing to subtract.
 */
export interface ShardCounters {
	shard: number;
	/** When the counters were read. Job end, after the last item settled. */
	scrapedAt: string;
	/** Seconds the server spent reading prompts. */
	readSeconds: number | null;
	/** Seconds it spent writing tokens. */
	writeSeconds: number | null;
	/** Reading as a share of the two together, whole percent. */
	readPct: number | null;
	/** Prompt tokens actually read, cached ones excluded. */
	promptTokens: number | null;
	/** Prompt tokens reused from the cache instead of read. */
	cachedTokens: number | null;
	/** Cached as a share of every prompt token the shard needed, whole percent. */
	cachedPct: number | null;
	/** Tokens the server wrote. */
	writtenTokens: number | null;
	readTokensPerSecond: number | null;
	writeTokensPerSecond: number | null;
	/** The longest sequence the server saw, prompt plus generation. */
	longestSequence: number | null;
	/** That sequence as a share of the context window, whole percent. */
	contextUsedPct: number | null;
	/** The shard job's own clock up to the scrape. A floor, never a ceiling. */
	jobSeconds: number | null;
	/** That clock as a share of `run.shard_timeout_minutes`, whole percent. */
	jobUsedPct: number | null;
	/** The processor the host drew, as the text /proc/cpuinfo printed. */
	cpuModel: string | null;
	/** The share of every processor second the host spent busy over the job. */
	cpuBusyPct: number | null;
	/** llama-server's own memory high-water mark. */
	peakRssBytes: number | null;
	/** What the shard paid opening the weights before its first item. */
	modelLoadMs: number | null;
	/** Slots busy per decode call. `1.0` says batching never happened. */
	slotsPerDecode: number | null;
}

/** Tokens and the seconds they took, summed. Never a mean of per-part rates.
 *
 * A rate is a ratio, and averaging ratios weighs a shard that did 20 items the
 * same as one that did 40 (`docs/reference/measurements.md`). The same shape
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
 * The runtime ledger was created for exactly this check and nothing performed
 * it on screen. Both sides count prompt tokens read - `input_tokens` minus
 * `cached_tokens` on the ledger, `prompt_tokens_total` on the server - so a
 * disagreement is one of the two instruments being wrong rather than the two
 * measuring different things.
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

/** One run, made of the shards that committed a row for it. */
export interface RunCounters {
	runId: string;
	date: string;
	/** Shards the run split into, from the row's own `shards` cell. */
	shards: number;
	/** One entry per distinct shard index that committed a row, ascending.
	 *
	 * Shorter than `shards` whenever a shard's job died before it scraped. Run
	 * `2026-08-29-3` is three of four on the committed ledger.
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
	 * The figure this module exists for. Measured 2026-08-30 over the 10 runs
	 * the committed ledger can be read for, it runs 1.01x to 4.35x, and a
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
	 * on the runner's 16 GB with headroom left. */
	peakRssBytes: Reading<number>;
	/** The slowest shard's load. Read against the same wall clock the job clock
	 * is read against, so the two are the same shard's worst case. */
	slowestModelLoadMs: Reading<number>;
	/** The busiest shard's slots per decode. `1.0` everywhere says batching is
	 * off, which is one line of text and never a chart. */
	slotsPerDecode: Reading<number>;
	clocks: ClockCheck;
}

/** A run whose rows cannot be made into one run, and what stopped it.
 *
 * Never dropped silently. `state/runtime-counters.csv` is merged line by line
 * with the union driver while the dedup that writes it reads a snapshot frozen
 * at checkout, so two workflow runs that computed the same `run_id` both append
 * and the file ends up with a shard index twice. Summed naively one such run
 * reported -394 seconds against the item ledger, which is not a number any
 * machine produced.
 */
export interface RefusedRun {
	runId: string;
	date: string;
	/** Rows the ledger holds for the run. */
	rows: number;
	/** Plain words: what could not be reconciled. */
	why: string;
}

/** Every run the ledger describes, and every run it could not. */
export interface MachineCounters {
	/** Newest first, by run id. */
	runs: RunCounters[];
	/** Newest first. A page that prints a run count prints this one beside it. */
	refused: RefusedRun[];
}

/** An empty cell is an absent value, never a zero. The reader's half of
 * `RuntimeCountersRow.from_csv_row`. */
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

/** The cells every row of one run must agree on for the run to be one run. */
const RUN_SHAPE = ['date', 'shards'] as const;

/** Every counter cell. Two rows for one shard are the same scrape only if all
 * of these match; a difference means two servers, and two servers cannot be
 * added or picked between. */
const COUNTER_CELLS = [
	'scraped_at',
	'prompt_tokens_total',
	'prompt_tokens_cached_total',
	'prompt_seconds_total',
	'tokens_predicted_total',
	'tokens_predicted_seconds_total',
	'n_decode_total',
	'n_tokens_max',
	'n_busy_slots_per_decode',
	'job_seconds',
	'cpu_model',
	'cpu_busy_pct',
	'peak_rss_bytes',
	'model_load_ms'
] as const;

function fingerprint(row: Record<string, string>, cells: readonly string[]): string {
	return cells.map((cell) => row[cell] ?? '').join('\u0000');
}

/** One shard's row read into figures, with the two ceilings applied. */
function shardCounters(row: Record<string, string>, limits: MachineLimits): ShardCounters {
	const readSeconds = measured(row.prompt_seconds_total);
	const writeSeconds = measured(row.tokens_predicted_seconds_total);
	const promptTokens = measured(row.prompt_tokens_total);
	const cachedTokens = measured(row.prompt_tokens_cached_total);
	const writtenTokens = measured(row.tokens_predicted_total);
	const longestSequence = measured(row.n_tokens_max);
	const jobSeconds = measured(row.job_seconds);
	return {
		shard: measured(row.shard) ?? 0,
		scrapedAt: row.scraped_at ?? '',
		readSeconds,
		writeSeconds,
		readPct:
			readSeconds === null || writeSeconds === null
				? null
				: sharePct(readSeconds, readSeconds + writeSeconds),
		promptTokens,
		cachedTokens,
		// The denominator is every prompt token the shard needed, read or reused,
		// so the share answers "would a bigger cache have saved wall clock".
		cachedPct:
			promptTokens === null || cachedTokens === null
				? null
				: sharePct(cachedTokens, promptTokens + cachedTokens),
		writtenTokens,
		readTokensPerSecond: rate(promptTokens, readSeconds),
		writeTokensPerSecond: rate(writtenTokens, writeSeconds),
		longestSequence,
		contextUsedPct: sharePct(longestSequence, limits.contextWindow),
		jobSeconds,
		jobUsedPct: sharePct(jobSeconds, limits.jobTimeoutSeconds),
		cpuModel: text(row.cpu_model),
		cpuBusyPct: measured(row.cpu_busy_pct),
		peakRssBytes: measured(row.peak_rss_bytes),
		modelLoadMs: measured(row.model_load_ms),
		slotsPerDecode: measured(row.n_busy_slots_per_decode)
	};
}

/** A `Reading` over the shards that answered a question, and only those.
 *
 * `pick` returns null for a shard that cannot answer, so the denominator on the
 * way out is the run's shard count and the numerator is who spoke.
 */
function reading<T, V>(
	shards: ShardCounters[],
	outOf: number,
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

const sum = (values: number[]): number => values.reduce((total, value) => total + value, 0);
const highest = (values: number[]): number => Math.max(...values);
const lowest = (values: number[]): number => Math.min(...values);

/** A pooled rate over the shards that reported both of its cells.
 *
 * Sum over sum, which is the only correct composition. A shard missing either
 * cell is left out of both sums rather than contributing a zero to one of them,
 * which would report a rate the machine never ran at.
 */
function pooledRate(
	shards: ShardCounters[],
	outOf: number,
	tokensOf: (shard: ShardCounters) => number | null,
	secondsOf: (shard: ShardCounters) => number | null
): Reading<number> {
	const pairs = shards
		.map((shard) => ({ tokens: tokensOf(shard), seconds: secondsOf(shard) }))
		.filter((pair): pair is { tokens: number; seconds: number } =>
			pair.tokens !== null && pair.seconds !== null
		);
	const seconds = sum(pairs.map((pair) => pair.seconds));
	return {
		value: pairs.length === 0 || seconds <= 0 ? null : sum(pairs.map((pair) => pair.tokens)) / seconds,
		from: pairs.length,
		outOf
	};
}

/** One run's item-health rows, pooled the way `reconcile_prefill.pool_ledger` pools them.
 *
 * `input_tokens - cached_tokens` is the definition: `cached_tokens` is what the
 * runtime reused instead of reading, so leaving it in reports a rate the
 * machine never ran at. A row missing either required cell predates token
 * capture and is evidence in neither direction, so it is skipped rather than
 * counted as an item that read nothing.
 */
function poolLedger(health: Record<string, string>[], runId: string): Pooled {
	let tokens = 0;
	let milliseconds = 0;
	let parts = 0;
	for (const row of health) {
		if (row.run_id !== runId) continue;
		const prefillMs = measured(row.prefill_ms);
		const inputTokens = measured(row.input_tokens);
		if (prefillMs === null || inputTokens === null) continue;
		tokens += inputTokens - (measured(row.cached_tokens) ?? 0);
		milliseconds += prefillMs;
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

function clockCheck(shards: ShardCounters[], health: Record<string, string>[], runId: string): ClockCheck {
	const ledger = poolLedger(health, runId);
	const server = poolServer(shards);
	if (ledger.rate === null || server.rate === null) {
		return { ledger, server, gapPct: null, agrees: null };
	}
	const gapPct = (Math.abs(ledger.rate - server.rate) / server.rate) * 100;
	return { ledger, server, gapPct, agrees: gapPct <= CLOCKS_AGREE_WITHIN_PCT };
}

/** The rows of one run, as one run - or the reason they are not one run.
 *
 * Shards are a set and never a count. Two rows carrying the same shard index
 * are one scrape written twice when every counter cell matches, and two
 * different servers when any cell differs. The second case cannot be summed and
 * cannot be picked between, so the run is refused whole: a page that prints
 * half a reconcilable run is worse than one that says which run it cannot read.
 */
function oneRun(
	runId: string,
	rows: Record<string, string>[],
	health: Record<string, string>[],
	limits: MachineLimits
): RunCounters | RefusedRun {
	const date = rows[0].date ?? '';
	const refuse = (why: string): RefusedRun => ({ runId, date, rows: rows.length, why });

	const shapes = new Set(rows.map((row) => fingerprint(row, RUN_SHAPE)));
	if (shapes.size > 1) {
		return refuse('its rows disagree about the day or the shard count, so they are not one run');
	}

	const byShard = new Map<string, Record<string, string>[]>();
	for (const row of rows) {
		const key = row.shard ?? '';
		// A row that does not say which shard it is cannot be deduplicated against
		// any other row, so the set the rest of this function relies on cannot be
		// built. Reading it as shard zero would merge it into a real shard's row.
		if (measured(key) === null) return refuse('a row does not say which shard it came from');
		byShard.set(key, [...(byShard.get(key) ?? []), row]);
	}
	const kept: Record<string, string>[] = [];
	for (const [shard, sameShard] of byShard) {
		const scrapes = new Set(sameShard.map((row) => fingerprint(row, COUNTER_CELLS)));
		if (scrapes.size > 1) {
			return refuse(
				`shard ${shard} committed ${scrapes.size} different scrapes, so two servers ` +
					'answered for one shard and neither can be added to the other'
			);
		}
		kept.push(sameShard[0]);
	}

	const shards = measured(rows[0].shards);
	if (shards === null || shards < 1) return refuse('no row says how many shards the run split into');
	if (kept.length > shards) {
		return refuse(
			`${kept.length} shards committed a row for a run that says it split into ${shards}`
		);
	}
	const reported = kept
		.map((row) => shardCounters(row, limits))
		.sort((a, b) => a.shard - b.shard);
	if (reported.some((shard) => shard.shard >= shards)) {
		return refuse(`a shard index sits at or above the run's own shard count of ${shards}`);
	}

	const over = <T>(pick: (shard: ShardCounters) => number | null, fold: (values: number[]) => T) =>
		reading(reported, shards, pick, fold);
	const readSeconds = over((shard) => shard.readSeconds, sum);
	const writeSeconds = over((shard) => shard.writeSeconds, sum);
	const promptTokens = over((shard) => shard.promptTokens, sum);
	const cachedTokens = over((shard) => shard.cachedTokens, sum);
	const readRates = reported
		.map((shard) => shard.readTokensPerSecond)
		.filter((value): value is number => value !== null);

	return {
		runId,
		date,
		shards,
		reported,
		readSeconds,
		writeSeconds,
		// Both halves or neither: a share of the two clocks needs a shard to have
		// reported both of them, and pairing a summed read against a summed write
		// over two different shard sets is not a share of anything.
		readPct: reading(
			reported,
			shards,
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
		promptTokens,
		cachedTokens,
		cachedPct: reading(
			reported,
			shards,
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
			shards,
			(shard) => shard.promptTokens,
			(shard) => shard.readSeconds
		),
		writeTokensPerSecond: pooledRate(
			reported,
			shards,
			(shard) => shard.writtenTokens,
			(shard) => shard.writeSeconds
		),
		// One shard cannot spread against itself, so a run of one reports nothing
		// rather than 1.00x, which would read as "the hosts agreed".
		readSpread: {
			value: readRates.length < 2 ? null : highest(readRates) / lowest(readRates),
			from: readRates.length,
			outOf: shards
		},
		longestSequence: over((shard) => shard.longestSequence, highest),
		contextUsedPct: over((shard) => shard.contextUsedPct, highest),
		slowestJobSeconds: over((shard) => shard.jobSeconds, highest),
		jobUsedPct: over((shard) => shard.jobUsedPct, highest),
		cpuModels: reading(
			reported,
			shards,
			(shard) => shard.cpuModel,
			(models) => [...new Set(models)].sort()
		),
		lowestCpuBusyPct: over((shard) => shard.cpuBusyPct, lowest),
		peakRssBytes: over((shard) => shard.peakRssBytes, highest),
		slowestModelLoadMs: over((shard) => shard.modelLoadMs, highest),
		slotsPerDecode: over((shard) => shard.slotsPerDecode, highest),
		clocks: clockCheck(reported, health, runId)
	};
}

/** Every run the two ledgers describe, newest first.
 *
 * Pure: it takes rows and the two ceilings, so a test drives a fixture ledger
 * without touching the disk and `loadMachineCounters` is the only thing that
 * knows where the files are.
 */
export function machineCounters(
	counters: Record<string, string>[],
	health: Record<string, string>[],
	limits: MachineLimits
): MachineCounters {
	const byRun = new Map<string, Record<string, string>[]>();
	for (const row of counters) {
		const runId = row.run_id ?? '';
		if (!runId) continue;
		byRun.set(runId, [...(byRun.get(runId) ?? []), row]);
	}
	const runs: RunCounters[] = [];
	const refused: RefusedRun[] = [];
	// Run ids are `<date>-<n>`, so a plain string sort orders a day's runs
	// correctly and orders the days too - up to run ten of one day, which this
	// pipeline has never reached and which `run.max_parallel` of 4 bounds.
	for (const runId of [...byRun.keys()].sort().reverse()) {
		const result = oneRun(runId, byRun.get(runId) ?? [], health, limits);
		if ('why' in result) refused.push(result);
		else runs.push(result);
	}
	return { runs, refused };
}

/** One row per work shard per run, read from the committed ledger.
 *
 * Through `STATE_ROOT` like every other ledger read, so a test can point the
 * whole tree at a fixture and a canary build cannot reach the real one.
 */
export function runtimeCounterRows(): CsvTable {
	return readCsv(join(STATE_ROOT, 'runtime-counters.csv'));
}

/** The two ceilings, read from `config/idhazh.json` through the one config reader.
 *
 * `models.inference.n_ctx` and `run.shard_timeout_minutes` (Rule #6). Both have
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
 */
export function loadMachineCounters(): MachineCounters {
	return machineCounters(runtimeCounterRows().rows, itemHealthRows().rows, machineLimits());
}
