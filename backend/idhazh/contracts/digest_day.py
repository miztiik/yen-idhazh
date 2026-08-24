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

from typing import ClassVar, Literal, Self

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
from idhazh.contracts.eval_row import BandReason, ConfidenceBand
from idhazh.contracts.route import VisualKind, VisualState
from idhazh.contracts.sources import SourceForm
from idhazh.contracts.taxonomy import EventType, LensId, SourceKind


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
    source_kind: SourceKind = Field(
        default=SourceKind.REPORTING,
        description="Who is speaking. A vendor's own copy must not look like a reporter's.",
    )
    published_at: Timestamp | None = None

    summary: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=1)
    lenses: list[LensId] = Field(default_factory=list)
    events: list[EventType] = Field(default_factory=list)
    entities: list[Slug] = Field(default_factory=list)

    band: ConfidenceBand
    band_reason: BandReason | None = Field(
        default=None,
        description=(
            "Why the item is not in the top band. An identifier the site turns into a "
            "sentence; null on a `high` item and on a day published before this existed."
        ),
    )
    source_form: SourceForm = Field(
        default=SourceForm.ARTICLE,
        description="Declared feed form, so a reader can see when an item is an abstract.",
    )
    reader_note: str | None = Field(
        default=None,
        description="Our sentence explaining a source limitation, never a badge.",
    )
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


class DigestEmbeddings(Model):
    """The day's item vectors, so a browser only ever embeds a reader's query.

    Inside the day payload rather than beside it, because the per-page request
    count is fixed and a sidecar would add one to every page whether or not a
    reader ever searches.

    Self-describing on purpose: a reader-side decoder that guesses the width or
    the dtype produces plausible nonsense instead of an error. Every field here
    exists so that a mismatch fails loudly.

    This whole block is optional and strippable. A day with no `embeddings`
    renders identically; it simply cannot be searched on the device.
    """

    model_id: Slug
    dimensions: int = Field(ge=1)
    dtype: Literal["int8"]
    vectors: dict[str, str] = Field(
        default_factory=dict,
        description="item_id -> base64 of the quantised vector, one entry per embedded item.",
    )


class DigestDay(Contract):
    """`frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json`."""

    __schema_stem__: ClassVar[str] = "digest-day"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-24T11:15",
            change="Added optional band_reason to published items.",
            why=(
                "The medium band printed 'Mostly matches the source', which is a grade and "
                "not a sentence: it told a reader an item was worse without telling them "
                "what was missing. Both things that cap an item at medium were already "
                "computed and neither reached the page. Null on a high item and on every "
                "day published before this, which keeps an older payload rendering exactly "
                "as it does today."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:51",
            change="Added source_form and reader_note to published items.",
            why=(
                "Short and abstract sources can now publish, so the page needs our own "
                "sentence that tells the reader what kind of source was summarized without "
                "turning the limitation into a badge."
            ),
        ),
        ChangelogEntry(
            version="2026-08-22",
            change="Added the optional embeddings block.",
            why=(
                "On-device search needs the day's vectors committed, and the corpus is "
                "fixed at publish. Additive and optional - a day written before this, or "
                "a day whose encoder was unavailable, still validates and still renders."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21T06:00",
            change="Added source_kind to a published item.",
            why=(
                "Reader's ruling: a company announcing itself and a reporter measuring it "
                "arrived on the page looking identical, and that is the risk a reader "
                "carries when they forward something."
            ),
        ),
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
    embeddings: DigestEmbeddings | None = None

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
