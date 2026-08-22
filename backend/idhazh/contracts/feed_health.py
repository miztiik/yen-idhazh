"""What every feed did, on every run.

One row per feed per run, appended to `state/feed-health/<YYYY-MM>.csv`. It is
written whether the run publishes or not, because the days a source is worth
measuring on are the days the run went badly.

Two readers depend on it. The plan stage reads the recent tail to decide
whether a feed has failed often enough to be skipped - a quarantine that lives
in the record, never in `config/sources.json`, so no run ever edits a file a
person owns. The published dashboard reads the same rows to show which sources
are healthy, which is the only way a reader can tell a quiet desk from a broken
one.

`FetchOutcome` lives here rather than in `idhazh.fetch` because it is now a
persisted vocabulary: it is a column in this ledger and a label on a published
page. Contracts are the bottom of the dependency graph (CLAUDE.md section 4),
so the shape a run writes cannot live in the module that produces it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Self

from pydantic import Field

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    Slug,
    Timestamp,
)


class FetchOutcome(StrEnum):
    """Why one read of one address ended the way it did.

    Deliberately coarser than an HTTP status. What a later decision needs is
    whether the address is worth asking again, and 403 and 404 answer that the
    same way while 503 answers it differently.
    """

    OK = "ok"
    ROBOTS_DENIED = "robots_denied"
    BLOCKED = "blocked"
    PERMANENT = "permanent"
    TRANSIENT = "transient"


#: Outcomes that count against a feed when quarantine is decided. A robots
#: refusal is not one of them: the source is working exactly as it asked to be
#: treated, and quarantining it would be us punishing a site for saying no.
FAILING_OUTCOMES: frozenset[FetchOutcome] = frozenset(
    {FetchOutcome.BLOCKED, FetchOutcome.PERMANENT, FetchOutcome.TRANSIENT}
)


class FeedHealthRow(Contract):
    """One feed, one run, one row."""

    __schema_stem__: ClassVar[str] = "feed-health-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-23",
            change="Initial shape: the feed, the run, the outcome and what it yielded.",
            why=(
                "A feed can go quiet for a week before anybody notices, and nothing "
                "recorded whether a source answered. A quarantine rule and a health "
                "dashboard both need a measurement that already exists."
            ),
        ),
    )

    run_id: RunId
    date: DateStamp
    feed_id: Slug
    checked_at: Timestamp
    outcome: FetchOutcome
    status: int | None = Field(
        default=None,
        ge=100,
        le=599,
        description="The HTTP status, when the request got far enough to have one.",
    )
    items: int = Field(
        default=0,
        ge=0,
        description=(
            "Candidates the feed yielded. Zero with an ok outcome is its own kind of "
            "broken - a feed that parses to nothing is not a feed that is working."
        ),
    )
    detail: str | None = Field(
        default=None,
        max_length=200,
        description="Our own one-line reason. Never the response body (Holy Law #11).",
    )

    @property
    def failing(self) -> bool:
        """Did this read count against the feed?

        An ok read that parsed to no entries counts. The most common way a feed
        dies is not a 500 - it is a silent reshape that still returns 200.
        """
        return self.outcome in FAILING_OUTCOMES or self.items == 0

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. An absent optional is an empty cell, not the word None."""
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent value, never the empty string."""
        payload: dict[str, Any] = {name: row[name] for name in cls.model_fields}
        for name in ("status", "detail"):
            if payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)
