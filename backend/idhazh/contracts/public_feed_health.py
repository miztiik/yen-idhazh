"""The browser-safe projection of the feed-health ledger.

`state/feed-health/<YYYY-MM>.csv` is the ledger - one row per feed per run - and
it carries one cell a reader must never receive. This is the narrow shape that
does cross, written to `frontend/public/feed-health/<YYYY-MM>.csv` and fetched a
month at a time.

`detail` crosses, and that is deliberate rather than an oversight. On
`ItemHealthRow` the same name holds a diagnostic that can quote fetched article
text, which is why `public_telemetry.py` refuses it; on `FeedHealthRow` the
field says in terms that it is "our own one-line reason. Never the response
body", capped at 200 characters by its own constraint. The console already
prints it beside a failing feed, and a failure a reader can see but not read is
a bar with no label.
"""

from __future__ import annotations

from typing import Any, ClassVar, Final, Self

from pydantic import Field

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, RunId, Slug, Timestamp
from idhazh.contracts.feed_health import FetchOutcome, RobotsOutcome

#: The one ledger cell that may never reach a browser.
#:
#: `endpoint_key` is the sha256 of the configured feed URL, and its own field
#: description on `FeedHealthRow` says it "identifies the address rather than the
#: feed". An address hashed is still an address (Rule #11), and every panel that
#: draws this ledger groups by `feed_id`, which is our own slug.
FORBIDDEN_COLUMNS: Final[frozenset[str]] = frozenset({"endpoint_key"})


class PublicFeedRow(Contract):
    """One feed read on one run, as the console is allowed to read it."""

    __schema_stem__: ClassVar[str] = "public-feed-health"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-09",
            change=(
                "Initial shape: the feed, the run, the outcome, what it yielded and "
                "what robots said, with endpoint_key refused at import."
            ),
            why=(
                "The console reads state/feed-health/ at build time and inlines the "
                "result, so the ledger's shape reached a reader with no contract and "
                "no version stamp (Rule #3). Naming it before a producer exists is "
                "what stops the producer and the consumer inventing two different "
                "lists. detail is kept because it is our own sentence and the panel "
                "prints it; endpoint_key is refused because it is the address."
            ),
        ),
    )

    run_id: RunId
    date: DateStamp
    feed_id: Slug
    checked_at: Timestamp
    outcome: FetchOutcome
    status: int | None = Field(default=None, ge=100, le=599)
    items: int = Field(default=0, ge=0)
    detail: str | None = Field(default=None, max_length=200)
    robots_outcome: RobotsOutcome | None = None
    robots_checked_at: Timestamp | None = None
    robots_status: int | None = Field(default=None, ge=100, le=599)
    target_attempted: bool | None = None

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """The published header. `version` is a field of the shape, not a cell."""
        return tuple(name for name in cls.model_fields if name != "version")

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. An absent optional is an empty cell."""
        payload = self.model_dump(mode="json")
        return {
            name: "" if payload[name] is None else str(payload[name])
            for name in self.csv_columns()
        }

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent value, never the empty string."""
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.csv_columns()}
        for name, field in cls.model_fields.items():
            if name in payload and field.default is None and payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)


if FORBIDDEN_COLUMNS & set(PublicFeedRow.model_fields):
    raise AssertionError(
        "a feed-health field a reader may never receive is on the published "
        f"projection: {sorted(FORBIDDEN_COLUMNS & set(PublicFeedRow.model_fields))}"
    )
