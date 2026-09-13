"""The visual ledger's two grains: one row per attempt, and what survives the fold.

`state/visuals/<YYYY-MM>.csv` records one row per **attempt** at a picture -
every refusal, every `none` and every published chart. `none` is the majority
outcome by design, so a `none` with no cause makes the largest number an
operator reads the one that explains nothing.

`observability.visuals_full_grain_months` decides how long that stays readable
attempt by attempt. Past it a month is folded to `VisualAggregateRow` and the
full-grain shard is deleted.

**The fold key is settled here, before anything writes a row, because the fold
cannot be revised.** A key is not a summary a later reader can re-derive: at the
window edge the attempts are gone, so a term left out of the key is a breakdown
nobody can ever ask for again. `FOLD_KEY` below is that key, spelled once and
checked at import against the fields of the folded row.

**Eight terms, in two halves.** `(date, decision, none_reason,
rejection_reason)` is the cause breakdown - which gate refused, and which check
inside the validator. `(potential_primary, family, element_band,
downgrade_depth)` is the stratum - what the article could have carried, what was
attempted over it, how many facts were available, and how far down the ladder
the attempt went. Folding on date alone would keep the daily totals and lose
both halves, which is the half that decides whether the typed reason was worth
building.

**The row carries a distribution and never a mean.** A bimodal spread is the
interesting finding and a mean hides it, so each measured column keeps a count,
the two outer quartiles, the median and both ends. A mean cannot be re-derived
from those and does not need to be: what a reader asks of a folded month is
where the mass sits, not where its centre of gravity is.

**What is deliberately lost once the shard goes**, stated rather than implied:
the per-item lookup and its join key, any percentile the quartiles do not carry,
correlation between two measured columns, the rationale text behind a refusal,
and any slice the eight terms above do not name.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, ItemId, RunId
from idhazh.contracts.item_health import ElementClass
from idhazh.contracts.visual import PlanDecision, VisualType
from idhazh.contracts.visual_decision import NoneReason, VisualState


class ValidatorCheck(StrEnum):
    """The nine checks, in the order the validator runs them.

    Each member is the property that must HOLD, not the failure - the same way
    `span_integrity_pass` and `derived_provenance_complete` are named.

    **It lives in `contracts/` because a ledger column now carries it.** It was
    declared in `idhazh.visual_validator` beside the code that runs the checks,
    with a note saying it moves here on the day something persists it. That day
    is this one: `rejection_reason` is a fold key term, so the vocabulary has to
    be declared at or below the level of the row that persists it (CLAUDE.md
    section 4). `visual_validator` imports it from here, so there is still one
    list and not two.
    """

    #: Every element the plan declares is one the article's table holds.
    ELEMENT_EXISTS = "element_exists"
    #: Each element's kind fits the channel it fills.
    SEMANTICALLY_COMPATIBLE = "semantically_compatible"
    #: Within one measured channel, every unit is convertible or identical.
    UNITS_CONVERTIBLE = "units_convertible"
    #: The filled roles are the ones this type declares.
    ROLES_VALID_FOR_TYPE = "roles_valid_for_type"
    #: The marks fit between the two committed chart-point knobs - and for a
    #: histogram, whose marks are its bins, there is a value for every bin.
    ENOUGH_DATA = "enough_data"
    #: No element fills one channel twice.
    NO_DUPLICATE_IN_ROLE = "no_duplicate_in_role"
    #: Every drawn figure reads out of the characters the element names.
    NO_INVENTED_VALUES = "no_invented_values"
    #: Every numeral in the prose is one a cited element states.
    NUMERALS_MATCHED = "numerals_matched"
    #: The plan met the vocabulary this build holds.
    PLAN_VERSION_CURRENT = "plan_version_current"


class VisualFamily(StrEnum):
    """Which vocabulary a plan's type belongs to.

    Coarser than the type and stable across a downgrade within a family, which
    is what makes it a stratum term: a `pie` stepped down to a `stacked_bar` is
    still a composition, and comparing the two as one group is comparing like
    with like. A cross-family move is refused by the ladder, so a family never
    changes under an attempt.

    Four families, and every declarable type belongs to exactly one - the check
    is at the bottom of this module rather than in a docstring, because a type
    in no family would be folded into a group nobody chose.
    """

    #: The eleven forms drawn on axes, and the only family with a renderer today.
    CHART = "chart"
    #: The parts of a declared whole, laid out rather than plotted.
    COMPOSITION = "composition"
    #: Nodes and edges: what leads to what.
    DIAGRAM = "diagram"
    #: The five short forms that state a fact rather than plot one.
    INFOGRAPHIC = "infographic"


_T = VisualType
_F = VisualFamily

#: Which family each declarable type belongs to. Declared as a total mapping
#: rather than as four sets, because the import-time check below can then ask
#: one question - is every type here - instead of three.
FAMILY_OF: Final[dict[VisualType, VisualFamily]] = {
    _T.BAR: _F.CHART,
    _T.DOT: _F.CHART,
    _T.LINE: _F.CHART,
    _T.AREA: _F.CHART,
    _T.SCATTER: _F.CHART,
    _T.BUBBLE: _F.CHART,
    _T.SLOPE: _F.CHART,
    _T.STACKED_BAR: _F.CHART,
    _T.PIE: _F.CHART,
    _T.HISTOGRAM: _F.CHART,
    _T.TIMELINE: _F.CHART,
    _T.TABLE: _F.COMPOSITION,
    _T.FLOW: _F.DIAGRAM,
    _T.COMPARISON: _F.INFOGRAPHIC,
    _T.CALLOUT: _F.INFOGRAPHIC,
    _T.QUOTECARD: _F.INFOGRAPHIC,
    _T.WHOWHAT: _F.INFOGRAPHIC,
    _T.KEYFACTS: _F.INFOGRAPHIC,
}

_UNPLACED = set(VisualType) - set(FAMILY_OF)
if _UNPLACED:
    raise TypeError(f"every visual type needs a family, and these have none: {sorted(_UNPLACED)}")


class ElementBand(StrEnum):
    """How many facts the article offered, as a band rather than a count.

    A band and not the raw count, because the count is the thing being folded:
    a key carrying it would put almost every attempt in a group of its own and
    the fold would summarise nothing. The raw counts survive as the distribution
    on the folded row, so a reader keeps both the stratum and the spread inside
    it.

    **The boundaries are powers of two, and the measurement agrees with them.**
    Counted 2026-09-13 over the 21 committed `state/item-health/` day files,
    1,716 rows carrying `elements_found`: p25 is 3, the median is 7 and p75 is
    16, against boundaries of 4, 8 and 16. The five bands then hold 8.0, 20.0,
    22.6, 23.7 and 25.7 percent of that population, so no band is a rounding
    error and none of them is half the archive. Spread is zero - the committed
    rows are a fixed set, counted exactly.

    **The boundaries are in this module and not in `config/`, and that is the
    one place this shape argues with Guardrail #6.** A band is a persisted key
    term on an irreversible fold: move a boundary and two folded months stop
    being comparable, with nothing left to re-fold either of them from. So it
    moves the way a contract moves - a changelog entry and a read-side migration
    - rather than the way a knob moves, which is an edit nobody records.
    """

    #: No element at all, so no picture was ever arithmetically possible.
    NONE = "none"
    #: One to three. Below the width any chart needs once a channel is paired.
    FEW = "few"
    #: Four to seven.
    SOME = "some"
    #: Eight to fifteen.
    MANY = "many"
    #: Sixteen or more.
    RICH = "rich"


#: The lower bound of each band, highest first, so `band_of` returns on the
#: first match and the table reads as the thresholds it is.
_BAND_FLOORS: Final[tuple[tuple[int, ElementBand], ...]] = (
    (16, ElementBand.RICH),
    (8, ElementBand.MANY),
    (4, ElementBand.SOME),
    (1, ElementBand.FEW),
    (0, ElementBand.NONE),
)


def band_of(elements_found: int | None) -> ElementBand | None:
    """Which band a count falls in, or nothing when no count was recorded.

    `None` in and `None` out, deliberately. An attempt whose extraction pass
    never ran has no count, and putting it in the `none` band would say the
    article stated no facts - which is a measurement, where the truth is that
    nobody measured.
    """
    if elements_found is None:
        return None
    for floor, band in _BAND_FLOORS:
        if elements_found >= floor:
            return band
    raise ValueError(f"a negative element count has no band: {elements_found}")


class VisualAttemptRow(Contract):
    """One attempt at one picture, on one run: the full grain the fold replaces.

    **One row per attempt, never one per published visual.** A per-publication
    ledger leaves every refusal uncommitted, so the machine loop stops being
    auditable while still being the gate, and a later run cannot tell a refused
    visual from one never attempted.

    This is the shape the fold reads. It carries the eight terms of `FOLD_KEY`
    and the two measured columns the folded row keeps a distribution of, and
    nothing else yet: the join key a human label needs, and a typed reason for
    every one of the six gates, arrive with the row that writes the ledger.
    Both are additive.
    """

    __schema_stem__: ClassVar[str] = "visual-attempt-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13T23:50",
            change=(
                "Initial shape: one row per attempt at a visual, carrying the eight "
                "terms the fold groups on and the two columns it keeps a distribution "
                "of. No writer yet."
            ),
            why=(
                "The fold this store takes at the window edge deletes the full-grain "
                "shard, so the group key has to be settled before the first row is "
                "written - a key settled narrow cannot be widened later against data "
                "that no longer exists. Settling it needs the shape it is a key OVER, "
                "so the attempt row is declared here at the grain the fold reads and "
                "widened by the row that builds the writer."
            ),
        ),
    )

    date: DateStamp
    run_id: RunId
    item_id: ItemId
    decision: PlanDecision = Field(
        description="Whether this attempt proposed a picture at all. Half of the key."
    )
    none_reason: NoneReason | None = Field(
        default=None,
        description=(
            "Which gate decided this item carries no picture. Empty on an attempt "
            "that proposed one, and on a refusal by a producer that recorded no gate - "
            "empty reads as nothing said which, never as a gate named none."
        ),
    )
    rejection_reason: ValidatorCheck | None = Field(
        default=None,
        description=(
            "The FIRST validator check that did not hold. The validator runs its nine "
            "checks in order and a refused plan usually fails several, so one cell "
            "holds the first rather than a list: a list in a CSV cell is unaggregatable, "
            "and the check an operator acts on is the one that fired first. Empty where "
            "no plan reached the validator."
        ),
    )
    potential_primary: ElementClass | None = Field(
        default=None,
        description=(
            "What the article's own numbers say it could have carried. Empty on the "
            "same terms as the item-health census: the extraction pass did not run, or "
            "its spans would not re-slice. Three classes and not five, which is that "
            "census's own settled reading - the other two are claims about language and "
            "have no query yet, and they arrive here as members rather than as a term."
        ),
    )
    family: VisualFamily | None = Field(
        default=None,
        description=(
            "Which vocabulary the attempted type belongs to. Empty where no plan named "
            "a type, which is every attempt refused before a plan was drafted."
        ),
    )
    elements_found: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Tier 1 elements the extraction pass kept for this article. The raw count, "
            "banded into the key by band_of and kept whole as a distribution on the "
            "folded row. Empty on the same terms as potential_primary."
        ),
    )
    downgrade_depth: int | None = Field(
        default=None,
        ge=0,
        description=(
            "The deepest rung of the downgrade ladder this attempt reached. Zero means "
            "the plan was accepted or refused as drafted. It is recorded on a refused "
            "attempt as well as a published one, because a keep rate by depth needs a "
            "denominator at that depth. Empty where no plan was drafted."
        ),
    )
    marks: int | None = Field(
        default=None,
        ge=0,
        description=(
            "How many marks the accepted plan drew, in the channel its type counts in. "
            "The ladder's own currency: each rung reads a percentile of the depth-0 "
            "published mark counts, so this is the population that floor is taken over. "
            "Empty on an attempt that proposed nothing."
        ),
    )
    state: VisualState = Field(
        description=(
            "What became of the visual. `rendered` is the one value that means a reader "
            "saw it, so it is the numerator of every keep rate here."
        )
    )

    @model_validator(mode="after")
    def _an_attempt_that_proposed_nothing_drew_nothing(self) -> Self:
        if self.decision is PlanDecision.VISUAL:
            if self.none_reason is not None:
                raise ValueError("an attempt that proposed a picture names no refusing gate")
            return self
        if self.state is not VisualState.ABSENT:
            raise ValueError("an attempt that proposed nothing cannot have rendered")
        if self.marks is not None:
            raise ValueError("an attempt that proposed nothing drew no marks")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the row."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. An absent optional is an empty cell."""
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent value, never the empty string."""
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        for name, field in cls.model_fields.items():
            if field.default is None and payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)


#: The group one month of attempts folds to, spelled once. Every name here is a
#: field of `VisualAggregateRow`, and every field of that row which is not here
#: is a count or a distribution figure - both halves are checked at import, so a
#: term added to the row without a decision about the key fails the build rather
#: than quietly widening or narrowing what a folded month can be asked.
FOLD_KEY: Final[tuple[str, ...]] = (
    "date",
    "decision",
    "none_reason",
    "rejection_reason",
    "potential_primary",
    "family",
    "element_band",
    "downgrade_depth",
)

#: The measured columns of the attempt row that survive the fold as a spread.
#: `decision_ms` is deliberately not one of them: how long the planner took is
#: the span tree's question, and the committed span rollup is held disjoint from
#: every ledger column for the reason a second account of one number is worse
#: than none.
DISTRIBUTED_COLUMNS: Final[tuple[str, ...]] = ("elements", "marks")

#: The five figures each distributed column keeps, in the order they appear on
#: the row. `n` is counted over the attempts that carried a value rather than
#: over the group, because a column empty on an attempt means unmeasured and
#: counting it as zero would say the attempt measured the value and got nothing.
DISTRIBUTION_FIGURES: Final[tuple[str, ...]] = ("n", "min", "p25", "p50", "p75", "max")


class VisualAggregateRow(Contract):
    """One `(date, decision, none_reason, rejection_reason, potential_primary,
    family, element_band, downgrade_depth)` group, folded from one month of
    attempts.

    **That eight-term tuple IS the key, and this description is where it is
    declared** - the convention `state/telemetry-aggregate/` already sets by
    naming its own `(date, stage)` pair in its description rather than leaving
    the group to be inferred from the code that writes it.

    Ordered by the key, so a folded month reads down the days and then down the
    causes rather than down the alphabet.

    **The fold can never grow the store.** A group holds at least one attempt, so
    the row count never rises, and this row is narrower than the attempt row it
    replaces. The pathological case is real and is bounded rather than argued
    away: a month in which every attempt lands in its own group folds to exactly
    as many rows as it had, each one smaller.
    """

    __schema_stem__: ClassVar[str] = "visual-aggregate-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13T23:50",
            change=(
                "Initial shape: one row per eight-term group, folded from a month of "
                "visual attempts, carrying counts and two distributions."
            ),
            why=(
                "state/visuals/ folds at observability.visuals_full_grain_months and the "
                "fold deletes the full-grain shard, so this shape is the whole of what a "
                "reader can ever ask of an old month. Four questions have to survive it: "
                "which gate refused most, how the keep rate moved with downgrade depth, "
                "how the strata differ, and how the measured columns are shaped. Folding "
                "on date alone answers none of the last three, and a mean answers the "
                "fourth with the one statistic that hides a bimodal spread."
            ),
        ),
    )

    date: DateStamp
    decision: PlanDecision
    none_reason: NoneReason | None = Field(default=None)
    rejection_reason: ValidatorCheck | None = Field(default=None)
    potential_primary: ElementClass | None = Field(default=None)
    family: VisualFamily | None = Field(default=None)
    element_band: ElementBand | None = Field(
        default=None,
        description=(
            "Which band the attempts' element counts fell in. Empty where no count was "
            "recorded, which is not the `none` band - one says nobody measured and the "
            "other says the article stated no facts."
        ),
    )
    downgrade_depth: int | None = Field(default=None, ge=0)

    attempts: int = Field(
        ge=1,
        description=(
            "Attempts the shard held for this group, counted as they were written. A "
            "group with no attempts is not written, so an absent group reads as never "
            "happened rather than as happened and measured nothing."
        ),
    )
    published: int = Field(
        ge=0,
        description=(
            "Of those, the attempts a reader saw - the ones whose state was rendered. "
            "The numerator of the keep rate; `attempts` is the denominator. Stored as "
            "two counts and never as the rate, because a rate cannot be added across "
            "groups and these two can."
        ),
    )

    elements_n: int = Field(
        ge=0, description="Attempts of this group that carried an element count."
    )
    elements_min: int | None = Field(default=None, ge=0)
    elements_p25: int | None = Field(default=None, ge=0)
    elements_p50: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Nearest-rank median of the element counts. Nearest rank rather than "
            "interpolation, so the figure is one an attempt really had and can be "
            "checked against the shard this replaced."
        ),
    )
    elements_p75: int | None = Field(default=None, ge=0)
    elements_max: int | None = Field(default=None, ge=0)

    marks_n: int = Field(ge=0, description="Attempts of this group that drew marks.")
    marks_min: int | None = Field(default=None, ge=0)
    marks_p25: int | None = Field(default=None, ge=0)
    marks_p50: int | None = Field(default=None, ge=0)
    marks_p75: int | None = Field(default=None, ge=0)
    marks_max: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _the_parts_fit_the_whole(self) -> Self:
        if self.published > self.attempts:
            raise ValueError("more published than attempted")
        for column in DISTRIBUTED_COLUMNS:
            counted: int = getattr(self, f"{column}_n")
            if counted > self.attempts:
                raise ValueError(f"more {column} readings than attempts")
            figures = [getattr(self, f"{column}_{name}") for name in DISTRIBUTION_FIGURES[1:]]
            if counted == 0:
                if any(value is not None for value in figures):
                    raise ValueError(f"a group that measured no {column} carries no spread")
                continue
            if any(value is None for value in figures):
                raise ValueError(f"a group that measured {column} carries its whole spread")
            ordered = [value for value in figures if value is not None]
            if ordered != sorted(ordered):
                raise ValueError(f"the {column} spread must run from smallest to largest")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the row."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. An absent optional is an empty cell."""
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent value, never the empty string."""
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        for name, field in cls.model_fields.items():
            if field.default is None and payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)


_MEASURES: Final[frozenset[str]] = frozenset(
    {"version", "attempts", "published"}
    | {f"{column}_{figure}" for column in DISTRIBUTED_COLUMNS for figure in DISTRIBUTION_FIGURES}
)
_DECLARED = set(VisualAggregateRow.model_fields)
_MISSING = set(FOLD_KEY) - _DECLARED
if _MISSING:
    raise TypeError(f"the fold key names fields the row has not got: {sorted(_MISSING)}")
if _DECLARED - set(FOLD_KEY) - _MEASURES:
    raise TypeError(
        "every field of the folded row is a key term or a measure, and these are "
        f"neither: {sorted(_DECLARED - set(FOLD_KEY) - _MEASURES)}"
    )
