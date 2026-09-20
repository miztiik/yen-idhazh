// Generated from `backend/idhazh/contracts/score_archive.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** The band, not the number, is what drives behaviour and what a reader sees. */
export const CONFIDENCE_BAND = ['high', 'medium', 'low'] as const;

export type ConfidenceBand = (typeof CONFIDENCE_BAND)[number];

/**
 * One numeric column of one cohort, as the five numbers that rebuild it.
 *
 * Deliberately not a mean and a standard deviation. Those are answers rather
 * than evidence: two cohorts' means cannot be added, and a pooled spread
 * cannot be recovered from two pooled spreads. `sum` and `sum_squares` can be
 * added across any set of cohorts and give back both.
 */
export interface Moment {
	/** Rows of this cohort that carried a value for this column. Never the cohort's row count: a nullable column is empty on every row written before it existed, and counting those as zero would say the row measured the value and got nothing. */
	n: number;

	/** Every value added together. A total survives; a mean does not. */
	sum: number;

	/** Every value squared, added together. With n and sum this gives the variance and so the spread, which Guardrail #10 asks for beside any number read off this archive. */
	sum_squares: number;

	/** The smallest value. Absent when n is zero - absent is not zero. */
	min?: number | null;

	/** The largest value. */
	max?: number | null;
}

/**
 * One (date, run, row version, model, scorer) group of scored items.
 *
 * Five fields of key, because every one of them changes what a number over the
 * group means. A day and a run separate two executions that published the same
 * date. The row version says which columns the rows carried at all. The model
 * says what produced the words, and the scorer version says which instrument
 * read them - and the scorer version is the one that makes a rate from two
 * cohorts unmixable rather than merely awkward.
 *
 * It was six until 2026-09-12, when the pipeline fingerprint left the key:
 * splitting a month on a stamp that moved on any of seventeen inputs turned
 * one day into several cohorts of a handful of rows each.
 */
export interface ScoreCohort {
	date: string;

	run_id: string;

	/** The eval-row schema stamp these rows carried. Part of the key because a column is null on every row stamped before it existed, so a cohort that mixed two stamps would report a coverage hole as a measurement. */
	row_version: string;

	model_id: string;

	scorer_version: string;

	/** Rows the shard held for this group, counted as written. */
	rows: number;

	/** How the group's faithfulness scores fall across ten buckets, lowest first. The distribution a percentile question can still be asked of approximately once the rows are gone, and the reason an exact percentile cannot be. */
	hhem_deciles: number[];

	/** How many rows the run banded high, medium and low. All three keys are present, zero included, so a reader never has to decide whether a missing band means none or means unrecorded. */
	bands: Record<string, number>;

	/** How many rows set each boolean column. Counted rather than folded into a rate, so a count over several cohorts is a sum instead of an average of averages. */
	signals: Record<string, number>;

	/** Rows that recorded the article's length before the truncation cap, so the cut is answerable at all. It is not the row count: a row stamped before 2026-08-27T21:00 can carry no pre-cap length. */
	cut_known: number;

	/** Of those, the rows where the model read less than the whole article. Read as the arithmetic and never as truncation_flagged, which means two different things either side of 2026-08-29T09:00. */
	cut: number;

	/** Rows carrying the digest of the text the scorer read. Zero on a month scored before 2026-08-27, when no run recorded a premise. */
	premise_recorded: number;

	/** Distinct premise digests among those. Below premise_recorded means two items were scored against the same text, which is the shape a broken extractor takes. */
	premise_distinct: number;

	/** One moment per numeric column of the eval row. Keyed by the column name, so a column added later is a new key rather than a shifted position. */
	measurements: Record<string, Moment>;
}

/** One month of `state/scores/`, after the full-grain rows are gone. */
export interface ScoreArchive {
	version?: string;

	/** The month this replaces, spelled the way its day files were filed under. */
	month: string;

	/** Data rows the month held, headers excluded. Reconciled against the day files before they are unlinked, so a summary of a truncated read can never be the reason a file is deleted. */
	source_rows: number;

	/** The month's day files, digested in day order into one hash. The one field that says WHICH files this summarises rather than describing what was in them. */
	source_sha256: string;

	/** One digest per distinct measurement the month held - the SHA-256 of the eval writer's observation key - sorted and distinct. This is what keeps the dedupe exact after the rows are gone: without it, the day a shard is deleted every observation in it becomes scoreable again as if it were new, and a count over the ledger stops being a count of items. */
	observation_digests: string[];

	/** Every group the month held, in key order. Their row counts sum to source_rows. */
	cohorts: ScoreCohort[];
}
