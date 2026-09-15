"""What the pipeline has already looked at, and what it has already published.

Two append-only ledgers, because they answer two different questions and are
written by two different jobs.

`SeenRow` answers "how old is this?" for an article whose feed gave no date.
Most feeds that omit a date also omit it consistently, so the only honest age
we have is the first time we saw the address. The plan stage writes it.

`PublishedRow` answers "have we already run this?" A 24-hour window alone does
not stop a repeat: an article published at 23:00 on Monday is seven hours old
at 06:00 on Tuesday and would be planned twice. The assemble stage writes it,
because until a digest is committed nothing was actually published.

Neither row is ever rewritten. A mutable "published" flag on a seen row would
turn an append into a read-modify-write over the whole history, and two runs
racing on that file would lose rows.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    RunId,
    Timestamp,
    UrlKey,
)


class SeenRow(Contract):
    """One row of `state/seen/<YYYY>/<MM>/<DD>.csv`, appended the first time an address
    is a candidate.

    It carries no address, for the reason `PublishedRow` carries none: nothing on
    the read path opens one. `ledger.load_seen` reads `url_key` and
    `first_seen_at` and returns a map of the two.

    `first_seen_run` is what says which file the row lives in. A run id is
    `<date>-<n>`, so its first ten characters are the run's digest date, which is
    the date `ledger.append_seen` files by. `first_seen_at` is a wall clock and
    crosses midnight independently of the run it belongs to, so it names the day
    a row was written and not the day the row is filed under.
    """

    __schema_stem__: ClassVar[str] = "seen-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-31",
            change="Removed canonical_url.",
            why="Nothing on the read path opened it, and it doubled the row for no reader.",
        ),
        ChangelogEntry(
            version="2026-08-22T11:00",
            change="Initial shape: the address, when we first saw it, and the run that saw it.",
            why="An undated article has no age we can trust.",
        ),
    )

    url_key: UrlKey
    first_seen_at: Timestamp
    first_seen_run: RunId

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. An absent optional is an empty cell."""
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}


class PublishedRow(Contract):
    """One row of `state/published/YYYY/MM/DD.csv`, appended when an item reaches a
    committed digest.

    It carries no address. `item_id` and `published_on` join to that day's
    committed payload, where the address is already published as `source_url` -
    see `docs/architecture/sources/freshness.md` for the worked recovery.
    """

    __schema_stem__: ClassVar[str] = "published-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-12T18:40",
            change="item_id accepts a second shape: sixteen Crockford base32 symbols.",
            why="Ten decimal digits is 33 bits of an address, which collides on a busy day.",
        ),
        ChangelogEntry(
            version="2026-09-08",
            change="Named the day file instead of the flat state/published.csv.",
            why="The flat file was split into state/published/YYYY/MM/DD.csv and removed.",
        ),
        ChangelogEntry(
            version="2026-08-26",
            change="Removed canonical_url.",
            why="Nothing on the read path opened it: load_published maps url_key to published_on.",
        ),
        ChangelogEntry(
            version="2026-08-22T11:00",
            change="Initial shape: the address, the day it ran, and the item it ran as.",
            why="A freshness window cannot stop a repeat on its own.",
        ),
    )

    url_key: UrlKey
    published_on: DateStamp = Field(description="The digest date, not the article's own date.")
    item_id: ItemId

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. An absent optional is an empty cell."""
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}
