// Generated from `backend/idhazh/contracts/visual.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * Whether this story wants a picture at all.
 *
 * `none` is the common and correct answer, and it is a decision rather than an
 * absence - a plan that declines still records why it declined and how sure it
 * was, so a refusal is legible.
 */
export const PLAN_DECISION = ['visual', 'none'] as const;

export type PlanDecision = (typeof PLAN_DECISION)[number];

/**
 * Which elements fill which channel: every role a key, an unused one empty.
 *
 * References only - a channel names the elements that fill it and never the
 * values they hold. Every field is required, so a decoder cannot answer for a
 * `bar` by quietly not mentioning `quantity`; an inapplicable channel is an
 * empty array, and whether empty is legal for a given type is the validator's
 * rule rather than this shape's.
 *
 * Field order is decode order here as it is on the plan itself, and it is the
 * order `EncodingRole` declares.
 */
export interface PlanEncodings {
	/** The discrete axis: what each mark is. */
	category: string[];

	/** The measured axis: how big each mark is. */
	quantity: string[];

	/** The second measured axis, where a type has two. */
	quantity_x: string[];

	/** The temporal axis. */
	time: string[];

	/** What splits the marks into groups. */
	series: string[];

	/** The third channel, drawn as area. */
	size: string[];

	/** The quantity that is binned rather than plotted. */
	bins: string[];

	/** Who or what a mark is about. */
	entity: string[];

	/** What names one dated event. */
	event_label: string[];
}

/**
 * What the reader is being asked to do, coarser than the type.
 *
 * A downgrade may change the type and never the purpose, so this is the thing
 * that survives the ladder and the thing a cross-family move would break. Each
 * member covers one or more rows of the section 7.2 type matrix.
 */
export const VISUAL_PURPOSE = ['comparison', 'trend', 'relationship', 'change', 'composition', 'distribution', 'sequence', 'detail', 'emphasis'] as const;

export type VisualPurpose = (typeof VISUAL_PURPOSE)[number];

/**
 * The full declarable vocabulary of forms a plan may ask for.
 *
 * Declarable is not renderable. A type with no compiler template can be named
 * by a plan and is deterministically downgraded to its nearest built
 * neighbour, which is how the planner says which template is worth building
 * next. What may reach a reader is gated elsewhere; what may be named is here.
 */
export const VISUAL_TYPE = ['bar', 'dot', 'line', 'area', 'scatter', 'bubble', 'slope', 'stacked_bar', 'pie', 'histogram', 'timeline', 'table', 'flow', 'comparison', 'callout', 'quotecard', 'whowhat', 'keyfacts'] as const;

export type VisualType = (typeof VISUAL_TYPE)[number];

/** One item's visual plan: references and closed names, and nothing else. */
export interface VisualPlan {
	version?: string;

	/** Whether this story wants a picture. Decoded first, so nothing conditions it. */
	decision: PlanDecision;

	/** What the reader is asked to do. Committed before the type, because a type chosen first turns the purpose into a rationalisation of it. Null on a plan that declines. */
	purpose: VisualPurpose | null;

	/** The form, from the full declarable vocabulary. Null on a plan that declines. */
	type: VisualType | null;

	/** Which elements fill which channel. Every role is a key and the decoder may not skip one, so a plan that draws nothing in a channel says so with an empty array rather than by silence. */
	encodings: PlanEncodings;

	/** Every element this plan draws from, so the validator has one list to check existence against rather than nine. */
	element_ids?: string[];

	/** The elements whose own characters name the marks and the axes. A reference and never a string: code cuts every character a reader sees, and the model points at which characters. */
	labels?: string[];

	/** The elements to mark first, so one mark lands before its siblings. A reference for the same reason a label is. */
	annotations?: string[];

	/** Why this form, or why nothing. Model prose, shown to no reader and to no reviewer - it is read when a decision is being audited and nowhere else. */
	why: string;

	/** What the picture is called. Null on a plan that declines. */
	title: string | null;

	/** One sentence of framing under the picture. Optional on any plan. */
	caption: string | null;

	/** How sure the model was, decoded after the type so it conditions nothing. Recorded, and it gates nothing. */
	confidence: number;

	/** The date-stamp of the planning vocabulary this plan was made against. Stamped by code, never decoded. A later build compares it against what it now holds, which is how vocabulary drift is found rather than drawn. */
	plan_version: string;
}
