"""The chart data a reader's browser draws: one published file per visual.

**The reader's browser draws the chart; the pipeline never draws one** (owner
ruling, 2026-09-13,
[`docs/architecture/publishing/visuals.md`](../../../docs/architecture/publishing/visuals.md)).
Code finds the quantities, the model labels them and selects elements by id,
the compiler turns plan plus elements into the data and its shape, and this is
that data - the last thing the pipeline writes and the first thing the drawing
code reads.

**It carries the data and its shape, and nothing else.** No geometry, no
authored prose, no colour, no width. `VisualPlan` refuses all four on the way in
and publishing the compiled result must not become the hole one gets through
(owner, 2026-09-13). What travels is what the compiler cut or derived from Tier
1 elements, so the strictest thing that can be said about a drawn figure is
still true after it is published: the article wrote it, or the four-function
allow-list computed it from figures the article wrote.

**Marks are a flat pool and the encoding names which of them fill which
channel.** That is what makes a new visual type cost an enum member rather than
a new document format - `line`, `pie` and `histogram` fill different roles over
the same two members. It is also what makes a malformed drawing sayable: a
`bar` whose `category` and `quantity` channels hold different counts is a
picture that cannot be drawn, and a shape where each mark already carried its
own name and its own length could not express one.

**One home for `renderer_version`.** The day payload points at this file and
records no version of its own. Two homes is how `spec_format` failed - a second
name for a fact already carried, whose only possible contribution was to
disagree with it (`visual_decision.py`, 2026-09-05T18:00).
"""

from __future__ import annotations

from typing import Annotated, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import ChangelogEntry, Contract, ItemId, Model, SchemaVersion
from idhazh.contracts.derived import DerivedNumber, DerivedUnit, DerivedValue
from idhazh.contracts.element import ElementId
from idhazh.contracts.visual import MAX_IDS_PER_ROLE, EncodingRole, VisualType

#: The date-stamp of the drawing contract: the compiler that writes this data
#: and the code that turns it into pixels, together. It is stamped by code and
#: read by the page, which refuses a version it does not know rather than
#: guessing at what a later shape meant.
#:
#: It is minted before anything draws from it, and that is the point. The owner
#: ruling's named cost is that a drawing stops being an archival artefact: a
#: committed SVG is a fixed record of what a reader saw on a given day, and a
#: spec plus drawing code can be redrawn differently by a later change with
#: nothing in the payload to show it moved. This field is what shows it.
RENDERER_VERSION: Final = "2026-09-13"

#: How a mark is addressed inside its own file. Local to one visual and never an
#: identity anything outside it holds, so it is short and positional rather than
#: derived from the element it came from: a derived mark comes from several
#: elements and a converted one from a table, so an element id could not name
#: every mark.
MARK_ID_PATTERN: Final = r"^m[0-9]{1,3}$"

#: The most marks one drawing can carry: every channel filled to the bound the
#: plan contract puts on a role. Written as the arithmetic so a wider plan
#: cannot leave a narrower published shape behind it.
MAX_MARKS: Final = MAX_IDS_PER_ROLE * len(EncodingRole)

MarkId = Annotated[str, StringConstraints(pattern=MARK_ID_PATTERN)]

_RoleMarks = Annotated[list[MarkId], Field(max_length=MAX_IDS_PER_ROLE)]


class VisualMark(Model):
    """One thing the drawing puts on the page, and where it came from.

    A mark is one entry in one channel - a bar's name or a bar's length, never
    both halves of a bar. That is what lets a channel have a length of its own,
    and a channel with a length of its own is the only way a drawing can be
    caught holding four names and three figures.

    **Every mark states its provenance and exactly one kind of it**, the same
    rule `DisplayedValue` holds: the Tier 1 element whose own characters or own
    figure it draws, or the derived value with its complete chain back to
    several of them. Written as two optionals with no rule, a mark that came
    from nowhere is a payload somebody can write.
    """

    mark_id: MarkId = Field(
        description="How the encoding below addresses this mark. Unique within one visual."
    )
    text: UntrustedLine | None = Field(
        description=(
            "What a naming mark says: the element's own characters, cut and sanitized "
            "where the trust boundary was crossed. Null on a mark that measures rather "
            "than names."
        )
    )
    value: DerivedNumber | None = Field(
        description=(
            "How big a measured mark is, as a decimal pinned to text the way a Tier 1 "
            "value is. Null on a mark that names rather than measures."
        )
    )
    unit: DerivedUnit | None = Field(
        description=(
            "What `value` measures. Null on a naming mark, and null on a count, which "
            "measures nothing."
        )
    )
    element_id: ElementId | None = Field(
        description="The Tier 1 element this mark was cut from. Null on a derived mark."
    )
    derived: DerivedValue | None = Field(
        description=(
            "The arithmetic and its chain, where no single element states the figure "
            "drawn. Null on a mark cut straight out of the article."
        )
    )

    @model_validator(mode="after")
    def _a_mark_came_from_one_of_the_two_places(self) -> Self:
        if (self.element_id is None) == (self.derived is None):
            raise ValueError(
                "a mark is an element the article wrote or a derived value with a chain "
                "- never both, and never neither"
            )
        return self

    @model_validator(mode="after")
    def _a_mark_says_something_or_measures_something(self) -> Self:
        """A mark carrying neither draws an empty space under a name nobody wrote."""
        if self.text is None and self.value is None:
            raise ValueError("a mark names something or measures something")
        if self.unit is not None and self.value is None:
            raise ValueError("a unit is what a value measures, so a mark with no value states none")
        return self

    @model_validator(mode="after")
    def _a_derived_mark_is_drawn_at_the_figure_its_chain_computed(self) -> Self:
        """The drawn figure sits at the top, and the chain may not disagree with it.

        A reader reads `value`, and an auditor reads `derived`. Two copies of one
        number is two numbers until something pins them, so this pins them - and
        the top-level copy is kept rather than dropped because a drawing that had
        to look inside a chain to find its own length would make "a mark whose
        value is absent" mean two different things.
        """
        if self.derived is None:
            return self
        if self.value != self.derived.value or self.unit != self.derived.unit:
            raise ValueError("a derived mark is drawn at the figure and unit its chain computed")
        return self


class VisualEncoding(Model):
    """Which marks fill which channel of the drawing.

    One field per member of `EncodingRole`, in that order, mirroring
    `PlanEncodings`. Every role is present and an unused one is empty, so "which
    channels does this drawing use" is a question about which are non-empty
    rather than about which are there - and a reader of this file learns the
    same nine words it would learn from the plan.
    """

    category: _RoleMarks = Field(description="The discrete axis: what each mark is.")
    quantity: _RoleMarks = Field(description="The measured axis: how big each mark is.")
    quantity_x: _RoleMarks = Field(description="The second measured axis, where a type has two.")
    time: _RoleMarks = Field(description="The temporal axis.")
    series: _RoleMarks = Field(description="What splits the marks into groups.")
    size: _RoleMarks = Field(description="The third channel, drawn as area.")
    bins: _RoleMarks = Field(description="The quantity that is binned rather than plotted.")
    entity: _RoleMarks = Field(description="Who or what a mark is about.")
    event_label: _RoleMarks = Field(description="What names one dated event.")

    def filled(self) -> dict[EncodingRole, list[str]]:
        """The channels this drawing actually draws with, by role."""
        drawn: dict[EncodingRole, list[str]] = {}
        for role in EncodingRole:
            marks: list[str] = getattr(self, role.value)
            if marks:
                drawn[role] = marks
        return drawn


class VisualData(Contract):
    """One published visual: its marks, its channels, its type and what draws it.

    Published at `frontend/public/digest/<YYYY>/<MM>/<DD>/<item_id>.json`, beside
    the day payload that points at it. **The shard is the day directory**, which
    is what every other published store uses and what a reader fetches. The chart
    data is kept out of `digest.json` because the day payload is never deleted,
    so anything inside it would be undeletable and `retention.image_months` would
    have nothing to act on (owner, 2026-09-13).
    """

    __schema_stem__: ClassVar[str] = "visual-data"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13T20:00",
            change=(
                "Initial shape: the marks with their values and provenance, the "
                "encoding that says which of them fills which channel, the type, and "
                "renderer_version."
            ),
            why=(
                "The owner ruled on 2026-09-13 that the reader's browser draws the "
                "chart and the pipeline never draws one, so the compiled data has to "
                "reach the reader. It could not: VisualDecision.spec lands under "
                "gitignored backend/var/, travels as a one-day artifact, and the "
                "published DigestVisual carried only where the drawing was. This is "
                "that data as a published contract. It lands ahead of the drawing code "
                "on purpose - while the build-time renderer still runs, the data on the "
                "wire can be checked against the picture the old renderer drew, and the "
                "moment that renderer is deleted the comparison is gone for good."
            ),
        ),
    )

    item_id: ItemId = Field(
        description="The story this drawing belongs to, and the stem of this file's own name."
    )
    type: VisualType = Field(
        description=(
            "The form the drawing takes. A type the drawing code does not know is "
            "refused rather than approximated - a chart that is nearly the plan is a "
            "chart nobody asked for."
        )
    )
    renderer_version: SchemaVersion = Field(
        description=(
            "The date-stamp of the drawing contract this data was compiled for. The "
            "page refuses a version it does not know, so a later change that would move "
            "pixels cannot redraw an older day without saying so."
        )
    )
    marks: list[VisualMark] = Field(
        min_length=1,
        max_length=MAX_MARKS,
        description="Every figure and every name the drawing puts on the page.",
    )
    encoding: VisualEncoding = Field(
        description="Which marks fill which channel. Every role a key, an unused one empty."
    )

    @model_validator(mode="after")
    def _every_mark_is_addressed_once_and_drawn_once(self) -> Self:
        """Ids resolve, ids are distinct, and nothing is carried that is not drawn.

        A channel naming a mark that is not there is a hole in the picture. A
        mark no channel names is weight a reader downloads and never sees, which
        is the same fault `validate-days` already holds a day's picture directory
        to. Two marks under one id is worse than either: whichever the drawing
        picks, the other one's provenance is what an auditor would read.
        """
        ids = [mark.mark_id for mark in self.marks]
        repeated = sorted({name for name in ids if ids.count(name) > 1})
        if repeated:
            raise ValueError(f"two marks share one id: {repeated}")

        held = set(ids)
        drawn: list[str] = [name for marks in self.encoding.filled().values() for name in marks]
        missing = sorted(set(drawn) - held)
        if missing:
            raise ValueError(f"a channel names a mark this drawing does not carry: {missing}")
        twice = sorted({name for name in drawn if drawn.count(name) > 1})
        if twice:
            raise ValueError(f"one mark is drawn in two channels: {twice}")
        idle = sorted(held - set(drawn))
        if idle:
            raise ValueError(f"a mark no channel draws: {idle}")
        return self
