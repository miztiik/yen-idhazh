// Generated from `backend/idhazh/contracts/visual_telemetry.py` by `python -m idhazh.contracts.export`.
// Never hand-edited: the drift gate regenerates it and fails on any diff
// (CLAUDE.md section 1a). Edit the Pydantic model instead.

/**
 * How many facts the article offered, as a band rather than a count.
 *
 * A band and not the raw count, because the count is the thing being folded:
 * a key carrying it would put almost every attempt in a group of its own and
 * the fold would summarise nothing. The raw counts survive as the distribution
 * on the folded row, so a reader keeps both the stratum and the spread inside
 * it.
 *
 * **The boundaries are powers of two, and the measurement agrees with them.**
 * Counted 2026-09-13 over the 21 committed `state/item-health/` day files,
 * 1,716 rows carrying `elements_found`: p25 is 3, the median is 7 and p75 is
 * 16, against boundaries of 4, 8 and 16. The five bands then hold 8.0, 20.0,
 * 22.6, 23.7 and 25.7 percent of that population, so no band is a rounding
 * error and none of them is half the archive. Spread is zero - the committed
 * rows are a fixed set, counted exactly.
 *
 * **The boundaries are in this module and not in `config/`, and that is the
 * one place this shape argues with Guardrail #6.** A band is a persisted key
 * term on an irreversible fold: move a boundary and two folded months stop
 * being comparable, with nothing left to re-fold either of them from. So it
 * moves the way a contract moves - a changelog entry and a read-side migration
 * - rather than the way a knob moves, which is an edit nobody records.
 */
export const ELEMENT_BAND = ['none', 'few', 'some', 'many', 'rich'] as const;

export type ElementBand = (typeof ELEMENT_BAND)[number];

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
 * One `(date, decision, none_reason, rejection_reason, potential_primary,
 * family, element_band, downgrade_depth)` group, folded from one month of
 * attempts.
 *
 * **That eight-term tuple IS the key, and this description is where it is
 * declared** - the convention `state/telemetry-aggregate/` already sets by
 * naming its own `(date, stage)` pair in its description rather than leaving
 * the group to be inferred from the code that writes it.
 *
 * Ordered by the key, so a folded month reads down the days and then down the
 * causes rather than down the alphabet.
 *
 * **The fold can never grow the store.** A group holds at least one attempt, so
 * the row count never rises, and this row is narrower than the attempt row it
 * replaces. The pathological case is real and is bounded rather than argued
 * away: a month in which every attempt lands in its own group folds to exactly
 * as many rows as it had, each one smaller.
 */
export interface VisualAggregateRow {
	version?: string;

	date: string;

	decision: PlanDecision;

	none_reason?: NoneReason | null;

	rejection_reason?: ValidatorCheck | null;

	potential_primary?: ElementClass | null;

	family?: VisualFamily | null;

	/** Which band the attempts' element counts fell in. Empty where no count was recorded, which is not the `none` band - one says nobody measured and the other says the article stated no facts. */
	element_band?: ElementBand | null;

	downgrade_depth?: number | null;

	/** Attempts the shard held for this group, counted as they were written. A group with no attempts is not written, so an absent group reads as never happened rather than as happened and measured nothing. */
	attempts: number;

	/** Of those, the attempts a reader saw - the ones whose state was rendered. The numerator of the keep rate; `attempts` is the denominator. Stored as two counts and never as the rate, because a rate cannot be added across groups and these two can. */
	published: number;

	/** Attempts of this group that carried an element count. */
	elements_n: number;

	elements_min?: number | null;

	elements_p25?: number | null;

	/** Nearest-rank median of the element counts. Nearest rank rather than interpolation, so the figure is one an attempt really had and can be checked against the shard this replaced. */
	elements_p50?: number | null;

	elements_p75?: number | null;

	elements_max?: number | null;

	/** Attempts of this group that drew marks. */
	marks_n: number;

	marks_min?: number | null;

	marks_p25?: number | null;

	marks_p50?: number | null;

	marks_p75?: number | null;

	marks_max?: number | null;
}
