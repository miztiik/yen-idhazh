"""The closed vocabularies and the vertical registry (`config/taxonomy.json`).

Lenses and event types are closed enums rather than free-text strings, so a new
value is a schema change carrying a changelog entry rather than a typo waiting
to happen. Verticals are config-declared, because a vertical is built in the
open over weeks under `draft` status until it clears its feed floor.

An id is an immutable slug; `display_name` is separate and freely mutable, so
renaming what a reader sees never orphans a payload written under the old label.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, Model, Slug


class LifecycleStatus(StrEnum):
    """Retire, never delete: a tombstone keeps old payloads valid."""

    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class SourceTier(IntEnum):
    """The tier IS the ranking weight (docs/architecture/sources/discovery.md)."""

    INSTITUTION = 1
    TRADE_PRESS = 2
    COMMUNITY = 3


class SourceKind(StrEnum):
    """What kind of speaker this is - the thing a reader uses to decide belief.

    "A company said its product is faster" and "a reporter measured it" are not
    the same claim, and without this they arrive looking identical. The
    dangerous case is `announcement`: forwarding a vendor's own copy without
    knowing it was the vendor is how a reader ends up carrying an ad.
    """

    REPORTING = "reporting"
    ANNOUNCEMENT = "announcement"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    GOVERNMENT = "government"
    COMMUNITY = "community"


class LensId(StrEnum):
    """A question asked of items already collected. Costs no extra request."""

    CHINA = "china"
    AI_ROI = "ai-roi"
    MARKETS = "markets"
    CYBER = "cyber"


class EventType(StrEnum):
    """What happened to an item. One or more per item."""

    RELEASE = "release"
    DEAL = "deal"
    ACQUISITION = "acquisition"
    FUNDING = "funding"
    CAPEX = "capex"
    EARNINGS = "earnings"
    REGULATION = "regulation"
    RESEARCH = "research"
    INCIDENT = "incident"


class Lifecycled(Model):
    """Anything that can be drafted, published and later retired."""

    status: LifecycleStatus = LifecycleStatus.ACTIVE
    retired_on: DateStamp | None = None

    @model_validator(mode="after")
    def _retired_on_matches_status(self) -> Self:
        retired = self.status is LifecycleStatus.RETIRED
        if retired and self.retired_on is None:
            raise ValueError("a retired entry must carry retired_on")
        if not retired and self.retired_on is not None:
            raise ValueError("retired_on is only meaningful on a retired entry")
        return self


class VerticalDef(Lifecycled):
    """A subject with its own reporters and its own feeds."""

    id: Slug
    display_name: str = Field(min_length=1)
    min_feeds: int = Field(
        ge=1,
        description="Feed floor below which the vertical does not render at all.",
    )


class LensDef(Lifecycled):
    id: LensId
    display_name: str = Field(min_length=1)


class EventDef(Model):
    id: EventType
    display_name: str = Field(min_length=1)


class Taxonomy(Contract):
    """`config/taxonomy.json` - the vocabulary every payload indexes against."""

    __schema_stem__: ClassVar[str] = "taxonomy"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-22T11:00",
            change="Removed VerticalDef.daily_cap.",
            why=(
                "It decided how big a vertical's day was before the ranking had a say. "
                "Supply and the score set the size now; max_per_source still stops one "
                "feed becoming the vertical."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: verticals, lenses and events.",
            why="Contracts before logic - the vocabulary is fixed before any stage reads it.",
        ),
    )

    verticals: list[VerticalDef]
    lenses: list[LensDef]
    events: list[EventDef]

    @model_validator(mode="after")
    def _vocabularies_are_complete_and_distinct(self) -> Self:
        vertical_ids = [item.id for item in self.verticals]
        if len(set(vertical_ids)) != len(vertical_ids):
            raise ValueError("vertical ids must be distinct")

        lens_ids = [item.id for item in self.lenses]
        if sorted(lens_ids) != sorted(LensId):
            raise ValueError("lenses must label every LensId exactly once")

        event_ids = [item.id for item in self.events]
        if sorted(event_ids) != sorted(EventType):
            raise ValueError("events must label every EventType exactly once")
        return self

    def vertical(self, vertical_id: str) -> VerticalDef | None:
        return next((item for item in self.verticals if item.id == vertical_id), None)
