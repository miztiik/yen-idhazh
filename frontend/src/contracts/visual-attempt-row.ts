// Generated from `backend/idhazh/contracts/visual_telemetry.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * What one article's numbers say it could carry, and nothing else.
 *
 * **Three classes, and the count is the point.** The visual programme names
 * five, and only two of them are a question about numbers. `comparative` and
 * `processual` are claims about how an article is written, so they have no
 * query yet and land with the diagram plan. Anything reporting per class before
 * then names three and says so, rather than letting a reader take three for the
 * whole taxonomy.
 *
 * The query rests on the element table's Tier 1 fields alone - `kind`, `value`
 * and `unit` - so it is byte-exact and carries no model judgement.
 * `idhazh.elements.classify` is the query; this is its vocabulary, and
 * `docs/architecture/extraction/elements.md` is the page that owns it.
 *
 * **It is declared here rather than beside the element contract**, with the
 * other closed vocabularies this census row carries, because
 * `contracts/element.py` sits above `contracts/article.py`, which sits above
 * this module. A label a census row persists has to be declared at or below the
 * row's own level, and this is the level.
 */
export const ELEMENT_CLASS = ['chartable', 'narrative', 'unclassified'] as const;

export type ElementClass = (typeof ELEMENT_CLASS)[number];

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
 * Whether this story wants a picture at all.
 *
 * `none` is the common and correct answer, and it is a decision rather than an
 * absence - a plan that declines still records why it declined and how sure it
 * was, so a refusal is legible.
 */
export const PLAN_DECISION = ['visual', 'none'] as const;

export type PlanDecision = (typeof PLAN_DECISION)[number];

/**
 * The nine checks, in the order the validator runs them.
 *
 * Each member is the property that must HOLD, not the failure - the same way
 * `span_integrity_pass` and `derived_provenance_complete` are named.
 *
 * **It lives in `contracts/` because a ledger column now carries it.** It was
 * declared in `idhazh.visual_validator` beside the code that runs the checks,
 * with a note saying it moves here on the day something persists it. That day
 * is this one: `rejection_reason` is a fold key term, so the vocabulary has to
 * be declared at or below the level of the row that persists it (CLAUDE.md
 * section 4). `visual_validator` imports it from here, so there is still one
 * list and not two.
 */
export const VALIDATOR_CHECK = ['element_exists', 'semantically_compatible', 'units_convertible', 'roles_valid_for_type', 'enough_data', 'no_duplicate_in_role', 'no_invented_values', 'numerals_matched', 'plan_version_current'] as const;

export type ValidatorCheck = (typeof VALIDATOR_CHECK)[number];

/**
 * Which vocabulary a plan's type belongs to.
 *
 * Coarser than the type and stable across a downgrade within a family, which
 * is what makes it a stratum term: a `pie` stepped down to a `stacked_bar` is
 * still a composition, and comparing the two as one group is comparing like
 * with like. A cross-family move is refused by the ladder, so a family never
 * changes under an attempt.
 *
 * Four families, and every declarable type belongs to exactly one - the check
 * is at the bottom of this module rather than in a docstring, because a type
 * in no family would be folded into a group nobody chose.
 */
export const VISUAL_FAMILY = ['chart', 'composition', 'diagram', 'infographic'] as const;

export type VisualFamily = (typeof VISUAL_FAMILY)[number];

/**
 * What became of the visual. "Could not make it" and "made it then threw it
 * away" are different facts, so they never share a member.
 */
export const VISUAL_STATE = ['absent', 'rendered', 'render_failed'] as const;

export type VisualState = (typeof VISUAL_STATE)[number];

/**
 * One attempt at one picture, on one run: the full grain the fold replaces.
 *
 * **One row per attempt, never one per published visual.** A per-publication
 * ledger leaves every refusal uncommitted, so the machine loop stops being
 * auditable while still being the gate, and a later run cannot tell a refused
 * visual from one never attempted.
 *
 * This is the shape the fold reads. It carries the eight terms of `FOLD_KEY`
 * and the two measured columns the folded row keeps a distribution of, and
 * nothing else yet: the join key a human label needs, and a typed reason for
 * every one of the six gates, arrive with the row that writes the ledger.
 * Both are additive.
 */
export interface VisualAttemptRow {
	version?: string;

	date: string;

	run_id: string;

	item_id: string;

	/** Whether this attempt proposed a picture at all. Half of the key. */
	decision: PlanDecision;

	/** Which gate decided this item carries no picture. Empty on an attempt that proposed one, and on a refusal by a producer that recorded no gate - empty reads as nothing said which, never as a gate named none. */
	none_reason?: NoneReason | null;

	/** The FIRST validator check that did not hold. The validator runs its nine checks in order and a refused plan usually fails several, so one cell holds the first rather than a list: a list in a CSV cell is unaggregatable, and the check an operator acts on is the one that fired first. Empty where no plan reached the validator. */
	rejection_reason?: ValidatorCheck | null;

	/** What the article's own numbers say it could have carried. Empty on the same terms as the item-health census: the extraction pass did not run, or its spans would not re-slice. Three classes and not five, which is that census's own settled reading - the other two are claims about language and have no query yet, and they arrive here as members rather than as a term. */
	potential_primary?: ElementClass | null;

	/** Which vocabulary the attempted type belongs to. Empty where no plan named a type, which is every attempt refused before a plan was drafted. */
	family?: VisualFamily | null;

	/** Tier 1 elements the extraction pass kept for this article. The raw count, banded into the key by band_of and kept whole as a distribution on the folded row. Empty on the same terms as potential_primary. */
	elements_found?: number | null;

	/** The deepest rung of the downgrade ladder this attempt reached. Zero means the plan was accepted or refused as drafted. It is recorded on a refused attempt as well as a published one, because a keep rate by depth needs a denominator at that depth. Empty where no plan was drafted. */
	downgrade_depth?: number | null;

	/** How many marks the accepted plan drew, in the channel its type counts in. The ladder's own currency: each rung reads a percentile of the depth-0 published mark counts, so this is the population that floor is taken over. Empty on an attempt that proposed nothing. */
	marks?: number | null;

	/** What became of the visual. `rendered` is the one value that means a reader saw it, so it is the numerator of every keep rate here. */
	state: VisualState;
}
