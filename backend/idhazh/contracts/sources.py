"""The curated feed lists (`config/sources.json`).

A vertical carries a feed list. A lens and an entity never do - a lens is a tag
applied after the fetch, and an entity's feeds live in `config/watchlist.json`.

A link aggregator is a vote, not a source: it contributes rank to a URL already
in the pool and never discovers, because a site with no subject taxonomy cannot
be asked for a subject. That is why salience feeds are a separate list.

Retired feeds are a third list for the same kind of reason. `feeds` is the list
the Collect stage loops, so anything in it costs a request every run and reaches
a reader; `retired` is a tombstone shelf, read by nobody who fetches and by
everybody who has to put a name on an id.
"""

from __future__ import annotations

from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, Slug, Url
from idhazh.contracts.taxonomy import Lifecycled, LifecycleStatus, SourceKind, SourceTier


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
    """A ranking signal. It adds weight to a URL already in the pool; it never discovers.

    What a vote is worth is `collect.front_page_bonus` - one number for every
    aggregator, not one per feed. An aggregator has no subject taxonomy to be
    graded on, so there is nothing for a per-feed weight to express.
    """

    id: Slug
    title: str = Field(min_length=1)
    url: Url


class Sources(Contract):
    """`config/sources.json` - what the Collect stage consults."""

    __schema_stem__: ClassVar[str] = "sources"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-22T10:00",
            change="Split retired feeds out of feeds into their own list.",
            why=(
                "A retired feed sat in the list Collect loops, so it cost a request every "
                "run and its articles still reached a reader - the retirement was recorded "
                "and not honoured. Two lists make the live one lean and the rule structural "
                "rather than a filter every caller has to remember."
            ),
        ),
        ChangelogEntry(
            version="2026-08-22T09:00",
            change="Removed weight from a salience feed.",
            why=(
                "Nothing read it. A vote is worth collect.front_page_bonus - one number "
                "for every aggregator - so a per-feed weight was a knob that looked "
                "tunable and moved nothing."
            ),
        ),
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

    feeds: list[FeedDef] = Field(
        description="The live list. Collect loops exactly this, so nothing retired belongs here.",
    )
    salience: list[SalienceFeedDef]
    retired: list[FeedDef] = Field(
        default_factory=list,
        description="Tombstones. Never fetched, never ranked, still able to name an id.",
    )

    def known_feeds(self) -> list[FeedDef]:
        """Every feed this project has ever read, live or retired.

        A published item carries a `source_id`, and that id has to resolve to a
        title and a kind long after the feed stopped being read - when an older
        run is re-assembled, or when a source is retired between the plan and
        the assemble of the same day. Reading `feeds` alone would put the raw
        slug on the page and silently relabel an announcement as reporting,
        which is the one thing `kind` exists to prevent.
        """
        return [*self.feeds, *self.retired]

    @model_validator(mode="after")
    def _each_list_holds_what_it_says(self) -> Self:
        for feed in self.feeds:
            if feed.status is LifecycleStatus.RETIRED:
                raise ValueError(f"retired feed {feed.id} belongs in `retired`, not `feeds`")
        for feed in self.retired:
            if feed.status is not LifecycleStatus.RETIRED:
                raise ValueError(f"feed {feed.id} sits in `retired` without a retired status")
        return self

    @model_validator(mode="after")
    def _ids_are_distinct(self) -> Self:
        known = self.known_feeds()
        ids = [feed.id for feed in known] + [feed.id for feed in self.salience]
        if len(set(ids)) != len(ids):
            raise ValueError("feed ids must be distinct across feeds, retired and salience")
        urls = [feed.url for feed in known]
        if len(set(urls)) != len(urls):
            raise ValueError("feed urls must be distinct across feeds and retired")
        return self
