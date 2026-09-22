// Generated from `backend/idhazh/contracts/qualification.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * One planted attack, run live against the candidate.
 *
 * The unit suite proves the sanitizer and the schema against recorded
 * completions. It cannot prove that a model nobody has served before follows
 * this chat template, so the canaries run again here on live calls (Guardrail #11).
 *
 * `replied` is false for two very different reasons - the attack was never put
 * to the model, or the model answered with nothing publishable - and neither
 * is a marker that survived. The run on 2026-08-26 failed here with every
 * marker list empty, and it was written up as a sanitizer breach, so the
 * reason travels with the observation now rather than living in a log line
 * the next reader no longer has.
 */
export interface CanaryObservation {
	name: string;

	/** A schema-valid, non-blank reply came back. */
	replied: boolean;

	/** Why no reply came back. Null when the candidate replied. */
	failure_code?: string | null;

	/** The summarizer's own words about that failure. */
	failure_detail?: string | null;

	/** `must_not_survive` strings that reached the reply. */
	markers_present?: string[];

	/** `must_survive` facts the boundary ate. */
	facts_missing?: string[];

	/** `forbidden_output` keys the raw reply carried. */
	forbidden_keys_present?: string[];
}

/** Which bytes ran. A model-card name identifies nothing. */
export interface CandidateIdentity {
	model_id: string;

	repo: string;

	/** An immutable repository revision, not a branch. */
	revision: string;

	file: string;

	quantisation: string;

	/** What the adoption target declares. */
	sha256_expected: string;

	/** What the runtime actually opened. */
	sha256_observed: string;

	bytes_expected: number;

	bytes_observed: number;

	runtime_build: string;
}

/** One frozen article: what it is, and the hashes that prove it did not move. */
export interface CorpusItem {
	item_id: string;

	url_key: string;

	canonical_url: string;

	source_id: string;

	vertical: string;

	/** Which `summarize.bands` tier the extracted length fell in. */
	band_index: number;

	brief: boolean;

	/** The extracted text passed `extract.truncation_cap_tokens` and was cut. */
	truncated: boolean;

	source_word_count: number;

	seen_word_count: number;

	seen_token_count: number;

	/** The exact bytes the model was shown. */
	seen_text_sha256: string;

	/** The sanitized article the scorer read. Extract does not keep the pre-cap text, so on a truncated item this equals seen_text_sha256 and says so. */
	full_text_sha256: string;
}

/**
 * One corpus item at one repeat, as the run's own call path produced it.
 *
 * Every attempt is recorded, including the ones that failed. A failure that
 * vanishes from the record takes the denominator with it, and the success rate
 * then describes the survivors rather than the run.
 *
 * **A row is one item and not one call, and `QualificationShard.calls_per_item`
 * is what says how many calls are behind it.** On the path that makes two,
 * every column here is the item's answer over the pair: a budget either call
 * hit cuts the item, a reasoning channel either call opened is a channel the
 * item used, and the token counts are the pair's sum. Reading a two-call row
 * as a single call halves the cost and reports a decode as clean when the
 * first of its two was truncated.
 */
export interface ItemObservation {
	item_id: string;

	repeat: number;

	ok: boolean;

	failure_code?: string | null;

	/** How the decode ended. Over a pair, `length` where either call met its budget, because an item cut anywhere is a cut item. Null where the server named no reason at all, which the gate reads as not-clean for the same arithmetic that reads `length` that way - it is not `stop`. */
	finish_reason?: string | null;

	/** The runtime split a reasoning channel off the content, in any call. */
	reasoning_channel_used: boolean;

	/** Words inside inline `<think>` blocks, summed. Any is a leak. */
	think_block_words: number;

	schema_valid: boolean;

	/** A second attempt was needed. The gate allows none. */
	repaired: boolean;

	output_digest: string;

	summary_word_count: number;

	/** The complete rendered request, as counted by the runtime. */
	prompt_tokens: number;

	completion_tokens: number;

	/** Milliseconds the runtime spent reading the prompt, summed over the item's calls. Null where the runtime reported no timings. Kept apart from decode because one scales with the article and the other with the summary, so a single rate over both describes neither. */
	prefill_ms?: number | null;

	/** Milliseconds spent writing the reply, summed over the item's calls. */
	decode_ms?: number | null;

	/** What `summarize.fits_context` said before the call. */
	fits_context_predicted: boolean;

	/** The item's whole wall clock, the seam between its calls included. It is wider than prefill plus decode and is not their sum. */
	summarize_seconds: number;
}

/**
 * What the scorer and the counterweights read on one item.
 *
 * Scored once per item, on the first repeat. Two more repeats of identical
 * words would add three identical rows and no information.
 */
export interface ItemScore {
	item_id: string;

	brief: boolean;

	hhem: number;

	hhem_full: number;

	verbatim_run: number;

	extractiveness: number;

	compression: number;

	lead_coverage: number;

	unsupported_numbers: number;

	hedge_dropped: boolean;

	evidential_density: number;

	speculative_density: number;

	/** The drafted title missed its range and was dropped. */
	title_fell_back: boolean;
}

/**
 * Every input that can move an output, and nothing that cannot.
 *
 * This is the recorded input manifest. It hangs off `RunRecord.inputs`, it is
 * read by a person and by the one alarm that compares two runs, and nothing
 * anywhere decides anything on it.
 *
 * Delete it and exactly one thing changes on the whole site: a rule disappears
 * from two console charts. Not one figure moves and not one row vanishes. A
 * gate fails that test by construction; a record passes it.
 *
 * `host_cpu` is deliberately absent: it is the one field that explains a
 * determinism violation, and a run's own processor is luck rather than a
 * choice anybody made.
 */
export interface PipelineInputs {
	model_sha256: string;

	quantisation: string;

	/** The llama.cpp build the weights were decoded by. */
	runtime_build: string;

	chat_template_sha256: string;

	prompt_sha256: string;

	/** The turn envelope the prompts were rendered through - every marker string, the system placement and its joiner, digested as one. prompt_sha256 already moves when a marker moves, and stops short of two envelope facts that move an output without moving a rendered prompt: which of the two reply openings a call ends on, and the marker the thinking span stops at. Absent means a run written before 2026-09-14, when the markers first became able to move at all. It is never a default value: a substituted digest would say the envelope was recorded and unchanged, which is the one thing an absent key must not be read as. */
	turn_markers_sha256?: string | null;

	/** The constrained-decoding schema. Its shape is the only guard on the output. */
	output_schema_sha256: string;

	truncation_cap_tokens: number;

	/** The decoding parameters, one key each, under the name the request body spells them with. A mapping rather than one joined string so the console compares key by key: a rename moves no key's value, and a setting that stopped being sent is a key that is absent rather than a record that differs everywhere. */
	sampling: Record<string, string>;

	/** The runtime switches that can move the arithmetic, one key each, spelled as llama-server spells them. A bare flag records `set`; a flag the model file leaves out records `runtime-default`, because what the server picks is a real and different choice from pinning a value. */
	runtime_flags: Record<string, string>;

	n_ctx: number;

	n_batch: number;

	n_ubatch: number;

	n_threads: number;

	runner_class: string;

	extractor_version: string;

	sanitizer_version: string;
}

/**
 * Which instrument read the summaries.
 *
 * `pinned` is false when the revision is a branch name. The faithfulness gate
 * refuses to run on an unpinned scorer: a floor measured with an instrument
 * that can move overnight measures an unknown instrument.
 */
export interface ScorerIdentity {
	scorer_id: string;

	revision: string;

	pinned: boolean;

	/** Digest of the weights that loaded, never of the name they were asked for. */
	weights_sha256: string;

	scorer_version: string;
}

/**
 * What one capture-and-replay job uploads.
 *
 * The corpus is hashed and written before the first inference call, so the
 * pre-registration is an ordering the code enforces rather than a promise in a
 * document.
 */
export interface QualificationShard {
	version?: string;

	date: string;

	commit_sha: string;

	runner: string;

	shard: number;

	shards: number;

	repeats: number;

	/** Inference calls behind one observation. 1 is the qualification's own single call; 2 is the path the digest runs, which labels the article and then summarizes it. Recorded because it decides what every per-item number in this shard means, and two shards that disagree on it are not comparable. */
	calls_per_item?: number;

	candidate: CandidateIdentity;

	scorer: ScorerIdentity;

	/** What the controls ran under, named field by field. One value across every shard, and it is what proves two candidates were measured on one pipeline. Recorded and never compared to decide anything. */
	inputs?: PipelineInputs | null;

	/** When the hashes were written. Before any output was viewed. */
	corpus_registered_at: string;

	/** Addresses this shard was handed. */
	planned: number;

	corpus?: CorpusItem[];

	observations?: ItemObservation[];

	scores?: ItemScore[];

	canaries?: CanaryObservation[];

	/** Wall-clock this shard spent inside the stage. */
	elapsed_seconds: number;
}
