// Generated from `backend/idhazh/contracts/label_row.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/** The band, not the number, is what drives behaviour and what a reader sees. */
export const CONFIDENCE_BAND = ['high', 'medium', 'low'] as const;

export type ConfidenceBand = (typeof CONFIDENCE_BAND)[number];

/**
 * Why, in one closed word.
 *
 * Every tag names a defect with a **different** fix. Two tags that lead to the
 * same code change would be one tag. Three of these deliberately mirror a
 * counterweight the pipeline already computes, which buys that counterweight's
 * own precision and recall out of the same 60 labels.
 *
 * Absent on purpose: severity, which is a second axis with its own agreement
 * problem; anything about style, which is not faithfulness; and `other`, which
 * grows until the vocabulary means nothing. `note` carries the misses.
 */
export const LABEL_TAG = ['none', 'invented_fact', 'wrong_number', 'overstated', 'wrong_subject', 'not_the_article', 'unjudgeable'] as const;

export type LabelTag = (typeof LABEL_TAG)[number];

/**
 * The one question. Not a bool - a bool named `unsupported` inverts in
 * somebody's head within a month.
 */
export const LABEL_VERDICT = ['supported', 'unsupported'] as const;

export type LabelVerdict = (typeof LABEL_VERDICT)[number];

/** One labelled item, appended by a human. */
export interface LabelRow {
	version?: string;

	/** Deterministic draw key, rebuilt from its value fields on read and never trusted from the file. */
	label_id: string;

	/** Which draw this row belongs to. Distinguishes a second draw from a re-label of the first. */
	draw_id: string;

	url_key: string;

	source_url: string;

	date: string;

	run_id: string;

	/** The exact summary that was judged. The load-bearing field: a mismatch means the label is about different words. */
	output_digest: string;

	summary_word_count: number;

	/** Words in the premise the labeller reads - the article after sanitizing and truncation, which is what the scorer read too. Not the whole article: that length is null on a ledger row that never recorded it, and a labeller cannot check a number against text nobody kept. */
	source_seen_word_count: number;

	/** The full string, band values included. Recorded so an analysis can refuse to mix instruments, hidden so it cannot anchor the labeller. */
	scorer_version: string;

	hhem_at_label: number;

	band_at_label: ConfidenceBand;

	verdict: LabelVerdict;

	tag: LabelTag;

	/** Who. Checked against evaluation.labellers. Two people disagreeing is signal; an anonymous ledger cannot see it. */
	labeller: string;

	labelled_at: string;

	/** How long this row took. The cheapest fatigue detector there is, and half of what makes a machine-paced dump detectable. */
	seconds_spent: number;

	/** Capped and sanitized. If notes pile onto one tag, the vocabulary is wrong. */
	note?: string | null;

	/** Numbers the summary asserted that appear nowhere in the article, as the scorer counted them at draw time. What the wrong_number tag is measured against. Null on a row written before 2026-09-03, which means re-join it from state/scores/ while that month is still at full grain - it does not mean zero. */
	unsupported_numbers?: number | null;

	/** The article hedged and the summary asserted, as the scorer read it at draw time. What the overstated tag is measured against. Null means unrecorded, never False. */
	hedge_dropped?: boolean | null;

	/** The text the scorer read looked like page furniture. What the not_the_article tag is measured against. Null means unrecorded, never False. */
	extraction_suspect?: boolean | null;
}
