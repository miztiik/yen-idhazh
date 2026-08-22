"""The day's work list, decided before any weights load.

The plan job reads feeds, deduplicates and ranks - all deterministic
arithmetic, no model - then writes this. Workers read it and never re-decide
what to work on, which is what makes a shard replayable and a re-run cheap.

Ranking lives here rather than in a worker for a reason: a story carried by
three independent feeds is the day's story, and only something holding the
whole day can see that.
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
    RunId,
    Slug,
    Timestamp,
    Url,
    UrlKey,
    derive_url_key,
)
from idhazh.contracts.taxonomy import SourceTier


class PlannedItem(Model):
    """One URL that survived deduplication and was chosen for the day.

    `item_id` is derived from `url_key`, so the same article carries the same
    id on every run of every day. `published_at` is the time the run believes -
    the feed's own date, unless it claimed a future too far ahead to be true,
    in which case it is when we first saw the address.
    """

    item_id: ItemId
    url_key: UrlKey
    source_url: Url = Field(description="The address as the feed gave it.")
    canonical_url: Url = Field(description="After canonicalisation. url_key derives from it.")
    source_id: Slug = Field(description="The feed that carried it first.")
    tier: SourceTier
    vertical: Slug
    title: UntrustedLine | None = None
    published_at: Timestamp | None = None

    carried_by: int = Field(
        default=1, ge=1, description="Independent feeds that carried this story today."
    )
    watchlist_hit: bool = False
    on_front_page: bool = Field(
        default=False, description="A salience feed voted for it. A vote, never a discovery."
    )
    rank_score: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _identity_is_rebuilt_not_trusted(self) -> Self:
        if self.url_key != derive_url_key(self.canonical_url):
            raise ValueError("url_key must be the sha256 of canonical_url, recomputed on read")
        if not self.item_id.startswith(f"{self.vertical}-"):
            raise ValueError("item_id must be addressed <vertical>-<NN>")
        return self


class VerticalPlan(Model):
    """Why a vertical contributed what it did, including when it contributed nothing."""

    id: Slug
    considered: int = Field(ge=0, description="Distinct URLs the feeds offered.")
    planned: int = Field(ge=0)
    live_feeds: int = Field(ge=0)
    below_feed_floor: bool = Field(
        default=False, description="Under its floor, so it is collected but never rendered."
    )

    @model_validator(mode="after")
    def _cannot_plan_more_than_it_saw(self) -> Self:
        if self.planned > self.considered:
            raise ValueError("a vertical cannot plan more items than it considered")
        if self.below_feed_floor and self.planned:
            raise ValueError("a vertical under its feed floor plans nothing")
        return self


class RunPlan(Contract):
    """What the plan job decided, before a single byte of an article was fetched."""

    __schema_stem__: ClassVar[str] = "run-plan"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-22T11:00",
            change=(
                "item_id is derived from the address instead of the rank position, and "
                "published_at now carries the time the run believes rather than the time "
                "the feed claimed."
            ),
            why=(
                "A rank position renumbers the day on every run, so on a six-hourly "
                "schedule the same story came back under a new id and published twice. A "
                "date a feed puts in the future is not a date, and forwarding one to a "
                "reader repeats the feed's claim as our own."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21T04:00",
            change="Initial shape: the ranked, capped, deduplicated work list for one run.",
            why="Contracts before logic - a worker reads a fixed shape and never re-decides.",
        ),
    )

    date: DateStamp
    run_id: RunId
    generated_at: Timestamp
    stale: bool = Field(
        default=False,
        description="Discovery failed and an earlier list was reused. Never skip a day silently.",
    )
    feeds_read: int = Field(default=0, ge=0)
    feeds_failed: int = Field(default=0, ge=0)
    verticals: list[VerticalPlan] = Field(default_factory=list)
    items: list[PlannedItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _the_list_is_ordered_and_distinct(self) -> Self:
        if len({item.url_key for item in self.items}) != len(self.items):
            raise ValueError("a planned list is deduplicated - url_key appears once")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ValueError("item ids must be distinct")

        seen: dict[str, float] = {}
        counts: dict[str, int] = {}
        for item in self.items:
            previous = seen.get(item.vertical)
            if previous is not None and item.rank_score > previous:
                raise ValueError("within a vertical, rank_score may never increase down the list")
            seen[item.vertical] = item.rank_score
            counts[item.vertical] = counts.get(item.vertical, 0) + 1

        counted = {vertical.id: vertical.planned for vertical in self.verticals}
        for vertical_id, total in counts.items():
            if counted.get(vertical_id) != total:
                raise ValueError(f"vertical {vertical_id} counts disagree with its items")
        return self
