"""The curated feed lists (`config/sources.json`).

A vertical carries a feed list. A lens and an entity never do - a lens is a tag
applied after the fetch, and an entity's feeds live in `config/watchlist.json`.

A link aggregator is a vote, not a source: it contributes rank to a URL already
in the pool and never discovers, because a site with no subject taxonomy cannot
be asked for a subject. That is why salience feeds are a separate list.
"""

from __future__ import annotations

from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, Slug, Url
from idhazh.contracts.taxonomy import Lifecycled, SourceKind, SourceTier


class FeedDef(Lifecycled):
    """One RSS/Atom feed, attached to exactly one vertical."""

    id: Slug
    vertical: Slug
    title: str = Field(min_length=1)
    url: Url
    tier: SourceTier
    kind: SourceKind = Field(
        default=SourceKind.REPORTING,
        description="Who is speaking. A reader needs this before they will share an item.",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Soft retirement: drop the weight, observe, then retire.",
    )


class SalienceFeedDef(Lifecycled):
    """A ranking signal. It adds weight to a URL already in the pool; it never discovers."""

    id: Slug
    title: str = Field(min_length=1)
    url: Url
    weight: float = Field(default=0.5, ge=0.0, le=1.0)


class Sources(Contract):
    """`config/sources.json` - what the Collect stage consults."""

    __schema_stem__: ClassVar[str] = "sources"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-21T06:00",
            change="Added kind to a feed.",
            why=(
                "A company announcing its own product and a reporter measuring it arrived "
                "looking identical. Reader named this as the one thing an item lacked "
                "before they would share it."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: per-vertical feeds plus a separate salience list.",
            why="Contracts before logic - Collect is written against a fixed source shape.",
        ),
    )

    feeds: list[FeedDef]
    salience: list[SalienceFeedDef]

    @model_validator(mode="after")
    def _ids_are_distinct(self) -> Self:
        ids = [feed.id for feed in self.feeds] + [feed.id for feed in self.salience]
        if len(set(ids)) != len(ids):
            raise ValueError("feed ids must be distinct across feeds and salience")
        urls = [feed.url for feed in self.feeds]
        if len(set(urls)) != len(urls):
            raise ValueError("feed urls must be distinct")
        return self

    def live_feeds_for(self, vertical_id: str) -> list[FeedDef]:
        return [
            feed for feed in self.feeds if feed.vertical == vertical_id and feed.retired_on is None
        ]
