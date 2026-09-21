// Generated from `backend/idhazh/contracts/knobs/models.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** Decoding is pinned here so a change of output is a reviewable diff. */
export interface InferenceConfig {
	/** The window one sequence gets. The default stays 8192 because it is the conservative window for weights nobody has put in front of a runner; each model file sets its own window. Whether its KV cache fits is decided by what the machine has free, not by the process's resident memory alone - docs/reference/pipeline-cost.md. */
	n_ctx?: number;

	n_threads?: number;

	n_batch?: number;

	n_ubatch?: number;

	/** llama-server -np. None omits the flag and keeps the runtime default. */
	n_parallel?: number | null;

	/** llama-server -tb. None omits the flag and lets it follow n_threads. */
	n_threads_batch?: number | null;

	/** llama-server --cpu-range, inclusive lo-hi. None omits the flag. */
	cpu_range?: string | null;

	/** llama-server --cpu-strict, 0 or 1. None omits the flag. */
	cpu_strict?: number | null;

	/** If false, emit --no-warmup. True lets llama-server warm at startup. */
	startup_warmup?: boolean;

	/** If true, emit --metrics and llama-server serves its counters on /metrics. On by default: without them a run cannot say how close it came to n_ctx, and a concurrency result has no busy-slot number to read it by. */
	metrics?: boolean;

	/** llama-server -fa. None omits the flag and leaves the runtime on auto. */
	flash_attention?: 'on' | 'off' | null;

	/** llama-server -lm. None omits the flag and keeps the runtime default. */
	load_mode?: 'mmap+mlock' | null;

	/** llama-server -ctk. None omits the flag and keeps full-precision KV. */
	cache_type_k?: 'q8_0' | null;

	/** llama-server -ctv. None omits the flag and keeps full-precision KV. */
	cache_type_v?: 'q8_0' | null;

	/** llama-server --prio. None omits the flag and keeps normal priority. */
	priority?: number | null;

	/** llama-server --poll. None omits the flag and keeps the runtime default. */
	poll?: number | null;

	/** llama-server -cms, in tokens; 0 means no minimum. None omits the flag. */
	checkpoint_min_step?: number | null;

	/** llama-server -ctxcp, maximum checkpoints per slot. None omits the flag. */
	ctx_checkpoints?: number | null;

	/** llama-server -cram, in MiB; -1 is unlimited and 0 disables the cache. None omits the flag. */
	cache_ram?: number | null;

	/** llama-server --cache-prompt or --no-cache-prompt. None omits the flag and preserves the completion requests' existing enabled cache. */
	cache_prompt?: boolean | null;

	/** llama-server -sps, shared-prefix fraction. None omits the flag. */
	slot_prompt_similarity?: number | null;

	/** llama-server --jinja or --no-jinja. None omits the flag. */
	jinja?: boolean | null;

	/** llama-server --reasoning-preserve or --no-reasoning-preserve. None omits the flag. */
	reasoning_preserve?: boolean | null;

	/** llama-server -lv. None omits the flag and keeps the runtime default of 3, which prints twelve lines and none of them names flash attention, the KV buffer or the compute buffer. At 4 the whole model-loader block comes back, which is what lets a check read the attention state off the server's own line instead of off the flag we passed it. Measured 2026-09-09 on a 12th Gen Intel Core i7-1265U against llama.cpp b10444, three runs a case and zero spread: one server start goes from 12 lines and 1,085 bytes to about 206 lines and 16,011 bytes. That is a job artifact kept for two days, never a committed file. It changes what the server says about itself and nothing about what it decodes, so idhazh.fingerprint leaves it out of the stamp. */
	log_verbosity?: number | null;

	/** How far the sampler may stray from the likeliest token. The default is 0.0 for the reason n_ctx's default is conservative: a temperature is a reading of one model's weights, and a number that suited one family applied to weights nobody has run is a setting somebody will trust. Every committed entry pins its own. Above 0.0 the seed stops being dead code and becomes the control that decides which token is drawn - docs/architecture/contracts/determinism.md. */
	temperature?: number;

	/** The share of probability mass the sampler may draw from. 1.0 is the whole distribution, which is not a second temperature and does not contradict one: temperature reshapes the distribution and this truncates its tail, so 1.0 leaves the truncation off and lets temperature alone decide. Lowering both is two instruments aimed at one effect, and then neither reading says which of them moved the words. */
	top_p?: number;

	/** Which sample the sampler draws. It is the whole of the repeatability story above temperature 0: same inputs and same seed is the same reply, same inputs and a different seed is a different one. At temperature 0 it is dead code and nothing reads it, which is what it was until 2026-09-17. It is enumerated in the fingerprint either way, so a change of sampler cannot move the words without moving the stamp. */
	seed?: number;

	/** The thinking span's budget. Null means no cap: the span runs until the model writes turns.thinking_close, and the window is the only other thing that stops it. An integer bounds the span at that many tokens. A cap exists at all because a model that never closes its reasoning block would otherwise decode to n_ctx and be recorded as a truncated summary, which names the wrong cause - the closing marker is what normally ends the span, and the cap is what catches a model that never writes one. Set it only from a reading taken on the weights it is set for; a number carried over from other weights caps a thought mid-sentence, and a truncated thought is worse than no thought at the same budget (arxiv 2504.09858). It is read only where the entry declares turns.thinking_close; an entry that declares no closing marker spends none of it. */
	max_think_tokens?: number | null;

	/** The answer span's budget. A crash guard, not a length target: the prompt sets the length and this only stops a runaway decode from burning a shard's whole timeout. Sized at 250 the reply ran out of budget mid-object and failed as a shape error, which named the wrong cause - so it is set well above any summary we want. It was max_output_tokens until 2026-09-14, when one budget stopped being able to say which of two spans overran. */
	max_answer_tokens?: number;

	/** One summarizer POST may wait this long. Sized from the measured worst 8B long article plus one cold prompt prefix, doubled; the shard timeout remains the outer bound. */
	request_timeout_minutes?: number;

	/** The weights this block is set for - the sha256 of the entry that carries it. Every number here is a measurement about one model on one runner, never a property of the pipeline, so the entry states which bytes the numbers were put in front of. Swap the weights and this is left behind, which is the one event the field exists to make loud. It says a person paired these numbers with these bytes; where the numbers came from is docs/concepts/config.md, because a runner and a date cannot be checked by a validator and a field nothing checks is a comment. */
	declared_for?: string | null;
}

/**
 * Which weights, and everything a run needs to talk to them.
 *
 * **This is the shape a person declares**, and `ModelsConfig` is made of it.
 * It is `ModelRef` plus the turn envelope, which is required here and absent
 * from the recorded shape - so a config entry that forgets its markers fails
 * at load, and a `run.json` written before the markers were declared still
 * reads. A swap that moved the markers is still visible in a run record:
 * `RunRecord.inputs.prompt_sha256` digests both turns rendered through them.
 *
 * Do not move `turns` down onto `ModelRef` as a tidy-up. That is the change
 * this split exists to prevent. `arch` is here for the same reason and not
 * for a different one.
 */
export interface ModelEntry {
	id: string;

	/** Hugging Face repository the GGUF is pulled from. */
	repo: string;

	/** The hub commit the weights are fetched at. A download that names a branch gets whatever was uploaded last, so the bytes can change under a config that still records the old sha256. */
	revision?: string | null;

	file: string;

	quantisation: string;

	/** Recorded once measured. A weight that changes silently changes every output. */
	sha256?: string | null;

	/** How many bytes those weights are, as the hub reports them. Optional: an entry nobody has fetched yet declares none, and the run then records the size it opened on both sides rather than comparing a number to itself. It sits beside sha256 because it is the same kind of fact and has the same source, and because a qualification that had to be told it on the command line was a fact about these weights living somewhere other than the file that names them. */
	byte_count?: number | null;

	/** The safetensors repository a fine-tune trains against, when this entry names a GGUF conversion of somebody else's weights. It sits here rather than in `finetune` because the two strings describe the same model: held apart, a model swap moves one and leaves the other, and a LoRA adapter loads onto a mismatched base without raising. Optional - only an entry we intend to fine-tune needs it. */
	hf_base_repo?: string | null;

	/** The runtime this entry's weights are served on. It sits on the entry for the same reason `hf_base_repo` does: held apart, a model swap moves the weights and leaves the numbers, and llama-server starts on them without raising. `ModelsConfig` refuses a block whose declared_for is not this entry's sha256, so a default block under measured weights is refused rather than inherited. */
	inference?: InferenceConfig;

	/** The architecture name inside the GGUF - its `general.architecture` key, which reads `qwen35` for the weights this entry names. Required and with no default, for the reason `turns` is: an entry that inherits the incumbent's architecture claims something nobody checked. `idhazh.llm.server.prove_the_entry` reads the key back out of the file the server was pointed at and refuses the run before the first item when the two disagree, which is what makes this a fact rather than a claim. It catches a repackaged GGUF under a familiar name - the one case where the digest, the alias and the filename all agree and only the words get worse. */
	arch: string;

	/** The turn envelope these weights are rendered with. Required and with no default: an entry that forgets its markers must fail rather than inherit the incumbent's, because inheriting them renders a prompt the grammar still accepts and nothing else can see is wrong. */
	turns: TurnsConfig;
}

/**
 * Where this model's template takes the system text. Two, and no third.
 *
 * A turn topology, so it is an enum rather than a free-form string: what
 * "folded into the first user turn" MEANS is a code path, and expressing it as
 * data would need a template language in config - a second renderer nobody
 * tests (docs/architecture/summarize/model-boundary.md).
 */
export const SYSTEM_PLACEMENT = ['own_turn', 'fold_into_first_user'] as const;

export type SystemPlacement = (typeof SYSTEM_PLACEMENT)[number];

/**
 * How one turn is written for the weights this entry names.
 *
 * It is the envelope, never the content. These strings decide where a turn
 * opens and closes, where the system text goes and how a reply begins; what
 * the turns SAY is `backend/idhazh/prompts/*.txt` and is the same set for
 * every model (docs/architecture/summarize/model-boundary.md).
 *
 * They belong beside the entry that names the weights, not in this project's
 * prompt directory: a marker is a fact about somebody else's weights, and
 * holding it apart from the entry lets a model swap move one and leave the
 * other. Nothing raises when that happens - a wrong
 * marker renders a prompt with no turn structure that the decoder's grammar
 * still accepts - worse summaries and no error anywhere.
 *
 * **The trailing newlines are load-bearing and invisible.** They survive here
 * because JSON spells them `\n` rather than leaving them at the end of a line
 * for an editor or a line-ending pass to rewrite.
 */
export interface TurnsConfig {
	/** Opens a turn, with the role substituted in. A string.Template placeholder, so `$role` or `${role}`; the substitution is strict, so a placeholder by any other name raises at the first render. */
	turn_opening: string;

	/** Closes a turn. The second call's prompt is the first one's spliced on this marker, so an empty seam would join two turns into one and break the prefix the two-call design rests on. */
	turn_closing: string;

	/** Where the model starts writing, with reasoning off. Not derived from turn_opening: a chat template ends a generation prompt with more than a role header, and what it ends with belongs to the model. */
	reply_opening: string;

	/** The same, with reasoning on. Recorded from the server that applies it. */
	reply_opening_thinking: string;

	/** What this model writes to close its reasoning block, and the whole of the declaration that reasoning is wanted. Not null means a call is decoded as two spans - one unconstrained span that stops here, then the schema-constrained answer on the same slot - and the prompt ends on reply_opening_thinking rather than reply_opening. Null means one schema-constrained span and no reasoning, which is where the incumbent sits. It replaced inference.thinking on 2026-09-14: a flag beside a marker is two places to disagree, and the flag alone could not have worked - the output schema binds the decode from the first token, so a think opener is not a legal token on either transport. */
	thinking_close?: string | null;

	/** Where this model's template takes the system text - its own turn, or folded into the first user turn. It is read by idhazh.llm.server.render_prompt, which never reads a model id: without this field a model with no system role could not be configured at all, only coded for. It has a default where the markers beside it have none, because the default is the topology of every template that HAS a system role rather than the incumbent's own string, and because case 1 of idhazh.llm.server.prove_the_entry refuses a run whose render disagrees with the server's own render of the same turns - so a placement declared wrong is caught before the first item rather than inherited in silence. */
	system_role?: SystemPlacement;

	/** What sits between the system text and the article when the two share a turn. Required under fold_into_first_user and refused under own_turn: a field that is read on one case and ignored on the other is a field somebody will set and trust. It may not be empty, because folding with no separator runs the last instruction into the opening fence of the untrusted block on one line, and the grammar still accepts the reply. */
	system_joiner?: string | null;

	/** The template variable that turns this model's reasoning on and off, sent as the one key of chat_template_kwargs. It is a name belonging to somebody else's Jinja template, so it is a model fact and not a project constant - it was spelled in this project's source and sent to every model until 2026-09-14. Null means this template reads no keywords at all, and then the request carries no chat_template_kwargs and thinking_close must be null too; this block refuses the pair. */
	thinking_kwarg?: string | null;

	/** The weights these markers are recorded from - the sha256 of the entry that carries them. It sits here for the reason inference.declared_for sits beside the numbers: swap the weights and the block is left behind, and this is the one event the field exists to make loud. Absent means an entry nobody has measured yet, which is legal; ModelsConfig refuses a block whose digest is not the entry's. */
	declared_for?: string | null;
}

/**
 * `config/models/<name>.json` - one whole model, in one file of its own.
 *
 * One entry per role, and each entry carries the settings it runs on. There is
 * no block shared between the entries. A role is a model family served by its
 * own llama-server process, and one block over two roles is a measurement
 * about one of them quietly applied to the other.
 *
 * One role is left. The small visual planner is retired: the two calls the
 * work stage now makes per item run on these weights, so the picture is
 * decided by the same model that wrote the summary.
 *
 * It is a file rather than a block of `config/idhazh.json` because everything
 * in it is a fact about one set of weights - the repository, the digest, the
 * window they were measured in, the markers their server renders. Held in the
 * shared file, a swap is an edit across every one of those lines and a revert
 * is the same edit backwards, with the previous model's numbers gone. Held
 * here, the incumbent and the candidate are two committed files and the swap
 * is `models_file` in `config/idhazh.json`.
 */
export interface ModelsConfig {
	version?: string;

	summarize: ModelEntry;

	judge?: ModelEntry | null;
}
