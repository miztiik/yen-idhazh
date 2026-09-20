// Generated from `backend/idhazh/contracts/visual_data.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * The four ways code may reach a number the article did not write.
 *
 * Each member's arithmetic is defined by the implementation of the same name in
 * `idhazh.derived_values`, and `inputs` is ordered because two of them read the
 * order: a share's part comes first and its whole follows.
 */
export const DERIVED_FUNCTION = ['count', 'sum', 'share_of_declared_whole', 'convert'] as const;

export type DerivedFunction = (typeof DERIVED_FUNCTION)[number];

/** One number code computed, and the complete chain back to what it read. */
export interface DerivedValue {
	/** Which of the four. Closed, and a name outside the list does not load. */
	function: DerivedFunction;

	/** The date-stamp of the arithmetic that produced this value - the four functions and the binning rule. Stamped by code, so a later build can say whether this number would come out the same today. */
	version: string;

	/** Every Tier 1 element this value read, in the order the function reads them. Element ids and never another derived value: a chain that nests can be complete at each hop and still name no element at the bottom. */
	inputs: string[];

	/** What code computed, as a decimal pinned to text the way a Tier 1 value is. */
	value: string;

	/** What this value measures, which for a conversion is the target unit. Null on a count, because a count of things measures nothing. */
	unit: string | null;

	/** What a conversion moved from. Null on the other three. */
	source_unit: string | null;

	/** The date-stamp of the table that said the two units measure the same thing. Null on the other three, because they read no table. */
	unit_table_version: string | null;

	/** The inclusive floor of the bin a count was taken over. Null off a histogram. */
	bin_lower: string | null;

	/** The ceiling of that bin. Null off a histogram. */
	bin_upper: string | null;
}

/**
 * Which marks fill which channel of the drawing.
 *
 * One field per member of `EncodingRole`, in that order, mirroring
 * `PlanEncodings`. Every role is present and an unused one is empty, so "which
 * channels does this drawing use" is a question about which are non-empty
 * rather than about which are there - and a reader of this file learns the
 * same nine words it would learn from the plan.
 */
export interface VisualEncoding {
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
 * One thing the drawing puts on the page, and where it came from.
 *
 * A mark is one entry in one channel - a bar's name or a bar's length, never
 * both halves of a bar. That is what lets a channel have a length of its own,
 * and a channel with a length of its own is the only way a drawing can be
 * caught holding four names and three figures.
 *
 * **Every mark states its provenance and exactly one kind of it**, the same
 * rule `DisplayedValue` holds: the Tier 1 element whose own characters or own
 * figure it draws, or the derived value with its complete chain back to
 * several of them. Written as two optionals with no rule, a mark that came
 * from nowhere is a payload somebody can write.
 */
export interface VisualMark {
	/** How the encoding below addresses this mark. Unique within one visual. */
	mark_id: string;

	/** What a naming mark says: the element's own characters, cut and sanitized where the trust boundary was crossed. Null on a mark that measures rather than names. */
	text: string | null;

	/** How big a measured mark is, as a decimal pinned to text the way a Tier 1 value is. Null on a mark that names rather than measures. */
	value: string | null;

	/** What `value` measures. Null on a naming mark, and null on a count, which measures nothing. */
	unit: string | null;

	/** The Tier 1 element this mark was cut from. Null on a derived mark. */
	element_id: string | null;

	/** The arithmetic and its chain, where no single element states the figure drawn. Null on a mark cut straight out of the article. */
	derived: DerivedValue | null;
}

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

/**
 * One published visual: its marks, its channels, its type and what draws it.
 *
 * Published at `frontend/public/digest/<YYYY>/<MM>/<DD>/<item_id>.json`, beside
 * the day payload that points at it. **The shard is the day directory**, which
 * is what every other published store uses and what a reader fetches. The chart
 * data is kept out of `digest.json` because the day payload is never deleted,
 * so anything inside it would be undeletable and `retention.image_months` would
 * have nothing to act on (owner, 2026-09-13).
 */
export interface VisualData {
	version?: string;

	/** The story this drawing belongs to, and the stem of this file's own name. */
	item_id: string;

	/** The form the drawing takes. A type the drawing code does not know is refused rather than approximated - a chart that is nearly the plan is a chart nobody asked for. */
	type: VisualType;

	/** The date-stamp of the drawing contract this data was compiled for. The page refuses a version it does not know, so a later change that would move pixels cannot redraw an older day without saying so. */
	renderer_version: string;

	/** Every figure and every name the drawing puts on the page. */
	marks: VisualMark[];

	/** Which marks fill which channel. Every role a key, an unused one empty. */
	encoding: VisualEncoding;
}
