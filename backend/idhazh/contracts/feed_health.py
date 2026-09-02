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
page. `RobotsOutcome` is here for the same reason. Contracts are the bottom of
the dependency graph (CLAUDE.md section 4), so the shape a run writes cannot
live in the module that produces it.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any, ClassVar, Self

from pydantic import Field

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    Sha256,
    Slug,
    Timestamp,
)


def derive_endpoint_key(feed_url: str) -> str:
    """Which address a run asked, as one cell.

    The sha256 of the validated configured feed URL. It says what was asked
    without putting the address in a file the console reads, and it is what a
    later retirement is filed against - so a feed whose configured URL changes
    is a new endpoint with no inherited record.

    Unlike every other derived value here it cannot be rebuilt on read, because
    the row deliberately does not carry the URL. The writer derives it with this
    function and nothing else spells the arithmetic.
    """
    return hashlib.sha256(feed_url.encode("utf-8")).hexdigest()


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
    # We did not ask - the feed was resting out a quarantine. A record, not a
    # measurement. It is written so a later run can tell "resting" apart from
    # "nobody has tried this feed yet", which is what lets a quarantine lift
    # itself instead of becoming a deletion nobody voted for.
    SKIPPED = "skipped"


class RobotsOutcome(StrEnum):
    """What `robots.txt` said about this address, as a decision and never a body.

    Three answers because three are actionable. A host that publishes no rules
    and a host whose rules allow us are the same permission, so they are one
    member; a refusal and a robots file we could not read are different, because
    the first is a publisher's stated policy and the second is our own failure
    to establish one. Neither of the last two says anything about whether the
    feed itself works, so neither is evidence about availability.
    """

    ALLOWED = "allowed"
    DENIED = "denied"
    # We could not establish permission - a 429, a 5xx, or a transport failure.
    # Unknown fails closed, so the target is not asked.
    UNREACHABLE = "unreachable"


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
            version="2026-09-02T20:00",
            change=(
                "endpoint_key, robots_outcome, robots_checked_at, robots_status and "
                "target_attempted appended, every one of them nullable. The committed "
                "shards are rewritten onto the wider header in the same commit by "
                "backend/utilities/migrate_feed_health.py, and every rewritten row "
                "carries five empty cells."
            ),
            why=(
                "The record could say what a feed answered and not which address was "
                "asked, whether the site allowed the request, or whether the request "
                "was made at all. A run cannot retire a dead address without knowing "
                "the address, and a robots refusal reads as a failed read without the "
                "permission beside it. Empty rather than backfilled: the configured URL "
                "may have moved since a row was written, and a guessed identity would "
                "retire the wrong address later."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T12:00",
            change="outcome gains `skipped`, for a run that held a quarantined feed back.",
            why=(
                "A quarantine that writes nothing can never lift: the failures that "
                "caused it stay the newest thing on record forever. A skip has to be "
                "recorded for the rest to end on its own."
            ),
        ),
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
        description="Our own one-line reason. Never the response body (Rule #11).",
    )
    # Everything below here was appended on 2026-09-02 and is empty on every row
    # written before that. A column is appended and never filed by meaning: a
    # cell inserted in the middle shifts every historical value one place right
    # under a reader that maps by position.
    endpoint_key: Sha256 | None = Field(
        default=None,
        description=(
            "The sha256 of the configured feed URL this run asked, from "
            "derive_endpoint_key. It identifies the address rather than the feed, so a "
            "feed whose URL is edited starts a fresh record. Empty on a row written "
            "before the column existed."
        ),
    )
    robots_outcome: RobotsOutcome | None = Field(
        default=None,
        description=(
            "What robots.txt said about this address. Empty on a row written before "
            "the column existed, which is not the same fact as allowed."
        ),
    )
    robots_checked_at: Timestamp | None = Field(
        default=None,
        description="When permission was established, so a recheck cadence has a clock.",
    )
    robots_status: int | None = Field(
        default=None,
        ge=100,
        le=599,
        description="The status robots.txt itself answered with, when there was one.",
    )
    target_attempted: bool | None = Field(
        default=None,
        description=(
            "Did this run request the feed address itself? False for a run that stopped "
            "at robots.txt or rested the feed, so evidence about the feed can be told "
            "apart from evidence about permission. The cell is spelled True or False, "
            "as every other boolean cell under state/ is."
        ),
    )

    @property
    def attempted(self) -> bool:
        """Did we actually ask this run? A quarantined feed was not asked."""
        return self.outcome is not FetchOutcome.SKIPPED

    @property
    def failing(self) -> bool:
        """Did this read count against the feed?

        A successful read that parsed to no entries counts. The most common way
        a feed dies is not a 500 - it is a silent reshape that still returns 200.
        A robots refusal never counts, and neither does a run we skipped: the
        first is a site working as it asked to be treated, and the second is a
        question we did not ask.
        """
        if self.outcome is FetchOutcome.OK:
            return self.items == 0
        return self.outcome in FAILING_OUTCOMES

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
        """The inverse. An empty cell is an absent value, never the empty string.

        A missing cell is absent too, so a shard written before a column existed
        reads with that column empty rather than raising. The guard that forces
        the migration is `ledger.require_matching_header`, and it sits on the
        write path where an unmigrated file would put cells under the wrong
        names.
        """
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        for name in cls._absent_when_blank():
            if payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)

    @classmethod
    def _absent_when_blank(cls) -> tuple[str, ...]:
        """Every optional cell, derived rather than listed a second time.

        A field declared `default=None` is one this row can be missing. Reading
        that off the model means a column added later cannot be forgotten here
        and come back from the ledger as the string `""`.
        """
        return tuple(name for name, field in cls.model_fields.items() if field.default is None)
