// Generated from `backend/idhazh/contracts/machine_shard.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** One work shard of one run, as its machine and its items reported it. */
export interface MachineShardRow {
	version?: string;

	date: string;

	run_id: string;

	/** Which work shard of the run this row folds. */
	shard: number;

	/** Item rows the shard committed with both of a model call's token cells. The denominator every fold below was taken over, so a total made from three items of forty is readable as one. */
	items: number;

	/** Prompt tokens the item ledger says this shard read: `input_tokens` minus `cached_tokens`, added over its items. Cached tokens are excluded because the server counts them that way, and counting them as read is the defect this pairing caught in August. */
	read_tokens?: number | null;

	/** Milliseconds the item ledger charged to prefill, added over the shard's items. The denominator of the ledger's own read rate. */
	read_ms?: number | null;

	/** Prompt tokens the shard reused from the cache instead of reading. Read beside `read_tokens`: the two together are every prompt token the shard needed. */
	cached_tokens?: number | null;

	/** Tokens the shard's model calls wrote, added over its items. */
	written_tokens?: number | null;

	/** Milliseconds the item ledger charged to decode, added over the items. */
	write_ms?: number | null;

	/** The longest prompt-plus-answer any one item reached. A maximum and never a sum - it is read against the configured context window, and a sum of sequences is a length no model call ever saw. */
	longest_sequence?: number | null;

	/** The context window the shard's server was started with. Carried so `longest_sequence` is readable without a config file from the same day. */
	n_ctx_configured?: number | null;

	/** The processor the host drew, in its own words, from the machine record at this key. Null where the record did not reach the shard. */
	cpu_model?: string | null;

	/** The lowest share of processor time any of the shard's items spent busy. The item ledger's `Watch` over the model window, not a whole-job figure: a low reading says that item waited rather than computed. */
	cpu_busy_pct?: number | null;

	/** The model server's memory high-water mark over the shard's items. */
	llama_rss_peak_bytes?: number | null;

	/** The pipeline process's own high-water mark. */
	python_rss_bytes?: number | null;

	/** What the container accounted to the shard, at its highest. */
	cgroup_peak_bytes?: number | null;

	/** What the shard paid opening the weights before its first item, from the machine record. Once a job, which is this row's grain. */
	model_load_ms?: number | null;

	/** The shard job's own wall clock, from the machine record. */
	job_seconds?: number | null;

	/** Prompt tokens the model server itself counted reading, cached ones excluded. The second instrument: `read_tokens` is arithmetic over the item ledger, and arithmetic over a ledger cannot check that ledger. */
	server_prompt_tokens?: number | null;

	/** Seconds the model server itself counted reading prompts. Pairs with the column above - a rate is a ratio, and the 80 percent error this pairing caught was in the numerator. */
	server_prompt_seconds?: number | null;
}
