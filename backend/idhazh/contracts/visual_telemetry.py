"""What one visual-design attempt records, including refusal and failed delivery.

The registered visual-design-attempts ledger uses immutable raw Parquet files
and lossless daily/monthly packing. Expired months are deleted, not summarized.
The older aggregate contract below remains readable but has no production writer.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, ItemId, RunId, Sha256
from idhazh.contracts.item_health import ElementClass
from idhazh.contracts.visual import PlanDecision, VisualType
from idhazh.contracts.visual_decision import NoneReason, VisualState
from idhazh.contracts.visual_outcome import validate_visual_outcome
from idhazh.contracts.visual_validation import ValidatorCheck as ValidatorCheck


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
    """One actual visual-design attempt, whether delivered, refused or failed.

    **One row per attempt, never one per published visual.** A per-publication
    ledger leaves every refusal uncommitted, so the machine loop stops being
    auditable while still being the gate, and a later run cannot tell a refused
    visual from one never attempted.

    Older rows may lack typed outcomes and visual identity. New rows copy the
    decision's exact identity; compaction keeps the full record until expiry.
    """

    __schema_stem__: ClassVar[str] = "visual-attempt-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-29",
            change="Record requested and delivered types and nullable floor evidence.",
            why="Refused drafted plans and delivery failures remain distinct attempts.",
        ),
        ChangelogEntry(
            version="2026-10-27T11:32",
            change="Add the visual decision join key to full-grain attempts.",
            why="A human review label needs to identify the exact visual.",
        ),
        ChangelogEntry(
            version="2026-10-27T04:00",
            change="Name pie exhaustiveness refusals in attempt records.",
            why="A refused pie must say which check stopped it.",
        ),
        ChangelogEntry(
            version="2026-10-26T09:41",
            change="Name the stacked-bar exhaustiveness refusal in attempt records.",
            why="A refused chart must say which check stopped it.",
        ),
        ChangelogEntry(
            version="2026-09-13",
            change="Earlier changes are in this file's git history.",
            why="Git retains the earlier contract history.",
        ),
    )

    date: DateStamp
    run_id: RunId
    item_id: ItemId
    decision: PlanDecision = Field(
        description="Whether a plan was drafted, including one later refused."
    )
    none_reason: NoneReason | None = Field(
        default=None,
        description=(
            "Which implemented gate refused delivery. May accompany a drafted plan. "
            "Null on delivery, render failure, or an older unrecorded cause."
        ),
    )
    rejection_reason: ValidatorCheck | None = Field(
        default=None,
        description=(
            "First validator check rejecting the original request, retained through "
            "replacement or refusal. Null if no validator rejection occurred."
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
            "Elements measured by the article extraction pass. Null when unmeasured "
            "or when spans did not re-slice."
        ),
    )
    downgrade_depth: int | None = Field(
        default=None,
        ge=0,
        description=(
            "The deepest rung of the downgrade ladder this attempt reached. Zero means "
            "the plan was accepted or refused as drafted. It is recorded on a refused "
            "attempt as well as a delivered one. Null where no typed plan was drafted "
            "or where older decisions did not measure the search."
        ),
    )
    marks: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Delivered mark count from the decision; null without delivery."
        ),
    )
    state: VisualState = Field(
        description=(
            "Whether visual data was written, absent or failed to render. A written "
            "file does not prove publication or a human decision to keep it."
        )
    )
    visual_id: Sha256 | None = Field(
        default=None,
        description=(
            "The exact visual decision's human-label join key. Null on legacy attempt "
            "rows written before this field existed."
        ),
    )
    planned_type: VisualType | None = Field(
        default=None,
        description="Original typed request, including later refusal; null on older rows.",
    )
    rendered_type: VisualType | None = Field(
        default=None,
        description="Successfully written type; null without delivery or on older rows.",
    )
    gate_floor_applied: bool | None = Field(
        default=None,
        description=(
            "True if an evaluated numeric floor excluded a candidate, false if compared "
            "floors excluded none, null when no numeric floor was evaluated or unmeasured."
        ),
    )

    @model_validator(mode="after")
    def _an_attempt_that_proposed_nothing_drew_nothing(self) -> Self:
        if self.decision is PlanDecision.VISUAL:
            if self.none_reason is not None and self.state is not VisualState.ABSENT:
                raise ValueError("a refusing gate records an absent visual")
            if self.planned_type is not None:
                if self.downgrade_depth is not None:
                    validate_visual_outcome(
                        self.planned_type,
                        self.rendered_type,
                        0 if self.planned_type is self.rendered_type else self.downgrade_depth,
                        self.marks,
                    )
                if (self.rendered_type is not None) != (self.state is VisualState.RENDERED):
                    raise ValueError("a typed rendered outcome records its delivered type")
                if self.rendered_type is None and self.marks is not None:
                    raise ValueError("only delivery records marks")
            return self
        if self.planned_type is not None or self.rendered_type is not None:
            raise ValueError("a typed request is a drafted visual plan")
        if self.state is not VisualState.ABSENT:
            raise ValueError("an attempt that proposed nothing cannot have rendered")
        if self.marks is not None:
            raise ValueError("an attempt that proposed nothing drew no marks")
        return self

    @model_validator(mode="after")
    def _floor_evidence_requires_a_reached_rung(self) -> Self:
        if self.rendered_type is not None and self.planned_type is None:
            raise ValueError("a delivered type requires its original request")
        if self.gate_floor_applied is not None and (
            self.planned_type is None
            or self.downgrade_depth is None
            or self.downgrade_depth == 0
        ):
            raise ValueError("floor evidence requires a reached downgrade rung")
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
    declared** - the convention `state/item-health-summary/` already sets by
    naming its own `(date, stage)` pair in its description rather than leaving
    the group to be inferred from the code that writes it.

    Ordered by the key, so a folded month reads down the days and then down the
    causes rather than down the alphabet.

    **The fold can never grow the ledger.** A group holds at least one attempt, so
    the row count never rises, and this row is narrower than the attempt row it
    replaces. The pathological case is real and is bounded rather than argued
    away: a month in which every attempt lands in its own group folds to exactly
    as many rows as it had, each one smaller.
    """

    __schema_stem__: ClassVar[str] = "visual-aggregate-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-26T09:41",
            change="Accept the stacked-bar exhaustiveness check in folded attempt rows.",
            why="A refused chart must keep its cause after the full-grain shard folds.",
        ),
        ChangelogEntry(
            version="2026-09-13T23:50",
            change="Initial shape: one row per eight-term group, folded from a month of attempts.",
            why="The visual ledger folds at the window edge and needed a shape to fold into.",
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
