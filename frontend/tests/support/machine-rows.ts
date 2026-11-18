/** Fixture rows for the two ledgers the Hardware route's run count reads.
 *
 * One shard's record lives in two files that no stage derives from the other -
 * `state/host-fingerprint/` for what the model server and the job clock said,
 * `state/item-health/` for which shard took each item - and a fixture that wrote
 * only one of them would drive half the reader.
 *
 * So a spec states a shard once, here, and gets back both rows.
 *
 * Real rows in the packed files' shapes, not a stand-in for one (Guardrail #7):
 * every cell below is a column the contract declares, and the reader is given
 * exactly what a packed day would hand it.
 */

/** One shard, stated the way a person checking the page would state it. Every
 * figure may be `''`, which is the ledger's own way of saying a cell was never
 * filled. */
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
	/** The machine record's digest of the host. Empty where the probe missed it. */
	fingerprint?: string;
	/** Validated online logical processors. */
	logicalProcessors?: number | '';
	modelLoadMs?: number | '';
}

const DATE = '2026-09-02';
const RUN = '2026-09-02-1';

function cell(value: number | string | undefined): string {
	return value === undefined || value === '' ? '' : String(value);
}

/** The machine record's row for one shard. */
export function hostRow(reading: ShardReading): Record<string, string> {
	return {
		version: '2026-10-10',
		date: reading.date ?? DATE,
		run_id: reading.runId ?? RUN,
		job: reading.job ?? '',
		shard: cell(reading.shard ?? 0),
		fingerprint: cell(reading.fingerprint),
		fingerprint_version: reading.fingerprint ? '2' : '',
		cpu_model: cell(reading.cpuModel),
		cpu_logical_processors: cell(reading.logicalProcessors),
		model_load_ms: cell(reading.modelLoadMs),
		job_seconds: cell(reading.jobSeconds),
		server_prompt_tokens: cell(reading.serverPromptTokens),
		server_prompt_seconds: cell(reading.serverPromptSeconds)
	};
}

/** The item ledger's row for one shard: which shard took the item, and nothing
 * else, because that is all the run count reads off this ledger. */
export function itemRow(reading: ShardReading): Record<string, string> {
	return {
		version: '2026-09-18',
		date: reading.date ?? DATE,
		run_id: reading.runId ?? RUN,
		item_id: `item-${reading.shard ?? 0}`,
		machine_shard: cell(reading.shard ?? 0)
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
