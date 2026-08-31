"""The day's work list, decided before any weights load.

The plan job reads feeds, deduplicates and ranks - all deterministic
arithmetic, no model - then writes this. Workers read it and never re-decide
what to work on, which is what makes a shard replayable and a re-run cheap.

Ranking lives here rather than in a worker for a reason: a story carried by
three independent feeds is the day's story, and only something holding the
whole day can see that.
"""

from __future__ import annotations

from enum import StrEnum
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
from idhazh.contracts.sources import SourceForm
from idhazh.contracts.taxonomy import SourceTier


class TimeSource(StrEnum):
    """Which clock the time on an item came from.

    `rank.appeared_at` prefers the feed's own date and falls back to when we
    first saw the address. Both answers used to land in one field, so nothing
    downstream could tell them apart - and the fallback is the one a reader
    would want flagged, because it is our clock and not the publisher's.
    """

    #: The feed's own publish date.
    FEED = "feed"
    #: When this project first saw the address. The feed gave no usable date.
    FIRST_SEEN = "first_seen"
    #: Neither clock gave a time, so the item carries none.
    UNKNOWN = "unknown"

    @property
    def names_a_clock(self) -> bool:
        """`unknown` is the one member that goes with no time at all."""
        return self is not TimeSource.UNKNOWN


class PlannedItem(Model):
    """One URL that survived deduplication and was chosen for the day.

    `item_id` is derived from `url_key`, so the same article carries the same
    id on every run of every day. `published_at` is the time the run believes -
    the feed's own date, unless it claimed a future too far ahead to be true,
    in which case it is when we first saw the address. `time_source` says which
    of the two it is.
    """

    item_id: ItemId
    url_key: UrlKey
    source_url: Url = Field(description="The address as the feed gave it.")
    canonical_url: Url = Field(description="After canonicalisation. url_key derives from it.")
    source_id: Slug = Field(description="The feed that carried it first.")
    tier: SourceTier
    source_form: SourceForm = Field(
        default=SourceForm.ARTICLE,
        description="Declared feed form, carried from config so workers never infer it.",
    )
    vertical: Slug
    title: UntrustedLine | None = None
    published_at: Timestamp | None = None
    time_source: TimeSource | None = Field(
        default=None,
        description=(
            "Which clock published_at came from. Null on a plan written before the "
            "field existed - unknown, and never a claim about a clock."
        ),
    )

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

    @model_validator(mode="after")
    def _the_clock_and_the_time_agree(self) -> Self:
        if self.time_source is not None and self.time_source.names_a_clock != (
            self.published_at is not None
        ):
            raise ValueError("time_source names a clock exactly when published_at carries a time")
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
    too_old: int = Field(
        default=0,
        ge=0,
        description=(
            "Of those considered, how many were past collect.max_age_hours. A desk "
            "whose feeds serve a back catalogue thins for this reason and no other, "
            "and a thin desk that cannot say why reads as a broken run."
        ),
    )

    @model_validator(mode="after")
    def _cannot_plan_more_than_it_saw(self) -> Self:
        if self.planned > self.considered:
            raise ValueError("a vertical cannot plan more items than it considered")
        if self.too_old > self.considered:
            raise ValueError("a vertical cannot drop more items than it considered")
        if self.below_feed_floor and self.planned:
            raise ValueError("a vertical under its feed floor plans nothing")
        return self


class RunPlan(Contract):
    """What the plan job decided, before a single byte of an article was fetched."""

    __schema_stem__: ClassVar[str] = "run-plan"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-31T10:30",
            change="Added time_source to each planned item.",
            why=(
                "published_at holds the feed's own date, or our first sight of the "
                "address when the feed gave no usable one, and the field could not say "
                "which. The choice is made in rank.appeared_at and was thrown away one "
                "line later, so a page printing the time could not vouch for it. "
                "Measured 2026-08-31 on the committed 2026-08-30 payload, 431 items: "
                "305 distinct HH:mm values, and 5 stamps - 1.2 percent - within two "
                "minutes of a run stamp. That last figure is an upper bound on the "
                "fallback rather than a count of it, because nothing committed records "
                "the choice yet - which is the defect. Additive with a default, so a "
                "plan an earlier run wrote still validates, and a null reads as "
                "unknown (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30",
            change="Added too_old to each vertical's plan summary.",
            why=(
                "collect.max_age_hours now refuses a story older than a day, and the "
                "verticals do not lose the same amount. Measured 2026-08-30 over the "
                "2,900 items published from 2026-08-22 to 2026-08-29: a one-day gate "
                "keeps 95.7 percent of world and 32.4 percent of ai, because the ai "
                "desk is largely fed by research-lab blogs that serve a back "
                "catalogue. Without this count a desk that halves overnight looks "
                "like a broken feed rather than a working gate. Additive with a "
                "default, so a plan an earlier run wrote still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:48",
            change="Added source_form to each planned item.",
            why=(
                "Workers need to know when a source is an abstract without detecting it "
                "from page text. Carrying the curator-declared feed form keeps that fact in "
                "the plan payload."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T12:00",
            change="feeds_skipped counts the feeds a quarantine held back this run.",
            why=(
                "A quarantined feed is neither read nor failed, so a short day looked "
                "like a quiet news day. The count says which it was."
            ),
        ),
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
    feeds_skipped: int = Field(
        default=0,
        ge=0,
        description="Held back by a quarantine. Neither read nor failed - never asked.",
    )
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
