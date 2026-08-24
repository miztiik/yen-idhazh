"""Whether an item gets a chart, a diagram, an illustration, or nothing.

"Nothing" is a real, frequent and correct answer. The failure mode being
designed against is decoration: a generated picture of a chart with invented
axis labels looks like evidence, and a reader who once notices an invented
number stops trusting every summary on the page.

A render failure degrades the item to no visual. It never fails the item and it
never fails the run.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import ChangelogEntry, Contract, ItemId, RelPath, Slug, Timestamp, UrlKey


class VisualKind(StrEnum):
    CHART = "chart"
    DIAGRAM = "diagram"
    IMAGE = "image"
    NONE = "none"


class SpecFormat(StrEnum):
    VEGA_LITE = "vega-lite"
    MERMAID = "mermaid"
    IMAGE_PROMPT = "image-prompt"


class VisualState(StrEnum):
    """What became of the visual. "Could not make it" and "made it then threw it
    away" are different facts, so they never share a member."""

    ABSENT = "absent"
    RENDERED = "rendered"
    RENDER_FAILED = "render_failed"


_FORMAT_FOR_KIND = {
    VisualKind.CHART: SpecFormat.VEGA_LITE,
    VisualKind.DIAGRAM: SpecFormat.MERMAID,
    VisualKind.IMAGE: SpecFormat.IMAGE_PROMPT,
}


class Route(Contract):
    """The Route stage's decision plus the Render stage's outcome, one per item."""

    __schema_stem__: ClassVar[str] = "route"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-24T23:10",
            change="Added asked_the_model, defaulting to true.",
            why=(
                "The router now decides an item without posting when no enabled visual "
                "kind could survive its checks. That decision must be a field, not a "
                "sentence a reader parses out of the rationale, because the run manifest "
                "counts it and a chart rate quoted against the wrong denominator is the "
                "first thing this gate would break. True on an older payload, which is "
                "correct: every item was asked before the gate existed."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T11:15",
            change="Added optional route_ms.",
            why=(
                "The route job sits between 51 and 60 minutes against a 60-minute bound and "
                "nothing recorded what it spent, so every argument about the budget was an "
                "estimate (Rule #10). Null on a payload written before the clock existed, "
                "which is what keeps the field additive."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: the four-way routing enum, the spec, and the render outcome.",
            why="Contracts before logic - Route and Render are written against a fixed payload.",
        ),
    )

    item_id: ItemId
    url_key: UrlKey
    kind: VisualKind
    rationale: UntrustedLine | None = None
    spec: str | None = Field(
        default=None, description="Vega-Lite JSON, Mermaid source, or the image prompt."
    )
    spec_format: SpecFormat | None = None
    asset_path: RelPath | None = Field(
        default=None, description="Relative POSIX path under frontend/public/, once rendered."
    )
    alt_text: UntrustedLine | None = None
    visual_state: VisualState = VisualState.ABSENT
    model_id: Slug
    routed_at: Timestamp
    route_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Wall-clock for this item: the router call plus the render. Null on a payload "
            "written before the clock existed."
        ),
    )
    asked_the_model: bool = Field(
        default=True,
        description=(
            "False when the router decided this item on its own facts and never posted. "
            "True on a payload written before the gate existed, because every item was "
            "asked then."
        ),
    )
    failure_detail: UntrustedLine | None = None

    @model_validator(mode="after")
    def _outcome_matches_the_decision(self) -> Self:
        if self.kind is VisualKind.NONE:
            if self.spec is not None or self.spec_format is not None:
                raise ValueError("a routed-to-nothing item carries no spec")
            if self.visual_state is not VisualState.ABSENT:
                raise ValueError("a routed-to-nothing item has no visual to be in a state about")
        else:
            if self.spec_format is not _FORMAT_FOR_KIND[self.kind]:
                expected = _FORMAT_FOR_KIND[self.kind].value
                raise ValueError(f"kind {self.kind.value} requires spec_format {expected}")
            if not self.spec:
                raise ValueError("a routed visual must carry the spec it was routed to")

        if self.visual_state is VisualState.RENDERED:
            if self.asset_path is None:
                raise ValueError("a rendered visual must record where it landed")
        elif self.asset_path is not None:
            raise ValueError("only a rendered visual carries an asset_path")

        if (self.visual_state is VisualState.RENDER_FAILED) != (self.failure_detail is not None):
            raise ValueError("a failed render records why, and only a failed render does")
        return self
