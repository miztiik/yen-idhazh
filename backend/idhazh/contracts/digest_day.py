"""The published day payload (`.../digest.json`) - what a reader actually gets.

One file per day carrying every item; a vertical route is a filter over this
same payload, never a second file. That is what keeps rendering any page at a
constant two requests however old the archive gets.

The order of `items` IS the published order: global, deterministic, and
identical for every reader. Read-state is a client-side mark that may change how
an item looks and may never change where it sits, whether it appears, or how it
ranks. An item introduced by a later run appends after the items already there,
which is why `introduced_by_run` may never decrease down the list.
"""

from __future__ import annotations

from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    Model,
    RelPath,
    Slug,
    Timestamp,
    Url,
)
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.route import VisualKind, VisualState
from idhazh.contracts.taxonomy import EventType, LensId


class DigestVisual(Model):
    kind: VisualKind
    state: VisualState
    path: RelPath | None = None
    alt: UntrustedLine | None = None

    @model_validator(mode="after")
    def _only_a_rendered_visual_has_a_path(self) -> Self:
        if (self.state is VisualState.RENDERED) != (self.path is not None):
            raise ValueError("a path is present exactly when the visual rendered")
        return self


class DigestRunRef(Model):
    """A run of this date, as the page footer and the new-arrivals block need it."""

    n: int = Field(ge=1)
    at: Timestamp
    items_added: int = Field(ge=0)


class DigestVerticalRef(Model):
    id: Slug
    display_name: str = Field(min_length=1)
    count: int = Field(ge=0)


class DigestItem(Model):
    """One item as a reader consumes it. The link is a first-class element, not a footnote."""

    item_id: ItemId
    vertical: Slug
    title: UntrustedLine
    source_url: Url
    source_id: Slug
    source_name: str = Field(min_length=1)
    published_at: Timestamp | None = None

    summary: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=1)
    lenses: list[LensId] = Field(default_factory=list)
    events: list[EventType] = Field(default_factory=list)
    entities: list[Slug] = Field(default_factory=list)

    band: ConfidenceBand
    truncated: bool = Field(
        default=False, description="The reader is told before they find out by clicking through."
    )
    visual: DigestVisual | None = None
    introduced_by_run: int = Field(
        ge=1, description="A global fact, true for every reader, asserted without any storage."
    )
    updated_at: Timestamp | None = Field(
        default=None,
        description="A later run changed this text; a revision is visible or it does not happen.",
    )

    @model_validator(mode="after")
    def _item_id_is_addressed_by_vertical(self) -> Self:
        if not self.item_id.startswith(f"{self.vertical}-"):
            raise ValueError("item_id must be addressed <vertical>-<NN>")
        return self


class DigestDay(Contract):
    """`frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json`."""

    __schema_stem__: ClassVar[str] = "digest-day"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: the day's items in published order, its runs, and its counts.",
            why="Contracts before logic - the published surface is fixed before it renders.",
        ),
    )

    date: DateStamp
    generated_at: Timestamp
    partial: bool = Field(description="A run with failures publishes, and says it was partial.")
    items_planned: int = Field(ge=0)
    items_failed: int = Field(ge=0)
    retention_window_months: int = Field(
        default=-1,
        ge=-1,
        description="Stated to the reader before anything is deleted. -1 means nothing is deleted.",
    )
    runs: list[DigestRunRef] = Field(min_length=1)
    verticals: list[DigestVerticalRef]
    items: list[DigestItem]

    @model_validator(mode="after")
    def _order_is_global_and_append_only(self) -> Self:
        item_ids = [item.item_id for item in self.items]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("item ids must be distinct within a day")

        introduced = [item.introduced_by_run for item in self.items]
        if introduced != sorted(introduced):
            raise ValueError("a later run appends; it never reorders what a reader already read")

        run_numbers = [run.n for run in self.runs]
        if run_numbers != list(range(1, len(self.runs) + 1)):
            raise ValueError("runs are numbered from 1 without gaps")
        if introduced and max(introduced) > len(self.runs):
            raise ValueError("an item cannot be introduced by a run that is not recorded")
        for run in self.runs:
            if introduced.count(run.n) != run.items_added:
                raise ValueError(f"run {run.n} items_added disagrees with the items it introduced")

        counted = {ref.id: ref.count for ref in self.verticals}
        if len(counted) != len(self.verticals):
            raise ValueError("vertical ids must be distinct")
        for item in self.items:
            if item.vertical not in counted:
                raise ValueError(f"item {item.item_id} names an unlisted vertical")
        for vertical_id, count in counted.items():
            actual = sum(1 for item in self.items if item.vertical == vertical_id)
            if actual != count:
                raise ValueError(f"vertical {vertical_id} count disagrees with its items")

        if self.partial != (self.items_failed > 0):
            raise ValueError("partial is exactly whether anything failed")
        if len(self.items) + self.items_failed > self.items_planned:
            raise ValueError("published plus failed cannot exceed planned")
        return self
