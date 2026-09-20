/** Fixture rows for the two ledgers the machine route reads.
 *
 * One shard's figures used to live in one row of one file, so a spec wrote one
 * object. They now live in two files that no stage derives from the other -
 * `state/host-fingerprint/` for what the model server and the job clock said,
 * `state/item-health/` for what the items cost - and a fixture that wrote only
 * one of them would drive half the reader.
 *
 * So a spec states a shard's figures once, here, and gets back both rows. The
 * numbers a spec asks for are the numbers the reader must produce: this builder
 * inverts the folds rather than restating them, so it cannot quietly agree with
 * a broken fold. `longestSequence` minus `writtenTokens` is the item's prompt,
 * and the read tokens the item ledger reports are that prompt minus the cache.
 *
 * Real rows in real files' shapes, not a stand-in for one (Guardrail #7): every
 * cell below is a column the contract declares, and the reader is given exactly
 * what a committed day would hand it.
 */

/** One shard's figures, stated the way a person checking the page would state
 * them. Every field may be `''`, which is the ledger's own way of saying a cell
 * was never filled - and which the reader must not read as zero. */
export interface ShardReading {
	date?: string;
	runId?: string;
	shard?: number;
	/** `host-fingerprint.job`. Empty is the work job, which is what is read. */
	job?: string;
	/** What the model server itself counted reading prompts. */
	serverPromptTokens?: number | '';
	serverPromptSeconds?: number | '';
	jobSeconds?: number | '';
	cpuModel?: string;
	/** Cores the host let the job see. What a load reading is read against. */
	cores?: number | '';
	modelLoadMs?: number | '';
	/** Prompt tokens the item reused instead of reading. */
	cachedTokens?: number | '';
	/** Tokens the item's model call wrote. */
	writtenTokens?: number | '';
	/** Seconds the item ledger charged to decode. */
	writeSeconds?: number | '';
	/** Prompt plus answer, which is what the context ceiling is a share of. */
	longestSequence?: number | '';
	cpuBusyPct?: number | '';
	/** The busiest the processor got over the item's model window. */
	cpuBusyMax?: number | '';
	/** The one-minute load when the item ended. A queue once it passes `cores`. */
	load?: number | '';
	/** Swap left when the item ended, and swap the host has. */
	swapFree?: number | '';
	swapTotal?: number | '';
	peakRssBytes?: number | '';
	/** Seconds the item ledger charged to read. The other clock. */
	ledgerReadSeconds?: number | '';
	/** The processor the item ledger recorded, where the machine record missed
	 * the shard. Left empty unless a spec is checking that fallback. */
	itemCpuModel?: string;
}

const DATE = '2026-09-02';
const RUN = '2026-09-02-1';

function cell(value: number | string | undefined): string {
	return value === undefined || value === '' ? '' : String(value);
}

/** The machine record's row for one shard. */
export function hostRow(reading: ShardReading): Record<string, string> {
	return {
		version: '2026-09-18',
		date: reading.date ?? DATE,
		run_id: reading.runId ?? RUN,
		job: reading.job ?? '',
		shard: cell(reading.shard ?? 0),
		cpu_model: cell(reading.cpuModel),
		cores: cell(reading.cores),
		model_load_ms: cell(reading.modelLoadMs),
		job_seconds: cell(reading.jobSeconds),
		server_prompt_tokens: cell(reading.serverPromptTokens),
		server_prompt_seconds: cell(reading.serverPromptSeconds)
	};
}

/** The item ledger's row for one shard.
 *
 * One row a shard, because every figure the reader folds off this ledger is a
 * sum, a maximum or a minimum - and one row states each of them exactly. A spec
 * that needs the fold itself checked passes several readings for one shard.
 */
export function itemRow(reading: ShardReading): Record<string, string> {
	const written = reading.writtenTokens;
	const longest = reading.longestSequence;
	const prompt =
		typeof longest === 'number' && typeof written === 'number' ? longest - written : '';
	return {
		version: '2026-09-18',
		date: reading.date ?? DATE,
		run_id: reading.runId ?? RUN,
		item_id: `item-${reading.shard ?? 0}`,
		shard: cell(reading.shard ?? 0),
		input_tokens: cell(prompt),
		cached_tokens: cell(reading.cachedTokens),
		output_tokens: cell(written),
		prefill_ms:
			typeof reading.ledgerReadSeconds === 'number' ? String(reading.ledgerReadSeconds * 1000) : '',
		decode_ms: typeof reading.writeSeconds === 'number' ? String(reading.writeSeconds * 1000) : '',
		cpu_busy_pct: cell(reading.cpuBusyPct),
		cpu_busy_max: cell(reading.cpuBusyMax),
		load_1m: cell(reading.load),
		os_swap_free_bytes: cell(reading.swapFree),
		os_swap_total_bytes: cell(reading.swapTotal),
		llama_rss_peak_bytes: cell(reading.peakRssBytes),
		cpu_model: cell(reading.itemCpuModel)
	};
}

/** Both ledgers' rows for a run of shards, in the shape the reader takes them. */
export function ledgers(readings: ShardReading[]): {
	hosts: Record<string, string>[];
	health: Record<string, string>[];
} {
	return { hosts: readings.map(hostRow), health: readings.map(itemRow) };
}

/** The planned shard count a run's manifest recorded, by run id. */
export function plan(...runs: [string, number][]): Map<string, number> {
	return new Map(runs);
}
