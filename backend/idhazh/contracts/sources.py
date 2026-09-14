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

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, Slug, Url, records_json
from idhazh.contracts.taxonomy import Lifecycled, LifecycleStatus, SourceKind, SourceTier


class SourceForm(StrEnum):
    ARTICLE = "article"
    ABSTRACT = "abstract"


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
    form: SourceForm = Field(
        default=SourceForm.ARTICLE,
        description=(
            "What the feed publishes. Abstract feeds are declared by a curator, never "
            "detected from source text."
        ),
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Soft retirement: drop the weight, observe, then retire.",
    )


class SalienceFeedDef(Lifecycled):
    """A published fact about a URL already in the pool. It never discovers.

    A vote sets `on_front_page` on the item, so the page can say another desk
    led with this story. It was also worth `collect.front_page_bonus` in the
    selection score until 2026-09-13, when the term was removed: it fired on 8
    of 5,682 published stories - 0.1 percent - while being worth more than the
    step between two source tiers, and a move nobody can attribute to a term is
    not a ranking term. The vote is still recorded, so restoring the term costs
    one weight once the signal is actually being supplied.

    There is no per-feed weight here and there never was a use for one. An
    aggregator has no subject taxonomy to be graded on.
    """

    id: Slug
    title: str = Field(min_length=1)
    url: Url


class Sources(Contract):
    """`config/sources.json` - what the Collect stage consults."""

    __schema_stem__: ClassVar[str] = "sources"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-13T18:00",
            change=(
                "A salience feed's description no longer says a vote is worth "
                "collect.front_page_bonus. No field was added, removed or retyped, so a "
                "config/sources.json written before this still loads and needs no "
                "read-side migration."
            ),
            why=(
                "collect.front_page_bonus was removed in the same commit, so the "
                "sentence named a config key that no longer exists. A vote is now a "
                "published fact about the item rather than a term of the score, and the "
                "description says which of the two it is."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:47",
            change="Added feed form with an abstract value.",
            why=(
                "A reader must be told when the summary is of an abstract, but detecting "
                "that from page text would turn a stranger's words into control data. The "
                "form is declared per feed instead."
            ),
        ),
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

    def to_json(self) -> str:
        """One feed a line - see `records_json`.

        A person curates this file and a reviewer reads the diff, and a feed's
        fields only mean anything together: the id says nothing without the
        vertical, the tier nothing without the title.
        """
        return records_json(self.model_dump(mode="json"))

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
