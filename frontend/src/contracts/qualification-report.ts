// Generated from `backend/idhazh/contracts/qualification.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

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

/**
 * A number recorded and never blocked on.
 *
 * Every one carries its denominator. A rate over four items is not a rate, and
 * a diagnostic that hides its denominator is how an unmeasured number gets
 * cited later as if it were evidence (Guardrail #10).
 *
 * **And every one carries its unit**, because `0.0412` answers nothing on its
 * own: the reader cannot tell a share from a count from a rate per second, and
 * a number nobody can act on is the failure this project keeps finding.
 * `name` is deliberately a string rather than a closed set - `stratification`
 * mints a row per configured band, so the vocabulary is only knowable once the
 * config is read.
 */
export interface Diagnostic {
	name: string;

	value: string;

	/** What the value is counted in - articles, a share, tokens a second. */
	unit: string;

	/** How many observations produced the value. */
	denominator: number;
}

/**
 * The ten gates that block adoption. Closed set, never free text.
 *
 * Every run asks every one of them. A report that omits one is refused by
 * name, because a gate nobody asked is a gate nobody can be shown to have
 * passed.
 */
export const GATE_NAME = ['reasoning_leakage', 'schema_validity', 'injection_canaries', 'publishable_length', 'context_fit', 'identity', 'budget', 'scored_denominator', 'faithfulness_floor', 'brief_copying_ceiling'] as const;

export type GateName = (typeof GATE_NAME)[number];

/**
 * One gate, and the arithmetic that decided it.
 *
 * `measured` and `threshold` are spelled rather than typed as floats because
 * the gates do not share a unit - one counts calls, one counts minutes, one is
 * a mean between zero and one - and a column that means a different thing on
 * every row is a column nobody can read.
 */
export interface GateOutcome {
	gate: GateName;

	status: GateStatus;

	/** What this run observed, in its own unit. */
	measured: string;

	/** The bar, in the same unit. */
	threshold: string;

	/** Where the bar is read from. Never a number typed here. */
	source: string;

	/** The gate's own words, so a reader needs no code. */
	detail: string;
}

export const GATE_STATUS = ['passed', 'failed'] as const;

export type GateStatus = (typeof GATE_STATUS)[number];

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

/** The merged verdict: every gate, every diagnostic, one answer. */
export interface QualificationReport {
	version?: string;

	date: string;

	commit_sha: string;

	runner: string;

	candidate: CandidateIdentity;

	scorer: ScorerIdentity;

	/** What the controls ran under, as every shard recorded it. */
	inputs?: PipelineInputs | null;

	/** Digest over the frozen item hashes. Two runs on one corpus share it. */
	corpus_digest: string;

	corpus_items: number;

	/** The full attempted denominator, failures included. */
	planned: number;

	repeats: number;

	scored: number;

	gates: GateOutcome[];

	/** Where the frozen corpus fell short of the shape `evaluation` asks for. Empty on a corpus that met it. A line here describes the measuring stick rather than the candidate and blocks nothing - the gate that refuses a run with too little evidence is `scored_denominator`. */
	corpus_shortfalls?: string[];

	diagnostics?: Diagnostic[];

	qualified: boolean;

	detail: string;
}
