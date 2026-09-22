"""Whether an item gets a chart or nothing.

"Nothing" is a real, frequent and correct answer. The failure mode being
designed against is decoration: a generated picture of a chart with invented
axis labels looks like evidence, and a reader who once notices an invented
number stops trusting every summary on the page.

A render failure degrades the item to no visual. It never fails the item and it
never fails the run.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import ChangelogEntry, Contract, ItemId, RelPath, Slug, Timestamp, UrlKey

#: What one item's decision is filed as, under `backend/var/run/<date>/items/`.
#: The writer, the reader and the workflow's upload glob all spell it, and a run
#: where they disagree uploads an empty artifact and publishes with no pictures.
PAYLOAD_SUFFIX: Final = ".visual.json"


class VisualKind(StrEnum):
    CHART = "chart"
    NONE = "none"


class VisualState(StrEnum):
    """What became of the visual. "Could not make it" and "made it then threw it
    away" are different facts, so they never share a member."""

    ABSENT = "absent"
    RENDERED = "rendered"
    RENDER_FAILED = "render_failed"


class NoneReason(StrEnum):
    """Which gate decided this item carries no picture.

    `none` is the majority outcome by design - two items in three - so a `none`
    with no cause makes the largest number an operator reads the one that
    explains nothing.

    **One member per gate, never one per call site.** The reachability gate
    refuses in two places and both record `not_reachable`, because what an
    operator acts on is the gate rather than the line of code.

    **And one member per gate that has a writer.** The design record names six
    gates and the two-call flow adds a seventh; the potential class, the novelty
    floor, the sufficiency bar and the per-visual byte cap are not built, so a
    member for each would be a word nobody can produce, nobody can retire and
    nobody can tell from a bug. Each arrives as an additive member with the row
    that builds its gate.

    The single-call planner these five replace writes nothing here. Its causes
    are sentences in `rationale` and several of them - no summary to illustrate,
    a reply that lost its shape, a kind with no renderer - are not gates at all,
    so typing them into this vocabulary would be work the row that retires that
    planner deletes.
    """

    #: The reachability gate refused before a plan was drafted: no choice over
    #: this article's elements could have survived the validator. The call still
    #: ran and still wrote the summary, with the plan fields suppressed.
    NOT_REACHABLE = "not_reachable"
    #: The model was asked and answered `none`. The ordinary answer, and the one
    #: the design wants to stay common.
    MODEL_DECLINED = "model_declined"
    #: A plan was drafted, the validator refused it, and the downgrade ladder
    #: reached no depth that validates. WHICH check refused is `ValidatorCheck`'s
    #: to say; one fact with two homes is a fact that can disagree with itself.
    VALIDATION_FAILED = "validation_failed"
    #: The reply ran out of output budget after the summary closed, so the plan
    #: was never written. The item publishes; the picture is what was lost.
    OUTPUT_BUDGET_CUT = "output_budget_cut"
    #: The reply was cut at the end of the context window rather than at the end
    #: of its budget: the article and the label call's reply in front of it left less room
    #: than the summarize-and-plan call's grammar may write. Separate from `output_budget_cut`
    #: because the two ask an operator for different things - a budget cut says look at
    #: the reply shape, and this one says look at
    #: `--ctx-size` on the summarize entry beside `extract.truncation_cap_tokens`.
    WINDOW_EXHAUSTED = "window_exhausted"


class VisualDecision(Contract):
    """The visual planner's decision plus the Render stage's outcome, one per item."""

    __schema_stem__: ClassVar[str] = "visual-decision"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13T22:30",
            change="Retired asset_path.",
            why="The build-time renderer is deleted, so nothing writes an SVG to name.",
        ),
        ChangelogEntry(
            version="2026-09-13T20:00",
            change="Added data_path, where this item's published visual data landed.",
            why="The reader's browser draws the chart, so it needs the marks rather than an SVG.",
        ),
        ChangelogEntry(
            version="2026-09-13",
            change="NoneReason takes a fifth member, window_exhausted.",
            why="A reply that runs into the wall of the context window had no name of its own.",
        ),
        ChangelogEntry(
            version="2026-09-12T18:40",
            change="item_id accepts a second shape: sixteen Crockford base32 symbols.",
            why="Ten decimal digits is 33 bits of an address, which collides on a busy day.",
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
        ),
    )

    item_id: ItemId
    url_key: UrlKey
    kind: VisualKind
    rationale: UntrustedLine | None = None
    spec: str | None = Field(
        default=None,
        description=(
            "The compiled drawing instruction, built here from the article's own "
            "numbers and read back by whatever draws it. Since 2026-09-13 that is the "
            "reader's browser and this holds the published visual-data document, the "
            "same bytes the file beside the day carries. The grammar is the drawing "
            "code's rather than this contract's - it was Vega-Lite JSON while the "
            "build-time renderer ran - and naming one here would date the field to a "
            "renderer this project has already changed twice. Null on an item decided "
            "to nothing."
        ),
    )
    data_path: RelPath | None = Field(
        default=None,
        description=(
            "Relative POSIX path under frontend/public/ to this visual's published "
            "data, as digest/<Y>/<M>/<D>/<item_id>.json beside the day payload that "
            "points at it. Null on a payload written before the file existed, and null "
            "where the compile landed and the write did not - absent reads as no data "
            "carried."
        ),
    )
    alt_text: UntrustedLine | None = None
    visual_state: VisualState = VisualState.ABSENT
    model_id: Slug
    decided_at: Timestamp
    decision_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Wall-clock for this item: the planner call plus the render. Null on a payload "
            "written before the clock existed."
        ),
    )
    asked_the_model: bool = Field(
        default=True,
        description=(
            "False when the planner decided this item on its own facts and never posted. "
            "True on a payload written before the gate existed, because every item was "
            "asked then."
        ),
    )
    drafted_chart: bool = Field(
        default=False,
        description=(
            "True when the model's reply asked for a chart, whatever this decision "
            "became. The gap between this and a kind of chart is what the post-model "
            "checks rejected."
        ),
    )
    none_reason: NoneReason | None = Field(
        default=None,
        description=(
            "Which gate decided this item carries no picture. Null on a decision that "
            "carries one, and null on a payload written before the field existed or by "
            "the single-call planner, which has no gate vocabulary."
        ),
    )
    failure_detail: UntrustedLine | None = None

    @model_validator(mode="after")
    def _a_published_chart_was_drafted_as_one(self) -> Self:
        """The read side for a payload written before `drafted_chart` existed."""
        if self.kind is VisualKind.CHART and not self.drafted_chart:
            self.drafted_chart = True
        return self

    @model_validator(mode="after")
    def _outcome_matches_the_decision(self) -> Self:
        if self.kind is VisualKind.NONE:
            if self.spec is not None:
                raise ValueError("an item decided to nothing carries no spec")
            if self.visual_state is not VisualState.ABSENT:
                raise ValueError("an item decided to nothing has no visual to be in a state about")
        else:
            if not self.spec:
                raise ValueError("a planned visual must carry the spec it was planned as")
            if self.none_reason is not None:
                raise ValueError("only an item decided to nothing records the gate that refused it")

        # The data file is the only thing a compiled visual publishes, so the
        # rule that stood over `asset_path` stands here: `rendered` and a path
        # arrive together in one `model_copy`, and a path on anything else names
        # a file nothing wrote.
        if self.visual_state is VisualState.RENDERED:
            if self.data_path is None:
                raise ValueError("a rendered visual must record where its marks landed")
        elif self.data_path is not None:
            raise ValueError("only a rendered visual carries a data_path")

        if (self.visual_state is VisualState.RENDER_FAILED) != (self.failure_detail is not None):
            raise ValueError("a failed render records why, and only a failed render does")
        return self
