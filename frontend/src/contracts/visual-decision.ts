// Generated from `backend/idhazh/contracts/visual_decision.py` by `python -m idhazh.contracts.export`.
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

export const VISUAL_KIND = ['chart', 'none'] as const;

export type VisualKind = (typeof VISUAL_KIND)[number];

/**
 * What became of the visual. "Could not make it" and "made it then threw it
 * away" are different facts, so they never share a member.
 */
export const VISUAL_STATE = ['absent', 'rendered', 'render_failed'] as const;

export type VisualState = (typeof VISUAL_STATE)[number];

/** The visual planner's decision plus the Render stage's outcome, one per item. */
export interface VisualDecision {
	version?: string;

	item_id: string;

	url_key: string;

	kind: VisualKind;

	rationale?: string | null;

	/** The compiled drawing instruction, built here from the article's own numbers and read back by whatever draws it. Since 2026-09-13 that is the reader's browser and this holds the published visual-data document, the same bytes the file beside the day carries. The grammar is the drawing code's rather than this contract's - it was Vega-Lite JSON while the build-time renderer ran - and naming one here would date the field to a renderer this project has already changed twice. Null on an item decided to nothing. */
	spec?: string | null;

	/** Relative POSIX path under frontend/public/ to this visual's published data, as digest/<Y>/<M>/<D>/<item_id>.json beside the day payload that points at it. Null on a payload written before the file existed, and null where the compile landed and the write did not - absent reads as no data carried. */
	data_path?: string | null;

	alt_text?: string | null;

	visual_state?: VisualState;

	model_id: string;

	decided_at: string;

	/** Wall-clock for this item: the planner call plus the render. Null on a payload written before the clock existed. */
	decision_ms?: number | null;

	/** False when the planner decided this item on its own facts and never posted. True on a payload written before the gate existed, because every item was asked then. */
	asked_the_model?: boolean;

	/** True when the model's reply asked for a chart, whatever this decision became. The gap between this and a kind of chart is what the post-model checks rejected. */
	drafted_chart?: boolean;

	/** Which gate decided this item carries no picture. Null on a decision that carries one, and null on a payload written before the field existed or by the single-call planner, which has no gate vocabulary. */
	none_reason?: NoneReason | null;

	failure_detail?: string | null;
}
