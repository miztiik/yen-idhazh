// Generated from `backend/idhazh/contracts/validation_row.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * Whether anybody published a number for this model, on this task.
 *
 * `not_reported` is not zero. A model whose card publishes no summarization or
 * faithfulness result has an unknown prior, and recording that as `0.0` would
 * put a fabricated worst case into every mean, chart and comparison that ever
 * reads the column (Guardrail #10).
 */
export const LEADERBOARD_PROVENANCE = ['reported', 'not_reported'] as const;

export type LeaderboardProvenance = (typeof LEADERBOARD_PROVENANCE)[number];

/** What the decision rule concluded. Never a free-text judgement. */
export const VALIDATION_VERDICT = ['confirmed', 'rescore_candidates', 'switch_and_pause', 'qualified', 'not_qualified'] as const;

export type ValidationVerdict = (typeof VALIDATION_VERDICT)[number];

/** One candidate model, scored end to end through our own pipeline. */
export interface ValidationRow {
	version?: string;

	model_id: string;

	/** The model currently configured. Exactly one row per run carries this. */
	is_incumbent: boolean;

	/** The model this run would run with. On a confirmed run, the incumbent. */
	selected: boolean;

	/** What the published leaderboard says. A prior, never evidence about us. */
	leaderboard_hhem?: number | null;

	/** Whether a published number exists at all. Missing stays missing. */
	leaderboard_provenance?: LeaderboardProvenance;

	/** Mean HHEM over the golden set, through our own pipeline. */
	measured_hhem: number;

	/** How many golden articles produced the mean. A mean of one is not one. */
	articles: number;

	/** The day this was measured, and the day file it lands in. */
	date: string;

	/** Which execution measured it. Two dispatches of one candidate are two verdicts. */
	run_id: string;

	/** The tree the measurement ran against. */
	commit_sha: string;

	/** Where it ran. A laptop number is not a gate. */
	runner: string;

	/** What the run concluded. A run-level fact, identical on every row. */
	verdict: ValidationVerdict;

	/** The rule's own words for why, so a reader needs no code. */
	detail: string;
}
