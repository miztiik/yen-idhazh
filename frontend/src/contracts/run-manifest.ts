// Generated from `backend/idhazh/contracts/run_manifest.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * One more file these weights need, and the flag that hands it to the server.
 *
 * A model is not always one file. Google ships a multi-token-prediction head
 * beside the gemma weights; another family ships a projector, an adapter or a
 * vocoder. Each is the same fact - bytes from a hub repository, verified, then
 * named on the command line - so each is an entry here rather than a typed
 * block of its own with its own five fields and its own argv branch.
 *
 * `flag` is what makes this a declaration rather than a download list. The
 * builder emits `<flag> <landed path>` and knows nothing about what the file
 * is for, so a projector or an adapter is a config-only change. A companion
 * with no flag is a file that must simply be present.
 */
export interface CompanionFile {
	/** Hugging Face repository the file is pulled from. */
	repo: string;

	/** The hub commit the file is fetched at. Never a branch: a branch gets whatever was uploaded last, under a digest that still reads the old bytes. */
	revision: string;

	/** The file name inside the repository, and one path segment. It becomes a path under the models directory and a shell argument beside it. */
	file: string;

	/** Required, with no exception. A blank digest makes `sha256sum --check` report 'no properly formatted checksum lines found', which names neither the entry nor the field. */
	sha256: string;

	/** How many bytes the hub reports. Absent where nobody has fetched it yet. */
	byte_count?: number | null;

	/** The llama-server flag that takes this file's landed path. Absent means the file must be present and is named by nothing on the command line. */
	flag?: string | null;
}

/** Which config bytes a run read. A silently edited knob changes every output. */
export interface ConfigDigest {
	path: string;

	sha256: string;
}

/**
 * Which weights, from where. Per-item payloads carry only the `id`.
 *
 * **This is the shape a run recorded**, and `run_manifest.ModelUse` embeds it.
 * `ModelEntry` below is the shape a person declares in `config/`. What a
 * reasoning span is closed with belongs to the second and not to this one: no
 * `model_ref` a run has ever written carries it, and a field required here
 * would stop today's build reading yesterday's run (`CLAUDE.md` section 11).
 */
export interface ModelRef {
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

	/** What a run recorded under the one settings block, before llama-server's own flags and the request values were split into the two blocks beside this one. A plain mapping and nothing writes it: a record written under the typed shape carries keys this build no longer names, and a typed field would refuse every one of them. */
	inference?: Record<string, unknown>;

	/** llama-server's own flags, spelled exactly as the binary spells them - `--ctx-size`, `-fa`, `--no-warmup`. A null value is a bare flag with no argument. Emitted verbatim, so naming one more option is a key here and no edit anywhere else, and a flag this build does not accept is refused by llama-server at start-up with the flag named. */
	server?: Record<string, unknown>;

	/** What goes in a request body rather than on the command line, under this project's own names. A sampling value cannot reach the command line because the builder reads only the block above. */
	request?: Record<string, unknown>;

	/** Every extra file these weights need beside the GGUF the entry names. The weights themselves stay in the fields above, because moving them here would move `declared_for`, the health check and `--model` for no gain. */
	companion_files?: CompanionFile[];

	/** What a run recorded when the draft head was a typed block of its own. A plain mapping and nothing writes it: six committed run records carry it, the reader forbids an extra key, and the head is now a companion file with its decode settings in the server block. */
	draft?: Record<string, unknown> | null;
}

export const MODEL_ROLE = ['summarize', 'route'] as const;

export type ModelRole = (typeof MODEL_ROLE)[number];

export interface ModelUse {
	role: ModelRole;

	model_ref: ModelRef;
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

	/** One canonical spelling of the decoding parameters. */
	sampling: string;

	/** One canonical spelling of the runtime knobs that move the arithmetic. */
	runtime_flags: string;

	n_ctx: number;

	n_batch: number;

	n_ubatch: number;

	n_threads: number;

	runner_class: string;

	extractor_version: string;

	sanitizer_version: string;
}

export interface RunRecord {
	/** The identity of the execution that made this record, as every ledger under state/ spells it. Addressed by the date and then by the CI run that produced it, so no second execution can compute the same one. Records written before 2026-08-31 carry the day's ordinal there instead, which is what two runs were able to share. */
	run_id: string;

	/** Run sequence within the date. 1 is the morning run. */
	n: number;

	started_at: string;

	completed_at?: string | null;

	status: RunStatus;

	commit_sha: string;

	/** The hardware this run's numbers were measured on. */
	runner: string;

	/** Source discovery failed and yesterday's list was reused. */
	source_list_stale?: boolean;

	models?: ModelUse[];

	/** Work shards this run planned, as the plan derived them before the matrix fanned out. It is the denominator for `N shards reported nothing`, and it has to come from the plan: a denominator counted off the same rows as the numerator can never disagree with them, so the check would have no red state at all. Null on a manifest written before it was recorded. */
	shards?: number | null;

	items_planned: number;

	items_succeeded: number;

	items_failed: number;

	items_skipped?: number;

	/** Items the router reached. Zero when the route job died. */
	items_routed?: number;

	/** Items the retired visual planner decided without asking the model, because no enabled visual kind could survive the checks. Counted separately so a chart rate is never quoted against items_routed alone. **Zero on every run since the planner retired**: the summarize-and-plan call writes the summary and the plan in one reply, so the model is asked on every item and the gate then decides what to do with the plan. Kept because the committed archive carries non-zero values a reader of an older day still needs. */
	items_prefiltered?: number;

	/** What the router spent on this day, summed over its items. Read against items_routed and against the job's own wall-clock: a stage total far below the job total says the fixed cost is the problem, not the model. */
	route_ms?: number | null;

	/** Items whose planner reply asked for a chart, whatever the decision became. Subtract the day's published charts and the remainder is what the post-model checks rejected - the only number that separates a model that does not want charts from checks that refuse the ones it wants. Zero on a manifest written before it existed. */
	charts_drafted?: number;

	verticals?: VerticalCount[];

	/** What this run summarized with, named field by field: the weights and their digest, the llama.cpp build, the chat template, the prompt, the output schema, the truncation cap, every decode and runtime setting including n_ctx, the runner class, and the extractor and sanitizer versions. Recorded, never compared to decide anything - no run, no pool, no window and no published number turns on it, so a run whose inputs moved is counted, averaged and published exactly as one whose inputs held still. Read with config_digests beside it, which says which config bytes were read. Null on a manifest written before 2026-09-12, and on a run that summarized nothing. */
	inputs?: PipelineInputs | null;

	/** Recorded, not raised. A gate that fires on a CPU class gets switched off. */
	determinism_violations?: number;

	/** Bytes under frontend/public/digest/ after this run - the committed payload tree, not the published site and not what the Pages cap is measured against. */
	site_bytes: number;

	/** Files under frontend/public/digest/ after this run. */
	site_files: number;

	/** Whether observability.evaluation_enabled was on for this run. False is deliberately off; true with no scorer_version is an instrument that failed to load. Null on a manifest written before this was recorded - never false, because absent and off are different facts. */
	evaluation_enabled?: boolean | null;

	/** The fraction of runs the scorer was set to run on, recorded on EVERY run whether or not this one was drawn. Without it a year-old ledger cannot tell 800 rows of 1,000 from 800 rows of 800. Null on a manifest written before this was recorded. */
	evaluation_sample_rate?: number | null;

	/** Whether this run was drawn at that rate. False is the third reason a run has no rows, beside switched off and failed to load, and none of the three can be read off an absence. Always true at a rate of 1.0. */
	evaluation_sampled?: boolean | null;

	/** The instrument that wrote this run's eval rows, as state/scores.csv spells it. Null when no row was written, which is what separates a run that measured nothing from one whose measurements are simply elsewhere. Null too on a manifest written before this was recorded. */
	scorer_version?: string | null;

	/** The scoring shape this run published under, as `idhazh.rank.RANK_VERSION` spells it. A published order that moved for a reason nobody recorded is a published order nobody can defend, and until this field existed the constant was read by nothing. Null on a manifest written before this was recorded, which is unknown rather than a claim about which shape ran. */
	rank_version?: string | null;

	config_digests?: ConfigDigest[];

	/** The merge line this run grouped the day at. Without it a reader of a committed run.json cannot tell a day grouped at 0.94 from a day grouped at 0.937, and the grouping is the thing the fitted line moves. Empty on a run that published before the line could move, which is every run before 2026-09-18. */
	same_story_floor_applied?: number | null;

	note?: string | null;
}

export const RUN_STATUS = ['completed', 'partial', 'failed'] as const;

export type RunStatus = (typeof RUN_STATUS)[number];

export interface VerticalCount {
	id: string;

	/** Items this run planned for this vertical. */
	planned: number;

	/** Items this run introduced into the day payload for this vertical. */
	published: number;

	/** A vertical under its floor is collected but not rendered. */
	below_feed_floor?: boolean;

	/** Feeds on this desk whose configured address this run was allowed to ask, as the plan counted them. Null on a manifest written before the count existed, which is unknown rather than a desk with no sources. */
	eligible_feeds?: number | null;

	/** The floor that count was measured against, so below_feed_floor can be checked against the two numbers that decided it rather than taken on trust. Null on a manifest written before it was recorded. */
	feed_floor?: number | null;
}

/** `frontend/public/digest/<YYYY>/<MM>/<DD>/run.json`. */
export interface RunManifest {
	version?: string;

	date: string;

	runs: RunRecord[];
}
