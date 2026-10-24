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

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    Slug,
    Url,
    records_json,
)
from idhazh.contracts.taxonomy import (
    Lifecycled,
    LifecycleStatus,
    SourceKind,
    SourceTier,
)


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
        default="reporting",
        description="Who is speaking. A reader needs this before they will share an item.",
    )
    publisher_id: Slug | None = None
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


class PublisherDef(Model):
    """One reviewed editorial publication reserved in the source catalog."""

    id: Slug
    display_name: str = Field(min_length=1)
    added_on: DateStamp | None = None
    status: LifecycleStatus | None = None
    retired_on: DateStamp | None = None
    retirement_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _retirement_fields_match_status(self) -> Self:
        retired = self.status is LifecycleStatus.RETIRED
        has_retirement_fields = self.retired_on is not None or self.retirement_reason is not None
        if has_retirement_fields and (self.retired_on is None or self.retirement_reason is None):
            raise ValueError("publisher retirement needs both retired_on and retirement_reason")
        if retired and self.added_on is not None and not has_retirement_fields:
            raise ValueError("a newly retired publisher needs retired_on and retirement_reason")
        if self.status is not LifecycleStatus.RETIRED and has_retirement_fields:
            raise ValueError("retirement fields are only meaningful on a retired publisher")
        if self.retirement_reason is not None and (
            not self.retirement_reason.strip()
            or self.retirement_reason != self.retirement_reason.lower()
        ):
            raise ValueError("publisher retirement_reason must be nonempty lowercase text")
        if (
            self.retired_on is not None
            and self.added_on is not None
            and self.retired_on < self.added_on
        ):
            raise ValueError("retired_on cannot precede added_on")
        return self


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
            version="2026-10-24T20:04",
            change="Add publisher definitions and nullable feed references.",
            why="New observations can retain reviewed identity while legacy values remain unknown.",
        ),
        ChangelogEntry(
            version="2026-10-20",
            change="Source classification accepts open kind and numeric tier identifiers.",
            why="Registry membership can change without invalidating recorded payloads.",
        ),
        ChangelogEntry(
            version="2026-09-13T18:00",
            change="A salience feed's description no longer prices a front-page vote.",
            why="The knob that paid for the vote was removed in the same commit.",
        ),
        ChangelogEntry(
            version="2026-08-23T18:47",
            change="Added feed form with an abstract value.",
            why="A reader must be told when the summary is of an abstract and not an article.",
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
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
    publishers: list[PublisherDef] = Field(default_factory=list)

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
        publisher_ids = [publisher.id for publisher in self.publishers]
        if len(set(publisher_ids)) != len(publisher_ids):
            raise ValueError("publisher ids must be distinct")
        known_publishers = set(publisher_ids)
        if any(
            feed.publisher_id is not None and feed.publisher_id not in known_publishers
            for feed in known
        ):
            raise ValueError("feed publisher_id must reference a defined publisher")
        return self
