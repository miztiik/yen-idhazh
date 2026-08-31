"""The served day payload - what a reader's browser actually fetches.

`frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json` is the committed day and
it is read from disk at build time. This is the other file: the projection
`frontend/scripts/copy-visuals.mjs` stages into `frontend/static/digest/`, which
the published site serves at `<base>/digest/<YYYY>/<MM>/<DD>/digest.json` and a
browser fetches over the network.

**It is a contract because it has a consumer we cannot upgrade** (Rule #3).
Until 2026-08-31 the field list was a JavaScript array in a build script, which
was honest while the one reader was our own archive page rendering a search
result. It stops being honest the moment a reader's cached shell fetches this
file: the shell in their browser can be older than the payload it reads, so the
shape has to carry its own `version` and every change to it has to say what an
older shell does (section 11). That address cannot move afterwards either.

**The read-side rule, in one sentence: absent and null both mean unknown, and a
reader may never fill either with a default.** Every plausible default is a
false claim - `0` for `carried_by` says no feed carried the story, `false` for
`on_front_page` denies a vote nobody counted, `0.0` for `rank_score` puts the
story at the bottom of its desk. The projector writes an explicit null for a
key the committed day does not hold, so an older shell sees a key it knows with
a value it can read; a newer shell reading an older file sees the key missing.
Both are the same fact and neither is a value.

**The migration path a change to this shape has to take.** Additive: declare the
field optional, stamp the version, append the changelog entry - an older shell
ignores a key it does not know, so nothing else is owed. Breaking: the read-side
migration lands in the shell, not only in the build, because the two are not
upgraded together and a reader can hold a shell for as long as their cache does.

What it drops, and what that is worth. Measured 2026-08-31 on this checkout,
11 committed days and 3,596 items, `gzip -9` over the compact projection: the
committed day is 792.24 gzipped bytes an item, and this projection is 468.38 -
40.9 percent less. `embeddings` is the block that pays for the projection
existing at all: no browser opens it, its one production reader is the backend's
index rebuild, and it was 40.0 percent of a day page. `events` and `entities`
are dropped because nothing renders them and the reading-page plan forbids
publishing them as reader-facing chips; `source_form`, `updated_at` and
`updated_by_run` because no component reads them - `updated_at` is null in every
payload ever written.
"""

from __future__ import annotations

from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    ItemId,
    Model,
    RelPath,
    Slug,
    Timestamp,
    Url,
    compact_json,
)
from idhazh.contracts.eval_row import BandReason, ConfidenceBand
from idhazh.contracts.route import VisualState
from idhazh.contracts.run_plan import TimeSource
from idhazh.contracts.taxonomy import LensId, SourceKind


class DigestViewVisual(Model):
    """The rendered chart, as the `<img>` needs it.

    `kind` is not here. It is read at build time off the committed tree for the
    console's chart count, and a browser drawing the image has no use for it.
    """

    state: VisualState
    path: RelPath | None = None
    alt: UntrustedLine | None = None

    @model_validator(mode="after")
    def _only_a_rendered_visual_has_a_path(self) -> Self:
        if (self.state is VisualState.RENDERED) != (self.path is not None):
            raise ValueError("a path is present exactly when the visual rendered")
        return self


class DigestViewItem(Model):
    """One item, narrowed to what a page renders from it.

    Every field here has a named renderer. The list is not "the published item
    minus the big bits" - it is traced along the render path, and a field
    without a reader does not earn the wire.
    """

    item_id: ItemId
    vertical: Slug
    title: UntrustedLine
    summary: str = Field(min_length=1)
    reader_note: str | None = Field(
        default=None,
        description="Our sentence explaining a source limitation, never a badge.",
    )
    band: ConfidenceBand
    band_reason: BandReason | None = Field(
        default=None,
        description=(
            "Why the item is not in the top band. Null on a `high` item and on a day "
            "published before this existed - 14 of 3,596 committed items on 2026-08-31."
        ),
    )
    truncated: bool = Field(
        default=False, description="The reader is told before they find out by clicking through."
    )
    visual: DigestViewVisual | None = None
    source_name: str = Field(min_length=1)
    source_id: Slug
    source_kind: SourceKind = Field(
        default=SourceKind.REPORTING,
        description="Who is speaking. A vendor's own copy must not look like a reporter's.",
    )
    source_url: Url
    published_at: Timestamp | None = None
    time_source: TimeSource | None = Field(
        default=None,
        description=(
            "Which clock `published_at` came from. Null reads as unknown: a page that "
            "prints a time without naming its clock cannot say which of the two it has."
        ),
    )
    carried_by: int | None = Field(
        default=None,
        ge=1,
        description="How many feeds carried this one address. Null is unknown, never 1.",
    )
    watchlist_hit: bool | None = Field(
        default=None,
        description="The story names a watchlist entity. Null is unknown, never false.",
    )
    on_front_page: bool | None = Field(
        default=None,
        description="A salience feed voted for it. Null is unknown, never false.",
    )
    rank_score: float | None = Field(
        default=None,
        ge=0.0,
        description="What the planning step scored the story at. Null is unknown, never 0.",
    )
    introduced_by_run: int = Field(
        ge=1, description="A global fact, true for every reader, asserted without any storage."
    )
    lenses: list[LensId] = Field(default_factory=list)
    key_points: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _item_id_is_addressed_by_vertical(self) -> Self:
        if not self.item_id.startswith(f"{self.vertical}-"):
            raise ValueError("item_id must be addressed <vertical>-<NN>")
        return self

    @model_validator(mode="after")
    def _the_clock_and_the_time_agree(self) -> Self:
        if self.time_source is not None and self.time_source.names_a_clock != (
            self.published_at is not None
        ):
            raise ValueError("time_source names a clock exactly when published_at carries a time")
        return self


class DigestView(Contract):
    """`<base>/digest/<YYYY>/<MM>/<DD>/digest.json`, as a browser fetches it."""

    __schema_stem__: ClassVar[str] = "digest-view"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-31T12:00",
            change=(
                "Initial shape: the day's items narrowed to what a page renders, "
                "carrying a version of their own."
            ),
            why=(
                "The staged day payload was a thirteen-name array in a build script, "
                "which was enough while the only reader was our own archive page. A "
                "reading route is about to fetch this file, so a browser we cannot "
                "upgrade will parse it and its address stops being movable - which is "
                "a persisted shape and therefore a contract before logic reads it "
                "(Rule #3). The version is here from the first byte so that an older "
                "shell reading a newer payload has something to branch on. Nine names "
                "join the thirteen in the same commit, each with a named renderer: "
                "carried_by, watchlist_hit, on_front_page and rank_score for the lead "
                "block, published_at and time_source for the time rail, "
                "introduced_by_run for the run divider, lenses for the topic chips, and "
                "key_points for the in-page filter that reads them today. Measured "
                "2026-08-31 over 11 committed days and 3,596 items, gzip -9: 361.78 "
                "bytes an item before and 468.38 after, against 792.24 for the "
                "committed day."
            ),
        ),
    )

    items: list[DigestViewItem]

    @model_validator(mode="after")
    def _the_published_order_survives_the_projection(self) -> Self:
        item_ids = [item.item_id for item in self.items]
        if len(set(item_ids)) != len(item_ids):
            raise ValueError("item ids must be distinct within a day")
        introduced = [item.introduced_by_run for item in self.items]
        if introduced != sorted(introduced):
            raise ValueError("a later run appends; it never reorders what a reader already read")
        return self

    def to_json(self) -> str:
        """Compact, like the month index and unlike every committed payload.

        A reader downloads this whole and its entries are counted in hundreds.
        The indent every other payload pays for buys a reviewable diff, and
        nobody reviews a diff of a file that is regenerated on every build.
        """
        return compact_json(self.model_dump(mode="json"))
