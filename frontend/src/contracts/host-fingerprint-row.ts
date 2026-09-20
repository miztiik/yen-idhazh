// Generated from `backend/idhazh/contracts/host_fingerprint.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * Which workflow job produced a row.
 *
 * Ours to name, so it is a closed set. Every other identifier on a host row is
 * a string the machine chose and cannot be one - see
 * `docs/reference/host-metrics.md`. Refusing anything else is what stops a typo
 * becoming a job nobody can group by.
 *
 * Every value is a job's own id in its workflow file, lowercase, so a reader
 * goes from a row to the steps that wrote it with no lookup table in between.
 * A display name would drift from the thing it identifies.
 *
 * It sits here, at the bottom of the contract graph, because three ledgers and
 * a filename grammar all name a job and none of them owns the vocabulary.
 *
 * **`visuals` is here for the rows and not for a job.** `digest.yml` ran one
 * until 2026-09-13, when the small model, its job and its flag were retired
 * together. Six committed counters rows still carry the value, and a member
 * with no producer left is the only thing that can read them back.
 *
 * **`decide` is here for a filename and not for a column.** `validate.yml`'s
 * gate job writes the validation ledger's segment, and the segment grammar
 * names its writer from this set - so the job belongs here. No row of the three
 * ledgers that carry a `job` column can hold it: that job stands no server up,
 * records no machine and reads no item. Their generated schemas list it because
 * one enum answers "which workflow job" for the whole repository, which is why
 * none of the three is version-stamped for it - a stamp says a shape moved, and
 * theirs did not.
 */
export const SERVER_JOB = ['plan', 'work', 'assemble', 'visuals', 'runtime', 'decide'] as const;

export type ServerJob = (typeof SERVER_JOB)[number];

/** One job, one machine, one row: what the host said it was. */
export interface HostFingerprintRow {
	version?: string;

	date: string;

	run_id: string;

	/** The workflow job that drew this machine. Every job that draws its own runner writes one row, because a run is only as fast as its slowest job. */
	job?: ServerJob;

	/** The shard within that job. A single-shard job writes 0. */
	shard: number;

	/** A digest over the columns that cannot change inside a job - vendor, family, model, stepping, core counts, cache and flags. Two jobs on the same kind of machine carry the same value, which is what makes a distribution countable without matching model-name strings by hand. Absent on the half a job writes at its end, which carries the clock and repeats nothing the probe already recorded. */
	fingerprint?: string | null;

	/** The `model name` line, in the host's own words. */
	cpu_model?: string | null;

	/** `vendor_id`: GenuineIntel, AuthenticAMD. */
	cpu_vendor?: string | null;

	/** `cpu family`. With model and stepping this names the part. */
	cpu_family?: number | null;

	/** `model`, the number rather than the marketing name. */
	cpu_model_number?: number | null;

	/** `stepping`. */
	cpu_stepping?: number | null;

	/** `microcode` revision, which moves under a fixed stepping. */
	microcode?: string | null;

	/** Physical cores the job can see. */
	cores?: number | null;

	/** Logical processors. Four on every stock runner so far. */
	threads?: number | null;

	/** L3 as the host reports it. Read beside `memcpy_probe_mib`: a probe buffer smaller than this measured cache rather than memory. */
	l3_cache_bytes?: number | null;

	/** `CPU max MHz`, where the host publishes one. */
	mhz_max?: number | null;

	/** The mean `cpu MHz` across processors at the moment of the probe. Not a reading under load - the probe runs before the model server starts - so it says what the machine idles at, never what it sustains. */
	mhz_at_probe?: number | null;

	/** The watched instruction-set flags this host reported, sorted and space joined. Empty means none of them, which is itself a reading. */
	flags?: string;

	/** How long the machine had been up when the job reached this probe. A small number is a freshly started virtual machine; a large one is a pooled machine this job was handed. */
	boot_seconds?: number | null;

	/** Large-block copy bandwidth, bytes read plus bytes written, the way STREAM counts a copy. Decode is bandwidth bound and nothing else here measures bandwidth. Absent where the probe was switched off. */
	memcpy_gib_s?: number | null;

	/** The buffer each side of the copy used. Below `l3_cache_bytes` the figure is a cache reading. */
	memcpy_probe_mib?: number | null;

	/** The platform's own name for this machine size, from the host metadata service. This is the placement decision in the platform's vocabulary rather than ours. Absent where the service did not answer. */
	vm_size?: string | null;

	/** The region the metadata service named. */
	vm_location?: string | null;

	/** The availability zone, where the platform publishes one. */
	vm_zone?: string | null;

	/** The fault domain, which separates one rack from another. */
	vm_fault_domain?: string | null;

	/** The runner label the platform gave this job. */
	runner_name?: string | null;

	/** When the probe read this machine. Absent on the half a job writes at its end, which measured no machine. */
	measured_at?: string | null;

	/** Milliseconds the server spent opening the weights before the first item. Once per job, which is this row's grain. */
	model_load_ms?: number | null;

	/** The job's own wall clock. The truncation cap reverts on the slowest work job's, and before this cell the only place that number lived was the GitHub jobs API, which drops a job record when the run ages out. */
	job_seconds?: number | null;

	/** Prompt tokens llama-server itself counted reading, cached tokens excluded. The second instrument. The item ledger's own answer is `sum(input_tokens) - sum(cached_tokens)`; a gap over 5 percent means one of the two is wrong, and arithmetic over that ledger could never say so. */
	server_prompt_tokens?: number | null;

	/** Seconds llama-server itself counted reading prompts. Pairs with the cell above - a rate is a ratio, and the 80 percent defect this check caught in August 2026 was in the numerator, so one cell alone could not see it. */
	server_prompt_seconds?: number | null;
}
