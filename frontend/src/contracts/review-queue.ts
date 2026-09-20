// Generated from `backend/idhazh/contracts/review_queue.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * Which gate decided this item carries no picture.
 *
 * `none` is the majority outcome by design - two items in three - so a `none`
 * with no cause makes the largest number an operator reads the one that
 * explains nothing.
 *
 * **One member per gate, never one per call site.** The reachability gate
 * refuses in two places and both record `not_reachable`, because what an
 * operator acts on is the gate rather than the line of code.
 *
 * **And one member per gate that has a writer.** The design record names six
 * gates and the two-call flow adds a seventh; the potential class, the novelty
 * floor, the sufficiency bar and the per-visual byte cap are not built, so a
 * member for each would be a word nobody can produce, nobody can retire and
 * nobody can tell from a bug. Each arrives as an additive member with the row
 * that builds its gate.
 *
 * The single-call planner these five replace writes nothing here. Its causes
 * are sentences in `rationale` and several of them - no summary to illustrate,
 * a reply that lost its shape, a kind with no renderer - are not gates at all,
 * so typing them into this vocabulary would be work the row that retires that
 * planner deletes.
 */
export const NONE_REASON = ['not_reachable', 'model_declined', 'validation_failed', 'output_budget_cut', 'window_exhausted'] as const;

export type NoneReason = (typeof NONE_REASON)[number];

/**
 * How big a population was, beside how much of it this queue carries.
 *
 * Both numbers, never one. The budget below caps each population in
 * proportion rather than truncating one of them, and a kept count on its own
 * reads identically on a day that fitted and a day that was cut - so only the
 * pair says which happened.
 */
export interface ReviewCensus {
	population: ReviewPopulation;

	/** Decisions this population held, before any cap. */
	seen: number;

	/** Rows this queue carries for it. */
	kept: number;
}

/**
 * Which of the three outcomes an item landed in.
 *
 * The split is read off the decision and never off the published day: the day
 * payload carries `visual: null` for every item that got no picture, so from
 * it alone a chart the validator refused and a story nobody drafted one for
 * are the same absence. Telling those two apart is most of the point.
 */
export const REVIEW_POPULATION = ['published', 'rejected', 'none'] as const;

export type ReviewPopulation = (typeof REVIEW_POPULATION)[number];

/** One item as a reviewer meets it. */
export interface ReviewRow {
	item_id: string;

	url_key: string;

	population: ReviewPopulation;

	title?: string | null;

	source_url: string;

	visual_state: VisualState;

	/** Which gate decided this item carries no picture. Null on a published row, and null on a decision written before the field existed. */
	none_reason?: NoneReason | null;

	rationale?: string | null;

	alt_text?: string | null;

	/** Where this row's drawing sits inside the review tree, relative to this file. A copy, so the tree is readable with the repository absent. Null on every row that carries no drawing. */
	asset_relpath?: string | null;
}

/**
 * What became of the visual. "Could not make it" and "made it then threw it
 * away" are different facts, so they never share a member.
 */
export const VISUAL_STATE = ['absent', 'rendered', 'render_failed'] as const;

export type VisualState = (typeof VISUAL_STATE)[number];

/** One day's review tree, as a machine reads it. */
export interface ReviewQueue {
	version?: string;

	date: string;

	built_at: string;

	/** What the tree was allowed to weigh. The writer caps each population in proportion rather than failing, because the job that builds this one also publishes the day. */
	budget_bytes: number;

	/** What the sheet and its drawings weigh. This file is not counted, because a number inside a document cannot include its own length - writing it twice to make it fit would only produce a figure that is wrong by the difference. */
	bytes_written: number;

	census: ReviewCensus[];

	rows: ReviewRow[];
}
